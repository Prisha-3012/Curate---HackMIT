"""POST /api/checkout — ARCHITECTURE.md §4.

STEP 3: returns a fixed approved response so C and D have something to call.
STEP 8 swaps the body for Cybersource sandbox auth + capture via services/payments.py.
"""

from fastapi import APIRouter

from apps.api import fixtures
from apps.api.models.schemas import CheckoutRequest, CheckoutResponse

router = APIRouter(prefix="/api", tags=["checkout"])


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest) -> CheckoutResponse:
    # STEP 3 stub.
    return fixtures.load_as(fixtures.CHECKOUT_APPROVED, CheckoutResponse)
