import asyncio
import logging
import os

import aiosqlite
from aiogram import Bot, Dispatcher

from config import load_config
from db import init_db
from handlers import setup_router
from health import health_path, heartbeat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Seconds to wait before restarting polling after an error. Long enough that an hour
# of Telegram being down costs 120 log lines, short enough to come back promptly.
POLL_RETRY_DELAY = 30


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

    # The database is closed in the finally block below, not from a dispatcher
    # shutdown hook: polling can stop and be retried several times in one run, and
    # closing the database on the first stop would leave the retries writing to a
    # closed connection.

    # Start polling.
    # Startup diagnostics must never stop the bot from starting. If Telegram is
    # unreachable right now, the polling loop below retries on its own, so a failed
    # get_me() is a reason to log and move on. Letting it raise here is worse than
    # it looks: main() unwinds while the aiohttp session and its DNS resolver thread
    # are still open, asyncio.run() then blocks forever waiting for that thread, and
    # the container keeps reporting "running" with a bot that will never poll.
    try:
        me = await bot.get_me()
    except Exception:
        logger.exception("Could not reach Telegram at startup; polling will keep retrying")
        me = None

    chats = (", ".join(str(c) for c in sorted(config.allowed_chat_ids))
             if config.allowed_chat_ids else "all chats")
    logger.info("Bot @%s started. Logging: %s", me.username if me else "unknown", chats)
    logger.info("Download media: %s", config.download_media)

    # With privacy mode on, a group bot only receives commands addressed to it —
    # it stays up, logs nothing, and looks perfectly healthy. Say so out loud.
    if me is not None and not me.can_read_all_group_messages:
        logger.warning(
            "Privacy mode is ON: this bot will NOT see ordinary group messages. "
            "Fix in @BotFather: /setprivacy -> select @%s -> Disable, "
            "then remove and re-add the bot to the group.", me.username)
    # Telegram being unreachable must not end the process. aiogram retries while it
    # is polling, but a failure during polling *startup* propagates out - and exiting
    # here would hand the restart loop to docker. That is how the neighbouring EZS bot
    # collected 27 restarts in 40 minutes on 19.08.2026: an unreachable Telegram was
    # treated as a dead process. Retry in place instead, at a pace that does not flood
    # the log, and let the container keep running.
    # The pulse runs alongside polling, so a wedged bot stops looking healthy.
    pulse = asyncio.create_task(heartbeat(bot, health_path(config.data_dir)))

    try:
        while True:
            try:
                await dp.start_polling(bot)
                break                      # stopped on purpose (signal), not an error
            except Exception:
                logger.exception("Polling stopped on error, retrying in %d s", POLL_RETRY_DELAY)
                await asyncio.sleep(POLL_RETRY_DELAY)
    finally:
        pulse.cancel()
        logger.info("Shutting down, closing database...")
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
