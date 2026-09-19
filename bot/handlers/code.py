import asyncio
import logging
from hydrogram import Client, filters
from hydrogram.errors import FloodWait
from hydrogram.types import Message

from bot.services.code_parser import LANGUAGE_COMMANDS, extract_code_block, parse_code_request
from bot.services.code_runner import code_runner


logger = logging.getLogger(__name__)


def _message_text(message: Message) -> str:
	return message.text or message.caption or ""


def _message_entities(message: Message):
	if message.text is not None:
		return message.entities

	return message.caption_entities


def _workspace(message: Message):
	thread_id = message.message_thread_id if message.is_topic_message else None
	return code_runner.workspace_service.get(message.chat.id, thread_id)


async def _edit(message: Message, text: str) -> None:
	while True:
		try:
			await message.edit(text, parse_mode=None)
			return
		except FloodWait as error:
			await asyncio.sleep(error.value)


async def _delete(message: Message) -> None:
	while True:
		try:
			await message.delete()
			return
		except FloodWait as error:
			await asyncio.sleep(error.value)


async def _send(
	client: Client,
	message: Message,
	text: str,
) -> Message:
	thread_id = message.message_thread_id if message.is_topic_message else None

	while True:
		try:
			return await client.send_message(
				chat_id=message.chat.id,
				text=text,
				message_thread_id=thread_id,
				parse_mode=None,
			)
		except FloodWait as error:
			await asyncio.sleep(error.value)


@Client.on_message(
	filters.me & filters.command(LANGUAGE_COMMANDS, prefixes="."),
)
async def code_command(client: Client, message: Message) -> None:
	logger.info("Code command received")

	try:
		request = parse_code_request(
			_message_text(message),
			_message_entities(message),
		)
		workspace = _workspace(message)

		if not request.code:
			if message.reply_to_message is None:
				raise ValueError("Не найден блок кода")

			request = request.__class__(
				language=request.language,
				extension=request.extension,
				filename=request.filename,
				code=extract_code_block(
					message.reply_to_message.text
						or message.reply_to_message.caption,
					message.reply_to_message.entities
					if message.reply_to_message.text is not None
					else message.reply_to_message.caption_entities,
				)
				or "",
			)

		process = await code_runner.create_and_start(workspace, request)

		await _delete(message)
		await _send(
			client,
			message,
			f"▶️ Запущено `{process.filename}`.",
		)
	except Exception as error:
		logger.exception("Code command failed")
		await _edit(message, 
			f"❌ {error}",
		)


@Client.on_message(
	filters.me & filters.command(["run", "start"], prefixes="."),
)
async def run_command(client: Client, message: Message) -> None:
	try:
		parts = (_message_text(message)).split(maxsplit=1)
		if len(parts) != 2:
			raise ValueError("Использование: .run <filename>")

		workspace = _workspace(message)
		process = await code_runner.start_existing(workspace, parts[1].strip())

		await _delete(message)
		await _send(client, message, f"▶️ Запущено `{process.filename}`.")
	except Exception as error:
		logger.exception("Run command failed")
		await _edit(message, f"❌ {error}")


@Client.on_message(
	filters.me & filters.command("stop", prefixes="."),
)
async def stop_command(client: Client, message: Message) -> None:
	try:
		parts = _message_text(message).split(maxsplit=1)
		if len(parts) != 2:
			raise ValueError("Использование: .stop <filename>")

		workspace = _workspace(message)
		stopped = await code_runner.stop(workspace, parts[1].strip())

		await _delete(message)
		await _send(
			client,
			message,
			"⏹ Программа остановлена." if stopped else "ℹ️ Программа не запущена.",
		)
	except Exception as error:
		logger.exception("Stop command failed")
		await _edit(message, f"❌ {error}")


@Client.on_message(
	filters.me & filters.command("debug", prefixes="."),
)
async def debug_command(client: Client, message: Message) -> None:
	try:
		workspace = _workspace(message)
		parts = _message_text(message).split(maxsplit=1)
		current = code_runner.workspace_service.debug_enabled(workspace)
		value = parts[1].strip().lower() if len(parts) == 2 else "toggle"

		if value == "on":
			enabled = True
		elif value == "off":
			enabled = False
		elif value == "toggle":
			enabled = not current
		else:
			raise ValueError("Использование: .debug [on|off|toggle]")

		code_runner.workspace_service.save_debug(workspace, enabled)
		await _delete(message)
		await _send(
			client,
			message,
			f"🐞 Debug {'включён' if enabled else 'выключен'}.",
		)
	except Exception as error:
		logger.exception("Debug command failed")
		await _edit(message, f"❌ {error}")


@Client.on_message(
	filters.me & filters.command(["exec", "terminal"], prefixes="."),
)
async def exec_command(client: Client, message: Message) -> None:
	try:
		parts = _message_text(message).split(maxsplit=1)
		if len(parts) != 2:
			raise ValueError("Использование: .exec <command>")

		workspace = _workspace(message)
		command = parts[1]
		output, code = await code_runner.exec_terminal(workspace, command)

		result = output.strip() or "<пустой вывод>"
		result = result[-8500:]

		parts = [
			f"$ {command}",
			result,
			"Process exited with code" if code in (None, 0) else f"Process exited with code {code}",
		]
		await _send(client, message, "```text\n" + "\n\n".join(parts) + "\n```")
		await _delete(message)
	except Exception as error:
		logger.exception("Terminal command failed")
		await _edit(message, f"❌ {error}")


@Client.on_message(
	filters.me & filters.command("reset", prefixes="."),
)
async def reset_command(client: Client, message: Message) -> None:
	try:
		await code_runner.reset()
		await _delete(message)
		await _send(client, message, "♻️ Контейнер пересоздан и запущен.")
	except Exception as error:
		logger.exception("Reset command failed")
		await _edit(message, f"❌ {error}")
