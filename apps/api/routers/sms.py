"""
Linq SMS channel (not Twilio).

Local run:
  cd apps/api && uvicorn main:app --reload --port 8000
  ngrok http 8000
  curl POST https://api.linqapp.com/api/partner/v3/webhook-subscriptions
    JSON: target_url https://<ngrok>/linq-webhook?version=2026-02-03
          subscribed_events including message.received
  Copy signing_secret -> LINQ_WEBHOOK_SECRET and restart uvicorn.
  Teammates must text the Linq number once so the chat exists.

B contract: run_agent(user_id, message) and notify_borrow_match(owner_phone, borrower_name, item_title).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any
from urllib.parse import quote

import requests
from fastapi import APIRouter, Request, Response

from services.agent import get_or_create_user_by_phone, run_agent

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

LINQ_API_BASE = "https://api.linqapp.com/api/partner/v3"
LINQ_MESSAGES_URL = f"{LINQ_API_BASE}/messages"
MAX_SMS_CHARS = 300
WEBHOOK_MAX_AGE_SECONDS = 5 * 60


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ.get('LINQ_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _linq_session() -> requests.Session:
    # Ignore HTTP(S)_PROXY so send_text can reach api.linqapp.com from this host.
    session = requests.Session()
    session.trust_env = False
    return session


def _clip_text(body: str) -> str:
    text = (body or "").replace("\r", " ").strip()
    if len(text) > MAX_SMS_CHARS:
        text = text[: MAX_SMS_CHARS - 1].rstrip() + "…"
    return text


def send_text(to: str, body: str, chat_id: str | None = None) -> None:
    """Send via existing chat when we have chat_id; else POST /v3/messages with to, no from."""
    text = _clip_text(body)
    parts = [{"type": "text", "value": text}]
    from_line = (os.environ.get("LINQ_FROM_NUMBER") or "").strip()

    try:
        if chat_id:
            url = f"{LINQ_API_BASE}/chats/{quote(chat_id, safe='')}/messages"
            payload: dict[str, Any] = {"parts": parts}
            resp = _linq_session().post(url, headers=_auth_headers(), json=payload, timeout=15)
            logger.info("Linq send_text via=chats status=%s", resp.status_code)
            if resp.status_code < 400:
                return
            logger.error("Linq send_text chats failed status=%s body=%s", resp.status_code, resp.text)

        url = LINQ_MESSAGES_URL
        payload = {"to": [to], "message": {"parts": parts}}
        if from_line:
            payload["from"] = from_line
        resp = _linq_session().post(url, headers=_auth_headers(), json=payload, timeout=15)
        logger.info(
            "Linq send_text via=messages status=%s used_from=%s",
            resp.status_code,
            bool(from_line),
        )
        if resp.status_code >= 400:
            logger.error("Linq send_text messages failed status=%s body=%s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Linq send_text request error")


def _signing_key(secret: str) -> bytes | None:
    raw = secret.strip().strip('"').strip("'")
    if raw.startswith("whsec_"):
        raw = raw[len("whsec_") :]
    if not raw:
        return None
    pad = (4 - len(raw) % 4) % 4
    try:
        return base64.b64decode(raw + ("=" * pad))
    except Exception:
        try:
            return base64.urlsafe_b64decode(raw + ("=" * pad))
        except Exception:
            logger.error("Linq webhook secret decode failed")
            return None


def verify_webhook(secret: str, body: bytes | str, headers: dict[str, str]) -> bool:
    """Linq Standard Webhooks (webhook-id, webhook-timestamp, webhook-signature)."""
    if not secret:
        logger.error("LINQ_WEBHOOK_SECRET missing")
        return False

    lower = {str(k).lower(): str(v) for k, v in headers.items()}
    msg_id = lower.get("webhook-id") or lower.get("svix-id") or ""
    timestamp = lower.get("webhook-timestamp") or lower.get("svix-timestamp") or ""
    signature_header = lower.get("webhook-signature") or lower.get("svix-signature") or ""
    if not msg_id or not timestamp or not signature_header:
        logger.error("Linq webhook missing signature headers")
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > WEBHOOK_MAX_AGE_SECONDS:
        logger.error("Linq webhook timestamp too old")
        return False

    key = _signing_key(secret)
    if key is None:
        return False

    if isinstance(body, bytes):
        body_bytes = body
    else:
        body_bytes = body.encode("utf-8")

    signed_content = f"{msg_id}.{timestamp}.".encode("utf-8") + body_bytes
    digest = hmac.new(key, signed_content, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")

    for part in signature_header.split(" "):
        part = part.strip()
        if not part:
            continue
        sig = ""
        if part.startswith("v1,"):
            sig = part[3:]
        elif part.startswith("v1="):
            sig = part[3:]
        else:
            version, _, maybe = part.partition(",")
            if version == "v1":
                sig = maybe
        if sig and hmac.compare_digest(sig, expected):
            return True

    logger.error("Linq webhook signature mismatch")
    return False


def format_plan_sms(plan: dict[str, Any] | None) -> str:
    plan = plan or {}
    bits: list[str] = []
    goal = (plan.get("goal_text") or "").strip()
    if goal:
        bits.append(goal)

    rec_ids = set()
    for need in plan.get("needs") or []:
        rid = need.get("recommended_listing_id")
        if rid:
            rec_ids.add(rid)
        for opt in need.get("options") or []:
            title = (opt.get("title") or "option").strip()
            rung = (opt.get("rung") or "").strip()
            price = opt.get("price")
            rec = " *" if opt.get("listing_id") in rec_ids else ""
            if isinstance(price, (int, float)) and price:
                dollars = f"${price / 100:.2f}" if price >= 100 else f"{price}c"
                bits.append(f"{rung}: {title} {dollars}{rec}".strip())
            else:
                bits.append(f"{rung}: {title}{rec}".strip())

    saved = (plan.get("impact") or {}).get("saved_cents")
    if isinstance(saved, (int, float)):
        bits.append(f"Est. saved ${saved / 100:.2f}")

    text = " | ".join(b for b in bits if b) or "Got it. Working on a plan."
    if len(text) > MAX_SMS_CHARS:
        text = text[: MAX_SMS_CHARS - 1].rstrip() + "…"
    return text


def notify_borrow_match(owner_phone: str, borrower_name: str, item_title: str) -> None:
    name = (borrower_name or "Someone").strip()
    item = (item_title or "your item").strip()
    send_text(
        owner_phone,
        f"{name} wants to borrow {item}. Reply yes if that works.",
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _event_type(payload: dict[str, Any]) -> str:
    for src in (payload, payload.get("data"), payload.get("event")):
        src = _as_dict(src)
        t = src.get("event_type") or src.get("type")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return ""


def _handle_value(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("handle", "phone", "number", "e164"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def _is_me_handle(value: Any) -> bool:
    return isinstance(value, dict) and value.get("is_me") is True


def _inbound_sender(data: dict[str, Any], payload: dict[str, Any]) -> str:
    """2026-02-03: data.sender_handle.handle. 2025-01-01: data.from / from_handle.handle."""
    sender = data.get("sender_handle")
    if sender is not None and not _is_me_handle(sender):
        phone = _handle_value(sender)
        if phone:
            return phone

    from_handle = data.get("from_handle")
    if from_handle is not None and not _is_me_handle(from_handle):
        phone = _handle_value(from_handle)
        if phone:
            return phone

    phone = _handle_value(data.get("from"))
    if phone:
        return phone

    blob = data.get("message") if isinstance(data.get("message"), dict) else {}
    for src in (blob, payload):
        if not isinstance(src, dict):
            continue
        for key in ("sender_handle", "from_handle", "from", "from_number"):
            val = src.get(key)
            if _is_me_handle(val):
                continue
            phone = _handle_value(val)
            if phone:
                return phone
    return ""


def _text_from_parts(blob: dict[str, Any]) -> str:
    parts = blob.get("parts")
    if not isinstance(parts, list):
        msg = blob.get("message")
        if isinstance(msg, dict):
            parts = msg.get("parts")
        elif isinstance(msg, str):
            return msg
    chunks: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, str):
                chunks.append(part)
                continue
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype in ("media", "link", "imessage_app", "experience"):
                continue
            if ptype in (None, "text") or "value" in part or "text" in part:
                val = part.get("value") or part.get("text") or ""
                if isinstance(val, str):
                    chunks.append(val)
    if chunks:
        return " ".join(c.strip() for c in chunks if c.strip())
    for key in ("text", "body", "content"):
        val = blob.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _chat_id(data: dict[str, Any]) -> str:
    chat = data.get("chat")
    if isinstance(chat, dict):
        cid = chat.get("id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
    cid = data.get("chat_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()
    return ""


def _is_inbound(data: dict[str, Any]) -> bool:
    direction = data.get("direction")
    if isinstance(direction, str) and direction.strip().lower() == "outbound":
        return False
    if data.get("is_from_me") is True:
        return False
    if _is_me_handle(data.get("sender_handle")) or _is_me_handle(data.get("from_handle")):
        return False
    return True


@router.post("/linq-webhook")
async def linq_webhook(request: Request) -> Response:
    raw = await request.body()
    secret = os.environ.get("LINQ_WEBHOOK_SECRET", "")
    if not verify_webhook(secret, raw, dict(request.headers)):
        return Response(status_code=401)

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        logger.info("Linq webhook ignored: invalid json")
        return Response(status_code=200)

    if not isinstance(payload, dict):
        return Response(status_code=200)

    event_type = _event_type(payload)
    webhook_version = payload.get("webhook_version") or request.query_params.get("version") or ""
    data = _as_dict(payload.get("data"))
    from_number = _inbound_sender(data, payload)
    message = _text_from_parts(data) or _text_from_parts(_as_dict(data.get("message")))
    chat_id = _chat_id(data)
    inbound = _is_inbound(data)

    logger.info(
        "Linq webhook event_type=%s webhook_version=%s inbound=%s from_ok=%s text_ok=%s chat_id_ok=%s",
        event_type or "missing",
        webhook_version or "missing",
        inbound,
        bool(from_number),
        bool(message),
        bool(chat_id),
    )

    if event_type != "message.received":
        return Response(status_code=200)
    if not inbound:
        logger.info("Linq webhook skip: not inbound")
        return Response(status_code=200)
    if not from_number:
        logger.error("Linq webhook message.received missing from")
        return Response(status_code=200)

    try:
        user_id = get_or_create_user_by_phone(from_number)
        plan = run_agent(user_id, message)
        send_text(from_number, format_plan_sms(plan), chat_id=chat_id or None)
    except Exception:
        logger.exception("Linq webhook reply failed")
    return Response(status_code=200)
