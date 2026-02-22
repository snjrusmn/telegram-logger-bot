import json

import pytest
import pytest_asyncio
import aiosqlite

from db import init_db, upsert_chat, upsert_user, insert_message, insert_event, commit


@pytest_asyncio.fixture
async def db():
    """Create an in-memory SQLite database for testing."""
    conn = await init_db(":memory:")
    yield conn
    await conn.close()


# --- init_db tests ---

@pytest.mark.asyncio
async def test_init_db_creates_all_tables(db):
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in await cursor.fetchall()]
    assert "chats" in tables
    assert "users" in tables
    assert "messages" in tables
    assert "events" in tables


@pytest.mark.asyncio
async def test_init_db_wal_mode(db):
    cursor = await db.execute("PRAGMA journal_mode")
    row = await cursor.fetchone()
    # In-memory databases may report "memory" instead of "wal"
    assert row[0] in ("wal", "memory")


@pytest.mark.asyncio
async def test_init_db_creates_indexes(db):
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    indexes = [row[0] for row in await cursor.fetchall()]
    assert "idx_messages_chat_date" in indexes
    assert "idx_messages_user" in indexes
    assert "idx_messages_msg_chat" in indexes
    assert "idx_events_chat_date" in indexes


# --- upsert_chat tests ---

@pytest.mark.asyncio
async def test_upsert_chat_insert(db):
    await upsert_chat(db, chat_id=-1001, title="Test Group", chat_type="supergroup")
    cursor = await db.execute("SELECT * FROM chats WHERE chat_id = -1001")
    row = await cursor.fetchone()
    assert row[0] == -1001
    assert row[1] == "Test Group"
    assert row[2] == "supergroup"
    assert row[3] is not None  # updated_at


@pytest.mark.asyncio
async def test_upsert_chat_update(db):
    await upsert_chat(db, chat_id=-1001, title="Old Name", chat_type="group")
    await upsert_chat(db, chat_id=-1001, title="New Name", chat_type="supergroup")
    cursor = await db.execute("SELECT title, type FROM chats WHERE chat_id = -1001")
    row = await cursor.fetchone()
    assert row[0] == "New Name"
    assert row[1] == "supergroup"


# --- upsert_user tests ---

@pytest.mark.asyncio
async def test_upsert_user_insert(db):
    await upsert_user(db, user_id=100, username="testuser", first_name="Test", last_name="User")
    cursor = await db.execute("SELECT * FROM users WHERE user_id = 100")
    row = await cursor.fetchone()
    assert row[0] == 100
    assert row[1] == "testuser"
    assert row[2] == "Test"
    assert row[3] == "User"


@pytest.mark.asyncio
async def test_upsert_user_update(db):
    await upsert_user(db, user_id=100, username="old", first_name="Old", last_name="Name")
    await upsert_user(db, user_id=100, username="new", first_name="New", last_name="Name")
    cursor = await db.execute("SELECT username, first_name FROM users WHERE user_id = 100")
    row = await cursor.fetchone()
    assert row[0] == "new"
    assert row[1] == "New"


# --- insert_message tests ---

@pytest.mark.asyncio
async def test_insert_message_text(db):
    await upsert_chat(db, -1001, "Chat", "group")
    await upsert_user(db, 100, "user", "First", "Last")
    await insert_message(
        db, msg_id=1, chat_id=-1001, user_id=100,
        date="2026-02-22T10:00:00", msg_type="text", text="Hello world",
    )
    cursor = await db.execute("SELECT * FROM messages WHERE msg_id = 1")
    row = await cursor.fetchone()
    assert row[1] == 1       # msg_id
    assert row[2] == -1001   # chat_id
    assert row[3] == 100     # user_id
    assert row[5] == "text"  # type
    assert row[6] == "Hello world"  # text
    assert row[12] == 0      # is_edit


@pytest.mark.asyncio
async def test_insert_message_with_user_id_none(db):
    """Channel posts may have no from_user."""
    await upsert_chat(db, -1001, "Channel", "channel")
    await insert_message(
        db, msg_id=1, chat_id=-1001, user_id=None,
        date="2026-02-22T10:00:00", msg_type="text", text="Channel post",
    )
    cursor = await db.execute("SELECT user_id FROM messages WHERE msg_id = 1")
    row = await cursor.fetchone()
    assert row[0] is None


@pytest.mark.asyncio
async def test_insert_message_with_media_meta(db):
    await upsert_chat(db, -1001, "Chat", "group")
    await upsert_user(db, 100, "user", "First", "Last")
    meta = {"size": 12345, "mime": "image/jpeg", "width": 800, "height": 600}
    await insert_message(
        db, msg_id=2, chat_id=-1001, user_id=100,
        date="2026-02-22T10:00:00", msg_type="photo",
        text="Caption", media_file_id="abc123", media_meta=meta,
    )
    cursor = await db.execute("SELECT media_file_id, media_meta FROM messages WHERE msg_id = 2")
    row = await cursor.fetchone()
    assert row[0] == "abc123"
    parsed = json.loads(row[1])
    assert parsed["size"] == 12345
    assert parsed["mime"] == "image/jpeg"


@pytest.mark.asyncio
async def test_insert_message_media_meta_strips_nulls(db):
    await upsert_chat(db, -1001, "Chat", "group")
    meta = {"size": 100, "mime": "video/mp4", "name": None, "duration": 30}
    await insert_message(
        db, msg_id=3, chat_id=-1001, user_id=None,
        date="2026-02-22T10:00:00", msg_type="video", media_meta=meta,
    )
    cursor = await db.execute("SELECT media_meta FROM messages WHERE msg_id = 3")
    row = await cursor.fetchone()
    parsed = json.loads(row[0])
    assert "name" not in parsed
    assert parsed["duration"] == 30


@pytest.mark.asyncio
async def test_insert_message_edit(db):
    await upsert_chat(db, -1001, "Chat", "group")
    await insert_message(
        db, msg_id=1, chat_id=-1001, user_id=None,
        date="2026-02-22T10:00:00", msg_type="text", text="Edited text",
        is_edit=True,
    )
    cursor = await db.execute("SELECT is_edit FROM messages WHERE msg_id = 1")
    row = await cursor.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_insert_message_with_reply_and_forward(db):
    await upsert_chat(db, -1001, "Chat", "group")
    await insert_message(
        db, msg_id=5, chat_id=-1001, user_id=None,
        date="2026-02-22T10:00:00", msg_type="text", text="Reply",
        reply_to=3, fwd_from=200, fwd_name="Forwarded User",
    )
    cursor = await db.execute(
        "SELECT reply_to, fwd_from, fwd_name FROM messages WHERE msg_id = 5"
    )
    row = await cursor.fetchone()
    assert row[0] == 3
    assert row[1] == 200
    assert row[2] == "Forwarded User"


# --- insert_event tests ---

@pytest.mark.asyncio
async def test_insert_event(db):
    await upsert_chat(db, -1001, "Chat", "group")
    await insert_event(
        db, chat_id=-1001, event_type="member_joined",
        date="2026-02-22T10:00:00", user_id=100,
        data={"username": "newuser"},
    )
    cursor = await db.execute("SELECT * FROM events")
    row = await cursor.fetchone()
    assert row[1] == -1001          # chat_id
    assert row[2] == 100            # user_id
    assert row[3] == "member_joined"  # type
    parsed = json.loads(row[4])
    assert parsed["username"] == "newuser"


@pytest.mark.asyncio
async def test_insert_event_without_data(db):
    await upsert_chat(db, -1001, "Chat", "group")
    await insert_event(
        db, chat_id=-1001, event_type="member_left",
        date="2026-02-22T10:00:00", user_id=100,
    )
    cursor = await db.execute("SELECT data FROM events")
    row = await cursor.fetchone()
    assert row[0] is None
