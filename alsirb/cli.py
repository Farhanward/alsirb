from __future__ import annotations

import argparse
import json
from pathlib import Path

from .batch import evaluate_preflight
from .datasets import convert_almunaa_events, fetch_neuralchemy_tasks
from .ledger import verify
from .models import ProjectTask
from .orchestrator import preflight_task, run_task
from .reports import batch_markdown, run_markdown


def _write_json(path: str | Path, data: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="alsirb", description="السرب: فريق وكلاء محلي يبني ويفحص البرامج.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--brief", required=True)
    preflight.add_argument("--name", default="")

    run = sub.add_parser("run")
    run.add_argument("--brief", required=True)
    run.add_argument("--name", default="")
    run.add_argument("--workspaces", default="workspaces")
    run.add_argument("--json-out", default="reports/alsirb_last_run.json")
    run.add_argument("--report", default="reports/alsirb_last_run.md")

    data = sub.add_parser("download-benchmark")
    data.add_argument("--out", default="data/benchmarks/alsirb_neuralchemy_tasks.jsonl")
    data.add_argument("--raw-out", default="")
    data.add_argument("--page-size", type=int, default=100)
    data.add_argument("--sleep", type=float, default=0.0)
    data.add_argument("--limit", type=int, default=0)

    convert = sub.add_parser("convert-events")
    convert.add_argument("--events", default="C:/Projects/almunaa/data/benchmarks/neuralchemy_prompt_injection_full.events.jsonl")
    convert.add_argument("--out", default="data/benchmarks/alsirb_neuralchemy_tasks.full.jsonl")

    batch = sub.add_parser("batch")
    batch.add_argument("--input", required=True)
    batch.add_argument("--json-out", default="reports/alsirb_preflight_benchmark.json")
    batch.add_argument("--report", default="reports/alsirb_preflight_benchmark.md")
    batch.add_argument("--max-records", type=int, default=0)

    stress = sub.add_parser("stress")
    stress.add_argument("--input", required=True)
    stress.add_argument("--repeat", type=int, default=3)
    stress.add_argument("--json-out", default="reports/alsirb_preflight_stress.json")
    stress.add_argument("--report", default="reports/alsirb_preflight_stress.md")
    stress.add_argument("--max-records", type=int, default=0)

    sub.add_parser("verify-ledger")

    serve = sub.add_parser("serve")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)

    sub.add_parser("version")

    args = parser.parse_args(argv)
    if args.cmd == "preflight":
        result = preflight_task(ProjectTask(brief=args.brief, name=args.name))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "run":
        result = run_task(ProjectTask(brief=args.brief, name=args.name), workspaces=args.workspaces)
        data_out = result.to_dict()
        _write_json(args.json_out, data_out)
        _write_text(args.report, run_markdown(result))
        print(json.dumps(data_out, ensure_ascii=False, indent=2))
        return 0 if result.status == "PASS" else 2
    if args.cmd == "download-benchmark":
        summary = fetch_neuralchemy_tasks(
            args.out,
            raw_path=args.raw_out or None,
            page_size=args.page_size,
            sleep_seconds=args.sleep,
            limit=args.limit,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "convert-events":
        summary = convert_almunaa_events(args.events, args.out)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "batch":
        summary = evaluate_preflight(args.input, repeat=1, max_records=args.max_records)
        _write_json(args.json_out, summary)
        _write_text(args.report, batch_markdown(summary, "تقرير اختبار السرب على بيانات Neuralchemy"))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["collapse_check"]["passed"] else 2
    if args.cmd == "stress":
        summary = evaluate_preflight(args.input, repeat=args.repeat, max_records=args.max_records)
        _write_json(args.json_out, summary)
        _write_text(args.report, batch_markdown(summary, "تقرير ضغط السرب"))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["collapse_check"]["passed"] else 2
    if args.cmd == "verify-ledger":
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "serve":
        from .service import run_server

        run_server(host=args.host, port=args.port)
        return 0
    if args.cmd == "version":
        from .version import __version__

        print(json.dumps({"service": "alsirb", "version": __version__}, ensure_ascii=False))
        return 0
    raise ValueError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
