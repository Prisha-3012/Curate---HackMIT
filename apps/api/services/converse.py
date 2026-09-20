"""The spoken front door. goal + budget, gathered by talking. §4 extension.

/api/mission needs a goal and (optionally) a budget. This gets them by
conversation instead of a text box, so the whole thing can be done by voice.

TWO IMPLEMENTATIONS, and the second is not a consolation prize:

  live    — a model picks what to ask, so it can follow whatever the person
            actually said. Dialogue runs on a SMALL model: measured, a lite
            model answers a conversational turn in ~0.5s where the
            decomposition model takes 6-9s, and an 8-second silence between
            turns is not a conversation.
  scripted — a fixed ladder: what are you trying to do, then what's your
            budget, then go. Instant, deterministic, no quota.

The scripted path is the fallback for every live failure, INCLUDING running out
of daily quota, which free tiers do in the middle of rehearsal. It is also what
DEMO_MODE replays. A conversation that degrades to fixed questions is barely
noticeable; one that errors mid-demo is fatal.

The model is never trusted to produce the goal text. It proposes, and
`_settle` re-derives budget_cents from what the PERSON said, so a hallucinated
number cannot become a spending limit.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import httpx

from apps.api.config import get_settings
from apps.api.models.schemas import ConverseMessage, ConverseReply
from apps.api.services import decompose

log = logging.getLogger(__name__)

OPENING = "Hi, I'm Otto. What are you trying to accomplish?"
BUDGET_QUESTION = "Got it. Roughly what would you like to spend?"
BUDGET_CHOICES = ["$50", "$100", "$250", "No limit"]
CONFIRMATION = "Let me see what you already have."

#: Answers to the budget question that mean "no budget", not "zero".
NO_LIMIT = {"no limit", "no budget", "whatever", "doesn't matter", "dont matter",
            "no cap", "unlimited", "not sure", "no idea"}

MAX_TURNS = 6

SYSTEM_PROMPT = """You are Otto. You are gathering exactly two things from \
someone so a planner can help them: WHAT they are trying to accomplish, and \
HOW MUCH they want to spend.

You are not the planner. Never suggest products, brands, shops or what they
should buy — something else does that, and it prefers things they already own
or can borrow. Suggesting purchases here removes that choice.

Rules:
- ONE question at a time, at most 20 words. Warm, not chatty.
- Ask at most {max_turns} questions in total. Fewer is better.
- Stop as soon as you know what they want to do. A budget is NICE TO HAVE, not
  required: if they decline, say nothing more about it and finish.
- When finished, set ready=true and put their goal in goal_text as a single
  sentence in their own words.
- offer 2-4 short choices whenever the answer is naturally a small set. Always
  include a way to decline.
"""

SHAPE = """
Reply with ONLY this JSON object:

{{"say": "...", "expects": "text" | "choice" | "none",
  "choices": ["...", "..."], "ready": true | false,
  "goal_text": "..." | null}}

`say` is spoken aloud, so write it to be heard, not read: no markdown, no lists,
no emoji. `choices` is [] unless expects is "choice". `goal_text` is null until
ready is true. Never include a budget figure in goal_text.
"""

#: Mirrors the frontend parser. The trailing guard rejects a truncated number
#: ("$12,34") but must NOT reject a sentence-ending period — "my budget is $100."
#: is how people talk, and Deepgram's smart formatting renders spoken amounts
#: this way, so this is the normal case rather than an edge one.
_MONEY = re.compile(r"\$\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?!\d)(?![.,]\d)")


#: "80 dollars", "80 bucks" — no symbol, which is how people type and how a
#: transcript reads when smart formatting does not fire.
_PLAIN = re.compile(
    r"\b(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(?:dollars?|bucks?|usd)\b",
    re.I,
)

#: Spoken amounts, for the same reason. Deliberately small: budgets people say
#: out loud are round, and a table big enough for "four hundred and seventeen"
#: would be more parser than this needs.
_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
#: Built from the vocabulary rather than "any few words", so filler cannot get
#: swallowed: "about eighty dollars" must read 80, not fail on "about".
_NUMBER_WORD = "|".join(
    sorted(set(_ONES) | set(_TENS) | {"hundred", "thousand", "and", "a", "an"},
           key=len, reverse=True)
)
_WORDS = re.compile(
    rf"\b((?:{_NUMBER_WORD})(?:[\s-]+(?:{_NUMBER_WORD}))*)\s+(?:dollars?|bucks?)\b",
    re.I,
)


def _words_to_number(phrase: str) -> Optional[int]:
    """"eighty" -> 80, "two hundred fifty" -> 250. None if not a number."""
    total, current, seen = 0, 0, False
    for token in re.split(r"[\s-]+", phrase.strip().lower()):
        if token in ("and", ""):
            continue
        if token in ("a", "an"):
            # "a hundred dollars" — the article IS the one.
            current = current or 1
            seen = True
            continue
        if token in _ONES:
            current += _ONES[token]; seen = True
        elif token in _TENS:
            current += _TENS[token]; seen = True
        elif token == "hundred":
            current = (current or 1) * 100; seen = True
        elif token == "thousand":
            total += (current or 1) * 1000; current = 0; seen = True
        else:
            return None
    return total + current if seen else None


def parse_budget_cents(text: str) -> Optional[int]:
    """Cents, or None when no explicit amount was stated.

    None is "unstated", never zero — §4 draws that distinction and a spoken
    "no limit" must not become a $0 budget that rejects every paid option.

    Three spellings are accepted because all three really occur: "$80" (typed,
    and what Deepgram's smart formatting produces), "80 dollars" (typed, or a
    transcript where it did not), and "eighty dollars" (spoken plainly). An
    amount understood only in its symbol form would make the spoken path
    quietly worse than the typed one.
    """
    body = text or ""

    found = _MONEY.findall(body)
    if len(found) > 1:
        return None  # several figures and no way to know which is the budget
    if len(found) == 1:
        try:
            return round(float(found[0].replace(",", "")) * 100)
        except ValueError:
            return None

    plain = _PLAIN.findall(body)
    if len(plain) == 1:
        whole, frac = plain[0]
        try:
            return round(float(f"{whole.replace(',', '')}.{frac or '0'}") * 100)
        except ValueError:
            return None
    if len(plain) > 1:
        return None

    spoken = [n for n in (_words_to_number(m) for m in _WORDS.findall(body))
              if n is not None]
    if len(spoken) == 1:
        return spoken[0] * 100
    return None


def _said_no_limit(text: str) -> bool:
    low = (text or "").strip().lower().rstrip(".!?")
    return low in NO_LIMIT or "no limit" in low or "no budget" in low


def _user_turns(messages: list[ConverseMessage]) -> list[str]:
    return [m.content for m in messages if m.role == "user"]


# --------------------------------------------------------------------------
# scripted: the fallback, and DEMO_MODE's replay
# --------------------------------------------------------------------------


def scripted(messages: list[ConverseMessage]) -> ConverseReply:
    """Goal, then budget, then go. Never asks anything it cannot act on."""
    said = _user_turns(messages)

    if not said:
        return ConverseReply(say=OPENING, expects="text", source="fixture")

    goal = said[0].strip()
    budget = parse_budget_cents(goal)

    # They already named a figure while stating the goal, so asking again would
    # be the kind of thing that makes an assistant feel deaf.
    if budget is not None:
        return _settle(goal, budget, messages, source="fixture")

    if len(said) == 1:
        return ConverseReply(
            say=BUDGET_QUESTION,
            expects="choice",
            choices=BUDGET_CHOICES,
            source="fixture",
        )

    answer = said[1]
    budget = None if _said_no_limit(answer) else parse_budget_cents(answer)
    return _settle(goal, budget, messages, source="fixture")


def _settle(
    goal: str,
    budget_cents: Optional[int],
    messages: list[ConverseMessage],
    *,
    source: str,
) -> ConverseReply:
    """Finish the conversation. Budget is re-derived from what the PERSON said,
    across every turn, so a model's guess can never become a spending limit."""
    if budget_cents is None:
        for said in _user_turns(messages):
            if _said_no_limit(said):
                budget_cents = None
                break
            found = parse_budget_cents(said)
            if found is not None:
                budget_cents = found
                break
    return ConverseReply(
        say=CONFIRMATION,
        expects="none",
        ready=True,
        goal_text=goal.strip(),
        budget_cents=budget_cents,
        source=source,
    )


# --------------------------------------------------------------------------
# live
# --------------------------------------------------------------------------


def _dialogue_model(chosen: decompose.Chosen) -> str:
    """A small, fast model for turn-taking.

    The decomposition model is chosen for reasoning quality over a large schema
    and takes 6-9s. Conversation needs latency, not depth.
    """
    s = get_settings()
    return s.llm_dialogue_model or chosen.model


def converse(messages: list[ConverseMessage], *, user_id: str = "") -> ConverseReply:
    """Otto's next turn. Never raises; falls back to the scripted ladder."""
    if len(_user_turns(messages)) >= MAX_TURNS:
        # Refuse to keep asking. Whatever we have is what we plan with.
        said = _user_turns(messages)
        return _settle(said[0], None, messages, source="fixture")

    chosen = decompose.pick_provider()
    if chosen is None:
        return scripted(messages)

    s = get_settings()
    wire = [{"role": "system", "content": SYSTEM_PROMPT.format(max_turns=MAX_TURNS) + SHAPE}]
    wire += [
        {"role": "assistant" if m.role == "otto" else "user", "content": m.content}
        for m in messages
    ]
    if not messages:
        wire.append({"role": "user", "content": "(they just opened the app; greet them)"})

    try:
        r = httpx.post(
            chosen.url,
            headers={"Authorization": f"Bearer {chosen.key}"},
            json={
                "model": _dialogue_model(chosen),
                "messages": wire,
                "response_format": {"type": "json_object"},
                "temperature": 0.5,
                # 800, not 200. Reasoning models spend the budget on a
                # `reasoning` field BEFORE emitting content, so a tight cap
                # truncates the JSON and the provider rejects its own output
                # with `json_validate_failed` — a 400, not a 200 with bad
                # content. Measured on groq/gpt-oss-120b: 1/5 calls succeeded
                # at 200 tokens, 5/5 at 800. A turn is two sentences, so this
                # headroom costs nothing on a model that does not reason.
                "max_tokens": 800,
            },
            timeout=s.llm_timeout_s,
        )
        r.raise_for_status()
        payload = json.loads(r.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        # Quota exhaustion lands here too, which on a free tier is a question of
        # when rather than whether.
        log.warning("converse via %s failed (%s); using the scripted ladder", chosen.name, exc)
        return scripted(messages)

    reply = _from_payload(payload, messages)
    if reply is None:
        log.warning("%s returned an unusable turn; using the scripted ladder", chosen.name)
        return scripted(messages)
    return reply


def _from_payload(
    payload: Any, messages: list[ConverseMessage]
) -> Optional[ConverseReply]:
    """Model output -> a turn, treating every field as untrusted."""
    if not isinstance(payload, dict):
        return None
    say = str(payload.get("say") or "").strip()
    if not say:
        return None

    said = _user_turns(messages)
    if bool(payload.get("ready")) and said:
        goal = str(payload.get("goal_text") or "").strip() or said[0]
        # Budget comes from the person, never from the model.
        return _settle(goal, None, messages, source="live")

    expects = payload.get("expects")
    raw_choices = payload.get("choices")
    choices = [
        str(c).strip()
        for c in (raw_choices if isinstance(raw_choices, list) else [])
        if str(c).strip()
    ][:6]
    if expects not in ("text", "choice", "none"):
        expects = "choice" if choices else "text"
    if expects == "choice" and not choices:
        expects = "text"
    if expects != "choice":
        choices = []

    return ConverseReply(
        say=say, expects=expects, choices=choices, ready=False, source="live"
    )
