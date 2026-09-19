import logging

from hydrogram import Client, filters
from hydrogram.types import Message


logger = logging.getLogger(__name__)


@Client.on_message(
	filters.incoming & filters.group & filters.new_chat_members
)
async def handle_new_user(client: Client, message: Message) -> None:
	logger.info("New user in group - ...")
