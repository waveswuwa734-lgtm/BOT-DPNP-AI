import os
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env file for development while still allowing Railway
# environment variables to take precedence in production.
load_dotenv(Path(__file__).with_name(".env"))

TOKEN_ENV_NAMES = (
    "TOKEN",
    "DISCORD_TOKEN",
    "BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
)


def _read_token():
    for env_name in TOKEN_ENV_NAMES:
        value = os.getenv(env_name)
        if value:
            cleaned_value = value.strip().strip("\"'")
            if cleaned_value:
                return cleaned_value
    return None


TOKEN = _read_token()

if not TOKEN:
    raise RuntimeError(
        "Discord bot token belum diatur. "
        "Tambahkan salah satu variable ini di Railway Variables atau file .env lokal: "
        f"{', '.join(TOKEN_ENV_NAMES)}."
    )

