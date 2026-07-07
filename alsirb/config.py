"""Central runtime configuration for alsirb (env-driven, ``ALSIRB_*``)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


@dataclass(frozen=True)
class ServiceConfig:
    home: Path = field(default_factory=lambda: PROJECT_ROOT)
    api_key: str = ""
    host: str = "127.0.0.1"
    port: int = 8791
    max_body_bytes: int = 1_048_576
    log_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    log_level: str = "INFO"

    @property
    def auth_required(self) -> bool:
        return bool(self.api_key)


def load_config() -> ServiceConfig:
    home = _env_path("ALSIRB_HOME", PROJECT_ROOT)
    return ServiceConfig(
        home=home,
        api_key=os.environ.get("ALSIRB_API_KEY", "").strip(),
        host=os.environ.get("ALSIRB_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_env_int("ALSIRB_PORT", 8791),
        max_body_bytes=_env_int("ALSIRB_MAX_BODY_BYTES", 1_048_576, minimum=1024),
        log_dir=_env_path("ALSIRB_LOG_DIR", home / "logs"),
        log_level=os.environ.get("ALSIRB_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
