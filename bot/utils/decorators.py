import asyncio
from functools import wraps

from hydrogram.errors import FloodWait


def handle_floodwait(func):
	@wraps(func)
	async def wrapper(*args, **kwargs):
		while True:
			try:
				return await func(*args, **kwargs)
			except FloodWait as error:
				await asyncio.sleep(error.value)
	return wrapper

def auto_delete(delay: float = 3):
	def decorator(func):
		@wraps(func)
		async def wrapper(client, message):
			await func(client, message)
			await asyncio.sleep(delay)
			try:
				await message.delete()
			except:
				pass

		return wrapper

	return decorator


__all__ = ["auto_delete"]
