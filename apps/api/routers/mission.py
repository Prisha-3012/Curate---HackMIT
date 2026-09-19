"""POST /api/mission and GET /api/mission/{id} — ARCHITECTURE.md §4.

With DEMO_MODE=on neither handler body runs: the middleware returns the hero
fixture first (§6). What follows is the live path.
"""

import logging

from fastapi import APIRouter, HTTPException

from apps.api import fixtures
from apps.api.db import repo
from apps.api.models.schemas import MissionRequest, Plan
from apps.api.services import planner

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["mission"])


@router.post("/mission", response_model=Plan)
def create_mission(payload: MissionRequest) -> Plan:
    try:
        plan = planner.build_plan(
            payload.goal_text,
            user_id=payload.user_id,
            budget_cents=payload.budget_cents,
        )
    except Exception:
        # Standing rule: never let the live path take the demo down.
        log.exception("planner failed, falling back to the hero fixture")
        return fixtures.load_as(fixtures.HERO_PLAN, Plan)

    stored = repo.save_mission(
        plan.mission_id,
        user_id=payload.user_id,
        goal_text=payload.goal_text,
        budget_cents=payload.budget_cents,
        plan_json=plan.model_dump(mode="json"),
    )
    if not stored:
        # Not fatal: the plan is still correct, but GET won't replay it exactly.
        log.warning("mission %s not persisted; GET will rebuild", plan.mission_id)

    return plan


@router.get("/mission/{mission_id}", response_model=Plan)
def get_mission(mission_id: str) -> Plan:
    """§4: returns the same object.

    Exact replay from missions.plan_json when it's there. When it isn't — DB
    down, or the mission predates persistence — rebuild rather than 404, since
    resolution is deterministic over the same seed.
    """
    stored = repo.get_plan_json(mission_id)
    if stored:
        return Plan.model_validate(stored)

    log.info("no stored plan for %s; rebuilding", mission_id)
    try:
        plan = planner.build_plan(
            "business casual for my internship",
            user_id=repo.DEMO_FALLBACK_USER,
            budget_cents=15000,
            mission_id=mission_id,
        )
        return plan
    except Exception:
        log.exception("rebuild failed for %s", mission_id)
        raise HTTPException(status_code=404, detail="mission not found")
