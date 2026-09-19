"""decompose.py — the seam between model output and the resolver.

Everything else in the suite stubs `planner.needs_for_goal` and feeds the
resolver pre-shaped rows, so this file is the only thing exercising the
conversion itself: strict-mode attr arrays back into dicts, provider selection,
and every route to the fixture fallback.

No network. httpx.post is stubbed throughout — a test that can reach the
internet is a test that fails on conference wifi.
"""

import json
from types import SimpleNamespace

import httpx
import pytest

from apps.api.services import decompose

MISSION = "11111111-2222-4333-8444-555555555555"


def _settings(**overrides):
    base = {
        "openai_api_key": None,
        "xai_api_key": None,
        "llm_provider": "auto",
        "llm_model": None,
        "llm_timeout_s": 4.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture()
def with_settings(monkeypatch):
    def _apply(**overrides):
        monkeypatch.setattr(decompose, "get_settings", lambda: _settings(**overrides))
    return _apply


def _response(payload: dict) -> httpx.Response:
    """A chat-completions response carrying `payload` as the JSON content."""
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        request=httpx.Request("POST", "https://example.invalid/v1/chat/completions"),
    )


def _needs_payload(*needs) -> dict:
    return {"needs": list(needs)}


def _need(label="keep food cold", **overrides):
    item = {
        "label": label,
        "rationale": "Fridge space runs out.",
        "category": "cold-storage",
        "priority": 1,
        "attrs": [{"key": "portable", "value": "true"}],
    }
    item.update(overrides)
    return item


# --- attrs: strict mode forces key/value arrays ----------------------------


def test_attrs_array_becomes_a_dict_with_scalars_coerced():
    """OpenAI strict mode forbids free-form objects, so attrs arrive as pairs.
    The resolver matches on real types, so "true" must not stay a string."""
    got = decompose._attrs_to_dict(
        [
            {"key": "waterproof", "value": "true"},
            {"key": "indoor", "value": "False"},
            {"key": "serves", "value": "12"},
            {"key": "warmth", "value": "cold"},
        ]
    )
    assert got == {
        "waterproof": True,
        "indoor": False,
        "serves": 12,
        "warmth": "cold",
    }


@pytest.mark.parametrize("raw", [None, {}, "attrs", 7])
def test_attrs_that_are_not_a_list_degrade_to_empty(raw):
    """A need with no attrs matches anything in its category, which is a worse
    plan but not a crash."""
    assert decompose._attrs_to_dict(raw) == {}


def test_malformed_attr_pairs_are_skipped_not_fatal():
    got = decompose._attrs_to_dict(
        [
            {"key": "good", "value": "yes"},
            {"key": "missing-value", "value": None},
            {"value": "no key"},
            "not a dict",
            {"key": 12, "value": "non-string key"},
        ]
    )
    assert got == {"good": "yes"}


# --- rows: the shape the resolver consumes ---------------------------------


def test_rows_match_the_seeded_need_shape():
    """The live path and the fixture path must feed the resolver identically."""
    rows = decompose._to_need_rows(_needs_payload(_need()), MISSION)
    assert len(rows) == 1
    assert set(rows[0]) == {"id", "label", "rationale", "category", "attrs", "priority"}
    assert rows[0]["label"] == "keep food cold"
    assert rows[0]["category"] == "cold-storage"
    assert rows[0]["attrs"] == {"portable": True}
    assert rows[0]["priority"] == 1


def test_need_ids_are_deterministic_for_a_mission():
    """GET /api/mission rebuilds a plan when the DB is down; stable ids keep the
    rebuild from looking like a different plan."""
    once = decompose._to_need_rows(_needs_payload(_need()), MISSION)
    twice = decompose._to_need_rows(_needs_payload(_need()), MISSION)
    other = decompose._to_need_rows(_needs_payload(_need()), "different-mission")
    assert once[0]["id"] == twice[0]["id"]
    assert once[0]["id"] != other[0]["id"]


def test_needs_are_capped_at_max_needs():
    payload = _needs_payload(*[_need(label=f"need {i}") for i in range(decompose.MAX_NEEDS + 4)])
    assert len(decompose._to_need_rows(payload, MISSION)) == decompose.MAX_NEEDS


def test_needs_without_a_label_are_dropped():
    """An unlabelled need has nothing to show the user and nothing to resolve."""
    rows = decompose._to_need_rows(
        _needs_payload(_need(label="   "), _need(label="a real need")), MISSION
    )
    assert [r["label"] for r in rows] == ["a real need"]


@pytest.mark.parametrize("given,expected", [(1, 1), (2, 2), (0, 1), (7, 1), ("1", 1)])
def test_out_of_range_priority_falls_back_to_essential(given, expected):
    """schemas.Need pins priority to 1..2, so anything else would 500 the route.
    Essential is the safe default: it keeps the need in the plan."""
    rows = decompose._to_need_rows(_needs_payload(_need(priority=given)), MISSION)
    assert rows[0]["priority"] == expected


def test_missing_category_becomes_other():
    rows = decompose._to_need_rows(_needs_payload(_need(category="")), MISSION)
    assert rows[0]["category"] == "other"


# --- provider selection ----------------------------------------------------


def test_no_keys_means_no_provider(with_settings):
    with_settings()
    assert decompose.pick_provider() is None


def test_auto_prefers_xai_when_both_keys_are_set(with_settings):
    with_settings(openai_api_key="sk-o", xai_api_key="sk-x")
    name, url, _model, key = decompose.pick_provider()
    assert (name, key) == ("xai", "sk-x")
    assert "x.ai" in url


def test_auto_falls_through_to_the_key_that_exists(with_settings):
    with_settings(openai_api_key="sk-o")
    name, url, _model, key = decompose.pick_provider()
    assert (name, key) == ("openai", "sk-o")
    assert "openai.com" in url


def test_an_explicit_provider_without_its_key_is_not_silently_swapped(with_settings):
    """Falling back to the other account would spend the wrong credits and hide
    the misconfiguration."""
    with_settings(openai_api_key="sk-o", llm_provider="xai")
    assert decompose.pick_provider() is None


def test_an_unknown_provider_warns_and_behaves_like_auto(with_settings):
    with_settings(openai_api_key="sk-o", llm_provider="anthropic")
    name, _url, _model, _key = decompose.pick_provider()
    assert name == "openai"


def test_llm_model_overrides_the_provider_default(with_settings):
    with_settings(xai_api_key="sk-x", llm_model="grok-9-ultra")
    _name, _url, model, _key = decompose.pick_provider()
    assert model == "grok-9-ultra"


# --- decompose(): the live path and every fallback -------------------------


def test_without_a_key_it_returns_the_seeded_needs(with_settings):
    with_settings()
    rows, source = decompose.decompose("anything", mission_id=MISSION)
    assert source == "fixture"
    assert rows and all("label" in r for r in rows)


def test_a_good_response_is_converted_and_tagged_with_the_provider(
    with_settings, monkeypatch
):
    with_settings(openai_api_key="sk-o")
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response(_needs_payload(_need()))
    )
    rows, source = decompose.decompose("keep the food cold", mission_id=MISSION)
    assert source == "openai"
    assert [r["label"] for r in rows] == ["keep food cold"]


def test_the_request_carries_the_chosen_model_and_timeout(with_settings, monkeypatch):
    with_settings(xai_api_key="sk-x", llm_timeout_s=1.25)
    seen = {}

    def _capture(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return _response(_needs_payload(_need()))

    monkeypatch.setattr(httpx, "post", _capture)
    decompose.decompose("a goal", mission_id=MISSION)

    assert "x.ai" in seen["url"]
    assert seen["json"]["model"] == decompose.PROVIDERS["xai"]["model"]
    assert seen["headers"]["Authorization"] == "Bearer sk-x"
    assert seen["timeout"] == 1.25
    # §6: the schema is what keeps the model from inventing a shape.
    assert seen["json"]["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    "boom",
    [
        httpx.TimeoutException("too slow"),
        httpx.ConnectError("no route"),
    ],
    ids=["timeout", "transport"],
)
def test_transport_failures_fall_back_to_the_fixture(with_settings, monkeypatch, boom):
    """§6: a failure here must degrade the plan, never take down /api/mission."""
    with_settings(openai_api_key="sk-o")

    def _raise(*a, **k):
        raise boom

    monkeypatch.setattr(httpx, "post", _raise)
    rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "fixture"
    assert rows


def test_an_http_error_status_falls_back_to_the_fixture(with_settings, monkeypatch):
    """A 403 from a bad key is the most likely real failure."""
    with_settings(xai_api_key="sk-bad")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            403,
            json={"error": "forbidden"},
            request=httpx.Request("POST", "https://api.x.ai/v1/chat/completions"),
        ),
    )
    _rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "fixture"


def test_content_that_is_not_json_falls_back_to_the_fixture(with_settings, monkeypatch):
    with_settings(openai_api_key="sk-o")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "I'm afraid I can't do that"}}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        ),
    )
    _rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "fixture"


def test_an_unexpected_envelope_falls_back_to_the_fixture(with_settings, monkeypatch):
    with_settings(openai_api_key="sk-o")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200,
            json={"unexpected": "shape"},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        ),
    )
    _rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "fixture"


def test_a_well_formed_but_empty_decomposition_falls_back(with_settings, monkeypatch):
    """A goal decomposed into nothing is not a plan, and an empty needs list
    would render as a blank screen."""
    with_settings(openai_api_key="sk-o")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response({"needs": []}))
    rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "fixture"
    assert rows


# --- grounding the model in the real catalogue -----------------------------


def test_vocabulary_is_drawn_from_the_seeded_listings():
    """A need phrased in a token no listing uses is unmet on a technicality."""
    categories, vocabulary = decompose.catalogue_vocabulary()
    assert "top" in categories and "shelter" in categories
    assert all(isinstance(v, list) for v in vocabulary.values())
    assert any(len(v) for v in vocabulary.values())


def test_the_prompt_carries_the_catalogue_to_the_model(with_settings, monkeypatch):
    with_settings(openai_api_key="sk-o")
    seen = {}

    def _capture(url, **kwargs):
        seen.update(kwargs)
        return _response(_needs_payload(_need()))

    monkeypatch.setattr(httpx, "post", _capture)
    decompose.decompose("a dinner for twelve", mission_id=MISSION)

    user_message = seen["json"]["messages"][1]["content"]
    assert "a dinner for twelve" in user_message
    assert "Known categories:" in user_message
    assert "cookware" in user_message
