"""Closet detection and OWN injection; no external provider or database calls."""
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.models.schemas import Rung
from apps.api.services import planner, resolver, wardrobe

RAW = {"category": "top", "color": " White ", "style": "Oxford",
       "formality": "business-casual", "material": "cotton", "pattern": "striped"}
NEED = {"id": "shirt-need", "label": "A suitable top", "rationale": "For the goal",
        "priority": 1, "category": "top", "attrs": {"color": "white", "style": "oxford"}}
MARKET = {"id": "market-shirt", "title": "Market shirt", "category": "top", "rung": "NEW",
          "price_cents": 2500, "retail_cents": 4000, "attrs": NEED["attrs"]}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "off")
    monkeypatch.setattr(wardrobe, "_WARDROBE", {})
    monkeypatch.setattr(wardrobe, "get_settings", lambda: SimpleNamespace(
        gemini_api_key=None, openai_api_key=None, groq_api_key=None, xai_api_key=None,
        llm_provider="auto", llm_timeout_s=1))
    monkeypatch.setattr(planner.repo, "listings", lambda: [])
    monkeypatch.setattr(planner.repo, "users_by_id", lambda: {})
    monkeypatch.setattr(planner.repo, "prefs_for", lambda user: {})
    monkeypatch.setattr(planner.repo, "save_mission", lambda *a, **kw: True)
    monkeypatch.setattr(planner, "needs_for_goal", lambda *a, **kw: ([NEED], "groq"))
    monkeypatch.setattr(planner.products, "fetch_products", lambda *a: [MARKET])


def vision_response(monkeypatch, payload):
    monkeypatch.setattr(wardrobe, "_pick_vision_provider", lambda: (
        "groq", "https://vision.invalid/chat", "vision-model", "test-key"))
    response = httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]},
                              request=httpx.Request("POST", "https://vision.invalid/chat"))
    monkeypatch.setattr(wardrobe.httpx, "post", lambda *a, **kw: response)


def test_no_wardrobe_preserves_the_existing_pipeline():
    options, recommended, unmet = resolver.resolve_need(NEED, [MARKET], viewer_id="A")
    plan = planner.build_plan("goal", user_id="A", budget_cents=5000)
    assert plan.needs[0].options == options
    assert plan.needs[0].recommended_listing_id == recommended
    assert plan.needs[0].unmet_reason == unmet
    assert plan.impact.plan_cents == 2500
    assert plan.source == "live"


def test_detected_attributes_and_free_own_conversion(monkeypatch):
    vision_response(monkeypatch, {"items": [RAW]})
    items, source = wardrobe.analyze_wardrobe(b"photo", content_type="image/png")
    assert source == "groq"
    assert items[0]["attrs"] == {"color": "white", "style": "oxford", "formality": "business-casual",
                                 "material": "cotton", "pattern": "striped"}
    own = wardrobe.to_own_listings(items, "A")[0]
    assert own["rung"] == "OWN" and own["price_cents"] == 0 and own["owner_id"] == "A"
    assert own["attrs"] == items[0]["attrs"]


def test_upload_enters_own_and_is_isolated_from_other_users(monkeypatch):
    vision_response(monkeypatch, {"items": [RAW]})
    with TestClient(app) as client:
        upload = client.post("/api/wardrobe", data={"user_id": "A"},
                             files={"image": ("closet.png", b"photo", "image/png")},
                             headers={"Origin": "http://localhost:3000"})
        assert upload.status_code == 200
        assert upload.headers["X-Wardrobe-Source"] == "groq"
        assert "X-Wardrobe-Source" in upload.headers["access-control-expose-headers"]
        assert client.get("/api/wardrobe/A").json() == upload.json()
        assert client.get("/api/wardrobe/B").json() == {"items": [], "count": 0, "source": "none"}
        for user, expected in [("A", "OWN"), ("B", "NEW")]:
            response = client.post("/api/mission", json={"user_id": user, "goal_text": "goal", "budget_cents": 5000})
            assert response.status_code == 200
            need = response.json()["needs"][0]
            chosen = next(o for o in need["options"] if o["listing_id"] == need["recommended_listing_id"])
            assert chosen["rung"] == expected
            if user == "A":
                assert chosen["price_cents"] == 0
                # A matching market alternative survives: there is no purchase suppression.
                assert [o["rung"] for o in need["options"]] == ["OWN", "NEW"]


@pytest.mark.parametrize("payload", [{}, {"items": "bad"}, {"items": [None]},
                                      {"items": [{}]}, {"items": [{"color": {}, "style": "tee"}]}])
def test_malformed_detection_invents_nothing(monkeypatch, payload):
    vision_response(monkeypatch, payload)
    assert wardrobe.analyze_wardrobe(b"photo") == ([], "error")


def test_empty_image_and_no_provider_invent_nothing():
    assert wardrobe.analyze_wardrobe(b"") == ([], "none")
    assert wardrobe.analyze_wardrobe(b"photo") == ([], "none")


def test_zero_detected_items_invents_nothing(monkeypatch):
    vision_response(monkeypatch, {"items": []})
    assert wardrobe.analyze_wardrobe(b"photo") == ([], "none")


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("timeout"), ValueError("bad JSON")])
def test_provider_failure_invents_nothing(monkeypatch, failure):
    vision_response(monkeypatch, {"items": [RAW]})
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(wardrobe.httpx, "post", fail)
    assert wardrobe.analyze_wardrobe(b"photo") == ([], "error")


@pytest.mark.parametrize("source", ["none", "error"])
@pytest.mark.parametrize("has_prior_wardrobe", [False, True])
def test_empty_detection_preserves_stored_inventory(monkeypatch, source, has_prior_wardrobe):
    with TestClient(app) as client:
        previous = {"items": [], "count": 0, "source": "none"}
        if has_prior_wardrobe:
            vision_response(monkeypatch, {"items": [RAW]})
            successful = client.post("/api/wardrobe", data={"user_id": "A"},
                                     files={"image": ("p.png", b"photo")})
            assert successful.status_code == 200
            assert successful.json()["count"] == 1
            previous = successful.json()

        monkeypatch.setattr(wardrobe, "analyze_wardrobe", lambda *a, **kw: ([], source))
        def unexpected_store(*args, **kwargs):
            pytest.fail("Empty detection must not call set_wardrobe")
        monkeypatch.setattr(wardrobe, "set_wardrobe", unexpected_store)

        response = client.post("/api/wardrobe", data={"user_id": "A"},
                               files={"image": ("p.png", b"photo")})
        assert response.status_code == 200
        assert response.json() == {"items": [], "count": 0, "source": source}
        assert response.headers["X-Wardrobe-Source"] == source
        assert wardrobe.get_wardrobe("A") == previous["items"]
        assert client.get("/api/wardrobe/A").json() == previous
        if not has_prior_wardrobe:
            assert wardrobe.get_wardrobe_meta("A") is None


def test_active_ladder_and_all_existing_routes_are_preserved():
    assert resolver.LADDER == (Rung.OWN, Rung.USED, Rung.NEW)
    paths = set(app.openapi()["paths"])
    assert {"/api/mission", "/api/converse", "/api/checkout", "/api/retailer/redirect",
            "/api/voice/transcribe", "/api/wardrobe", "/api/wardrobe/{user_id}"} <= paths
