import logging

from hydrogram import Client

from bot.settings import (
        TELEGRAM_API_ID as TAID,
        TELEGRAM_API_HASH as TAHASH,

	LOGS_DIR,

        SESSION,
)
from bot.logger import setup_logger


def main() -> None:
	setup_logger(LOGS_DIR)

	logger = logging.getLogger(__name__)


	logger.info("Starting userbot")

	app = Client(
	        str(SESSION),
        	api_id=TAID,
        	api_hash=TAHASH,
		plugins={
			"root": "bot.handlers",
		},
	)

	app.run()

	logger.info("Userbot stopped")


if __name__ == "__main__":
	main()
