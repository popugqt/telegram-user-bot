import asyncio
import os
import sys

from hydrogram.types import Message

from bot.utils import animations



def reboot() -> None:
	os.execv(
		sys.executable,
		[sys.executable, *sys.argv],
	)


async def animate_message(
	message: Message,
	animation: tuple[str, ...],
	delay: float = 3,
) -> None:
	for frame in animation:
		await message.edit(frame, parse_mode=None)
		await asyncio.sleep(delay)


async def auto_delete(message: Message, delay: float = 3) -> None:
	await asyncio.sleep(delay)
	try:
		await message.delete()
	except Exception:
		pass


__all__ = [
	"reboot",
	"animate_message",
	"animations",
	"auto_delete",
]
