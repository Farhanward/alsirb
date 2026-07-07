from __future__ import annotations

import subprocess
import sys
import time
import re
from pathlib import Path
from typing import Any

from .models import CommandResult, ProjectTask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIBLINGS = {
    "almunaa": Path("C:/Projects/almunaa"),
    "aegis": Path("C:/Projects/aegis_local"),
    "kashif": Path("C:/Projects/kashif"),
}
_ALMUNAA_MODEL: Any | None = None
_ALMUNAA_MODEL_LOADED = False


def _should_use_lexical_model(text: str) -> bool:
    clean = text.strip()
    if len(clean) < 30:
        return False
    latin = sum(1 for char in clean.lower() if "a" <= char <= "z")
    return latin >= 12


def _deobfuscate_local(text: str) -> tuple[str, str]:
    try:
        _ensure_path(SIBLINGS["almunaa"])
        from almunaa.normalization import deobfuscate_text

        deobfuscated = deobfuscate_text(text)
    except Exception:
        deobfuscated = text.lower()
    squashed = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "", deobfuscated)
    return deobfuscated, squashed


def _local_swarm_findings(text: str) -> list[dict[str, Any]]:
    deobfuscated, squashed = _deobfuscate_local(text)
    joined = f"{deobfuscated}\n{squashed}"
    rules: list[tuple[str, str, str, str, re.Pattern[str]]] = [
        (
            "SWARM_PWNED_INJECTION",
            "high",
            "بصمة PWNED مموهة",
            "رصد السرب عبارة PWNED/PWND الشائعة في اختبارات حقن الأوامر.",
            re.compile(r"(?:i?havebeen)?pwn(?:e?d)?|pwnd|pwde|havebeenpw|rmihave", re.I),
        ),
        (
            "SWARM_OBFUSCATED_EXECUTION",
            "high",
            "طلب تنفيذ مموه",
            "رصد السرب طلب تنفيذ/eval/whoami بعد التطبيع.",
            re.compile(r"(execute|ex3cute|execu?te|eval|whoami|whoam|hackcat|hackr|catetcpasswd|runwhoam)", re.I),
        ),
        (
            "SWARM_HARMFUL_CONTENT",
            "high",
            "طلب محتوى ضار",
            "رصد السرب طلباً ضاراً واضحاً خارج بناء البرمجيات الآمن.",
            re.compile(
                r"(holocaust.{0,80}neverhappened|neverhappened.{0,80}holocaust|"
                r"anorexia|bulimia|fakenews|biracialmarriage|tamperwithvotingmachines|"
                r"harvestedorgans|blackmarket|5gcausescovid|ransomware|keylogger)",
                re.I,
            ),
        ),
        (
            "SWARM_SECRET_TOKEN",
            "high",
            "إشارة سر أو مفتاح",
            "رصد السرب طلباً يتضمن مفاتيح أو أسراراً لا يجب تحويلها إلى عمل وكيل.",
            re.compile(r"(secretkey|privatekey|apikey|token|credentials|password)", re.I),
        ),
        (
            "SWARM_CHAT_SENTINEL",
            "high",
            "رمز تحكم محادثة",
            "رصد السرب رمزاً شائعاً لمحاولة كسر حدود المحادثة.",
            re.compile(r"(<\|imend\|>|<\|im_start\|>|imend)", re.I),
        ),
        (
            "SWARM_PRIORITY_OVERRIDE",
            "high",
            "أولوية تعليمات مضادة",
            "رصد السرب محاولة جعل تعليمات المستخدم تتجاوز السياسات.",
            re.compile(r"(highestpriority|conflictinginstructions|ignoreallprevious|ignorepreviousinstructions|最高优先级)", re.I),
        ),
    ]
    findings: list[dict[str, Any]] = []
    for code, severity, title, detail, pattern in rules:
        match = pattern.search(joined)
        if not match:
            continue
        findings.append(
            {
                "code": code,
                "layer": "input",
                "severity": severity,
                "title": title,
                "detail": detail,
                "evidence": match.group(0)[:160],
            }
        )
    return findings


def _ensure_path(path: Path) -> None:
    resolved = str(path.resolve(strict=False))
    if path.exists() and resolved not in sys.path:
        sys.path.insert(0, resolved)


def guard_task(task: ProjectTask) -> dict[str, Any]:
    global _ALMUNAA_MODEL, _ALMUNAA_MODEL_LOADED
    _ensure_path(SIBLINGS["almunaa"])
    try:
        from almunaa.core import scan_event
        from almunaa.lexical_model import LexicalModel
        from almunaa.models import AgentEvent

        if not _ALMUNAA_MODEL_LOADED:
            model_path = SIBLINGS["almunaa"] / "models" / "almunaa_lexical_guard.json"
            if model_path.exists():
                _ALMUNAA_MODEL = LexicalModel.load(model_path)
            _ALMUNAA_MODEL_LOADED = True
        event = AgentEvent.from_dict(
            {
                "kind": "input",
                "agent": "alsirb-intake",
                "content": task.brief,
                "context": {
                    "project_name": task.name,
                    "language": task.language,
                    "audience": task.audience,
                    "constraints": task.constraints,
                },
            }
        )
        model = _ALMUNAA_MODEL if _should_use_lexical_model(task.brief) else None
        result = scan_event(event, write_ledger=False, write_quarantine=False, lexical_model=model)
        data = result.to_dict()
        extra_findings = _local_swarm_findings(task.brief)
        if extra_findings:
            data["findings"].extend(extra_findings)
            data["score"] = max(0.0, float(data.get("score") or 100.0) - 38.0 * len(extra_findings))
            if str(data.get("action")) == "ALLOW":
                data["action"] = "QUARANTINE"
        return data
    except Exception as exc:
        lowered = task.brief.lower()
        suspicious = any(token in lowered for token in ("ignore previous", ".env", "id_rsa", "docker.sock", "rm -rf", "powershell -enc"))
        return {
            "action": "BLOCK" if suspicious else "REVIEW",
            "score": 0 if suspicious else 65,
            "incident_id": "fallback",
            "findings": [
                {
                    "code": "FALLBACK_GUARD",
                    "layer": "input",
                    "severity": "critical" if suspicious else "medium",
                    "title": "حارس احتياطي",
                    "detail": "تعذر تحميل المناعة؛ استخدم السرب فحصاً احتياطياً.",
                    "evidence": repr(exc)[:240],
                }
            ],
        }


def scan_project(project_dir: str | Path) -> dict[str, Any]:
    _ensure_path(SIBLINGS["kashif"])
    try:
        from kashif.scanner import scan_path

        report = scan_path(project_dir)
        data = report.to_dict()
        severities = data.get("stats", {}).get("severity_counts", {})
        data["passed"] = not any(severities.get(level, 0) for level in ("critical", "high"))
        return data
    except Exception as exc:
        return {
            "root": str(Path(project_dir).resolve(strict=False)),
            "files": [],
            "findings": [
                {
                    "code": "KASHIF_UNAVAILABLE",
                    "severity": "medium",
                    "title": "تعذر تشغيل كاشف",
                    "file": "",
                    "line": 0,
                    "evidence": repr(exc)[:240],
                    "cwe": "",
                }
            ],
            "stats": {"file_count": 0, "finding_count": 1, "severity_counts": {"medium": 1}},
            "passed": False,
        }


def _fallback_run(command: str, cwd: Path, timeout: float) -> CommandResult:
    started = time.perf_counter()
    argv = command.split()
    allowed = argv[:3] == ["python", "-m", "unittest"] and str(cwd.resolve(strict=False)).startswith("C:\\Projects")
    if not allowed:
        return CommandResult(
            command=command,
            decision={"action": "BLOCK", "reason": "fallback runner allows only python -m unittest under C:/Projects"},
            executed=False,
            returncode=None,
            elapsed_seconds=time.perf_counter() - started,
        )
    completed = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, shell=False, timeout=timeout)
    return CommandResult(
        command=command,
        decision={"action": "ALLOW", "reason": "fallback safe unittest command"},
        executed=True,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        elapsed_seconds=time.perf_counter() - started,
    )


def run_unit_tests(project_dir: str | Path) -> CommandResult:
    command = "python -m unittest discover -s tests -v"
    cwd = Path(project_dir).resolve(strict=False)
    _ensure_path(SIBLINGS["aegis"])
    try:
        from aegis.models import ToolIntent
        from aegis.policy import AllowedCommand, GatePolicy
        from aegis.runner import run_intent

        policy = GatePolicy(
            allowed_commands=(
                AllowedCommand("python", (("-m", "unittest", "discover", "-s", "tests", "-v"), ("--version",), ("-V",)), 45.0),
            ),
            blocked_patterns=(),
            allowed_cwd_roots=(Path("C:/Projects").resolve(strict=False),),
            max_output_chars=20000,
            almunaa_model_path=SIBLINGS["almunaa"] / "models" / "almunaa_lexical_guard.json",
        )
        intent = ToolIntent(
            tool="shell",
            command=command,
            reason="اختبار وحدة للمشروع المحلي الناتج فقط.",
            agent="alsirb-tester",
            cwd=str(cwd),
            timeout_seconds=45,
            context={"project_dir": str(cwd)},
        )
        result = run_intent(
            intent,
            policy=policy,
            ledger_path=PROJECT_ROOT / "ledger" / "alsirb-aegis-ledger.jsonl",
            record=True,
        )
        return CommandResult(
            command=command,
            decision=result.decision.to_dict(),
            executed=result.executed,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_seconds=result.elapsed_seconds,
        )
    except Exception:
        return _fallback_run(command, cwd, 45.0)
