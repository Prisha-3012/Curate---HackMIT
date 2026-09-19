"""POST /api/converse — §4 extension, 2026-09-19.

The spoken front door to POST /api/mission. Stateless: the client sends the
whole conversation each time, so there is no session to expire mid-demo and no
seventh table.

When `ready` comes back true, the client POSTs `goal_text` and `budget_cents`
to /api/mission. This route never builds a plan itself — keeping that seam
means the typed path and the spoken path produce identical plans.
"""

import logging

from fastapi import APIRouter

from apps.api.models.schemas import ConverseReply, ConverseRequest
from apps.api.services import converse as service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["converse"])


@router.post("/converse", response_model=ConverseReply)
def converse(payload: ConverseRequest) -> ConverseReply:
    try:
        return service.converse(payload.messages, user_id=payload.user_id)
    except Exception:
        # Standing rule: the live path never takes the demo down. The scripted
        # ladder needs no network and cannot realistically fail.
        log.exception("converse failed entirely; falling back to the script")
        return service.scripted(payload.messages)
