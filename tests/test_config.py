import os
from pathlib import Path

import pytest

from config import load_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove BOT_TOKEN from env before each test."""
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("DOWNLOAD_MEDIA", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)


def test_missing_bot_token_raises(monkeypatch):
    with pytest.raises(ValueError, match="BOT_TOKEN is required"):
        load_config(env_path="/dev/null")


def test_bot_token_loaded(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test_token_123")
    cfg = load_config(env_path="/dev/null")
    assert cfg.bot_token == "test_token_123"


@pytest.mark.parametrize("value,expected", [
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("1", True),
    ("yes", True),
    ("false", False),
    ("False", False),
    ("0", False),
    ("no", False),
    ("", False),
])
def test_download_media_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DOWNLOAD_MEDIA", value)
    cfg = load_config(env_path="/dev/null")
    assert cfg.download_media is expected


def test_download_media_default(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    cfg = load_config(env_path="/dev/null")
    assert cfg.download_media is False


def test_data_dir_default(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    cfg = load_config(env_path="/dev/null")
    assert cfg.data_dir == Path("./data")


def test_data_dir_custom(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DATA_DIR", "/tmp/custom")
    cfg = load_config(env_path="/dev/null")
    assert cfg.data_dir == Path("/tmp/custom")


def test_db_path_property(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    cfg = load_config(env_path="/dev/null")
    assert cfg.db_path == Path("./data/logger.db")


def test_media_dir_property(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    cfg = load_config(env_path="/dev/null")
    assert cfg.media_dir == Path("./data/media")
