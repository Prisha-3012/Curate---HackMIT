"""POST /api/checkout — ARCHITECTURE.md §4.

With DEMO_MODE=on the middleware returns the fixture before this runs (§6).

§1: "If the chosen option is on the NEW or USED rung and it's apparel, FitCheck
gates it with a size + confidence score before checkout fires." That gate is
enforced here, not in the frontend — a client-side-only gate is not a gate.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from apps.api.db import repo
from apps.api.models.schemas import (
    Category,
    CheckoutRequest,
    CheckoutResponse,
    Rung,
    needs_fitcheck_for,
)
from apps.api.services import payments

log = logging.getLogger(__name__)
router = APIRouter(tags=["checkout"])


@router.post("/api/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest) -> CheckoutResponse:
    listing = next(
        (item for item in repo.listings() if item["id"] == payload.listing_id), None
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")

    rung = Rung(listing["rung"])
    category = Category(listing["category"])

    # OWN and BORROW cost nothing and are not purchases. Charging for them would
    # be charging a user for their own jacket.
    if rung in (Rung.OWN, Rung.BORROW):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{listing['title']!r} is on the {rung.value} rung and costs "
                f"nothing — there is nothing to check out."
            ),
        )

    # §1's FitCheck gate.
    if needs_fitcheck_for(category, rung) and not payload.measurement_id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{listing['title']!r} needs a FitCheck before purchase. "
                f"Run POST /api/fitcheck and pass the measurement_id."
            ),
        )

    amount_cents = int(listing.get("price_cents") or 0)
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="listing has no price")

    # Keyed on the buyer and the listing so a double-clicked button cannot
    # charge twice, while a genuine second purchase still can.
    idempotency_key = f"enough-{payload.user_id}-{payload.listing_id}"

    response, source = payments.charge(
        amount_cents=amount_cents,
        description=f"ENOUGH — {listing['title']}",
        idempotency_key=idempotency_key,
    )
    log.info(
        "checkout %s via %s -> %s (%s)",
        payload.listing_id, source, response.status, response.txn_id,
    )

    if response.status == "approved":
        repo.save_purchase(
            purchase_id=str(uuid.uuid4()),
            user_id=payload.user_id,
            listing_id=payload.listing_id,
            measurement_id=payload.measurement_id,
            size_bought=payload.size_label,
            amount_cents=response.amount_cents,
            txn_id=response.txn_id,
        )

    return response


@router.get("/receipt/{txn_id}", response_class=HTMLResponse)
def receipt(txn_id: str) -> HTMLResponse:
    """§4's receipt_url. Stripe has a hosted receipt but it needs a customer
    email we don't collect, so this stands in."""
    demo = txn_id.startswith("demo_")
    banner = (
        "<p style='color:#b45309'>Demo transaction — no payment was processed.</p>"
        if demo
        else "<p style='color:#047857'>Stripe test mode — no real money moved.</p>"
    )
    return HTMLResponse(
        f"<!doctype html><meta charset=utf-8><title>Receipt {txn_id}</title>"
        f"<body style='font-family:system-ui;max-width:32rem;margin:4rem auto'>"
        f"<h1>ENOUGH</h1><p>Transaction <code>{txn_id}</code></p>{banner}</body>"
    )
