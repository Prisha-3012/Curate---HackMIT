"""DEMO_MODE short-circuit.

Decision (2026-09-19): DEMO_MODE=on returns fixtures for EVERY route,
unconditionally. This overrides §6's narrower rule, which short-circuits only when
request_matches_hero_path(payload) fuzzy-matches the demo goal string.

Rationale: on stage, nothing should be able to reach the network. §6's version lets
an off-script goal fall through to the live pipeline, which is exactly the moment
you least want a live pipeline.

Implemented as middleware rather than a dependency so the short-circuit happens
before any handler body runs, and so a router added later cannot forget to opt in.
"""

import re
from typing import Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api import fixtures
from apps.api.config import demo_mode_enabled

#: (method, compiled path pattern) -> fixture name.
#: Routes absent from this table are NOT short-circuited; they 503 in demo mode
#: rather than silently running live code.
_ROUTES: list[tuple[str, re.Pattern[str], str]] = [
    ("POST", re.compile(r"^/api/mission/?$"), fixtures.HERO_PLAN),
    ("GET", re.compile(r"^/api/mission/[^/]+/?$"), fixtures.HERO_PLAN),
    ("POST", re.compile(r"^/api/fitcheck/?$"), fixtures.FITCHECK_RESULT),
    ("POST", re.compile(r"^/api/checkout/?$"), fixtures.CHECKOUT_APPROVED),
    ("POST", re.compile(r"^/api/voice/transcribe/?$"), fixtures.TRANSCRIPT),
    # One canned turn that is already ready, so demo mode reaches the plan
    # rather than looping on a conversation the fixture cannot advance.
    ("POST", re.compile(r"^/api/converse/?$"), fixtures.CONVERSE_OPENING),
]

#: Never short-circuited: infrastructure routes that must tell the truth even in
#: demo mode, and the TTS route, which returns audio rather than JSON.
_PASSTHROUGH: list[tuple[str, re.Pattern[str]]] = [
    ("GET", re.compile(r"^/health/?$")),
    ("GET", re.compile(r"^/docs")),
    ("GET", re.compile(r"^/redoc")),
    ("GET", re.compile(r"^/openapi.json$")),
    ("POST", re.compile(r"^/api/voice/speak/?$")),
    ("GET", re.compile(r"^/receipt/")),
]


def _fixture_for(method: str, path: str) -> Optional[str]:
    for verb, pattern, name in _ROUTES:
        if verb == method and pattern.match(path):
            return name
    return None


def _is_passthrough(method: str, path: str) -> bool:
    if path == "/":
        return True
    return any(verb == method and pat.match(path) for verb, pat in _PASSTHROUGH)


class DemoModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not demo_mode_enabled():
            return await call_next(request)

        method, path = request.method, request.url.path

        if _is_passthrough(method, path):
            return await call_next(request)

        name = _fixture_for(method, path)
        if name is None:
            # An API route with no fixture. Refuse rather than run live code,
            # so a missing fixture surfaces in rehearsal instead of on stage.
            if path.startswith("/api/"):
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": (
                            f"DEMO_MODE=on and no fixture is registered for "
                            f"{method} {path}. Add one to apps/api/demo.py."
                        )
                    },
                )
            return await call_next(request)

        return JSONResponse(
            status_code=200,
            content=fixtures.load_fixture(name),
            headers={"X-Demo-Fixture": name},
        )
