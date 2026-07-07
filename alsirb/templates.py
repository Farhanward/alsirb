from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path

from .models import ProjectTask, slugify


@dataclass(frozen=True)
class ProjectSpec:
    kind: str
    slug: str
    package: str
    title: str
    description: str


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    folded = text.lower()
    return any(needle in folded for needle in needles)


def select_spec(task: ProjectTask) -> ProjectSpec:
    brief = task.brief
    slug = slugify(task.name or brief[:40], "sirb_app")
    package = f"{slug.replace('-', '_')}_app"
    if _contains_any(brief, ("todo", "task", "kanban", "مهام", "مهمة", "قائمة")):
        return ProjectSpec("task_tracker", slug, package, "Task Tracker", "A local CLI for creating and completing tasks.")
    if _contains_any(brief, ("note", "notes", "memo", "ملاحظ", "مذكرة", "دفتر")):
        return ProjectSpec("notes", slug, package, "Notes CLI", "A local CLI for writing and searching notes.")
    if _contains_any(brief, ("text", "word", "words", "نص", "كلمات", "تحليل")):
        return ProjectSpec("text_analyzer", slug, package, "Text Analyzer", "A local CLI for text metrics and top terms.")
    return ProjectSpec("record_keeper", slug, package, "Record Keeper", "A local CLI for structured records with search.")


def _common_cli(spec: ProjectSpec, commands: str) -> str:
    return f'''from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import {commands}


def _load(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="{spec.slug}", description="{spec.description}")
    parser.add_argument("--db", default="data.json", help="JSON data file")
    sub = parser.add_subparsers(dest="cmd", required=True)
    build_parser(sub)
    args = parser.parse_args(argv)
    db = Path(args.db)
    rows = _load(db)
    result, changed = dispatch(args, rows)
    if changed:
        _save(db, rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
'''


def _cli_entrypoint() -> str:
    return '''

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _task_core() -> str:
    return '''from __future__ import annotations

from datetime import datetime, UTC


def add_task(tasks, title: str, priority: str = "normal"):
    title = title.strip()
    if not title:
        raise ValueError("title is required")
    item = {
        "id": len(tasks) + 1,
        "title": title,
        "priority": priority or "normal",
        "done": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    tasks.append(item)
    return item


def complete_task(tasks, task_id: int):
    for item in tasks:
        if int(item["id"]) == int(task_id):
            item["done"] = True
            item["completed_at"] = datetime.now(UTC).isoformat()
            return item
    raise LookupError(f"task not found: {task_id}")


def list_tasks(tasks, include_done: bool = False):
    return [item for item in tasks if include_done or not item.get("done")]
'''


def _task_cli() -> str:
    return _common_cli(ProjectSpec("task_tracker", "task-tracker", "task_tracker_app", "Task Tracker", "A local task tracker."), "add_task, complete_task, list_tasks") + '''

def build_parser(sub):
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("--priority", default="normal")
    done = sub.add_parser("done")
    done.add_argument("id", type=int)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--all", action="store_true")


def dispatch(args, rows):
    if args.cmd == "add":
        return add_task(rows, args.title, args.priority), True
    if args.cmd == "done":
        return complete_task(rows, args.id), True
    if args.cmd == "list":
        return list_tasks(rows, include_done=args.all), False
    raise ValueError(args.cmd)
''' + _cli_entrypoint()


def _notes_core() -> str:
    return '''from __future__ import annotations

from datetime import datetime, UTC


def create_note(notes, title: str, body: str, tags=None):
    title = title.strip()
    body = body.strip()
    if not title or not body:
        raise ValueError("title and body are required")
    item = {
        "id": len(notes) + 1,
        "title": title,
        "body": body,
        "tags": list(tags or []),
        "created_at": datetime.now(UTC).isoformat(),
    }
    notes.append(item)
    return item


def search_notes(notes, query: str):
    needle = query.casefold().strip()
    if not needle:
        return list(notes)
    return [
        item for item in notes
        if needle in item["title"].casefold()
        or needle in item["body"].casefold()
        or any(needle in tag.casefold() for tag in item.get("tags", []))
    ]
'''


def _notes_cli() -> str:
    return _common_cli(ProjectSpec("notes", "notes-cli", "notes_cli_app", "Notes CLI", "A local notes CLI."), "create_note, search_notes") + '''

def build_parser(sub):
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("body")
    add.add_argument("--tag", action="append", default=[])
    search = sub.add_parser("search")
    search.add_argument("query")


def dispatch(args, rows):
    if args.cmd == "add":
        return create_note(rows, args.title, args.body, args.tag), True
    if args.cmd == "search":
        return search_notes(rows, args.query), False
    raise ValueError(args.cmd)
''' + _cli_entrypoint()


def _text_core() -> str:
    return '''from __future__ import annotations

import re
from collections import Counter

WORD_RE = re.compile(r"[a-zA-Z0-9\\u0600-\\u06ff]+")


def analyze_text(text: str, top_n: int = 10):
    words = [match.group(0).casefold() for match in WORD_RE.finditer(text)]
    counts = Counter(words)
    return {
        "characters": len(text),
        "words": len(words),
        "unique_words": len(counts),
        "lines": text.count("\\n") + (1 if text else 0),
        "top_terms": counts.most_common(top_n),
    }
'''


def _text_cli() -> str:
    return _common_cli(ProjectSpec("text_analyzer", "text-analyzer", "text_analyzer_app", "Text Analyzer", "A local text analyzer."), "analyze_text") + '''

def build_parser(sub):
    analyze = sub.add_parser("analyze")
    analyze.add_argument("text")
    analyze.add_argument("--top", type=int, default=10)


def dispatch(args, rows):
    if args.cmd == "analyze":
        return analyze_text(args.text, args.top), False
    raise ValueError(args.cmd)
''' + _cli_entrypoint()


def _record_core() -> str:
    return '''from __future__ import annotations

from datetime import datetime, UTC


def create_record(records, title: str, detail: str, status: str = "open"):
    title = title.strip()
    detail = detail.strip()
    if not title or not detail:
        raise ValueError("title and detail are required")
    item = {
        "id": len(records) + 1,
        "title": title,
        "detail": detail,
        "status": status or "open",
        "created_at": datetime.now(UTC).isoformat(),
    }
    records.append(item)
    return item


def search_records(records, query: str):
    needle = query.casefold().strip()
    if not needle:
        return list(records)
    return [
        item for item in records
        if needle in item["title"].casefold()
        or needle in item["detail"].casefold()
        or needle in item["status"].casefold()
    ]
'''


def _record_cli() -> str:
    return _common_cli(ProjectSpec("record_keeper", "record-keeper", "record_keeper_app", "Record Keeper", "A local record keeper."), "create_record, search_records") + '''

def build_parser(sub):
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("detail")
    add.add_argument("--status", default="open")
    search = sub.add_parser("search")
    search.add_argument("query")


def dispatch(args, rows):
    if args.cmd == "add":
        return create_record(rows, args.title, args.detail, args.status), True
    if args.cmd == "search":
        return search_records(rows, args.query), False
    raise ValueError(args.cmd)
''' + _cli_entrypoint()


def _tests(spec: ProjectSpec) -> str:
    package = spec.package
    if spec.kind == "task_tracker":
        body = '''
    def test_add_and_complete_task(self):
        rows = []
        item = core.add_task(rows, "ship the build", "high")
        self.assertEqual(item["id"], 1)
        self.assertFalse(item["done"])
        core.complete_task(rows, 1)
        self.assertEqual(core.list_tasks(rows), [])
        self.assertEqual(len(core.list_tasks(rows, include_done=True)), 1)
'''
    elif spec.kind == "notes":
        body = '''
    def test_create_and_search_note(self):
        rows = []
        core.create_note(rows, "Launch", "Prepare local demo", ["demo"])
        self.assertEqual(len(core.search_notes(rows, "launch")), 1)
        self.assertEqual(len(core.search_notes(rows, "demo")), 1)
        self.assertEqual(core.search_notes(rows, "missing"), [])
'''
    elif spec.kind == "text_analyzer":
        body = '''
    def test_analyze_text(self):
        result = core.analyze_text("alpha beta alpha\\nمرحبا")
        self.assertEqual(result["words"], 4)
        self.assertEqual(result["lines"], 2)
        self.assertEqual(result["top_terms"][0][0], "alpha")
'''
    else:
        body = '''
    def test_create_and_search_record(self):
        rows = []
        core.create_record(rows, "Build", "Create a local tool", "open")
        self.assertEqual(len(core.search_records(rows, "local")), 1)
        self.assertEqual(len(core.search_records(rows, "closed")), 0)
'''
    return f'''from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from {package} import core


class GeneratedProjectTests(unittest.TestCase):
{body}


if __name__ == "__main__":
    unittest.main()
'''


def _files_for(spec: ProjectSpec, task: ProjectTask) -> dict[str, str]:
    if spec.kind == "task_tracker":
        core = _task_core()
        cli = _task_cli()
    elif spec.kind == "notes":
        core = _notes_core()
        cli = _notes_cli()
    elif spec.kind == "text_analyzer":
        core = _text_core()
        cli = _text_cli()
    else:
        core = _record_core()
        cli = _record_cli()
    readme = f"""# {spec.title}

Generated by AlSirb from this brief:

> {task.brief}

## Run

```powershell
python -m {spec.package}.cli --help
```

## Test

```powershell
python -m unittest discover -s tests -v
```
"""
    pyproject = f"""[project]
name = "{spec.slug}"
version = "0.1.0"
description = "{spec.description}"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools]
package-dir = {{"" = "src"}}
packages = ["{spec.package}"]
"""
    return {
        "README.md": readme,
        "pyproject.toml": pyproject,
        f"src/{spec.package}/__init__.py": f'"""Generated {spec.title} package."""\n',
        f"src/{spec.package}/core.py": core,
        f"src/{spec.package}/cli.py": cli,
        "tests/test_core.py": _tests(spec),
    }


def write_project(task: ProjectTask, target_dir: str | Path) -> ProjectSpec:
    spec = select_spec(task)
    root = Path(target_dir)
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in _files_for(spec, task).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return spec
