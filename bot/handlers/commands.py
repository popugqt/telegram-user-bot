import asyncio
import logging
from pathlib import Path

from hydrogram import Client, filters
from hydrogram.errors import FloodWait
from hydrogram.types import Message

from bot.services.ocr import OCRService, normalize_languages
from bot.settings import DOWNLOADS_DIR
from bot.utils.decorators import auto_delete, handle_floodwait
from bot.utils.functions import animate_message, animations as anim, reboot


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

logger = logging.getLogger(__name__)


@Client.on_message(
	filters.me & filters.command("help", prefixes=".")
)
@auto_delete(30)
async def help_command(client: Client, message: Message) -> None:
	logger.info("Help command received")

	await message.edit(
		"Доступные команды:\n\n"
		".help\n"
		".ocr\n"
		".delete <count>\n"
		".clear\n"
		".cls\n"
		".reboot\n"
		".python [filename]\n"
		".node [filename]\n"
		".cpp [filename]\n"
		".java [filename]\n"
		".brainfuck [filename]\n"
		".bf [filename]\n"
		".run <filename>\n"
		".stop <filename>\n"
		".debug [on|off|toggle]\n"
		".exec <command>\n"
		".reset",
		parse_mode=None,
	)


@Client.on_message(
	filters.me & filters.command("reboot", prefixes=".")
)
async def reboot_command(client: Client, message: Message) -> None:
	logger.info("Reboot command received")

	await animate_message(
		message,
		anim.REBOOTING,
		1.5 / len(anim.REBOOTING),
	)
	await message.delete()

	logger.info("Rebooting...")
	reboot()


def _is_image_message(message: Message) -> bool:
	if message.photo:
		return True

	if message.document and message.document.file_name:
		extension = Path(message.document.file_name).suffix.lower()
		return extension in IMAGE_EXTENSIONS

	return False


async def _get_image_messages(message: Message) -> list[Message]:
	if not _is_image_message(message):
		return []

	if message.media_group_id:
		try:
			media_group = await message.get_media_group()
		except ValueError:
			media_group = [message]

		return [
			item
			for item in media_group
			if _is_image_message(item)
		]

	return [message]


async def _recognize_images(
	messages: list[Message],
	languages: str = "rus+eng",
) -> str:
	ocr = OCRService(languages=languages)
	results: list[str] = []

	DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

	for item in messages:
		if item.photo:
			path = DOWNLOADS_DIR / f"{item.id}.jpg"
		else:
			extension = Path(item.document.file_name).suffix.lower()
			path = DOWNLOADS_DIR / f"{item.id}{extension}"

		try:
			logger.info("Downloading image %s for OCR", item.id)

			downloaded_path = await item.download(
				file_name=str(path),
			)

			if downloaded_path is None:
				logger.warning("Failed to download image %s", item.id)
				continue

			text = ocr.recognize_file(downloaded_path)
			if text:
				results.append(text)
		finally:
			path.unlink(missing_ok=True)

	return "\n\n".join(results)


def _ocr_language(message: Message) -> str:
	parts = message.command[1:] if len(message.command) > 1 else []
	value = " ".join(parts).strip()
	languages = normalize_languages(value or None)

	if languages not in {"rus", "eng", "rus+eng"}:
		raise ValueError(
			"Язык OCR: ru, eng, ru+eng, ru/eng, ру/англ"
		)

	return languages


async def _send_ocr_result(
	client: Client,
	message: Message,
	text: str,
	edit_caption: bool = False,
) -> None:
	formatted = f"```text\n{text}\n```"
	limit = 3500 if not edit_caption else 900

	if len(formatted) <= limit:
		if edit_caption:
			await message.edit_caption(formatted, parse_mode=None)
		else:
			await message.edit(formatted, parse_mode=None)
		return

	status = "✅ Распознавание завершено. Результат отправлен сообщениями."
	if edit_caption:
		await message.edit_caption(status, parse_mode=None)
	else:
		await message.edit(status, parse_mode=None)

	thread_id = message.message_thread_id if message.is_topic_message else None
	for offset in range(0, len(text), 3500):
		chunk = text[offset:offset + 3500]
		while True:
			try:
				await client.send_message(
					chat_id=message.chat.id,
					text=f"```text\n{chunk}\n```",
					message_thread_id=thread_id,
					parse_mode=None,
				)
				break
			except FloodWait as error:
				await asyncio.sleep(error.value)


@Client.on_message(
	filters.me
	& filters.reply
	& ~filters.media
	& filters.command("ocr", prefixes="."),
)
@handle_floodwait
async def ocr_reply_command(client: Client, message: Message) -> None:
	logger.info("OCR reply command received")
	target = message.reply_to_message

	if target is None:
		await message.edit(
			"❌ Не удалось получить сообщение.",
			parse_mode=None,
		)
		return

	images = await _get_image_messages(target)
	try:
		languages = _ocr_language(message)
	except ValueError as error:
		await message.edit(str(error), parse_mode=None)
		return

	if not images:
		await message.edit(
			"❌ В сообщении нет поддерживаемого изображения.",
			parse_mode=None,
		)
		return

	await message.edit("🔄 Распознавание...", parse_mode=None)
	text = await _recognize_images(images, languages)

	if not text:
		text = "❌ Не удалось распознать текст."

	await _send_ocr_result(client, message, text)


@Client.on_message(
	filters.me
	& (filters.photo | filters.document)
	& filters.command("ocr", prefixes="."),
)
@handle_floodwait
async def ocr_attachment_command(client: Client, message: Message) -> None:
	logger.info("OCR attachment command received")
	try:
		languages = _ocr_language(message)
	except ValueError as error:
		await message.edit_caption(str(error), parse_mode=None)
		return

	images = await _get_image_messages(message)

	if not images:
		await message.edit_caption(
			"❌ Поддерживаются только PNG, JPG, JPEG и WEBP.",
			parse_mode=None,
		)
		return

	await message.edit_caption("🔄 Распознавание...", parse_mode=None)
	text = await _recognize_images(images, languages)

	if not text:
		text = "❌ Не удалось распознать текст."

	await _send_ocr_result(
		client,
		message,
		text,
		edit_caption=True,
	)


@Client.on_message(
	filters.me & filters.command(["delete", "del", "clear", "cls"], prefixes="."),
)
@handle_floodwait
async def delete_command(client: Client, message: Message) -> None:
	logger.info("Delete command received")

	command = message.command
	command_id = message.id
	chat_id = message.chat.id
	topic_id = message.message_thread_id if message.is_topic_message else None
	me = await client.get_me()

	if command[0].lower() in {"clear", "cls"}:
		if len(command) != 1:
			await message.delete()
			return
		count = -1
	else:
		try:
			if len(command) < 2:
				await message.delete()
				return

			count = int(command[1])
		except ValueError:
			await message.delete()
			return

		if count == 0 or count < -1:
			await message.delete()
			return

	message_ids: list[int] = [command_id]

	async for item in client.get_chat_history(chat_id):
		if item.id >= command_id:
			continue

		if item.from_user is None or item.from_user.id != me.id:
			continue

		if message.is_topic_message:
			if item.message_thread_id != topic_id:
				continue
		elif item.is_topic_message:
			continue

		message_ids.append(item.id)

		if count != -1 and len(message_ids) - 1 >= count:
			break

	await client.delete_messages(chat_id, message_ids)
