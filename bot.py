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
    router = setup_router()
    dp.include_router(router)

    # Shutdown hook
    async def on_shutdown() -> None:
        logger.info("Shutting down, closing database...")
        await db.close()

    dp.shutdown.register(on_shutdown)

    # Start polling
    logger.info("Bot started. Logging messages from all chats.")
    logger.info("Download media: %s", config.download_media)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
