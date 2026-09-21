"""Generate local secrets. Does not overwrite an existing .env."""

from pathlib import Path
import secrets, base64, os

root = Path(__file__).resolve().parent.parent
path = root / ".env"
if path.exists():
    raise SystemExit(".env already exists; no files changed.")
text = (root / ".env.example").read_text()
password = secrets.token_urlsafe(32)
values = {
    "ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "BOT_INTERNAL_SECRET": secrets.token_urlsafe(48),
    "TELEGRAM_WEBHOOK_SECRET": secrets.token_urlsafe(32),
    "POSTGRES_PASSWORD": password,
}
for key, value in values.items():
    text = text.replace(key + "=\n", key + "=" + value + "\n")
text = text.replace("CHANGE_ME", password)
fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as file:
    file.write(text)
print("Created .env with generated secrets (values not printed).")
