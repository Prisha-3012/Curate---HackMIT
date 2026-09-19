"""Payment rails behind one interface.

ARCHITECTURE.md §4 fixes the /api/checkout request and response shapes. Which
processor sits behind them is an implementation detail, and it has already
changed once — see the changelog entry for 2026-09-19.

CURRENT RAIL: Stripe test mode. Cybersource sandbox credentials and HTTP
Signature auth were verified working (real transaction ids came back) but every
request returned 502 SERVER_ERROR / SYSTEM_ERROR, which is account provisioning,
not code. §8 names Stripe test mode as the documented fallback.

Every call has an explicit timeout and a fixture fallback, per the standing rule.
A dead gateway degrades to an approved demo response rather than taking the demo
down — and says so in the logs, so a silent fixture can't be mistaken for a real
charge.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional, Protocol

import httpx

from apps.api.config import get_settings
from apps.api.models.schemas import CheckoutResponse

log = logging.getLogger(__name__)

STRIPE_BASE = "https://api.stripe.com/v1"

#: Stripe's documented test payment method for 4242 4242 4242 4242. Real card
#: numbers are never accepted by the API directly, and never belong in this repo.
TEST_PAYMENT_METHOD = "pm_card_visa"


class PaymentError(RuntimeError):
    """The gateway refused, errored, or was unreachable."""


class Rail(Protocol):
    """Both implementations satisfy this, so the router never branches on which
    processor is live."""

    name: str

    def available(self) -> bool: ...

    def charge(
        self, *, amount_cents: int, description: str, idempotency_key: str
    ) -> CheckoutResponse: ...


# --------------------------------------------------------------------------
# Stripe test mode
# --------------------------------------------------------------------------


class StripeRail:
    name = "stripe"

    def available(self) -> bool:
        key = (get_settings().stripe_secret_key or "").strip()
        # Test keys only. sk_test_ (secret) and rk_test_ (restricted) both
        # qualify; anything _live_ would be a real charge and is refused here
        # rather than at the point of use.
        return bool(key) and "_test_" in key[:12]

    def charge(
        self, *, amount_cents: int, description: str, idempotency_key: str
    ) -> CheckoutResponse:
        s = get_settings()
        key = (s.stripe_secret_key or "").strip()
        if not self.available():
            raise PaymentError("no usable Stripe test key configured")

        try:
            r = httpx.post(
                f"{STRIPE_BASE}/payment_intents",
                auth=(key, ""),
                data={
                    "amount": str(amount_cents),
                    "currency": "usd",
                    "payment_method": TEST_PAYMENT_METHOD,
                    "confirm": "true",
                    "description": description[:350],
                    "automatic_payment_methods[enabled]": "true",
                    "automatic_payment_methods[allow_redirects]": "never",
                },
                # Idempotency matters: a retried capture must not charge twice.
                headers={"Idempotency-Key": idempotency_key},
                timeout=s.stripe_timeout_s,
            )
        except httpx.HTTPError as exc:
            raise PaymentError(f"stripe unreachable: {exc}") from exc

        data: dict[str, Any] = r.json() if r.content else {}

        if r.status_code == 200:
            status = data.get("status")
            if status == "succeeded":
                txn = data.get("id", "")
                return CheckoutResponse(
                    status="approved",
                    txn_id=txn,
                    amount_cents=int(data.get("amount_received") or amount_cents),
                    receipt_url=f"/receipt/{txn}",
                )
            # Confirmed but not succeeded: needs 3DS, or is still processing.
            # Neither is an approval, so it must not be reported as one.
            log.warning("stripe returned status=%s, treating as declined", status)
            return CheckoutResponse(
                status="declined",
                txn_id=data.get("id", ""),
                amount_cents=amount_cents,
            )

        err = data.get("error") or {}
        # A card decline is a normal outcome, not an integration failure.
        if err.get("type") == "card_error":
            log.info("stripe declined: %s", err.get("code"))
            return CheckoutResponse(
                status="declined",
                txn_id=(err.get("payment_intent") or {}).get("id", ""),
                amount_cents=amount_cents,
            )
        raise PaymentError(
            f"stripe {r.status_code} {err.get('code')}: {err.get('message')}"
        )


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------

_RAILS: list[Rail] = [StripeRail()]


def active_rail() -> Optional[Rail]:
    """First configured rail, or None. Order is preference order."""
    return next((rail for rail in _RAILS if rail.available()), None)


def rail_status() -> dict[str, bool]:
    """For /health — which rails could actually take a payment right now."""
    return {rail.name: rail.available() for rail in _RAILS}


def fixture_response(amount_cents: int) -> CheckoutResponse:
    """The fallback. Clearly marked so a demo charge is never mistaken for real."""
    txn = f"demo_{uuid.uuid4().hex[:20]}"
    return CheckoutResponse(
        status="approved",
        txn_id=txn,
        amount_cents=amount_cents,
        receipt_url=f"/receipt/{txn}",
    )


def charge(
    *, amount_cents: int, description: str, idempotency_key: str
) -> tuple[CheckoutResponse, str]:
    """Charge via the active rail, falling back to a fixture.

    Returns (response, source) where source is the rail name or "fixture", so
    the caller can log and /health can report it honestly.
    """
    rail = active_rail()
    if rail is None:
        log.warning("no payment rail configured; returning fixture response")
        return fixture_response(amount_cents), "fixture"

    try:
        return (
            rail.charge(
                amount_cents=amount_cents,
                description=description,
                idempotency_key=idempotency_key,
            ),
            rail.name,
        )
    except PaymentError:
        log.exception("%s failed; falling back to fixture", rail.name)
        return fixture_response(amount_cents), "fixture"
