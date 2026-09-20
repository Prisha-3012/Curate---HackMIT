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
        "gemini_api_key": None,
        "groq_api_key": None,
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


def test_auto_prefers_groq_then_gemini_then_xai_then_openai(with_settings):
    """The usable free tiers first. Groq ahead of Gemini because Gemini's free
    tier is 20 requests per day per model — a limit you hit in rehearsal."""
    with_settings(openai_api_key="sk-o", xai_api_key="sk-x",
                  gemini_api_key="sk-g", groq_api_key="sk-q")
    assert decompose.pick_provider().name == "groq"

    with_settings(openai_api_key="sk-o", xai_api_key="sk-x", gemini_api_key="sk-g")
    assert decompose.pick_provider().name == "gemini"

    with_settings(openai_api_key="sk-o", xai_api_key="sk-x")
    chosen = decompose.pick_provider()
    assert (chosen.name, chosen.key) == ("xai", "sk-x")
    assert "x.ai" in chosen.url


def test_auto_falls_through_to_the_key_that_exists(with_settings):
    with_settings(openai_api_key="sk-o")
    chosen = decompose.pick_provider()
    assert (chosen.name, chosen.key) == ("openai", "sk-o")
    assert "openai.com" in chosen.url


def test_an_explicit_provider_without_its_key_is_not_silently_swapped(with_settings):
    """Falling back to the other account would spend the wrong credits and hide
    the misconfiguration."""
    with_settings(openai_api_key="sk-o", llm_provider="xai")
    assert decompose.pick_provider() is None


def test_an_unknown_provider_warns_and_behaves_like_auto(with_settings):
    with_settings(openai_api_key="sk-o", llm_provider="anthropic")
    assert decompose.pick_provider().name == "openai"


def test_llm_model_overrides_the_provider_default(with_settings):
    with_settings(xai_api_key="sk-x", llm_model="grok-9-ultra")
    assert decompose.pick_provider().model == "grok-9-ultra"


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


# --- providers that cannot enforce a schema --------------------------------


def test_gemini_asks_for_json_object_not_a_strict_schema(with_settings, monkeypatch):
    """strict:true is an OpenAI feature. Compat layers accept the field and
    ignore the enforcement, so output degrades to prose and the fixture
    fallback hides it. Ask for what the endpoint can actually honour."""
    with_settings(gemini_api_key="sk-g")
    seen = {}

    def _capture(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return _response(_needs_payload(_need()))

    monkeypatch.setattr(httpx, "post", _capture)
    _rows, source = decompose.decompose("a dinner for twelve", mission_id=MISSION)

    assert source == "gemini"
    assert "generativelanguage.googleapis.com" in seen["url"]
    assert seen["json"]["response_format"] == {"type": "json_object"}
    # json_object guarantees parseable JSON but NOT the shape, so the shape has
    # to be spelled out in words instead.
    assert "needs" in seen["json"]["messages"][1]["content"]
    assert "priority" in seen["json"]["messages"][1]["content"]


def test_strict_providers_still_send_the_schema(with_settings, monkeypatch):
    with_settings(openai_api_key="sk-o")
    seen = {}
    monkeypatch.setattr(
        httpx, "post",
        lambda url, **kw: (seen.update(kw), _response(_needs_payload(_need())))[1],
    )
    decompose.decompose("a goal", mission_id=MISSION)
    fmt = seen["json"]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True


def test_attrs_as_a_plain_object_are_kept(with_settings, monkeypatch):
    """A non-strict provider returns {"waterproof": true}, not a key/value
    array. Dropping it would resolve every need on category alone."""
    with_settings(gemini_api_key="sk-g")
    payload = _needs_payload(
        _need(attrs={"waterproof": True, "serves": 12, "warmth": "cold"})
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(payload))
    rows, _source = decompose.decompose("a goal", mission_id=MISSION)
    assert rows[0]["attrs"] == {"waterproof": True, "serves": 12, "warmth": "cold"}


def test_a_bare_list_of_needs_is_accepted(with_settings, monkeypatch):
    """Without schema enforcement the envelope is a coin flip. Throwing away a
    good decomposition over its wrapper would be a silent downgrade."""
    with_settings(gemini_api_key="sk-g")
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response([_need(label="keep food cold")])
    )
    rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "gemini"
    assert [r["label"] for r in rows] == ["keep food cold"]


def test_needs_under_an_unexpected_key_are_still_found(with_settings, monkeypatch):
    with_settings(gemini_api_key="sk-g")
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response({"decomposition": [_need()]})
    )
    rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert source == "gemini"
    assert len(rows) == 1


def test_non_dict_entries_in_the_list_are_skipped(with_settings, monkeypatch):
    """Nothing validates the items, so a stray string must not crash the route."""
    with_settings(gemini_api_key="sk-g")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _response({"needs": ["just a string", _need(), 42]}),
    )
    rows, _source = decompose.decompose("a goal", mission_id=MISSION)
    assert len(rows) == 1


def test_a_5xx_is_retried_once(with_settings, monkeypatch):
    """Gemini load-sheds with 503s. Without a retry a goal randomly comes back
    in the seeded wardrobe needs, which reads as a broken decomposer."""
    with_settings(gemini_api_key="sk-g")
    calls = []

    def _flaky(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return httpx.Response(
                503, json={"error": "overloaded"},
                request=httpx.Request("POST", url),
            )
        return _response(_needs_payload(_need()))

    monkeypatch.setattr(httpx, "post", _flaky)
    rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert len(calls) == 2, "the 503 should have been retried"
    assert source == "gemini"
    assert rows


def test_a_4xx_is_not_retried(with_settings, monkeypatch):
    """A bad key or a dead model id will not fix itself, and retrying only
    doubles the wait before the fixture fallback."""
    with_settings(gemini_api_key="sk-g")
    calls = []

    def _denied(url, **kwargs):
        calls.append(url)
        return httpx.Response(403, json={"error": "nope"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _denied)
    _rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert len(calls) == 1, "a 4xx must not be retried"
    assert source == "fixture"


def test_a_persistent_5xx_gives_up_after_one_retry(with_settings, monkeypatch):
    with_settings(gemini_api_key="sk-g")
    calls = []

    def _down(url, **kwargs):
        calls.append(url)
        return httpx.Response(503, json={"error": "still down"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _down)
    _rows, source = decompose.decompose("a goal", mission_id=MISSION)
    assert len(calls) == 2
    assert source == "fixture"


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_functional_guidance_and_explicit_constraints_survive(provider, with_settings, monkeypatch):
    with_settings(**{f"{provider}_api_key": "test-key"})
    attrs = {"style": "boots", "color": "red", "material": "leather",
             "waterproof": True, "warmth": "cold", "quantity": 2}
    seen = {}
    def capture(url, **kwargs):
        seen.update(kwargs)
        return _response(_needs_payload(_need(attrs=attrs)))
    monkeypatch.setattr(httpx, "post", capture)
    rows, _ = decompose.decompose(
        "I explicitly want two red leather boots for cold, wet weather.", mission_id=MISSION)
    assert rows[0]["attrs"] == attrs
    system = seen["json"]["messages"][0]["content"]
    assert "explicit user preferences/constraints or functionally necessary" in system
    assert "not a checklist" in system
    assert "sneaker=false" in system
    assert "labels and rationales" in system
    if provider == "openai":
        guidance = seen["json"]["response_format"]["json_schema"]["schema"]["properties"]["needs"]["items"]["properties"]["attrs"]["description"]
    else:
        guidance = seen["json"]["messages"][1]["content"]
    assert "never invent" in guidance or "Do not invent" in guidance


def test_functional_internship_rows_reach_planner_unchanged(with_settings, monkeypatch):
    from apps.api.services import planner, wardrobe
    with_settings(gemini_api_key="test-key")
    expected = [
        {"formality": "business-casual", "quantity": 3},
        {"formality": "business-casual", "quantity": 3},
        {"formality": "business-casual"},
    ]
    payload = _needs_payload(*[
        _need(label=category, category=category, attrs=attrs)
        for category, attrs in zip(["top", "bottom", "footwear"], expected)
    ])
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _response(payload))
    monkeypatch.setattr(planner.products, "fetch_products", lambda *a: [])
    monkeypatch.setattr(wardrobe, "get_wardrobe", lambda user: [])
    seen = []
    def capture(row, *args, **kwargs):
        seen.append(row["attrs"])
        return [], None, "No candidates"
    monkeypatch.setattr(planner.resolver, "resolve_need", capture)
    planner.build_plan(
        "I start my first internship next week. I need enough business-casual clothes "
        "for three days in-office. I have $100.", user_id="test", budget_cents=10000)
    assert seen == expected
