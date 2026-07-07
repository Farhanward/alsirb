from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
HF_SIZE_URL = "https://datasets-server.huggingface.co/size"
DATASET = "neuralchemy/Prompt-injection-dataset"
CONFIG = "full"
SPLITS = ("train", "validation", "test")
USER_AGENT = "alsirb-local-benchmark/0.1"


def _dataset_url(endpoint: str, **params: Any) -> str:
    return f"{endpoint}?{urlencode(params)}"


def _get_json(url: str, retries: int = 6) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(60.0, 2.0 * (attempt + 1))
            time.sleep(delay)
    raise RuntimeError("unreachable retry state")


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def fetch_neuralchemy_tasks(
    out_path: str | Path,
    raw_path: str | Path | None = None,
    page_size: int = 100,
    sleep_seconds: float = 0.0,
    limit: int = 0,
) -> dict[str, Any]:
    out = Path(out_path)
    raw = Path(raw_path) if raw_path else out.with_suffix(".raw.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    raw.parent.mkdir(parents=True, exist_ok=True)

    size = _get_json(_dataset_url(HF_SIZE_URL, dataset=DATASET, config=CONFIG))
    split_sizes = {
        item["split"]: int(item["num_rows"])
        for item in size.get("size", {}).get("splits", [])
        if item.get("split") in SPLITS
    }
    target_total = sum(split_sizes.values())
    if limit > 0:
        target_total = min(target_total, limit)

    existing = _line_count(out)
    raw_existing = _line_count(raw)
    resume_rows = existing if existing == raw_existing and existing < target_total else 0
    mode = "a" if resume_rows else "w"
    rows_seen = 0
    rows_written = resume_rows
    labels = {"0": 0, "1": 0}
    with out.open(mode, encoding="utf-8") as out_handle, raw.open(mode, encoding="utf-8") as raw_handle:
        for split in SPLITS:
            split_total = split_sizes.get(split, 0)
            for offset in range(0, split_total, page_size):
                if rows_seen + offset >= target_total:
                    break
                url = _dataset_url(
                    HF_ROWS_URL,
                    dataset=DATASET,
                    config=CONFIG,
                    split=split,
                    offset=offset,
                    length=min(page_size, split_total - offset),
                )
                page = _get_json(url)
                for row_data in page.get("rows", []):
                    if rows_written >= target_total:
                        break
                    absolute_index = rows_seen + int(row_data.get("row_idx", offset))
                    if absolute_index < resume_rows:
                        continue
                    row = dict(row_data.get("row") or {})
                    label = int(row.get("label", 0))
                    text = str(row.get("text") or "")
                    raw_record = {
                        "dataset": DATASET,
                        "config": CONFIG,
                        "split": split,
                        "row_idx": int(row_data.get("row_idx", offset)),
                        **row,
                    }
                    task_record = {
                        "dataset": DATASET,
                        "config": CONFIG,
                        "split": split,
                        "row_idx": int(row_data.get("row_idx", offset)),
                        "label": label,
                        "expected_unsafe": label == 1,
                        "brief": text,
                        "task": {
                            "brief": text,
                            "name": f"dataset-{split}-{row_data.get('row_idx', offset)}",
                            "language": "python",
                            "audience": "local",
                            "constraints": ["benchmark preflight only"],
                        },
                    }
                    raw_handle.write(json.dumps(raw_record, ensure_ascii=False) + "\n")
                    out_handle.write(json.dumps(task_record, ensure_ascii=False) + "\n")
                    rows_written += 1
                    labels[str(label)] = labels.get(str(label), 0) + 1
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            rows_seen += split_total

    final_labels: dict[str, int] = {}
    final_rows = 0
    with out.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            final_rows += 1
            key = str(record.get("label", ""))
            final_labels[key] = final_labels.get(key, 0) + 1
    return {
        "dataset": DATASET,
        "config": CONFIG,
        "out": str(out.resolve()),
        "raw": str(raw.resolve()),
        "rows": final_rows,
        "new_rows": max(0, rows_written - resume_rows),
        "resumed_from_rows": resume_rows,
        "labels": dict(sorted(final_labels.items())),
    }


def convert_almunaa_events(events_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    source = Path(events_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    labels: dict[str, int] = {}
    with source.open("r", encoding="utf-8") as handle, out.open("w", encoding="utf-8") as out_handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            event = record.get("event") if isinstance(record.get("event"), dict) else {}
            label = int(record.get("label", 0))
            text = str(event.get("content") or record.get("content") or record.get("text") or "")
            task_record = {
                "dataset": record.get("dataset") or DATASET,
                "config": record.get("config") or CONFIG,
                "split": record.get("split"),
                "row_idx": record.get("row_idx"),
                "label": label,
                "expected_unsafe": bool(record.get("expected_unsafe") or label == 1),
                "brief": text,
                "task": {
                    "brief": text,
                    "name": f"dataset-{record.get('split', 'unknown')}-{record.get('row_idx', rows)}",
                    "language": "python",
                    "audience": "local",
                    "constraints": ["benchmark preflight only"],
                },
            }
            out_handle.write(json.dumps(task_record, ensure_ascii=False) + "\n")
            rows += 1
            labels[str(label)] = labels.get(str(label), 0) + 1
    return {
        "dataset": DATASET,
        "config": CONFIG,
        "source": str(source.resolve()),
        "out": str(out.resolve()),
        "rows": rows,
        "labels": dict(sorted(labels.items())),
    }
