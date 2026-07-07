from __future__ import annotations

from typing import Any

from .models import SwarmRun


def run_markdown(run: SwarmRun) -> str:
    lines = [
        "# تقرير السرب",
        "",
        f"- الحالة: `{run.status}`",
        f"- المهمة: {run.task.brief}",
        f"- مساحة العمل: `{run.workspace}`",
        f"- المشروع الناتج: `{run.project_dir}`",
        f"- مدة التشغيل: `{run.elapsed_seconds:.2f}s`",
        f"- سجل التدقيق: `{run.ledger}`",
        "",
        "## الأدوار",
        "",
    ]
    for packet in run.packets:
        lines.append(f"- **{packet.role}**: `{packet.status}` -> `{packet.output_path}`")
        for note in packet.notes:
            lines.append(f"  - {note}")
    lines.extend(
        [
            "",
            "## الحوكمة",
            "",
            f"- قرار المناعة: `{run.immunity.get('action')}`",
            f"- درجة المناعة: `{run.immunity.get('score')}`",
            f"- ملاحظات المناعة: `{len(run.immunity.get('findings') or [])}`",
            "",
            "## الأمن والاختبار",
            "",
            f"- كاشف: `{'PASS' if run.security_scan.get('passed') else 'FAIL'}`",
            f"- إحصاءات كاشف: `{run.security_scan.get('stats', {})}`",
        ]
    )
    if run.test_result:
        lines.extend(
            [
                f"- AEGIS: `{run.test_result.decision.get('action')}`",
                f"- الاختبارات: `{'PASS' if run.test_result.ok else 'FAIL'}`",
                f"- كود الخروج: `{run.test_result.returncode}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def batch_markdown(summary: dict[str, Any], title: str = "تقرير اختبار السرب") -> str:
    metrics = summary.get("metrics", {})
    latency = summary.get("latency_ms", {})
    memory = summary.get("memory_mb", {})
    lines = [
        f"# {title}",
        "",
        f"- الملف: `{summary.get('input')}`",
        f"- السجلات الأصلية: `{summary.get('records')}`",
        f"- التكرار: `{summary.get('repeat')}`",
        f"- المعالجة الكلية: `{summary.get('processed')}`",
        f"- الأخطاء: `{summary.get('errors')}`",
        f"- الانهيار: `{'PASS' if summary.get('collapse_check', {}).get('passed') else 'FAIL'}`",
        "",
        "## الدقة",
        "",
        f"- Accuracy: `{metrics.get('accuracy', 0):.4f}`",
        f"- Precision: `{metrics.get('precision', 0):.4f}`",
        f"- Recall: `{metrics.get('recall', 0):.4f}`",
        f"- Specificity: `{metrics.get('specificity', 0):.4f}`",
        f"- F1: `{metrics.get('f1', 0):.4f}`",
        f"- TP/TN/FP/FN: `{metrics.get('tp')}/{metrics.get('tn')}/{metrics.get('fp')}/{metrics.get('fn')}`",
        "",
        "## الأداء",
        "",
        f"- mean: `{latency.get('mean', 0):.4f}ms`",
        f"- p50: `{latency.get('p50', 0):.4f}ms`",
        f"- p95: `{latency.get('p95', 0):.4f}ms`",
        f"- p99: `{latency.get('p99', 0):.4f}ms`",
        f"- max: `{latency.get('max', 0):.4f}ms`",
        f"- peak memory: `{memory.get('peak', 0):.4f}MB`",
        f"- elapsed: `{summary.get('elapsed_seconds', 0):.2f}s`",
        "",
        "## قرارات المناعة",
        "",
    ]
    for key, value in (summary.get("action_counts") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)
