import json
import time

import pytest

from health import (
    STALE_AFTER, age, health_path, is_stale, read_health, write_health,
)


def test_health_path_sits_next_to_the_database(tmp_path):
    assert health_path(tmp_path) == tmp_path / "health.json"


def test_write_then_read_roundtrip(tmp_path):
    path = health_path(tmp_path)
    write_health(path, {"ts": 1000.0, "telegram_ok": True})
    assert read_health(path) == {"ts": 1000.0, "telegram_ok": True}


def test_write_creates_missing_directory(tmp_path):
    path = tmp_path / "nested" / "health.json"
    write_health(path, {"ts": 1.0})
    assert read_health(path) == {"ts": 1.0}


def test_write_leaves_no_temp_file_behind(tmp_path):
    """The write is atomic via a temp file - it must not linger."""
    write_health(health_path(tmp_path), {"ts": 1.0})
    assert [p.name for p in tmp_path.iterdir()] == ["health.json"]


def test_read_missing_file_is_none(tmp_path):
    assert read_health(tmp_path / "nope.json") is None


def test_read_corrupt_file_is_none(tmp_path):
    path = health_path(tmp_path)
    path.write_text("{ this is not json", encoding="utf-8")
    assert read_health(path) is None


# --- is_stale: this decides whether the container is marked unhealthy ---

def test_missing_pulse_is_stale():
    """The bot writes a pulse at startup, so no file means it never got there."""
    assert is_stale(None) is True


def test_pulse_without_timestamp_is_stale():
    assert is_stale({"telegram_ok": True}) is True


def test_pulse_with_junk_timestamp_is_stale():
    assert is_stale({"ts": "just now"}) is True


def test_fresh_pulse_is_not_stale():
    now = 10_000.0
    assert is_stale({"ts": now - 5}, now=now) is False


def test_pulse_just_inside_the_threshold_is_not_stale():
    now = 10_000.0
    assert is_stale({"ts": now - (STALE_AFTER - 1)}, now=now) is False


def test_pulse_past_the_threshold_is_stale():
    now = 10_000.0
    assert is_stale({"ts": now - (STALE_AFTER + 1)}, now=now) is True


def test_unreachable_telegram_does_not_make_the_pulse_stale():
    """The whole point: an outage must not mark the bot dead. A watchdog that
    conflated the two restarted the neighbouring EZS bot 27 times in 40 minutes."""
    now = 10_000.0
    pulse = {"ts": now - 5, "telegram_ok": False,
             "last_ok": now - 3600, "last_error": "TelegramNetworkError: ..."}
    assert is_stale(pulse, now=now) is False


# --- age ---

def test_age_of_missing_health_is_none():
    assert age(None) is None


def test_age_of_absent_key_is_none():
    assert age({"ts": 1.0}, key="last_ok") is None


def test_age_counts_seconds_since_timestamp():
    assert age({"ts": 9_000.0}, now=10_000.0) == 1000.0


# --- healthcheck script: same decision, through the real entry point ---

def test_healthcheck_exits_zero_on_fresh_pulse(tmp_path, monkeypatch):
    import healthcheck
    write_health(health_path(tmp_path), {"ts": time.time()})
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert healthcheck.main() == 0


def test_healthcheck_exits_one_on_stale_pulse(tmp_path, monkeypatch):
    import healthcheck
    write_health(health_path(tmp_path), {"ts": time.time() - STALE_AFTER - 60})
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert healthcheck.main() == 1


def test_healthcheck_exits_one_when_pulse_missing(tmp_path, monkeypatch):
    import healthcheck
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert healthcheck.main() == 1


def test_healthcheck_stays_zero_while_telegram_is_down(tmp_path, monkeypatch):
    """An outage must never turn into an unhealthy container."""
    import healthcheck
    write_health(health_path(tmp_path), {
        "ts": time.time(), "telegram_ok": False,
        "last_error": "TelegramNetworkError: Cannot connect to host",
    })
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert healthcheck.main() == 0


# --- heartbeat loop ---

@pytest.mark.asyncio
async def test_heartbeat_writes_a_pulse_immediately(tmp_path, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    import health as health_mod

    monkeypatch.setattr(health_mod, "BEAT_INTERVAL", 0.01)
    bot = MagicMock()
    bot.get_me = AsyncMock(return_value=MagicMock())

    path = health_path(tmp_path)
    task = asyncio.create_task(health_mod.heartbeat(bot, path))
    await asyncio.sleep(0.05)
    task.cancel()

    pulse = read_health(path)
    assert pulse is not None
    assert pulse["telegram_ok"] is True
    assert pulse["last_ok"] is not None
    assert is_stale(pulse) is False


@pytest.mark.asyncio
async def test_heartbeat_keeps_beating_when_telegram_fails(tmp_path, monkeypatch):
    """A failed ping is recorded, not fatal - the bot is alive and retrying."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    import health as health_mod

    monkeypatch.setattr(health_mod, "BEAT_INTERVAL", 0.01)
    bot = MagicMock()
    bot.get_me = AsyncMock(side_effect=Exception("Cannot connect to host"))

    path = health_path(tmp_path)
    task = asyncio.create_task(health_mod.heartbeat(bot, path))
    await asyncio.sleep(0.05)
    task.cancel()

    pulse = read_health(path)
    assert pulse["telegram_ok"] is False
    assert "Cannot connect to host" in pulse["last_error"]
    assert is_stale(pulse) is False          # still alive
