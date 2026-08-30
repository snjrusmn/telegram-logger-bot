"""Pulse file: evidence that the bot is actually running, not merely present.

A container reporting "Up" only proves a process exists. It says nothing about
whether the polling loop is alive - a bot can sit there wedged forever while
docker keeps reporting it as healthy, and nobody finds out until someone goes
looking for messages that were never collected.

So the bot keeps a file fresh. It can only do that while its event loop runs,
which makes a stale file a reliable sign of a dead bot.

Reachability of Telegram is recorded here too, but deliberately kept separate
from liveness: an outage is not a reason to call the bot broken. See
healthcheck.py for why that distinction matters.
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

BEAT_INTERVAL = 60          # seconds between pulse writes
TELEGRAM_PING_EVERY = 5     # ping Telegram once every N beats, so every 5 minutes
STALE_AFTER = 300           # a pulse older than this means the bot is not running


def health_path(data_dir) -> Path:
    return Path(data_dir) / "health.json"


def write_health(path, payload: Dict[str, Any]) -> None:
    """Write the pulse atomically: a reader must never catch a half-written file
    and mistake it for a dead bot."""
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        logger.exception("Could not write the pulse file at %s", path)


def read_health(path) -> Optional[dict]:
    """Parsed pulse file, or None if it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def is_stale(health: Optional[dict], now: Optional[float] = None,
             stale_after: int = STALE_AFTER) -> bool:
    """True when the pulse is missing, malformed or too old.

    A missing file counts as stale: at startup the bot writes one immediately,
    so its absence means the bot never got that far.
    """
    if not health:
        return True
    ts = health.get("ts")
    if not isinstance(ts, (int, float)):
        return True
    return (now if now is not None else time.time()) - ts > stale_after


def age(health: Optional[dict], key: str = "ts", now: Optional[float] = None):
    """Seconds since the given timestamp, or None if it is absent."""
    if not health:
        return None
    ts = health.get(key)
    if not isinstance(ts, (int, float)):
        return None
    return (now if now is not None else time.time()) - ts


async def heartbeat(bot, path) -> None:
    """Write the pulse every BEAT_INTERVAL seconds for as long as the bot runs.

    Telegram is pinged only every few beats, and a failed ping is recorded
    without interrupting the pulse: the bot is still alive and will keep
    retrying, and marking it dead over a network blip is how you end up
    restarting a perfectly healthy process.
    """
    started_at = time.time()
    telegram_ok: Optional[bool] = None
    last_ok: Optional[float] = None
    last_error: Optional[str] = None
    beat = 0

    while True:
        if beat % TELEGRAM_PING_EVERY == 0:
            try:
                await bot.get_me()
                telegram_ok, last_ok, last_error = True, time.time(), None
            except Exception as e:                      # noqa: BLE001 - never fatal
                telegram_ok = False
                last_error = f"{type(e).__name__}: {e}"[:300]

        write_health(path, {
            "ts": time.time(),
            "started_at": started_at,
            "pid": os.getpid(),
            "telegram_ok": telegram_ok,
            "last_ok": last_ok,
            "last_error": last_error,
        })
        beat += 1
        await asyncio.sleep(BEAT_INTERVAL)
