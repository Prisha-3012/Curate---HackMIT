"""ENOUGH API.

§7: "main.py is written once in hour 0 and never touched again." Routers register
themselves here; add a router, don't edit the wiring.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.db import repo
from apps.api.services import payments
from apps.api.demo import DemoModeMiddleware
from apps.api.routers import checkout, mission, voice

#: §6, verbatim.
DEMO_MODE = os.getenv("DEMO_MODE", "off")

app = FastAPI(
    title="ENOUGH API",
    version="0.1.0",
    description=(
        "Goal in, Plan out. Shapes are fixed by ARCHITECTURE.md §4 — /docs is the "
        "contract the frontend, CV and checkout lanes code against."
    ),
)

#: C's Next.js dev server. Explicit origins rather than "*" because the wildcard
#: is incompatible with allow_credentials, and cookies/auth headers are cheaper to
#: allow now than to debug mid-demo.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",  # Next falls back to 3001 when 3000 is taken
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",  # preview deploys
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Demo-Fixture"],
)
app.add_middleware(DemoModeMiddleware)

app.include_router(mission.router)
app.include_router(checkout.router)
app.include_router(voice.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Never short-circuited — this must tell the truth in demo mode."""
    s = get_settings()
    return {
        "ok": True,
        "demo_mode": DEMO_MODE,
        # PRESENT, not working. A present key with no credit behind it reads
        # true here and still decomposes every goal into the seeded needs —
        # `python -m apps.api.preflight` is what answers "does it work".
        "credentials_present": {
            "gemini": bool(s.gemini_api_key),
            "openai": bool(s.openai_api_key),
            "xai": bool(s.xai_api_key),
            "supabase": bool(s.supabase_url and s.supabase_key),
            "cybersource": bool(s.cybersource_merchant_id and s.cybersource_secret_key),
            "deepgram": bool(s.deepgram_api_key),
        },
        "payment_rails": payments.rail_status(),
        "data_source": repo.source(),
    }
