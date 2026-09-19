import asyncio
import json
import logging
import re
import shutil
import shlex
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hydrogram.errors import FloodWait

from bot.services.code_parser import CodeRequest
from bot.services.docker import DockerService
from bot.services.workspace import Workspace, WorkspaceService
from bot.settings import (
	CODE_RUNNER_EXEC_TIMEOUT,
	CODE_RUNNER_OUTPUT_LIMIT,
	CODE_RUNNER_TIMEOUT,
	WORKSPACES_DIR,
)


logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {"py", "js", "cpp", "java", "bf"}
JAVA_PUBLIC_TYPE = re.compile(
	r"\bpublic\s+(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)"
)


@dataclass(slots=True)
class RunningProcess:
	run_id: str
	pid: int
	filename: str
	language: str
	chat_id: int
	thread_id: int | None
	workspace: Workspace
	run_dir: Path
	started_at: float
	task: asyncio.Task | None = field(default=None, repr=False)


class CodeRunnerService:
	def __init__(self) -> None:
		self.workspace_service = WorkspaceService()
		self.docker = DockerService(WORKSPACES_DIR)
		self.processes: dict[tuple[int, int | None, str], RunningProcess] = {}
		self._lock: asyncio.Lock | None = None
		self.available = False
		self.client: Any | None = None

	async def start(self) -> bool:
		try:
			await self.docker.start()
		except Exception:
			logger.exception("Code runner failed to start")
			self.available = False
			return False

		self.available = True
		await self._restore_processes()
		return True

	def set_client(self, client: Any) -> None:
		self.client = client

	def _get_lock(self) -> asyncio.Lock:
		if self._lock is None:
			self._lock = asyncio.Lock()

		return self._lock

	async def close(self) -> None:
		tasks: list[asyncio.Task] = []
		for process in list(self.processes.values()):
			if process.task is not None:
				process.task.cancel()
				tasks.append(process.task)

		if tasks:
			await asyncio.gather(*tasks, return_exceptions=True)

		self.processes.clear()
		await self.docker.close(stop_container=True)
		self.available = False

	async def _restore_processes(self) -> None:
		for meta_path in self.workspace_service.find_run_metadata():
			try:
				data = json.loads(meta_path.read_text(encoding="utf-8"))
				chat_id = int(data["chat_id"])
				thread_id = data.get("thread_id")
				if thread_id is not None:
					thread_id = int(thread_id)

				process = RunningProcess(
					run_id=str(data["run_id"]),
					pid=int(data["pid"]),
					filename=str(data["filename"]),
					language=str(data["language"]),
					chat_id=chat_id,
					thread_id=thread_id,
					workspace=self.workspace_service.get(chat_id, thread_id),
					run_dir=meta_path.parent,
					started_at=float(data.get("started_at", time.time())),
				)
			except (OSError, ValueError, KeyError, TypeError):
				logger.warning("Failed to restore process from %s", meta_path)
				continue

			try:
				running = await self.is_running(process.pid)
			except Exception:
				logger.exception("Failed to inspect restored process %s", process.pid)
				continue

			if not running:
				continue

			self._set_process(process)
			process.task = asyncio.create_task(self._watch_process(process))

	def _set_process(self, process: RunningProcess) -> None:
		self.processes[
			(process.chat_id, process.thread_id, process.filename)
		] = process

	def _process_key(
		self,
		workspace: Workspace,
		filename: str,
	) -> tuple[int, int | None, str]:
		return workspace.chat_id, workspace.thread_id, filename

	def _find_process(
		self,
		workspace: Workspace,
		filename: str,
	) -> RunningProcess | None:
		return self.processes.get(self._process_key(workspace, filename))

	def _create_filename(
		self,
		workspace: Workspace,
		extension: str,
		filename: str | None,
	) -> str:
		if filename:
			filename = self.workspace_service.validate_filename(filename)
			path = Path(filename)

			if path.suffix.lower() == f".{extension}":
				return filename

			if path.suffix:
				filename = path.stem

			return f"{filename}.{extension}"

		candidate = f"app.{extension}"
		index = 2

		while (workspace.host_path / candidate).exists():
			candidate = f"app-{index}.{extension}"
			index += 1

		return candidate

	def _prepare_java_source(
		self,
		workspace: Workspace,
		run_dir: Path,
		filename: str,
	) -> str:
		source = (workspace.host_path / filename).read_text(encoding="utf-8")
		match = JAVA_PUBLIC_TYPE.search(source)
		source_name = f"{match.group(1)}.java" if match else "Main.java"

		source_dir = run_dir / "src"
		source_dir.mkdir(parents=True, exist_ok=True)
		(source_dir / source_name).write_text(source, encoding="utf-8")

		return source_name

	def _create_run_script(
		self,
		workspace: Workspace,
		run_dir: Path,
		request: CodeRequest,
		filename: str,
	) -> str:
		run_rel = run_dir.relative_to(workspace.host_path).as_posix()
		file_q = shlex.quote(filename)
		status_q = shlex.quote(f"{run_rel}/status")

		lines = [
			"#!/bin/sh",
			"set +e",
			f"STATUS={status_q}",
			"ulimit -c 0 2>/dev/null || true",
			"ulimit -n 256 2>/dev/null || true",
			"ulimit -u 128 2>/dev/null || true",
			"ulimit -f 32768 2>/dev/null || true",
			"finish() { printf '%s\\n' 143 > \"$STATUS\"; exit 143; }",
			"trap finish TERM INT",
		]

		if request.extension == "py":
			lines.append(f"python3 -u {file_q}")
		elif request.extension == "js":
			lines.append(f"node {file_q}")
		elif request.extension == "cpp":
			binary_q = shlex.quote(f"{run_rel}/program")
			lines.extend([
				f"g++ -std=c++20 -O2 -pipe {file_q} -o {binary_q}",
				"CODE=$?",
				"if [ \"$CODE\" -ne 0 ]; then exit \"$CODE\"; fi",
				f"stdbuf -oL -eL {binary_q}",
			])
		elif request.extension == "bf":
			lines.append(f"brainfuck {file_q}")
		elif request.extension == "java":
			source_name = self._prepare_java_source(
				workspace,
				run_dir,
				filename,
			)
			classes_q = shlex.quote(f"{run_rel}/classes")
			source_q = shlex.quote(f"{run_rel}/src/{source_name}")
			lines.extend([
				f"rm -rf {classes_q}",
				f"mkdir -p {classes_q}",
				f"javac -encoding UTF-8 -d {classes_q} {source_q}",
				"CODE=$?",
				"if [ \"$CODE\" -ne 0 ]; then exit \"$CODE\"; fi",
				"MAIN=",
				f"for CLASS in $(find {classes_q} -type f -name '*.class' ! -name '*$*'); do",
				f"\tNAME=${{CLASS#'{run_rel}/classes/'}}",
				"\tNAME=${NAME%.class}",
				"\tNAME=$(printf '%s' \"$NAME\" | tr '/' '.')",
				f"\tif javap -classpath {classes_q} \"$NAME\" 2>/dev/null | grep -q 'public static void main(java.lang.String\\[\\]);'; then",
				"\t\tMAIN=$NAME",
				"\t\tbreak",
				"\tfi",
				"done",
				"if [ -z \"$MAIN\" ]; then",
				"\techo 'Не найден public static void main(String[])' >&2",
				"\texit 1",
				"fi",
				f"stdbuf -oL -eL java -cp {classes_q} \"$MAIN\"",
			])
		else:
			raise ValueError("Неподдерживаемый язык")

		lines.extend([
			"CODE=$?",
			"printf '%s\\n' \"$CODE\" > \"$STATUS\"",
			"exit \"$CODE\"",
		])

		return "\n".join(lines) + "\n"

	async def create_and_start(
		self,
		workspace: Workspace,
		request: CodeRequest,
	) -> RunningProcess:
		if not self.available:
			raise RuntimeError("Code runner недоступен")

		if not request.code.strip():
			raise ValueError("В команде нет блока кода")

		filename = self._create_filename(
			workspace,
			request.extension,
			request.filename,
		)

		existing = self._find_process(workspace, filename)
		if existing is not None and await self.is_running(existing.pid):
			raise RuntimeError(f"Программа {filename} уже запущена")

		path = workspace.host_path / filename
		path.write_text(request.code, encoding="utf-8")

		return await self.start_existing(
			workspace,
			filename,
			language=request.language,
		)

	async def start_existing(
		self,
		workspace: Workspace,
		filename: str,
		language: str | None = None,
	) -> RunningProcess:
		filename = self.workspace_service.validate_filename(filename)
		self.workspace_service.resolve_file(workspace, filename)

		extension = Path(filename).suffix.lower().lstrip(".")
		if extension not in SUPPORTED_EXTENSIONS:
			raise ValueError("Расширение файла не поддерживается")

		return await self._start_existing(workspace, filename, language or extension)

	async def _start_existing(
		self,
		workspace: Workspace,
		filename: str,
		language: str,
	) -> RunningProcess:
		async with self._get_lock():
			existing = self._find_process(workspace, filename)
			if existing is not None and await self.is_running(existing.pid):
				raise RuntimeError(f"Программа {filename} уже запущена")

			if existing is not None:
				self.processes.pop(
					self._process_key(workspace, filename),
					None,
				)

			run_id = uuid.uuid4().hex
			run_dir = workspace.host_path / ".runner" / "runs" / run_id
			run_dir.mkdir(parents=True, exist_ok=True)

			request = CodeRequest(
				language=language,
				extension=Path(filename).suffix.lower().lstrip("."),
				filename=filename,
				code="",
			)
			script = self._create_run_script(
				workspace,
				run_dir,
				request,
				filename,
			)
			script_path = run_dir / "run.sh"
			script_path.write_text(script, encoding="utf-8")
			script_path.chmod(0o755)

			meta_path = run_dir / "meta.json"
			container_script = (
				f"{workspace.container_path}/.runner/runs/{run_id}/run.sh"
			)
			log_rel = f".runner/runs/{run_id}/log.txt"
			command = (
				f"nohup setsid {shlex.quote(container_script)} "
				f"> {shlex.quote(log_rel)} 2>&1 < /dev/null & echo $!"
			)

			output, exit_code = await self.docker.exec(
				command,
				workdir=workspace.container_path,
				timeout=10,
			)

			if exit_code != 0:
				raise RuntimeError(output.strip() or "Не удалось запустить программу")

			try:
				pid = int(output.strip().splitlines()[-1])
			except (ValueError, IndexError):
				raise RuntimeError(
					f"Docker не вернул PID процесса: {output.strip()}"
				)

			process = RunningProcess(
				run_id=run_id,
				pid=pid,
				filename=filename,
				language=language,
				chat_id=workspace.chat_id,
				thread_id=workspace.thread_id,
				workspace=workspace,
				run_dir=run_dir,
				started_at=time.time(),
			)

			meta_path.write_text(
				json.dumps(
					{
						"run_id": process.run_id,
						"pid": process.pid,
						"filename": process.filename,
						"language": process.language,
						"chat_id": process.chat_id,
						"thread_id": process.thread_id,
						"started_at": process.started_at,
					},
					ensure_ascii=False,
					indent=2,
				),
				encoding="utf-8",
			)

			self._set_process(process)
			process.task = asyncio.create_task(self._watch_process(process))
			return process

	async def is_running(self, pid: int) -> bool:
		_, code = await self.docker.exec(
			f"kill -0 {int(pid)} 2>/dev/null",
			timeout=5,
		)
		return code == 0

	async def stop(self, workspace: Workspace, filename: str) -> bool:
		filename = self.workspace_service.validate_filename(filename)
		process = self._find_process(workspace, filename)

		if process is None:
			return False

		if not await self.is_running(process.pid):
			self.processes.pop(self._process_key(workspace, filename), None)
			return False

		await self.docker.exec(
			f"kill -TERM -- -{int(process.pid)} 2>/dev/null || true; "
			"sleep 1; "
			f"kill -0 -{int(process.pid)} 2>/dev/null "
			"&& kill -KILL -- -{int(process.pid)} 2>/dev/null || true",
			workdir=workspace.container_path,
			timeout=5,
		)
		return True

	async def exec_terminal(
		self,
		workspace: Workspace,
		command: str,
	) -> tuple[str, int | None]:
		command = command.strip()
		if not command:
			raise ValueError("Не указана команда")

		timeout_command = (
			f"timeout --kill-after=2s {CODE_RUNNER_EXEC_TIMEOUT}s "
			f"/bin/sh -lc {shlex.quote(command)}"
		)
		return await self.docker.exec(
			timeout_command,
			workdir=workspace.container_path,
			timeout=CODE_RUNNER_EXEC_TIMEOUT + 5,
		)

	async def reset(self) -> None:
		if not self.available:
			await self.docker.start()
			self.available = True

		async with self._get_lock():
			tasks: list[asyncio.Task] = []
			for process in list(self.processes.values()):
				if process.task is not None:
					process.task.cancel()
					tasks.append(process.task)

			if tasks:
				await asyncio.gather(*tasks, return_exceptions=True)

			self.processes.clear()
			await self.docker.reset(rebuild=True)
			self.available = True
			self._remove_run_metadata()

	def _remove_run_metadata(self) -> None:
		for meta_path in self.workspace_service.find_run_metadata():
			run_dir = meta_path.parent
			try:
				shutil.rmtree(run_dir)
			except OSError:
				logger.warning("Failed to clean run directory %s", run_dir)

	async def _watch_process(self, process: RunningProcess) -> None:
		log_path = process.run_dir / "log.txt"
		status_path = process.run_dir / "status"
		position = 0
		unsent = ""
		last_send = 0.0
		timed_out = False

		try:
			while True:
				chunk = self._read_new_output(log_path, position)
				if chunk is not None:
					position, new_text = chunk
					if new_text:
						if len(unsent) + len(new_text) <= CODE_RUNNER_OUTPUT_LIMIT:
							unsent += new_text
						else:
							unsent = (unsent + new_text)[-CODE_RUNNER_OUTPUT_LIMIT:]

					if (
						self.workspace_service.debug_enabled(process.workspace)
						and unsent
						and time.monotonic() - last_send >= 0.8
					):
						await self._send_chunks(process, unsent)
						unsent = ""
						last_send = time.monotonic()

				if not await self.is_running(process.pid):
					break

				if time.time() - process.started_at >= CODE_RUNNER_TIMEOUT:
					timed_out = True
					await self.stop(process.workspace, process.filename)
					break

				await asyncio.sleep(0.5)

			await asyncio.sleep(0.2)
			chunk = self._read_new_output(log_path, position)
			if chunk is not None:
				position, new_text = chunk
				unsent += new_text

			status = await self._read_exit_code(status_path)
			if timed_out:
				status = 124

			if unsent:
				await self._send_chunks(process, unsent)

			await self._send_text(
				process,
				self._finish_message(process, status, timed_out),
			)
		except asyncio.CancelledError:
			raise
		except Exception:
			logger.exception("Process watcher failed for %s", process.filename)
		finally:
			self.processes.pop(
				self._process_key(process.workspace, process.filename),
				None,
			)

	def _read_new_output(
		self,
		path: Path,
		position: int,
	) -> tuple[int, str] | None:
		if not path.exists():
			return None

		try:
			with path.open("r", encoding="utf-8", errors="replace") as file:
				file.seek(position)
				text = file.read()
				return file.tell(), text
		except OSError:
			return None

	async def _read_exit_code(self, path: Path) -> int:
		for _ in range(10):
			if path.is_file():
				try:
					return int(path.read_text(encoding="utf-8").strip())
				except (OSError, ValueError):
					pass
			await asyncio.sleep(0.1)

		return 1

	def _finish_message(
		self,
		process: RunningProcess,
		status: int,
		timed_out: bool,
	) -> str:
		if timed_out:
			return (
				f"⏱ `{process.filename}` остановлен: превышено время "
				f"выполнения ({CODE_RUNNER_TIMEOUT} сек)."
			)

		if status == 0:
			return f"✅ `{process.filename}` завершил работу с кодом 0."

		if status == 143:
			return f"⏹ `{process.filename}` остановлен."

		return f"❌ `{process.filename}` завершил работу с кодом {status}."

	async def _send_chunks(self, process: RunningProcess, text: str) -> None:
		text = text.strip("\n")
		if not text:
			return

		for offset in range(0, len(text), 3500):
			chunk = text[offset:offset + 3500]
			await self._send_text(
				process,
				f"```text\n{chunk}\n```",
			)

	async def _send_text(self, process: RunningProcess, text: str) -> None:
		if self.client is None:
			logger.warning("Telegram client is not ready for runner output")
			return

		while True:
			try:
				await self.client.send_message(
					chat_id=process.chat_id,
					text=text,
					message_thread_id=process.thread_id,
					parse_mode=None,
				)
				return
			except FloodWait as error:
				await asyncio.sleep(error.value)


code_runner = CodeRunnerService()


__all__ = ["CodeRunnerService", "RunningProcess", "code_runner"]
