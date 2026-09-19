"""Checkout: the gate, the rails, and the fallback.

Nothing here hits Stripe. Gateway behaviour is stubbed so the suite stays fast
and offline; the real charge is proven by a live end-to-end run instead.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.models.schemas import CheckoutResponse
from apps.api.services import payments

USER = "00000000-0000-0000-0000-000000000001"
USED_SHIRT = "4f70ab53-1d2e-4f60-8b84-9c5d1e3f70a4"   # top/USED  -> needs fitcheck
USED_BLAZER = "6192cd75-3f40-4b82-8da6-1e7f305092c6"  # outerwear/USED -> no fitcheck
OWN_OXFORDS = "1c4d7e20-8a9b-4c3d-9e51-6f2a8b0c4d71"  # OWN -> not purchasable
BORROW_SHIRT = "3e6f9a42-0c1d-4e5f-9a73-8b4c0d2e6f93" # BORROW -> not purchasable


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("DEMO_MODE", "off")
    # Never call a real gateway from the suite.
    monkeypatch.setattr(
        payments, "charge",
        lambda **kw: (payments.fixture_response(kw["amount_cents"]), "stub"),
    )
    return TestClient(app)


def _body(listing_id, measurement_id=None, size="M"):
    return {
        "user_id": USER, "listing_id": listing_id,
        "measurement_id": measurement_id, "size_label": size,
    }


# --- the FitCheck gate (§1) ------------------------------------------------


def test_used_apparel_without_a_fitcheck_is_blocked(client):
    r = client.post("/api/checkout", json=_body(USED_SHIRT))
    assert r.status_code == 409
    assert "FitCheck" in r.json()["detail"]


def test_used_apparel_with_a_fitcheck_goes_through(client):
    r = client.post("/api/checkout", json=_body(USED_SHIRT, measurement_id="m-1"))
    assert r.status_code == 200
    assert CheckoutResponse.model_validate(r.json()).status == "approved"


def test_non_fitcheckable_category_needs_no_measurement(client):
    """Outerwear can't be fit-checked, so requiring one would deadlock it."""
    r = client.post("/api/checkout", json=_body(USED_BLAZER))
    assert r.status_code == 200


# --- free rungs are not purchases ------------------------------------------


@pytest.mark.parametrize("listing_id", [OWN_OXFORDS, BORROW_SHIRT])
def test_own_and_borrow_cannot_be_checked_out(client, listing_id):
    r = client.post("/api/checkout", json=_body(listing_id))
    assert r.status_code == 400
    assert "nothing to check out" in r.json()["detail"]


def test_unknown_listing_is_404(client):
    r = client.post("/api/checkout", json=_body("00000000-0000-0000-0000-00000000dead"))
    assert r.status_code == 404


# --- the rail abstraction --------------------------------------------------


def test_live_keys_are_refused_by_the_rail():
    """A live key must never be usable here — this charges a card."""
    rail = payments.StripeRail()
    for key, ok in [
        ("sk_test_abc123", True),
        ("rk_test_abc123", True),
        ("sk_live_abc123", False),
        ("rk_live_abc123", False),
        ("", False),
    ]:
        import apps.api.config as cfg
        cfg.get_settings.cache_clear()
        object.__setattr__(cfg.get_settings(), "stripe_secret_key", key)
        assert rail.available() is ok, f"{key[:8]} should be available={ok}"
    cfg.get_settings.cache_clear()


def test_charge_falls_back_to_fixture_when_the_gateway_fails(monkeypatch):
    """Standing rule: a dead gateway degrades, it doesn't take the demo down."""
    class Broken:
        name = "broken"
        def available(self): return True
        def charge(self, **kw): raise payments.PaymentError("gateway on fire")

    monkeypatch.setattr(payments, "_RAILS", [Broken()])
    resp, source = payments.charge(
        amount_cents=2600, description="x", idempotency_key="k"
    )
    assert source == "fixture"
    assert resp.status == "approved"
    assert resp.txn_id.startswith("demo_")


def test_fixture_transactions_are_clearly_marked():
    """A demo charge must never be mistakable for a real one."""
    assert payments.fixture_response(2600).txn_id.startswith("demo_")


def test_no_rail_configured_still_returns_a_plan(monkeypatch):
    monkeypatch.setattr(payments, "_RAILS", [])
    resp, source = payments.charge(amount_cents=2600, description="x", idempotency_key="k")
    assert source == "fixture" and resp.status == "approved"


# --- receipt ---------------------------------------------------------------


def test_receipt_distinguishes_demo_from_test_mode(client):
    demo = client.get("/receipt/demo_abc123").text
    assert "no payment was processed" in demo
    real = client.get("/receipt/pi_3UHabc").text
    assert "no real money moved" in real
