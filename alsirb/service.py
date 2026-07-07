"""Alsirb preflight gateway as a local HTTP service.

``POST /api/preflight`` checks a project brief through the immunity guard and
returns whether the swarm is allowed to build it. Full builds (``run``) stay
CLI-only by design — the HTTP surface never writes workspaces or executes
generated code on behalf of a network client.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from typing import Any

from .http_base import BaseServiceHandler, build_server
from .models import ProjectTask
from .orchestrator import preflight_task


def _preflight_route(data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    brief = str(data.get("brief") or "").strip()
    if not brief:
        return 400, {"ok": False, "error": "missing 'brief'"}
    result = preflight_task(ProjectTask(brief=brief, name=str(data.get("name") or "")))
    return 200, {
        "ok": True,
        "allowed": bool(result.get("allowed")),
        "action": result.get("action"),
        "score": result.get("score"),
        "findings": result.get("findings") or [],
    }


class Handler(BaseServiceHandler):
    post_routes = {"/api/preflight": staticmethod(_preflight_route)}


def create_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    return build_server(Handler, host=host, port=port)


def run_server(host: str | None = None, port: int | None = None) -> None:
    from .version import __version__

    server = create_server(host=host, port=port)
    print(f"alsirb service v{__version__}: http://{server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
