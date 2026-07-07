from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def slugify(value: str, fallback: str = "sirb_project") -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "-", text, flags=re.I).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    if not text:
        text = fallback
    ascii_only = re.sub(r"[^a-z0-9-]+", "", text)
    if ascii_only and len(ascii_only) >= 3:
        text = ascii_only
    else:
        text = fallback
    return text[:80].strip("-") or fallback


@dataclass
class ProjectTask:
    brief: str
    name: str = ""
    language: str = "python"
    audience: str = "local"
    constraints: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.name or self.brief[:60])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectTask":
        return cls(
            brief=str(data.get("brief") or data.get("content") or ""),
            name=str(data.get("name") or ""),
            language=str(data.get("language") or "python"),
            audience=str(data.get("audience") or "local"),
            constraints=[str(item) for item in data.get("constraints") or []],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief": self.brief,
            "name": self.name,
            "slug": self.slug,
            "language": self.language,
            "audience": self.audience,
            "constraints": self.constraints,
        }


@dataclass
class RolePacket:
    role: str
    objective: str
    status: str
    output_path: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "objective": self.objective,
            "status": self.status,
            "output_path": self.output_path,
            "notes": self.notes,
        }


@dataclass
class CommandResult:
    command: str
    decision: dict[str, Any]
    executed: bool
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.executed and self.returncode == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "decision": self.decision,
            "executed": self.executed,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }


@dataclass
class SwarmRun:
    run_id: str
    task: ProjectTask
    workspace: Path
    project_dir: Path | None
    status: str
    packets: list[RolePacket] = field(default_factory=list)
    immunity: dict[str, Any] = field(default_factory=dict)
    security_scan: dict[str, Any] = field(default_factory=dict)
    test_result: CommandResult | None = None
    ledger: dict[str, Any] | None = None
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task": self.task.to_dict(),
            "workspace": str(self.workspace.resolve(strict=False)),
            "project_dir": str(self.project_dir.resolve(strict=False)) if self.project_dir else None,
            "status": self.status,
            "packets": [packet.to_dict() for packet in self.packets],
            "immunity": self.immunity,
            "security_scan": self.security_scan,
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "ledger": self.ledger,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }
