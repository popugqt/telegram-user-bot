import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


DEFAULT_LOG_FORMAT = ("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColorFormatter(logging.Formatter):
	COLORS = {
		logging.DEBUG: (117, 34, 72),
		logging.INFO: (190, 24, 93),
		logging.WARNING: (225, 29, 72),
		logging.ERROR: (244, 63, 94),
		logging.CRITICAL: (255, 0, 60),
	}

	RESET = "\033[0m"

	def format(self, record: logging.LogRecord) -> str:
		message = super().format(record)

		r, g, b = self.COLORS.get(record.levelno, (255, 255, 255),)
		color = f"\033[38;2;{r};{g};{b}m"

		return f"{color}{message}{self.RESET}"

def setup_logger(logs_dir: Path) -> None:
	logs_dir.mkdir(parents=True, exist_ok=True)

	logger = logging.getLogger()

	if logger.handlers:
		return

	logger.setLevel(logging.DEBUG)

	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.INFO)
	console_handler.setFormatter(ColorFormatter(
		DEFAULT_LOG_FORMAT,
		DATE_FORMAT,
	))

	file_handler = RotatingFileHandler(
		logs_dir / "userbot.log",
		maxBytes=5*2**20,
		backupCount=3,
		encoding="utf-8",
	)

	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(logging.Formatter(
		DEFAULT_LOG_FORMAT,
		DATE_FORMAT,
	))

	logger.addHandler(console_handler)
	logger.addHandler(file_handler)
