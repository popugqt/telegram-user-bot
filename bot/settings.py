from os import getenv, getgid, getuid
from pathlib import Path
import re

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


TELEGRAM_API_ID = int(getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = getenv("TELEGRAM_API_HASH", "")

STORAGE_DIR = BASE_DIR / "storage"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
GENERATED_DIR = STORAGE_DIR / "generated"
SESSION_DIR = STORAGE_DIR / "session"
WORKSPACES_DIR = STORAGE_DIR / "workspaces"

LOGS_DIR = BASE_DIR / "logs"

SESSION_NAME = getenv("SESSION_NAME", "userbot")
SESSION = str(SESSION_DIR / SESSION_NAME)
RUNNER_SCOPE = re.sub(r"[^a-z0-9_.-]+", "-", SESSION_NAME.lower()).strip("-.") or "userbot"

configured_image = getenv("CODE_RUNNER_IMAGE")
CODE_RUNNER_IMAGE = (
	configured_image
	if configured_image and configured_image != "telegram-userbot-code-runner:latest"
	else f"telegram-userbot-code-runner:{RUNNER_SCOPE}"
)

configured_container = getenv("CODE_RUNNER_CONTAINER")
CODE_RUNNER_CONTAINER = (
	configured_container
	if configured_container and configured_container != "telegram-userbot-code-runner"
	else f"telegram-userbot-code-runner-{RUNNER_SCOPE}"
)
CODE_RUNNER_USER = getenv(
	"CODE_RUNNER_USER",
	f"{getuid()}:{getgid()}",
)
CODE_RUNNER_MEMORY = int(
	getenv("CODE_RUNNER_MEMORY", str(1024 * 1024 * 1024)),
)
CODE_RUNNER_CPUS = int(getenv("CODE_RUNNER_CPUS", "1"))
CODE_RUNNER_TIMEOUT = int(getenv("CODE_RUNNER_TIMEOUT", "600"))
CODE_RUNNER_EXEC_TIMEOUT = int(getenv("CODE_RUNNER_EXEC_TIMEOUT", "30"))
CODE_RUNNER_OUTPUT_LIMIT = int(getenv("CODE_RUNNER_OUTPUT_LIMIT", "100000"))


def ensure_storage_dirs() -> None:
	for path in (
		STORAGE_DIR,
		DOWNLOADS_DIR,
		GENERATED_DIR,
		SESSION_DIR,
		WORKSPACES_DIR,
		LOGS_DIR,
	):
		path.mkdir(parents=True, exist_ok=True)


__all__ = [
	"TELEGRAM_API_ID",
	"TELEGRAM_API_HASH",
	"STORAGE_DIR",
	"DOWNLOADS_DIR",
	"GENERATED_DIR",
	"SESSION_DIR",
	"WORKSPACES_DIR",
	"LOGS_DIR",
	"SESSION_NAME",
	"RUNNER_SCOPE",
	"SESSION",
	"CODE_RUNNER_IMAGE",
	"CODE_RUNNER_CONTAINER",
	"CODE_RUNNER_USER",
	"CODE_RUNNER_MEMORY",
	"CODE_RUNNER_CPUS",
	"CODE_RUNNER_TIMEOUT",
	"CODE_RUNNER_EXEC_TIMEOUT",
	"CODE_RUNNER_OUTPUT_LIMIT",
	"ensure_storage_dirs",
]
