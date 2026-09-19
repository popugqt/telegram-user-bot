import asyncio
import gzip
import io
import logging
import tarfile
from pathlib import Path
from typing import Any

import aiodocker
from aiodocker.exceptions import DockerError

from bot.settings import (
	CODE_RUNNER_CONTAINER,
	CODE_RUNNER_CPUS,
	CODE_RUNNER_IMAGE,
	CODE_RUNNER_MEMORY,
	CODE_RUNNER_USER,
	WORKSPACES_DIR,
)


logger = logging.getLogger(__name__)


class DockerService:
	def __init__(
		self,
		root: Path,
		image: str = CODE_RUNNER_IMAGE,
		container_name: str = CODE_RUNNER_CONTAINER,
	) -> None:
		self.root = root
		self.image = image
		self.container_name = container_name
		self.docker: aiodocker.Docker | None = None
		self.container = None
		self._lock: asyncio.Lock | None = None

	def _get_lock(self) -> asyncio.Lock:
		if self._lock is None:
			self._lock = asyncio.Lock()

		return self._lock

	async def start(self) -> None:
		if self.docker is None:
			self.docker = aiodocker.Docker()

		try:
			await self._ensure_image()
			await self.ensure_container()
		except Exception:
			logger.exception("Docker service failed to start")
			await self.close(stop_container=False)
			raise

	async def _ensure_image(self) -> None:
		assert self.docker is not None

		try:
			await self.docker.images.inspect(self.image)
			return
		except DockerError as error:
			if error.status != 404:
				raise

		logger.info("Building code runner image %s", self.image)

		context = self._build_context()
		results = await self.docker.images.build(
			fileobj=io.BytesIO(context),
			path_dockerfile="Dockerfile",
			tag=self.image,
			pull=True,
			rm=True,
			forcerm=True,
			encoding="gzip",
			quiet=True,
			stream=False,
		)

		for result in results:
			if isinstance(result, dict) and result.get("error"):
				raise RuntimeError(result["error"])

		logger.info("Code runner image built")

	def _build_context(self) -> bytes:
		context_dir = Path(__file__).resolve().parent.parent.parent / "docker" / "code-runner"
		buffer = io.BytesIO()

		with tarfile.open(fileobj=buffer, mode="w") as archive:
			for path in (context_dir / "Dockerfile", context_dir / "brainfuck"):
				archive.add(path, arcname=path.name)

		return gzip.compress(buffer.getvalue())

	async def _get_container(self):
		assert self.docker is not None

		try:
			return await self.docker.containers.get(self.container_name)
		except DockerError as error:
			if error.status != 404:
				raise
			return None

	async def ensure_container(self):
		assert self.docker is not None

		container = await self._get_container()

		if container is not None:
			info = await container.show()
			if not info.get("State", {}).get("Running", False):
				await container.start()

			self.container = container
			return container

		WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

		config: dict[str, Any] = {
			"Image": self.image,
			"Cmd": ["/bin/sh", "-c", "while :; do sleep 3600; done"],
			"WorkingDir": "/workspaces",
			"User": CODE_RUNNER_USER,
			"AttachStdin": False,
			"AttachStdout": False,
			"AttachStderr": False,
			"Tty": False,
			"OpenStdin": False,
			"Env": ["HOME=/tmp"],
			"HostConfig": {
				"Binds": [f"{WORKSPACES_DIR.resolve()}:/workspaces:rw"],
				"NetworkMode": "none",
				"Memory": CODE_RUNNER_MEMORY,
				"NanoCpus": CODE_RUNNER_CPUS * 1_000_000_000,
				"PidsLimit": 128,
				"SecurityOpt": ["no-new-privileges:true"],
				"Tmpfs": {
					"/tmp": "rw,nosuid,size=256m",
				},
			},
			"Labels": {
				"telegram-user-bot": "code-runner",
			},
		}

		container = await self.docker.containers.create(
			config=config,
			name=self.container_name,
		)
		await container.start()
		self.container = container

		logger.info("Code runner container started")
		return container

	async def reset(self, rebuild: bool = True) -> None:
		async with self._get_lock():
			await self._reset(rebuild=rebuild)

	async def _reset(self, rebuild: bool = True) -> None:
		assert self.docker is not None

		container = await self._get_container()

		if container is not None:
			try:
				await container.delete(force=True)
			except DockerError as error:
				if error.status != 404:
					raise

		self.container = None

		if rebuild:
			try:
				await self.docker.images.delete(self.image, force=True)
			except DockerError as error:
				if error.status != 404:
					raise

			await self._ensure_image()

		await self._ensure_container()

	async def exec(
		self,
		command: str,
		workdir: str = "/workspaces",
		user: str = CODE_RUNNER_USER,
		timeout: float | None = None,
	) -> tuple[str, int | None]:
		container = await self.ensure_container()

		exec_instance = await container.exec(
			["/bin/sh", "-lc", command],
			stdout=True,
			stderr=True,
			tty=False,
			privileged=False,
			user=user,
			workdir=workdir,
		)

		stream = exec_instance.start()
		output: list[str] = []

		try:
			async def read_stream() -> None:
				while True:
					item = await stream.read_out()
					if item is None:
						break
					output.append(item.data.decode("utf-8", errors="replace"))

			if timeout is None:
				await read_stream()
			else:
				import asyncio
				await asyncio.wait_for(read_stream(), timeout=timeout)
		finally:
			close = getattr(stream, "close", None)
			if close is not None:
				await close()

		info = await exec_instance.inspect()
		return "".join(output), info.get("ExitCode")

	async def close(self, stop_container: bool = True) -> None:
		if self.docker is None:
			return

		try:
			if stop_container:
				container = await self._get_container()
				if container is not None:
					try:
						await container.stop(t=2)
					except DockerError as error:
						if error.status != 404:
							raise
		finally:
			await self.docker.close()
			self.docker = None
			self.container = None


__all__ = ["DockerService"]
