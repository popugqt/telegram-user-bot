import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from bot.settings import WORKSPACES_DIR


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class Workspace:
	chat_id: int
	thread_id: int | None
	host_path: Path
	container_path: str


class WorkspaceService:
	ROOT_CONTAINER_PATH = "/workspaces"
	DEBUG_FILE = ".runner/debug.json"
	RUNS_DIR = ".runner/runs"

	def __init__(self, root: Path = WORKSPACES_DIR) -> None:
		self.root = root
		self.root.mkdir(parents=True, exist_ok=True)

	def get(self, chat_id: int, thread_id: int | None) -> Workspace:
		chat_dir = self.root / f"chat_{chat_id}"
		topic_dir = chat_dir / (f"topic_{thread_id}" if thread_id else "main")
		topic_dir.mkdir(parents=True, exist_ok=True)

		return Workspace(
			chat_id=chat_id,
			thread_id=thread_id,
			host_path=topic_dir,
			container_path=(
				f"{self.ROOT_CONTAINER_PATH}/{chat_dir.name}/{topic_dir.name}"
			),
		)

	def validate_filename(self, filename: str) -> str:
		filename = filename.strip()

		if not filename or filename in {".", ".."}:
			raise ValueError("Некорректное имя файла")

		if Path(filename).name != filename:
			raise ValueError("Имя файла не может содержать путь")

		if not re.fullmatch(r"[A-Za-z0-9_.+-]+", filename):
			raise ValueError("Имя файла содержит недопустимые символы")

		return filename

	def resolve_file(self, workspace: Workspace, filename: str) -> Path:
		filename = self.validate_filename(filename)
		path = workspace.host_path / filename

		if not path.is_file():
			raise FileNotFoundError(f"Файл {filename} не найден")

		return path

	def save_debug(self, workspace: Workspace, enabled: bool) -> None:
		path = workspace.host_path / self.DEBUG_FILE
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(
			json.dumps({"enabled": enabled}, ensure_ascii=False, indent=2),
			encoding="utf-8",
		)

	def debug_enabled(self, workspace: Workspace) -> bool:
		path = workspace.host_path / self.DEBUG_FILE

		if not path.is_file():
			return True

		try:
			data = json.loads(path.read_text(encoding="utf-8"))
			return bool(data.get("enabled", True))
		except (OSError, ValueError, TypeError):
			logger.warning("Failed to read debug settings: %s", path)
			return True

	def clean_run_metadata(self) -> None:
		for run_dir in self.root.glob("chat_*/**/.runner/runs/*"):
			if not run_dir.is_dir():
				continue

			for child in run_dir.iterdir():
				if child.is_file() and child.name != "log.txt":
					try:
						child.unlink()
					except OSError:
						logger.warning("Failed to remove %s", child)

	def find_run_metadata(self) -> list[Path]:
		return list(self.root.glob("chat_*/**/.runner/runs/*/meta.json"))


__all__ = ["Workspace", "WorkspaceService"]
