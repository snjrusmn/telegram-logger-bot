import json
from typing import Optional

import aiosqlite

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    type TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id),
    user_id INTEGER REFERENCES users(user_id),
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT,
    media_file_id TEXT,
    media_meta TEXT,
    reply_to INTEGER,
    fwd_from INTEGER,
    fwd_name TEXT,
    is_edit INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id),
    user_id INTEGER,
    type TEXT NOT NULL,
    data TEXT,
    date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_msg_chat ON messages(msg_id, chat_id);
CREATE INDEX IF NOT EXISTS idx_events_chat_date ON events(chat_id, date);
"""


async def init_db(db_path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.executescript(SCHEMA_SQL)
    await db.commit()
    return db


async def upsert_chat(
    db: aiosqlite.Connection,
    chat_id: int,
    title: Optional[str],
    chat_type: Optional[str],
) -> None:
    await db.execute(
        """INSERT INTO chats (chat_id, title, type, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(chat_id) DO UPDATE SET
               title = excluded.title,
               type = excluded.type,
               updated_at = datetime('now')""",
        (chat_id, title, chat_type),
    )


async def upsert_user(
    db: aiosqlite.Connection,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> None:
    await db.execute(
        """INSERT INTO users (user_id, username, first_name, last_name, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
               username = excluded.username,
               first_name = excluded.first_name,
               last_name = excluded.last_name,
               updated_at = datetime('now')""",
        (user_id, username, first_name, last_name),
    )


async def insert_message(
    db: aiosqlite.Connection,
    msg_id: int,
    chat_id: int,
    user_id: Optional[int],
    date: str,
    msg_type: str,
    text: Optional[str] = None,
    media_file_id: Optional[str] = None,
    media_meta: Optional[dict] = None,
    reply_to: Optional[int] = None,
    fwd_from: Optional[int] = None,
    fwd_name: Optional[str] = None,
    is_edit: bool = False,
) -> None:
    meta_json = None
    if media_meta:
        # Only include non-null fields to save space
        meta_json = json.dumps(
            {k: v for k, v in media_meta.items() if v is not None},
            ensure_ascii=False,
        )

    await db.execute(
        """INSERT INTO messages
           (msg_id, chat_id, user_id, date, type, text, media_file_id,
            media_meta, reply_to, fwd_from, fwd_name, is_edit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            msg_id, chat_id, user_id, date, msg_type, text,
            media_file_id, meta_json, reply_to, fwd_from, fwd_name,
            1 if is_edit else 0,
        ),
    )


async def insert_event(
    db: aiosqlite.Connection,
    chat_id: int,
    event_type: str,
    date: str,
    user_id: Optional[int] = None,
    data: Optional[dict] = None,
) -> None:
    data_json = None
    if data:
        data_json = json.dumps(data, ensure_ascii=False)

    await db.execute(
        """INSERT INTO events (chat_id, user_id, type, data, date)
           VALUES (?, ?, ?, ?, ?)""",
        (chat_id, user_id, event_type, data_json, date),
    )


async def commit(db: aiosqlite.Connection) -> None:
    """Commit all pending changes. Call once after all operations for a message."""
    await db.commit()
