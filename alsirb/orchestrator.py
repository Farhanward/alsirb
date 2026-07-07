from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .integrations import guard_task, run_unit_tests, scan_project
from .ledger import append
from .models import ProjectTask, RolePacket, SwarmRun
from .templates import ProjectSpec, select_spec, write_project


DEFAULT_WORKSPACES = Path("workspaces")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _memory(workspace: Path, role: str, event: str, payload: dict[str, Any]) -> None:
    record = {"timestamp": _now(), "role": role, "event": event, "payload": payload}
    with (workspace / "shared_memory.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def preflight_task(task: ProjectTask) -> dict[str, Any]:
    immunity = guard_task(task)
    action = str(immunity.get("action") or "REVIEW")
    findings = immunity.get("findings") or []
    severe = [
        item for item in findings
        if str(item.get("severity", "")).lower() in {"critical", "high"}
    ]
    return {
        "allowed": action not in {"BLOCK", "QUARANTINE"} and not severe,
        "action": action,
        "score": immunity.get("score"),
        "findings": findings,
        "raw": immunity,
    }


def _architecture(task: ProjectTask, spec: ProjectSpec) -> str:
    return f"""# معمارية السرب

- المهمة: {task.brief}
- القالب المختار: `{spec.kind}`
- الحزمة: `{spec.package}`
- اللغة: `{task.language}`

## الأدوار

1. المعماري: يحول الجملة إلى نوع برنامج وحدود واضحة.
2. المبرمج: يولد مشروع Python CLI قابل للتشغيل.
3. المراجع: يتحقق من اكتمال الملفات الأساسية وقابلية القراءة.
4. الفاحص الأمني: يمرر المشروع إلى كاشف ويرفض المخاطر العالية.
5. المختبر: يشغل الاختبارات عبر AEGIS فقط عند السماح.
6. مسؤول التسليم: يكتب خلاصة التشغيل والمسارات.

## قرار التصميم

السرب يستخدم قوالب محلية حتمية بدلاً من توليد عشوائي، حتى تكون المخرجات قابلة للتكرار والمراجعة. يمكن لاحقاً تبديل عقل كل دور بنموذج محلي من ZEED مع بقاء نفس البوابات والسجل.
"""


def _plan(task: ProjectTask, spec: ProjectSpec) -> str:
    constraints = "\n".join(f"- {item}" for item in task.constraints) or "- لا توجد قيود إضافية."
    return f"""# خطة التنفيذ

## موجز

{task.brief}

## القيود

{constraints}

## خطوات البناء

- إنشاء مشروع `{spec.slug}`.
- كتابة `core.py` بمنطق العمل.
- كتابة `cli.py` بواجهة أوامر محلية.
- إضافة اختبارات وحدة في `tests/test_core.py`.
- فحص كاشف ثم تشغيل الاختبارات عبر AEGIS.
"""


def _review(project_dir: Path) -> tuple[str, bool]:
    required = ["README.md", "pyproject.toml", "tests/test_core.py"]
    missing = [name for name in required if not (project_dir / name).exists()]
    src_files = list((project_dir / "src").rglob("*.py")) if (project_dir / "src").exists() else []
    ok = not missing and len(src_files) >= 2
    lines = [
        "# مراجعة المبرمج",
        "",
        f"- المشروع: `{project_dir}`",
        f"- ملفات Python داخل src: `{len(src_files)}`",
        f"- الملفات المفقودة: `{missing}`",
        f"- القرار: `{'PASS' if ok else 'FAIL'}`",
        "",
    ]
    return "\n".join(lines), ok


def _security_markdown(scan: dict[str, Any]) -> str:
    stats = scan.get("stats", {})
    lines = [
        "# تقرير الفحص الأمني",
        "",
        f"- الملفات: `{stats.get('file_count', 0)}`",
        f"- الملاحظات: `{stats.get('finding_count', 0)}`",
        f"- الشدات: `{stats.get('severity_counts', {})}`",
        f"- القرار: `{'PASS' if scan.get('passed') else 'FAIL'}`",
        "",
        "## أعلى الملاحظات",
        "",
    ]
    findings = scan.get("findings") or []
    if not findings:
        lines.append("لا توجد ملاحظات ضمن قواعد كاشف الحالية.")
    for finding in findings[:40]:
        loc = finding.get("file") or ""
        if finding.get("line"):
            loc = f"{loc}:{finding.get('line')}"
        lines.append(f"- **{finding.get('severity')} / {finding.get('title')}** `{loc}` — `{finding.get('evidence', '')}`")
    lines.append("")
    return "\n".join(lines)


def _handoff(run: SwarmRun) -> str:
    return f"""# تسليم السرب

- الحالة: `{run.status}`
- مساحة العمل: `{run.workspace}`
- المشروع الناتج: `{run.project_dir}`
- مدة التشغيل: `{run.elapsed_seconds:.2f}s`
- فحص المناعة: `{run.immunity.get('action')}`
- فحص كاشف: `{'PASS' if run.security_scan.get('passed') else 'FAIL'}`
- الاختبارات: `{'PASS' if run.test_result and run.test_result.ok else 'FAIL'}`

## آلية عمل الحاويات/الأدوار باختصار

السرب هنا لا يشغل حاويات Docker؛ المقصود بالحاويات العملية هو أدوار معزولة داخل مساحة عمل واحدة: كل دور يستلم ذاكرة مشتركة، يكتب مخرجه في ملف مستقل، ولا يفتح بوابة التنفيذ إلا دور المختبر عبر AEGIS. هذا يجعل العمل قابلاً للتدقيق مثل خط إنتاج صغير.
"""


def run_task(task: ProjectTask, workspaces: str | Path = DEFAULT_WORKSPACES) -> SwarmRun:
    started = time.perf_counter()
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    workspace = Path(workspaces) / f"{task.slug}-{run_id}"
    workspace.mkdir(parents=True, exist_ok=True)
    packets: list[RolePacket] = []

    _write(workspace / "brief.md", f"# موجز المهمة\n\n{task.brief}\n")
    _memory(workspace, "intake", "task_received", task.to_dict())
    immunity = guard_task(task)
    _memory(workspace, "intake", "immunity_result", immunity)
    if str(immunity.get("action")) in {"BLOCK", "QUARANTINE"}:
        packets.append(RolePacket("intake", "فحص وصف المهمة قبل البناء", "blocked", "brief.md", ["رفضت المناعة الوصف قبل إنشاء أي مشروع."]))
        run = SwarmRun(run_id, task, workspace, None, "BLOCKED", packets, immunity, elapsed_seconds=time.perf_counter() - started)
        run.ledger = append({"kind": "swarm_run", "result": run.to_dict()})
        _write(workspace / "handoff.md", _handoff(run))
        return run

    spec = select_spec(task)
    architecture = _architecture(task, spec)
    _write(workspace / "architecture.md", architecture)
    packets.append(RolePacket("architect", "تحويل الفكرة إلى معمارية وقالب بناء", "done", "architecture.md", [f"template={spec.kind}"]))
    _memory(workspace, "architect", "selected_spec", {"kind": spec.kind, "package": spec.package})

    plan = _plan(task, spec)
    _write(workspace / "implementation_plan.md", plan)
    packets.append(RolePacket("planner", "تقسيم العمل إلى خطوات قابلة للتنفيذ", "done", "implementation_plan.md"))

    project_dir = workspace / "project"
    write_project(task, project_dir)
    packets.append(RolePacket("implementer", "توليد مشروع CLI واختباراته", "done", str(project_dir), [f"package={spec.package}"]))
    _memory(workspace, "implementer", "project_written", {"project_dir": str(project_dir)})

    review_text, review_ok = _review(project_dir)
    _write(workspace / "review.md", review_text)
    packets.append(RolePacket("reviewer", "مراجعة اكتمال الملفات", "done" if review_ok else "failed", "review.md"))

    scan = scan_project(project_dir)
    _write(workspace / "security_report.md", _security_markdown(scan))
    packets.append(RolePacket("security", "فحص كاشف للمشروع الناتج", "done" if scan.get("passed") else "failed", "security_report.md"))
    _memory(workspace, "security", "scan_finished", {"passed": scan.get("passed"), "stats": scan.get("stats")})

    test_result = run_unit_tests(project_dir)
    test_md = "# تقرير الاختبارات\n\n"
    test_md += f"- الأمر: `{test_result.command}`\n"
    test_md += f"- قرار AEGIS: `{test_result.decision.get('action')}` — {test_result.decision.get('reason')}\n"
    test_md += f"- نُفّذ: `{test_result.executed}`\n"
    test_md += f"- كود الخروج: `{test_result.returncode}`\n\n"
    test_md += "## stdout\n\n```text\n" + (test_result.stdout or "")[-4000:] + "\n```\n\n"
    test_md += "## stderr\n\n```text\n" + (test_result.stderr or "")[-4000:] + "\n```\n"
    _write(workspace / "test_report.md", test_md)
    packets.append(RolePacket("tester", "تشغيل اختبارات الوحدة عبر بوابة تنفيذ", "done" if test_result.ok else "failed", "test_report.md"))
    _memory(workspace, "tester", "tests_finished", test_result.to_dict())

    status = "PASS" if review_ok and scan.get("passed") and test_result.ok else "FAIL"
    run = SwarmRun(
        run_id=run_id,
        task=task,
        workspace=workspace,
        project_dir=project_dir,
        status=status,
        packets=packets,
        immunity=immunity,
        security_scan=scan,
        test_result=test_result,
        elapsed_seconds=time.perf_counter() - started,
    )
    _write(workspace / "handoff.md", _handoff(run))
    run.ledger = append({"kind": "swarm_run", "result": run.to_dict()})
    _memory(workspace, "delivery", "run_finished", {"status": status, "ledger": run.ledger})
    return run
