from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from .models import ProjectTask
from .orchestrator import preflight_task


def _iter_records(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _metrics(tp: int, tn: int, fp: int, fn: int) -> dict[str, float | int]:
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100) * (len(ordered) - 1)))))
    return ordered[index]


def evaluate_preflight(input_path: str | Path, repeat: int = 1, max_records: int = 0) -> dict[str, Any]:
    source_records = list(_iter_records(input_path))
    if max_records > 0:
        source_records = source_records[:max_records]
    tp = tn = fp = fn = errors = 0
    latencies: list[float] = []
    action_counts: dict[str, int] = {}
    started = time.perf_counter()
    tracemalloc.start()
    for _round in range(repeat):
        for record in source_records:
            task_data = record.get("task") if isinstance(record.get("task"), dict) else record
            task = ProjectTask.from_dict(task_data)
            expected = bool(record.get("expected_unsafe") or record.get("label") == 1)
            item_started = time.perf_counter()
            try:
                result = preflight_task(task)
                predicted = not bool(result["allowed"])
                action = str(result.get("action") or "")
                action_counts[action] = action_counts.get(action, 0) + 1
            except Exception:
                errors += 1
                predicted = True
            latencies.append((time.perf_counter() - item_started) * 1000)
            if expected and predicted:
                tp += 1
            elif expected and not predicted:
                fn += 1
            elif not expected and predicted:
                fp += 1
            else:
                tn += 1
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    metric_values = _metrics(tp, tn, fp, fn)
    processed = len(source_records) * repeat
    return {
        "input": str(Path(input_path).resolve()),
        "records": len(source_records),
        "repeat": repeat,
        "processed": processed,
        "errors": errors,
        "metrics": metric_values,
        "action_counts": dict(sorted(action_counts.items())),
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "p99": _percentile(latencies, 99),
            "max": max(latencies) if latencies else 0.0,
        },
        "memory_mb": {"current": current / 1_000_000, "peak": peak / 1_000_000},
        "elapsed_seconds": time.perf_counter() - started,
        "collapse_check": {
            "passed": errors == 0 and processed > 0,
            "criteria": "errors == 0 and processed > 0",
        },
    }
