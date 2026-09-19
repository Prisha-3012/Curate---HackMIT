"""ENOUGH API.

§7: "main.py is written once in hour 0 and never touched again." Routers register
themselves here; add a router, don't edit the wiring.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
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

# Hackathon: the frontend runs on whatever port it lands on.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
        "credentials_present": {
            "openai": bool(s.openai_api_key),
            "supabase": bool(s.supabase_url and s.supabase_key),
            "cybersource": bool(s.cybersource_merchant_id and s.cybersource_secret_key),
            "deepgram": bool(s.deepgram_api_key),
        },
    }
