"""Explicit operator command. Reads environment; never prints the bot token."""

import os, json, urllib.request

url = "https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"] + "/setWebhook"
body = json.dumps(
    {
        "url": os.environ["APP_URL"] + "/telegram/webhook",
        "secret_token": os.environ["TELEGRAM_WEBHOOK_SECRET"],
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False,
    }
).encode()
try:
    with urllib.request.urlopen(
        urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        ),
        timeout=20,
    ) as r:
        result = json.load(r)
    print(
        "Webhook configured."
        if result.get("ok")
        else "Telegram rejected webhook configuration."
    )
except Exception:
    raise SystemExit(
        "Webhook configuration failed. Check credentials and HTTPS without exposing the token."
    )
