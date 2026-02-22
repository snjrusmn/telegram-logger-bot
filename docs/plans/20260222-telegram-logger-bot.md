# Telegram Logger Bot

## Overview
- Автономный Telegram-бот для молчаливого логирования всех событий в групповых чатах
- Записывает сообщения, медиа-метаданные, сервисные события в SQLite
- Оптимизированная нормализованная БД для использования другими AI/нейросетями (минимум токенов)
- Open-source проект на GitHub с лицензией Apache 2.0

## Prerequisites
- **ВАЖНО:** Перед использованием бота необходимо отключить Privacy Mode через @BotFather → `/setprivacy` → `Disable`. Без этого бот видит только команды (/), упоминания и ответы на свои сообщения.

## Context (from discovery)
- **Проект пустой** — начинаем с нуля
- **Расположение:** `/Users/sanjarusmanov/Documents/AI_PROJECTS/TG-BOT-Logger/`
- **Стек:** Python 3.11+ · aiogram 3.x · aiosqlite · python-dotenv
- **GitHub name:** `telegram-logger-bot`

## Development Approach
- **testing approach**: Regular (code first, базовые тесты для db, config, handlers)
- complete each task fully before moving to the next
- make small, focused changes
- aiogram 3.x DI pattern: передаём db и config через `dp["db"]`, `dp["config"]`
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**

## Testing Strategy
- **unit tests**: pytest + pytest-asyncio + aiosqlite in-memory DB для db.py
- **integration tests**: mock aiogram message objects для handlers.py
- Тестовая команда: `python -m pytest tests/ -v`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with + prefix
- document issues/blockers with !! prefix
- update plan if implementation deviates from original scope

## Implementation Steps

### Task 1: Project scaffolding + git init

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] `git init` — инициализировать репозиторий сразу
- [ ] create `requirements.txt` with: aiogram>=3.4, aiosqlite>=0.20, python-dotenv>=1.0, pytest>=8.0, pytest-asyncio>=0.23
- [ ] create `.env.example` with: BOT_TOKEN, DOWNLOAD_MEDIA=false, DATA_DIR=./data
- [ ] create `.gitignore` (Python defaults + .env, data/, *.db)
- [ ] create `config.py` — load settings from .env using python-dotenv:
  - BOT_TOKEN (required, raise error if missing)
  - DOWNLOAD_MEDIA (bool, parse "true"/"false"/"1"/"0", default false)
  - DATA_DIR (path, default "./data")
- [ ] create `tests/__init__.py`
- [ ] write `tests/test_config.py`:
  - test missing BOT_TOKEN raises error
  - test DOWNLOAD_MEDIA parses bool correctly
  - test DATA_DIR defaults
- [ ] install dependencies: `pip install -r requirements.txt`
- [ ] run tests — must pass before Task 2

### Task 2: Database layer

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] create `db.py` with async functions using aiosqlite:
  - `init_db(db_path)` — create tables, enable WAL mode (`PRAGMA journal_mode=WAL`), create indexes
  - `upsert_chat(db, chat_id, title, type)` — INSERT OR REPLACE, explicitly set `updated_at = datetime('now')` in ON CONFLICT
  - `upsert_user(db, user_id, username, first_name, last_name)` — same pattern with explicit updated_at
  - `insert_message(db, **kwargs)` — insert message record (user_id can be NULL for channel posts)
  - `insert_event(db, **kwargs)` — insert event record
- [ ] SQL schema (4 tables):
  - `chats`: chat_id (PK), title, type, updated_at
  - `users`: user_id (PK), username, first_name, last_name, updated_at
  - `messages`: id (autoincrement), msg_id, chat_id (FK), user_id (FK, nullable), date, type, text, media_file_id, media_meta (JSON), reply_to, fwd_from, fwd_name, is_edit (bool), created_at
  - `events`: id (autoincrement), chat_id (FK), user_id, type, data (JSON), date, created_at
- [ ] create indexes: messages(chat_id, date), messages(user_id), messages(msg_id, chat_id), events(chat_id, date)
- [ ] write tests for init_db — verify all 4 tables created, WAL mode enabled (in-memory SQLite)
- [ ] write tests for upsert_chat, upsert_user — insert + update (verify updated_at changes)
- [ ] write tests for insert_message with user_id=None (channel post case)
- [ ] write tests for insert_event — verify data stored correctly
- [ ] run tests — must pass before Task 3

### Task 3: Message handlers

**Files:**
- Create: `handlers.py`
- Create: `tests/test_handlers.py`

- [ ] create `handlers.py` with aiogram Router:
  - handlers получают db и config через aiogram 3.x DI (keyword arguments: `db: aiosqlite.Connection, config: Config`)
  - `setup_router()` — создать и вернуть router со всеми зарегистрированными handlers
- [ ] implement text message handler `@router.message(F.text)`:
  - check `message.from_user` is not None before upsert_user (может быть None в каналах)
  - extract chat, user, text, reply_to
  - parse `message.forward_origin` (MessageOriginUser/Chat/HiddenUser/Channel) вместо старых forward_from полей
  - → upsert_chat, upsert_user (if not None), insert_message
- [ ] implement media handler `@router.message(F.content_type.in_({ContentType.PHOTO, ...}))`:
  - handle: photo, video, document, audio, voice, video_note, sticker, animation
  - extract media_meta JSON (file_id, size, mime, name, duration) — only non-null fields
  - caption as text
  - if config.DOWNLOAD_MEDIA: download file to DATA_DIR/media/
  - → upsert_chat, upsert_user, insert_message
- [ ] implement catch-all handler `@router.message()` (lowest priority):
  - for unknown message types (poll, location, contact, dice, etc.)
  - log as type="other", store content_type string in text field
- [ ] implement `@router.edited_message()` handler (SEPARATE from @router.message!):
  - same logic as text/media handlers but with is_edit=True
- [ ] implement service events handlers:
  - `F.new_chat_members` → insert_event(type="member_joined") for each member
  - `F.left_chat_member` → insert_event(type="member_left")
  - `F.new_chat_title` → insert_event(type="title_changed") + upsert_chat
  - `F.pinned_message` → insert_event(type="message_pinned")
- [ ] wrap all handlers in try/except — log errors to stderr, never lose silently. On DB error, log to stderr with message details for debugging
- [ ] write tests: mock Message object → verify correct db calls for text message
- [ ] write tests: mock Message with photo → verify media_meta extraction
- [ ] write tests: mock Message with from_user=None → verify no crash, user_id=None in DB
- [ ] write tests: mock edited_message → verify is_edit=True
- [ ] write tests: mock service event → verify event insertion
- [ ] run tests — must pass before Task 4

### Task 4: Bot entry point

**Files:**
- Create: `bot.py`

- [ ] create `bot.py`:
  - load config from config.py
  - init Bot + Dispatcher (aiogram 3.x)
  - inject dependencies: `dp["db"] = db`, `dp["config"] = config`
  - `on_startup`: call init_db, create data/ and data/media/ dirs if needed
  - `on_shutdown`: close db connection (`await db.close()`)
  - register router from handlers.py
  - start polling (long polling)
- [ ] run full test suite: `python -m pytest tests/ -v`
- [ ] run tests — must pass before Task 5

### Task 5: GitHub packaging

**Files:**
- Create: `LICENSE`
- Create: `README.md`

- [ ] create `LICENSE` — Apache 2.0, copyright 2026
- [ ] create `README.md`:
  - Project name + badges (Python, License, aiogram)
  - One-line description (EN + RU)
  - Features list
  - Prerequisites: BotFather privacy mode must be DISABLED
  - Quick start (4 steps: clone, .env, install, run)
  - Database schema overview (for AI consumers)
  - Example SQL queries for AI usage
  - Configuration options table (.env variables)
  - License section
- [ ] run tests — must pass before Task 6

### Task 6: Verify acceptance criteria
- [ ] verify: bot silently logs text messages from group chats
- [ ] verify: bot logs media metadata (photo, video, doc, audio, voice, sticker)
- [ ] verify: bot logs service events (join, leave, title change, pin)
- [ ] verify: bot handles edited messages (is_edit=True)
- [ ] verify: bot handles replies and forwards (forward_origin)
- [ ] verify: bot handles from_user=None without crash
- [ ] verify: DOWNLOAD_MEDIA toggle works
- [ ] verify: multiple chats logged simultaneously
- [ ] verify: database is AI-friendly (normalized, compact)
- [ ] verify: error in one handler doesn't crash the bot
- [ ] run full test suite: `python -m pytest tests/ -v`

### Task 7: [Final] Cleanup and publish
- [ ] git commit all work
- [ ] update README.md if needed after testing
- [ ] move this plan to `docs/plans/completed/`

## Technical Details

### Database Schema
```sql
PRAGMA journal_mode=WAL;

CREATE TABLE chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    type TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE messages (
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

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id),
    user_id INTEGER,
    type TEXT NOT NULL,
    data TEXT,
    date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_messages_chat_date ON messages(chat_id, date);
CREATE INDEX idx_messages_user ON messages(user_id);
CREATE INDEX idx_messages_msg_chat ON messages(msg_id, chat_id);
CREATE INDEX idx_events_chat_date ON events(chat_id, date);
```

### aiogram 3.x DI Pattern
```python
# bot.py
dp = Dispatcher()
dp["db"] = db_connection
dp["config"] = config

# handlers.py
@router.message(F.text)
async def on_text(message: Message, db: aiosqlite.Connection, config: Config):
    ...
```

### Config (.env)
| Variable | Default | Description |
|----------|---------|-------------|
| BOT_TOKEN | (required) | Telegram Bot API token from @BotFather |
| DOWNLOAD_MEDIA | false | Download media files to disk (true/false) |
| DATA_DIR | ./data | Directory for DB and media files |

### forward_origin Parsing
```python
# Вместо устаревших message.forward_from / forward_from_chat
origin = message.forward_origin
if isinstance(origin, MessageOriginUser):
    fwd_from = origin.sender_user.id
    fwd_name = origin.sender_user.full_name
elif isinstance(origin, MessageOriginHiddenUser):
    fwd_name = origin.sender_user_name
elif isinstance(origin, MessageOriginChat):
    fwd_from = origin.sender_chat.id
    fwd_name = origin.sender_chat.title
elif isinstance(origin, MessageOriginChannel):
    fwd_from = origin.chat.id
    fwd_name = origin.chat.title
```

### Media Meta JSON Format
```json
{"size": 123456, "mime": "image/jpeg", "width": 1920, "height": 1080}
```
Only non-null fields included to save tokens.

## Post-Completion

**Manual verification:**
- Disable privacy mode via @BotFather → /setprivacy → Disable
- Add bot to 2-3 real group chats and verify logging
- Send various message types (text, photo, sticker, voice, document)
- Test member join/leave events
- Verify SQLite file can be opened and queried by AI tools

**GitHub publishing:**
- Create repository `telegram-logger-bot` on GitHub
- Push code with `gh repo create`
- Add topics: telegram, bot, logger, sqlite, aiogram, python

**Future improvements (v2):**
- `ChatMemberUpdated` handlers for large groups (requires admin privileges)
- `MAX_MEDIA_SIZE` config option for download limits
- `schema_version` table + auto-migration for schema changes
- Connection pooling for high-load scenarios
