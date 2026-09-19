# ENOUGH---HackMIT

SMS-only Linq channel (not Twilio). No web app in this branch.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill LINQ_API_KEY and LINQ_WEBHOOK_SECRET; do not commit .env
cd apps/api
uvicorn main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

## Linq webhook (ngrok)

```bash
ngrok http 8000
```

Subscribe (use your ngrok URL):

```bash
curl -X POST https://api.linqapp.com/api/partner/v3/webhook-subscriptions \
  -H "Authorization: Bearer $LINQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://<ngrok>/linq-webhook?version=2026-02-03",
    "subscribed_events": ["message.received"]
  }'
```

Copy `signing_secret` into `LINQ_WEBHOOK_SECRET` and restart uvicorn.

Teammates must text the Linq number once so the chat exists before outbound `send_text` works.

## B contract

- `run_agent(user_id, message)` — plan for an inbound SMS
- `notify_borrow_match(owner_phone, borrower_name, item_title)` — SMS the owner
