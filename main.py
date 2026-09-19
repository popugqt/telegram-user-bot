import asyncio
import logging

from hydrogram import Client, idle

from bot.database import create_tables
from bot.logger import setup_logger
from bot.services.code_runner import code_runner
from bot.settings import (
	LOGS_DIR,
	SESSION,
	TELEGRAM_API_HASH,
	TELEGRAM_API_ID,
	ensure_storage_dirs,
)


setup_logger(LOGS_DIR)
logger = logging.getLogger(__name__)


async def main() -> None:
	ensure_storage_dirs()

	if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
		raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set")

	app = Client(
		SESSION,
		api_id=TELEGRAM_API_ID,
		api_hash=TELEGRAM_API_HASH,
		plugins={"root": "bot/handlers"},
	)

	code_runner.set_client(app)
	create_tables()

	await app.start()
	logger.info("Userbot started")

	if await code_runner.start():
		logger.info("Code runner is ready")
	else:
		logger.error("Code runner is unavailable")

	try:
		await idle()
	finally:
		await code_runner.close()
		await app.stop()


if __name__ == "__main__":
	asyncio.run(main())
