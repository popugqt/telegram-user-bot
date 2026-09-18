from pathlib import Path
from os import getenv

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_API_ID = int(getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = getenv("TELEGRAM_API_HASH")

STORAGE_DIR = BASE_DIR / "storage"

DOWNLOADS_DIR = STORAGE_DIR / "downloads"
GENERATED_DIR = STORAGE_DIR / "generated"
SESSION_DIR = STORAGE_DIR / "session"
WORKSPACES_DIR = STORAGE_DIR / "workspaces"

LOGS_DIR = BASE_DIR / "logs"

SESSION = str(SESSION_DIR / getenv("SESSION_NAME", "userbot"))


__all__ = [
	"TELEGRAM_API_ID",
	"TELEGRAM_API_HASH",

	"STORAGE_DIR",

	"DOWNLOADS_DIR",
	"GENERATED_DIR",
	"SESSION_DIR",
	"WORKSPACES_DIR",

	"LOGS_DIR",

	"SESSION"
]
