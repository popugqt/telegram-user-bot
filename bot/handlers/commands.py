import logging

from hydrogram import Client, filters
from hydrogram.types import Message

from bot.services.ocr import OCRService
from bot.utils.decorators import (
	auto_delete,
	handle_floodwait,
)
from bot.utils.functions import (
	animate_message,
	reboot,
	animations as anim,
)
from bot.settings import *


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

logger = logging.getLogger(__name__)

@Client.on_message(
	filters.me & filters.command("help", prefixes=".")
)
@auto_delete(30)
async def help_command(client: Client, message: Message) -> None:
	logger.info("Help command received")

	await message.edit(
		"Доступные команды:\n"
		"`.help` - Список доступных команд\n"
		"`.ocr` **[ОП]** - Распознать текст с изображения\n"
		"`.delete` **[А]** <__count__> - Удаляет __count__ (`-1` - удаляет все "
		"сообщения) сообщений из текущего чата\n"
		"`.reboot` **[Н]** - Перезапускает бота\n"
		"\n"
		"Теги:\n"
		"`Н` - Команда не принимает аргументов\n"
		"`А` - Команда принимает аргументы\n"
		"`О` - Команда срабатывает, при ответе на сообщение\n"
		"`П` - Команда работает с прикрепленными файлами\n"
		"(если у команды не указаны теги, то считайте, что она испольузет теги `Н` и `А`)\n"
	)

@Client.on_message(
	filters.me & filters.command("reboot", prefixes=".")
)
async def reboot_command(client: Client, message: Message) -> None:
	logger.info("Reboot command received")

	await animate_message(message, anim.REBOOTING, 1.5/len(anim.REBOOTING))
	await message.delete()

	logger.info("Rebooting...")

	reboot()

@Client.on_message(
	filters.me & filters.command(["delete", "del"], prefixes="."),
)
async def delete_command(client: Client, message: Message) -> None:
	logger.info("Delete command received")

	command = message.command
	await message.delete()

	try:
		if len(command) < 2: return
		count = int(command[1])
	except ValueError: return

	if count == 0 or count < -1: return

	chat_id = message.chat.id
	command_id = message.id
	topic_id = message.message_thread_id if message.is_topic_message else None
	me = await client.get_me()

	message_ids: list[int] = []

	async for item in client.get_chat_history(chat_id):
		if item.id >= command_id or \
			item.from_user is None or \
			item.from_user.id != me.id:
			continue

		if message.is_topic_message:
			if item.message_thread_id != topic_id:
				continue
		elif item.is_topic_message:
			continue

		message_ids.append(item.id)

		if count != -1 and len(message_ids) >= count:
			break

	await message.delete()

	if message_ids:
		await client.delete_messages(chat_id, message_ids)

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


async def _recognize_images(messages: list[Message]) -> str:
	ocr = OCRService()
	results: list[str] = []

	DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

	for item in messages:
		if item.photo:
			path = DOWNLOADS_DIR / f"{item.id}.jpg"
		else:
			extension = Path(
				item.document.file_name
			).suffix.lower()

			path = DOWNLOADS_DIR / f"{item.id}{extension}"

		try:
			logger.info(
				"Downloading image %s for OCR",
				item.id,
			)

			downloaded_path = await item.download(
				file_name=str(path),
			)

			if downloaded_path is None:
				logger.warning(
					"Failed to download image %s",
					item.id,
				)
				continue

			text = ocr.recognize_file(downloaded_path)

			results.append(text)

		finally:
			path.unlink(missing_ok=True)

	return "\n\n".join(results)


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

	if not images:
		await message.edit(
			"❌ В сообщении нет поддерживаемого изображения.",
			parse_mode=None,
		)
		return

	await message.edit(
		"🔄 Распознавание...",
		parse_mode=None,
	)

	text = await _recognize_images(images)

	if not text:
		text = "❌ Не удалось распознать текст."

	await message.edit(
		text,
		parse_mode=None,
	)


@Client.on_message(
	filters.me
	& (filters.photo | filters.document)
	& filters.command("ocr", prefixes="."),
)
async def ocr_attachment_command(client: Client, message: Message) -> None:
	logger.info("OCR attachment command received")

	images = await _get_image_messages(message)

	if not images:
		await message.edit_caption(
			"❌ Поддерживаются только PNG, JPG, JPEG и WEBP.",
			parse_mode=None,
		)
		return

	await message.edit_caption(
		"🔄 Распознавание...",
		parse_mode=None,
	)

	text = await _recognize_images(images)

	if not text:
		text = "❌ Не удалось распознать текст."

	await message.edit_caption(
		text,
		parse_mode=None,
	)

