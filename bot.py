import asyncio
import logging
import os

import aiosqlite
from aiogram import Bot, Dispatcher

from config import load_config
from db import init_db
from handlers import setup_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()

    # Ensure data directories exist
    os.makedirs(config.data_dir, exist_ok=True)
    if config.download_media:
        os.makedirs(config.media_dir, exist_ok=True)

    # Initialize database
    db = await init_db(str(config.db_path))
    logger.info("Database initialized at %s", config.db_path)

    # Setup bot and dispatcher
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    # Inject dependencies via aiogram DI
    dp["db"] = db
    dp["config"] = config

    # Register handlers
    router = setup_router(config.allowed_chat_ids)
    dp.include_router(router)

    # Shutdown hook
    async def on_shutdown() -> None:
        logger.info("Shutting down, closing database...")
        await db.close()

    dp.shutdown.register(on_shutdown)

    # Start polling
    me = await bot.get_me()
    if config.allowed_chat_ids:
        logger.info("Bot @%s started. Logging chats: %s", me.username,
                    ", ".join(str(c) for c in sorted(config.allowed_chat_ids)))
    else:
        logger.info("Bot @%s started. Logging messages from all chats.", me.username)
    logger.info("Download media: %s", config.download_media)

    # With privacy mode on, a group bot only receives commands addressed to it —
    # it stays up, logs nothing, and looks perfectly healthy. Say so out loud.
    if not me.can_read_all_group_messages:
        logger.warning(
            "Privacy mode is ON: this bot will NOT see ordinary group messages. "
            "Fix in @BotFather: /setprivacy -> select @%s -> Disable, "
            "then remove and re-add the bot to the group.", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
