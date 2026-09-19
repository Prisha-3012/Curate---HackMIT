"""POST /api/mission and GET /api/mission/{id} — ARCHITECTURE.md §4.

STEP 3: both routes return the hero fixture. Zero logic. The point is to prove the
spine responds and to hand C a real Plan to render against from hour 3.

Steps 5-7 replace the body with decompose -> resolve -> savings. The response shape
does not change when that happens; that is the whole reason the fixture exists.
"""

from fastapi import APIRouter

from apps.api import fixtures
from apps.api.models.schemas import MissionRequest, Plan

router = APIRouter(prefix="/api", tags=["mission"])


@router.post("/mission", response_model=Plan)
def create_mission(payload: MissionRequest) -> Plan:
    # STEP 3 stub. Validated on the way out so a fixture that drifts from
    # schemas.py fails here rather than in the frontend.
    plan = fixtures.load_as(fixtures.HERO_PLAN, Plan)
    return plan.model_copy(
        update={"goal_text": payload.goal_text, "budget_cents": payload.budget_cents}
    )


@router.get("/mission/{mission_id}", response_model=Plan)
def get_mission(mission_id: str) -> Plan:
    """§4: returns the same object.

    Step 4 adds missions.plan_json and this becomes an exact replay of what POST
    returned. Until then it is the fixture with the requested id echoed back.
    """
    plan = fixtures.load_as(fixtures.HERO_PLAN, Plan)
    return plan.model_copy(update={"mission_id": mission_id})
