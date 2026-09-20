"""The spoken front door. §4 extension.

Nothing here reaches the network: conftest blanks the provider keys, so the
default path is the scripted ladder, and the live tests stub httpx.post.
"""

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.models.schemas import ConverseMessage, ConverseReply
from apps.api.services import converse

USER = "00000000-0000-0000-0000-000000000001"


def turns(*pairs) -> list[ConverseMessage]:
    """turns(("otto","hi"), ("user","a dinner")) -> messages."""
    return [ConverseMessage(role=r, content=c) for r, c in pairs]


# --- budget parsing, server side -------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("My budget is $100.", 10000),          # Deepgram renders speech like this
        ("$0", 0),
        ("$39.90", 3990),
        ("$1,000", 100000),
        ("around $250!", 25000),
        ("business casual for my internship", None),
        ("$10 or $20", None),                    # ambiguous: do not guess
        ("$12,34", None),                        # malformed: do not truncate
        # Said or typed without the symbol. A budget understood only in its
        # "$80" form would make the spoken path quietly worse than the typed one.
        ("80 dollars", 8000),
        ("fifty bucks", 5000),
        ("about eighty dollars", 8000),          # filler must not swallow it
        ("a hundred dollars", 10000),            # the article IS the one
        ("two hundred fifty dollars", 25000),
        ("maybe a thousand dollars", 100000),
        ("zero dollars", 0),
        ("I have twelve people", None),          # a count is not a budget
    ],
)
def test_budget_is_read_from_what_was_said(text, expected):
    assert converse.parse_budget_cents(text) == expected


def test_no_limit_is_unstated_not_zero():
    """A spoken "no limit" becoming $0 would reject every paid option — the
    opposite of what they meant."""
    reply = converse.scripted(turns(("otto", "?"), ("user", "a dinner for twelve"),
                                    ("otto", "budget?"), ("user", "no limit")))
    assert reply.ready is True
    assert reply.budget_cents is None


# --- the scripted ladder ---------------------------------------------------


def test_it_opens_by_asking_what_you_want():
    reply = converse.scripted([])
    assert reply.expects == "text"
    assert reply.ready is False
    assert "?" in reply.say


def test_it_asks_for_a_budget_when_none_was_stated():
    reply = converse.scripted(turns(("otto", "?"), ("user", "a dinner for twelve")))
    assert reply.ready is False
    assert reply.expects == "choice"
    assert reply.choices
    assert any("no limit" in c.lower() for c in reply.choices), (
        "there must be a way to decline, or the only exit is inventing a number"
    )


def test_a_budget_stated_up_front_is_not_asked_for_again():
    """Asking again for something they already said is what makes an assistant
    feel deaf."""
    reply = converse.scripted(
        turns(("otto", "?"), ("user", "business casual for my internship, $100"))
    )
    assert reply.ready is True
    assert reply.budget_cents == 10000
    assert reply.goal_text == "business casual for my internship, $100"


def test_the_budget_answer_completes_the_conversation():
    reply = converse.scripted(turns(("otto", "?"), ("user", "a camping trip"),
                                    ("otto", "budget?"), ("user", "$250")))
    assert reply.ready is True
    assert reply.expects == "none"
    assert reply.budget_cents == 25000
    assert reply.goal_text == "a camping trip"


def test_it_gives_up_asking_after_max_turns():
    """A conversation that will not end is worse than an imperfect plan."""
    said = [("user", f"answer {i}") for i in range(converse.MAX_TURNS)]
    reply = converse.converse(turns(("otto", "?"), *said), user_id=USER)
    assert reply.ready is True


# --- the live path ---------------------------------------------------------


def _reply(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        request=httpx.Request("POST", "https://example.invalid/chat"),
    )


@pytest.fixture()
def with_provider(monkeypatch):
    def _apply(**overrides):
        chosen = converse.decompose.Chosen(
            name="groq", url="https://example.invalid/chat",
            model="test-model", key="k", structured="object",
        )
        monkeypatch.setattr(converse.decompose, "pick_provider", lambda: chosen)
        monkeypatch.setattr(
            converse, "get_settings",
            lambda: SimpleNamespace(llm_timeout_s=4.0,
                                    llm_dialogue_model=overrides.get("dialogue_model")),
        )
    return _apply


def test_a_live_turn_is_used_and_labelled(with_provider, monkeypatch):
    with_provider()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _reply(
        {"say": "How many people?", "expects": "choice",
         "choices": ["2", "6", "12"], "ready": False}))
    reply = converse.converse(turns(("otto", "?"), ("user", "a dinner")), user_id=USER)
    assert reply.source == "live"
    assert reply.say == "How many people?"
    assert reply.choices == ["2", "6", "12"]


def test_the_dialogue_model_overrides_the_provider_default(with_provider, monkeypatch):
    """Conversation needs a fast model; the decomposition model takes 6-9s."""
    with_provider(dialogue_model="tiny-fast")
    seen = {}
    monkeypatch.setattr(httpx, "post", lambda url, **k: (seen.update(k), _reply(
        {"say": "ok?", "expects": "text", "ready": False}))[1])
    converse.converse(turns(("otto", "?"), ("user", "a dinner")), user_id=USER)
    assert seen["json"]["model"] == "tiny-fast"


def test_a_model_budget_is_ignored_in_favour_of_what_was_said(with_provider, monkeypatch):
    """The model proposes; the person decides. A hallucinated figure must never
    become a spending limit."""
    with_provider()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _reply(
        {"say": "Got it.", "expects": "none", "ready": True,
         "goal_text": "a dinner for twelve", "budget_cents": 999999}))
    reply = converse.converse(
        turns(("otto", "?"), ("user", "a dinner for twelve, $80")), user_id=USER
    )
    assert reply.ready is True
    assert reply.budget_cents == 8000, "the model's number must not win"


def test_choices_without_a_choice_expectation_are_reconciled(with_provider, monkeypatch):
    with_provider()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _reply(
        {"say": "Indoors or out?", "expects": "choice", "choices": [], "ready": False}))
    reply = converse.converse(turns(("otto", "?"), ("user", "a party")), user_id=USER)
    assert reply.expects == "text", "a choice turn with no choices is a dead end"


@pytest.mark.parametrize(
    "bad",
    [
        lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("slow")),
        lambda *a, **k: httpx.Response(429, json={"error": "quota"},
                                       request=httpx.Request("POST", "https://x/chat")),
        lambda *a, **k: httpx.Response(200, json={"choices": [{"message": {"content": "sorry!"}}]},
                                       request=httpx.Request("POST", "https://x/chat")),
        lambda *a, **k: _reply({"say": "", "expects": "text"}),
    ],
    ids=["timeout", "quota-exhausted", "not-json", "empty-say"],
)
def test_live_failures_fall_back_to_the_script(with_provider, monkeypatch, bad):
    """Free tiers run out mid-rehearsal. Degrading to fixed questions is barely
    noticeable; erroring mid-demo is fatal."""
    with_provider()
    monkeypatch.setattr(httpx, "post", bad)
    reply = converse.converse(turns(("otto", "?"), ("user", "a dinner")), user_id=USER)
    assert reply.source == "fixture"
    assert reply.say


# --- the route -------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "off")
    return TestClient(app)


def test_route_opens_the_conversation(client):
    r = client.post("/api/converse", json={"user_id": USER, "messages": []})
    assert r.status_code == 200
    body = ConverseReply.model_validate(r.json())
    assert body.ready is False
    assert body.say


def test_route_reaches_ready_with_a_goal_and_budget(client):
    r = client.post("/api/converse", json={"user_id": USER, "messages": [
        {"role": "otto", "content": "What are you trying to accomplish?"},
        {"role": "user", "content": "business casual for my internship. My budget is $100."},
    ]})
    body = ConverseReply.model_validate(r.json())
    assert body.ready is True
    assert body.budget_cents == 10000


def test_demo_mode_replays_a_ready_turn(monkeypatch):
    """The fixture cannot advance a conversation, so it must not start one."""
    monkeypatch.setenv("DEMO_MODE", "on")
    r = TestClient(app).post("/api/converse", json={"user_id": USER, "messages": []})
    assert r.status_code == 200
    body = ConverseReply.model_validate(r.json())
    assert body.ready is True
    assert body.source == "fixture"
