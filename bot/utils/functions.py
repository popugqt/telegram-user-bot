import os
import sys
import asyncio

from bot.utils import animations
from hydrogram.types import Message


def reboot() -> None:
	os.execv(
                sys.executable,
                [sys.executable, *sys.argv],
        )

async def animate_message(message: Message, animation: tuple[str], delay: float = 3):
	for frame in animation:
		await message.edit(frame)
		await asyncio.sleep(delay)

async def auto_delete(message: Message, delay: float = 3) -> None:
	await asyncio.sleep(3)
	await message.delete()


__all__ = [
	"reboot",
	"animation_message",
	"animations",
	"auto_delete"
]
