import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import aiosqlite

from config import Config
from db import init_db
from handlers import (
    setup_router, _extract_forward_info, _extract_media_meta, _sanitize_filename,
    _with_group,
)


@pytest_asyncio.fixture
async def db():
    conn = await init_db(":memory:")
    yield conn
    await conn.close()


@pytest.fixture
def config(tmp_path):
    return Config(
        bot_token="test_token",
        download_media=False,
        data_dir=tmp_path,
    )


def _make_chat(chat_id=-1001, title="Test Group", chat_type="supergroup"):
    chat = MagicMock()
    chat.id = chat_id
    chat.title = title
    chat.type = chat_type
    return chat


def _make_user(user_id=100, username="testuser", first_name="Test", last_name="User"):
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.first_name = first_name
    user.last_name = last_name
    user.full_name = f"{first_name} {last_name}"
    return user


def _make_message(
    text=None,
    chat=None,
    from_user=None,
    message_id=1,
    content_type="text",
    reply_to_message=None,
    forward_origin=None,
    photo=None,
    video=None,
    document=None,
    audio=None,
    voice=None,
    video_note=None,
    sticker=None,
    animation=None,
    caption=None,
    new_chat_members=None,
    left_chat_member=None,
    new_chat_title=None,
    pinned_message=None,
    media_group_id=None,
):
    msg = MagicMock(spec=[
        "text", "chat", "from_user", "message_id", "content_type",
        "date", "reply_to_message", "forward_origin",
        "photo", "video", "document", "audio", "voice",
        "video_note", "sticker", "animation", "caption",
        "new_chat_members", "left_chat_member", "new_chat_title",
        "pinned_message", "media_group_id", "bot",
    ])
    msg.text = text
    msg.chat = chat or _make_chat()
    msg.from_user = from_user if from_user is not None else _make_user()
    msg.message_id = message_id
    msg.content_type = content_type
    msg.date = datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc)
    msg.reply_to_message = reply_to_message
    msg.forward_origin = forward_origin
    msg.photo = photo
    msg.video = video
    msg.document = document
    msg.audio = audio
    msg.voice = voice
    msg.video_note = video_note
    msg.sticker = sticker
    msg.animation = animation
    msg.caption = caption
    msg.new_chat_members = new_chat_members
    msg.left_chat_member = left_chat_member
    msg.new_chat_title = new_chat_title
    msg.pinned_message = pinned_message
    msg.media_group_id = media_group_id
    msg.bot = AsyncMock()
    return msg


# --- _extract_forward_info tests ---

def test_extract_forward_info_none():
    msg = _make_message(forward_origin=None)
    fwd_from, fwd_name = _extract_forward_info(msg)
    assert fwd_from is None
    assert fwd_name is None


def test_extract_forward_info_user():
    from aiogram.types import MessageOriginUser
    user = _make_user(user_id=200, first_name="Fwd", last_name="User")
    origin = MagicMock(spec=MessageOriginUser)
    origin.sender_user = user
    msg = _make_message(forward_origin=origin)
    fwd_from, fwd_name = _extract_forward_info(msg)
    assert fwd_from == 200
    assert fwd_name == "Fwd User"


def test_extract_forward_info_hidden_user():
    from aiogram.types import MessageOriginHiddenUser
    origin = MagicMock(spec=MessageOriginHiddenUser)
    origin.sender_user_name = "Hidden Person"
    msg = _make_message(forward_origin=origin)
    fwd_from, fwd_name = _extract_forward_info(msg)
    assert fwd_from is None
    assert fwd_name == "Hidden Person"


def test_extract_forward_info_chat():
    from aiogram.types import MessageOriginChat
    chat = MagicMock()
    chat.id = -5001
    chat.title = "Some Chat"
    origin = MagicMock(spec=MessageOriginChat)
    origin.sender_chat = chat
    msg = _make_message(forward_origin=origin)
    fwd_from, fwd_name = _extract_forward_info(msg)
    assert fwd_from == -5001
    assert fwd_name == "Some Chat"


def test_extract_forward_info_channel():
    from aiogram.types import MessageOriginChannel
    chat = MagicMock()
    chat.id = -6001
    chat.title = "News Channel"
    origin = MagicMock(spec=MessageOriginChannel)
    origin.chat = chat
    msg = _make_message(forward_origin=origin)
    fwd_from, fwd_name = _extract_forward_info(msg)
    assert fwd_from == -6001
    assert fwd_name == "News Channel"


# --- _extract_media_meta tests ---

def test_extract_media_meta_photo():
    from aiogram.enums import ContentType
    photo_size = MagicMock()
    photo_size.file_id = "photo_123"
    photo_size.file_size = 50000
    photo_size.width = 1920
    photo_size.height = 1080
    msg = _make_message(content_type=ContentType.PHOTO, photo=[photo_size])
    file_id, meta, msg_type = _extract_media_meta(msg)
    assert file_id == "photo_123"
    assert meta["size"] == 50000
    assert meta["width"] == 1920
    assert msg_type == "photo"


def test_extract_media_meta_document():
    from aiogram.enums import ContentType
    doc = MagicMock()
    doc.file_id = "doc_456"
    doc.file_size = 100000
    doc.mime_type = "application/pdf"
    doc.file_name = "report.pdf"
    msg = _make_message(content_type=ContentType.DOCUMENT, document=doc)
    file_id, meta, msg_type = _extract_media_meta(msg)
    assert file_id == "doc_456"
    assert meta["mime"] == "application/pdf"
    assert meta["name"] == "report.pdf"
    assert msg_type == "document"


def test_extract_media_meta_sticker():
    from aiogram.enums import ContentType
    sticker = MagicMock()
    sticker.file_id = "sticker_789"
    sticker.emoji = "😀"
    sticker.set_name = "HappyPack"
    sticker.width = 512
    sticker.height = 512
    msg = _make_message(content_type=ContentType.STICKER, sticker=sticker)
    file_id, meta, msg_type = _extract_media_meta(msg)
    assert file_id == "sticker_789"
    assert meta["emoji"] == "😀"
    assert msg_type == "sticker"


# --- Handler integration tests (using db directly) ---

@pytest.mark.asyncio
async def test_text_message_logged(db, config):
    """Simulate what the text handler does."""
    from db import upsert_chat, upsert_user, insert_message

    msg = _make_message(text="Hello world")

    # Simulate handler logic
    await upsert_chat(db, msg.chat.id, msg.chat.title, msg.chat.type)
    await upsert_user(db, msg.from_user.id, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)
    await insert_message(
        db, msg_id=msg.message_id, chat_id=msg.chat.id,
        user_id=msg.from_user.id, date=msg.date.isoformat(),
        msg_type="text", text=msg.text,
    )

    # Verify
    cursor = await db.execute("SELECT text, type FROM messages WHERE msg_id = 1")
    row = await cursor.fetchone()
    assert row[0] == "Hello world"
    assert row[1] == "text"

    cursor = await db.execute("SELECT title FROM chats WHERE chat_id = ?", (msg.chat.id,))
    row = await cursor.fetchone()
    assert row[0] == "Test Group"

    cursor = await db.execute("SELECT username FROM users WHERE user_id = ?", (msg.from_user.id,))
    row = await cursor.fetchone()
    assert row[0] == "testuser"


@pytest.mark.asyncio
async def test_media_message_meta_logged(db, config):
    """Simulate what the media handler does for a photo."""
    from aiogram.enums import ContentType
    from db import upsert_chat, upsert_user, insert_message

    photo_size = MagicMock()
    photo_size.file_id = "photo_abc"
    photo_size.file_size = 99000
    photo_size.width = 800
    photo_size.height = 600

    msg = _make_message(
        content_type=ContentType.PHOTO,
        photo=[photo_size],
        caption="Nice photo!",
    )

    file_id, meta, msg_type = _extract_media_meta(msg)

    await upsert_chat(db, msg.chat.id, msg.chat.title, msg.chat.type)
    await upsert_user(db, msg.from_user.id, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)
    await insert_message(
        db, msg_id=msg.message_id, chat_id=msg.chat.id,
        user_id=msg.from_user.id, date=msg.date.isoformat(),
        msg_type=msg_type, text=msg.caption,
        media_file_id=file_id, media_meta=meta,
    )

    cursor = await db.execute("SELECT type, text, media_file_id, media_meta FROM messages")
    row = await cursor.fetchone()
    assert row[0] == "photo"
    assert row[1] == "Nice photo!"
    assert row[2] == "photo_abc"
    parsed = json.loads(row[3])
    assert parsed["size"] == 99000


@pytest.mark.asyncio
async def test_message_with_from_user_none(db, config):
    """Channel posts have no from_user — should not crash."""
    from db import upsert_chat, insert_message

    msg = _make_message(text="Channel announcement")
    msg.from_user = None

    await upsert_chat(db, msg.chat.id, msg.chat.title, msg.chat.type)

    user_id = msg.from_user.id if msg.from_user else None
    await insert_message(
        db, msg_id=msg.message_id, chat_id=msg.chat.id,
        user_id=user_id, date=msg.date.isoformat(),
        msg_type="text", text=msg.text,
    )

    cursor = await db.execute("SELECT user_id, text FROM messages")
    row = await cursor.fetchone()
    assert row[0] is None
    assert row[1] == "Channel announcement"


@pytest.mark.asyncio
async def test_edited_message_has_is_edit_flag(db, config):
    """Edited messages should be logged with is_edit=True."""
    from db import upsert_chat, upsert_user, insert_message

    msg = _make_message(text="Corrected text")

    await upsert_chat(db, msg.chat.id, msg.chat.title, msg.chat.type)
    await upsert_user(db, msg.from_user.id, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)
    await insert_message(
        db, msg_id=msg.message_id, chat_id=msg.chat.id,
        user_id=msg.from_user.id, date=msg.date.isoformat(),
        msg_type="text", text=msg.text, is_edit=True,
    )

    cursor = await db.execute("SELECT is_edit, text FROM messages")
    row = await cursor.fetchone()
    assert row[0] == 1
    assert row[1] == "Corrected text"


@pytest.mark.asyncio
async def test_service_event_member_joined(db, config):
    """Member join event should be logged to events table."""
    from db import upsert_chat, upsert_user, insert_event

    new_member = _make_user(user_id=200, username="newguy", first_name="New", last_name="Guy")
    msg = _make_message(new_chat_members=[new_member])

    await upsert_chat(db, msg.chat.id, msg.chat.title, msg.chat.type)
    await upsert_user(db, new_member.id, new_member.username, new_member.first_name, new_member.last_name)
    await insert_event(
        db, chat_id=msg.chat.id, event_type="member_joined",
        date=msg.date.isoformat(), user_id=new_member.id,
        data={"username": new_member.username, "first_name": new_member.first_name},
    )

    cursor = await db.execute("SELECT type, user_id, data FROM events")
    row = await cursor.fetchone()
    assert row[0] == "member_joined"
    assert row[1] == 200
    parsed = json.loads(row[2])
    assert parsed["username"] == "newguy"


@pytest.mark.asyncio
async def test_setup_router_returns_router():
    """setup_router should return a Router instance."""
    from aiogram import Router
    router = setup_router()
    assert isinstance(router, Router)


# --- _with_group tests ---

def test_with_group_no_album_leaves_meta_alone():
    meta = {"size": 100}
    msg = _make_message(media_group_id=None)
    assert _with_group(meta, msg) is meta


def test_with_group_adds_album_id():
    msg = _make_message(media_group_id="13847290184")
    meta = _with_group({"size": 100}, msg)
    assert meta == {"size": 100, "group": "13847290184"}


def test_with_group_does_not_mutate_original():
    original = {"size": 100}
    msg = _make_message(media_group_id="13847290184")
    _with_group(original, msg)
    assert original == {"size": 100}


def test_with_group_handles_missing_meta():
    msg = _make_message(media_group_id="13847290184")
    assert _with_group(None, msg) == {"group": "13847290184"}


# --- Media download tests (through the real handler) ---

def _handler_by_name(router, name):
    for handler in router.message.handlers:
        if handler.callback.__name__ == name:
            return handler.callback
    raise AssertionError(f"handler {name} is not registered")


@pytest.mark.asyncio
async def test_downloaded_media_records_its_path(db, tmp_path):
    """Whatever reads this database later must not have to guess the filename."""
    from aiogram.enums import ContentType

    doc = MagicMock()
    doc.file_id = "doc_555"
    doc.file_size = 100000
    doc.mime_type = "application/pdf"
    doc.file_name = "Оплата.pdf"

    msg = _make_message(
        content_type=ContentType.DOCUMENT, document=doc, message_id=77,
        caption="оплата GULAMOV AZIZ по 26UZ041", media_group_id="1384729",
    )
    msg.bot.get_file.return_value.file_path = "documents/file_5.pdf"

    config = Config(bot_token="t", download_media=True, data_dir=tmp_path)
    on_media = _handler_by_name(setup_router(), "on_media")
    await on_media(msg, db, config)

    cursor = await db.execute("SELECT text, media_meta FROM messages WHERE msg_id = 77")
    text, meta_json = await cursor.fetchone()
    meta = json.loads(meta_json)
    assert text == "оплата GULAMOV AZIZ по 26UZ041"
    assert meta["group"] == "1384729"
    assert meta["path"] == str(tmp_path / "media" / "-1001_77_file_5.pdf")
    msg.bot.download_file.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_download_still_logs_the_message(db, tmp_path):
    """Telegram refuses files over 20 MB — the record must survive anyway."""
    from aiogram.enums import ContentType

    doc = MagicMock()
    doc.file_id = "doc_666"
    doc.file_size = 45_000_000
    doc.mime_type = "application/pdf"
    doc.file_name = "Договор.pdf"

    msg = _make_message(content_type=ContentType.DOCUMENT, document=doc, message_id=88)
    msg.bot.get_file.side_effect = Exception("file is too big")

    config = Config(bot_token="t", download_media=True, data_dir=tmp_path)
    on_media = _handler_by_name(setup_router(), "on_media")
    await on_media(msg, db, config)

    cursor = await db.execute(
        "SELECT media_file_id, media_meta FROM messages WHERE msg_id = 88")
    file_id, meta_json = await cursor.fetchone()
    meta = json.loads(meta_json)
    assert file_id == "doc_666"
    assert meta["name"] == "Договор.pdf"
    assert "path" not in meta          # no path == the file was never saved


@pytest.mark.asyncio
async def test_command_keeps_its_text(db, tmp_path):
    """The text handler skips commands, so they fall through to the catch-all.
    Store what was typed, not the name of the content type."""
    msg = _make_message(text="/start", message_id=1)

    config = Config(bot_token="t", download_media=False, data_dir=tmp_path)
    on_other = _handler_by_name(setup_router(), "on_other")
    await on_other(msg, db, config)

    cursor = await db.execute("SELECT type, text FROM messages WHERE msg_id = 1")
    msg_type, text = await cursor.fetchone()
    assert msg_type == "other"
    assert text == "/start"


# --- Chat allowlist tests ---

@pytest.mark.asyncio
async def test_no_allowlist_logs_every_chat():
    """Default behaviour must not change: no allowlist, no chat filter."""
    router = setup_router()
    passed, _ = await router.message.check_root_filters(_make_message())
    assert passed is True


@pytest.mark.asyncio
async def test_allowlist_passes_listed_chat():
    router = setup_router([-4228822135])
    msg = _make_message(chat=_make_chat(chat_id=-4228822135))
    passed, _ = await router.message.check_root_filters(msg)
    assert passed is True


@pytest.mark.asyncio
async def test_allowlist_blocks_other_chat():
    """A bot added to an unrelated group must not quietly collect it."""
    router = setup_router([-4228822135])
    msg = _make_message(chat=_make_chat(chat_id=-1009999999))
    passed, _ = await router.message.check_root_filters(msg)
    assert passed is False


@pytest.mark.asyncio
async def test_allowlist_applies_to_edited_messages_too():
    router = setup_router([-4228822135])
    allowed = _make_message(chat=_make_chat(chat_id=-4228822135))
    other = _make_message(chat=_make_chat(chat_id=-1009999999))
    assert (await router.edited_message.check_root_filters(allowed))[0] is True
    assert (await router.edited_message.check_root_filters(other))[0] is False


# --- _sanitize_filename tests ---

def test_sanitize_filename_normal():
    assert _sanitize_filename("photo.jpg") == "photo.jpg"


def test_sanitize_filename_with_path():
    assert _sanitize_filename("photos/file_123.jpg") == "file_123.jpg"


def test_sanitize_filename_with_dots_traversal():
    assert _sanitize_filename("../../etc/passwd") == "passwd"


def test_sanitize_filename_with_special_chars():
    result = _sanitize_filename("file name (1).jpg")
    assert "/" not in result
    assert ".." not in result
