import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print(".env already exists; left unchanged.")
else:
    text = (
        (root / ".env.example")
        .read_text()
        .replace("SECRET_KEY=replace-with-random-value", "SECRET_KEY=" + secrets.token_urlsafe(48))
        .replace(
            "DB_PASSWORD=replace-with-random-value", "DB_PASSWORD=" + secrets.token_urlsafe(32)
        )
    )
    path.write_text(text)
    path.chmod(0o600)
    print("Created .env with random secrets. Keep it private.")
