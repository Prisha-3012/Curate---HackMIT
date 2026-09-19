"""The fixture and schemas.py must agree, and the fixture's own arithmetic must
hold. §6 calls hero_plan.json both the contract and the safety net — these tests
are what keep it honest as the real services land in steps 5-8.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api import fixtures
from apps.api.main import app
from apps.api.models.schemas import (
    Category,
    CheckoutResponse,
    FitCheckResult,
    Plan,
    Rung,
    TranscribeResponse,
    needs_fitcheck_for,
)


DEMO_USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def plan() -> Plan:
    return fixtures.load_as(fixtures.HERO_PLAN, Plan)


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("DEMO_MODE", "on")
    return TestClient(app)


# --- the fixture validates -------------------------------------------------


def test_every_fixture_validates() -> None:
    fixtures.load_as(fixtures.HERO_PLAN, Plan)
    fixtures.load_as(fixtures.FITCHECK_RESULT, FitCheckResult)
    fixtures.load_as(fixtures.CHECKOUT_APPROVED, CheckoutResponse)
    fixtures.load_as(fixtures.TRANSCRIPT, TranscribeResponse)


def test_hero_plan_shape(plan: Plan) -> None:
    assert plan.goal_text == "business casual for my internship"
    assert len(plan.needs) == 3, "the hero plan is specified as three needs"
    rungs = {opt.rung for need in plan.needs for opt in need.options}
    assert rungs == set(Rung), f"hero plan must span all four rungs, got {rungs}"


# --- referential integrity -------------------------------------------------


def test_recommended_listing_is_one_of_the_options(plan: Plan) -> None:
    for need in plan.needs:
        ids = {opt.listing_id for opt in need.options}
        assert need.recommended_listing_id in ids, (
            f"need {need.label!r} recommends {need.recommended_listing_id}, "
            f"which is not among its own options"
        )


def test_listing_ids_are_unique(plan: Plan) -> None:
    ids = [opt.listing_id for need in plan.needs for opt in need.options]
    assert len(ids) == len(set(ids))


# --- the impact arithmetic holds -------------------------------------------


def _recommended(plan: Plan) -> list:
    out = []
    for need in plan.needs:
        out.append(next(o for o in need.options if o.listing_id == need.recommended_listing_id))
    return out


def test_plan_cents_matches_recommended_options(plan: Plan) -> None:
    assert plan.impact.plan_cents == sum(o.price_cents for o in _recommended(plan))


def test_baseline_matches_retail_of_recommended(plan: Plan) -> None:
    """§4: baseline is 'cost if every need were bought NEW'."""
    assert plan.impact.baseline_cents == sum(o.retail_cents for o in _recommended(plan))


def test_saved_is_baseline_minus_plan(plan: Plan) -> None:
    impact = plan.impact
    assert impact.saved_cents == impact.baseline_cents - impact.plan_cents


def test_items_reused_counts_non_new_recommendations(plan: Plan) -> None:
    reused = sum(1 for o in _recommended(plan) if o.rung is not Rung.NEW)
    assert plan.impact.items_reused == reused


def test_plan_is_within_budget(plan: Plan) -> None:
    """Not enforced by §4, but the hero demo's whole story is coming in under."""
    assert plan.impact.plan_cents <= plan.budget_cents


# --- the FitCheck gate is self-consistent ----------------------------------


def test_fitcheck_gate_matches_the_rule() -> None:
    assert needs_fitcheck_for(Category.TOP, Rung.NEW) is True
    assert needs_fitcheck_for(Category.BOTTOM, Rung.USED) is True
    # Decided 2026-09-19: footwear can be flagged but never fit-checked, so it isn't.
    assert needs_fitcheck_for(Category.FOOTWEAR, Rung.USED) is False
    assert needs_fitcheck_for(Category.OUTERWEAR, Rung.NEW) is False
    # Already in hand: no fit risk worth gating on.
    assert needs_fitcheck_for(Category.TOP, Rung.OWN) is False
    assert needs_fitcheck_for(Category.TOP, Rung.BORROW) is False


def test_no_own_or_borrow_option_requests_fitcheck(plan: Plan) -> None:
    for need in plan.needs:
        for opt in need.options:
            if opt.rung in (Rung.OWN, Rung.BORROW):
                assert not opt.needs_fitcheck, f"{opt.title} is on {opt.rung.value}"


# --- the spine responds ----------------------------------------------------


def test_health_tells_the_truth_in_demo_mode(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["demo_mode"] in ("on", "off")


def test_post_mission_returns_a_plan(client: TestClient) -> None:
    r = client.post(
        "/api/mission",
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "goal_text": "business casual for my internship",
            "budget_cents": 15000,
        },
    )
    assert r.status_code == 200
    assert r.headers.get("X-Demo-Fixture") == fixtures.HERO_PLAN
    Plan.model_validate(r.json())


def test_get_mission_returns_the_same_object(client: TestClient) -> None:
    post = client.post(
        "/api/mission",
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "goal_text": "business casual for my internship",
            "budget_cents": 15000,
        },
    ).json()
    got = client.get(f"/api/mission/{post['mission_id']}").json()
    assert got == post, "§4: GET /api/mission/{id} returns the same object"


def test_checkout_and_voice_respond(client: TestClient) -> None:
    r = client.post(
        "/api/checkout",
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "listing_id": "4f70ab53-1d2e-4f60-8b84-9c5d1e3f70a4",
            "measurement_id": None,
            "size_label": "M",
        },
    )
    assert r.status_code == 200
    CheckoutResponse.model_validate(r.json())

    r = client.post("/api/voice/speak", json={"text": "You already own most of this."})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")


def test_unregistered_api_route_refuses_rather_than_running_live(client: TestClient) -> None:
    """A missing fixture must surface in rehearsal, not on stage."""
    r = client.post("/api/not-a-real-route", json={})
    assert r.status_code == 503
    assert "no fixture is registered" in r.json()["detail"]


# --- provenance: fixture data must never pass as a live result -------------


def test_the_hero_fixture_declares_itself_a_fixture(plan: Plan) -> None:
    """It is a WARDROBE plan. Served for a camping goal it answers the wrong
    question, so it has to say what it is."""
    assert plan.source == "fixture"


def test_demo_mode_responses_are_labelled_as_fixtures(client: TestClient) -> None:
    r = client.post(
        "/api/mission",
        json={"user_id": DEMO_USER, "goal_text": "anything at all", "budget_cents": 15000},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "fixture"
    assert r.headers.get("X-Demo-Fixture") == fixtures.HERO_PLAN


def test_a_live_plan_is_labelled_live(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "off")
    from apps.api.services import planner

    monkeypatch.setattr(
        planner,
        "needs_for_goal",
        lambda goal, **kw: [
            {
                "id": "prov-0001",
                "label": "a warm layer",
                "rationale": "x",
                "category": "outerwear",
                "attrs": {"formality": "business-casual"},
                "priority": 1,
            }
        ],
    )
    r = TestClient(app).post(
        "/api/mission",
        json={"user_id": DEMO_USER, "goal_text": "a real goal", "budget_cents": 50000},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "live"


def test_a_planner_failure_is_labelled_a_fixture_not_a_live_plan(monkeypatch) -> None:
    """The standing rule keeps this at 200 so the demo cannot go down. That makes
    the label the ONLY thing separating canned data from a real answer."""
    monkeypatch.setenv("DEMO_MODE", "off")
    from apps.api.services import planner

    def _explode(*a, **k):
        raise RuntimeError("live pipeline is down")

    monkeypatch.setattr(planner, "build_plan", _explode)
    r = TestClient(app).post(
        "/api/mission",
        json={"user_id": DEMO_USER, "goal_text": "a camping trip", "budget_cents": 20000},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "fixture", (
        "a failed live plan was served as though it were real"
    )


# --- $0 is a budget, absent is not -----------------------------------------


def test_a_mission_may_omit_the_budget(monkeypatch) -> None:
    """budget_cents is optional: None means unstated, not zero."""
    monkeypatch.setenv("DEMO_MODE", "off")
    from apps.api.services import planner

    monkeypatch.setattr(
        planner,
        "needs_for_goal",
        lambda goal, **kw: [
            {
                "id": "prov-0002",
                "label": "a warm layer",
                "rationale": "x",
                "category": "outerwear",
                "attrs": {"formality": "business-casual"},
                "priority": 1,
            }
        ],
    )
    r = TestClient(app).post(
        "/api/mission", json={"user_id": DEMO_USER, "goal_text": "a real goal"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["budget_cents"] is None
    assert body["needs"][0]["recommended_listing_id"] is not None
