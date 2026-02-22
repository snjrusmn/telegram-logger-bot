<div align="center">

# Telegram Logger Bot

**Silent chat logger for AI-powered analysis**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white)](https://python.org)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.1-blue)](https://github.com/snjrusmn/telegram-logger-bot/releases)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen?logo=pytest&logoColor=white)](#testing)

[English](#why-this-tool) | [Русский](#зачем-этот-инструмент)

</div>

---

## Why This Tool?

Modern teams communicate in Telegram. Conversations contain decisions, action items, feedback, and context that gets lost in the chat scroll. This bot captures everything silently and stores it in a structured database that AI can query directly.

**The problem:**
- Important decisions get buried in chat history
- No searchable archive of group discussions
- AI assistants can't access your Telegram chat context
- Manual chat exports are messy and unstructured

**The solution:**
Add this bot to your group chats. It silently records every message, media metadata, and event into a normalized SQLite database. Then point any AI tool at the database and ask questions about your conversations.

---

## Зачем этот инструмент?

Современные команды общаются в Telegram. В переписках содержатся решения, задачи, обратная связь и контекст, который теряется в потоке сообщений. Этот бот молча записывает всё в структурированную базу данных, которую AI может читать напрямую.

**Проблема:**
- Важные решения теряются в истории чата
- Нет удобного архива групповых обсуждений
- AI-ассистенты не имеют доступа к контексту из Telegram
- Ручной экспорт чатов неструктурирован и неудобен

**Решение:**
Добавьте бота в групповые чаты. Он молча записывает каждое сообщение, метаданные медиа и события в нормализованную SQLite базу. Затем подключите любой AI-инструмент к базе и задавайте вопросы о ваших переписках.

---

## Features

| Feature | Description |
|---------|-------------|
| **Silent logging** | Bot never responds in chat &mdash; invisible to participants |
| **All message types** | Text, photos, videos, documents, audio, voice, video notes, stickers, GIFs |
| **Service events** | Member join/leave, title changes, pinned messages |
| **Edit tracking** | Edited messages logged separately with `is_edit` flag |
| **Reply chains** | `reply_to` field links responses to original messages |
| **Forward origin** | Full chain: user, chat, channel, or hidden user |
| **Normalized DB** | 4 tables, no data duplication &mdash; minimal token cost for AI |
| **Media download** | Optional: save files to disk or just log metadata |
| **Multi-chat** | One bot instance handles unlimited groups simultaneously |
| **Error resilient** | Errors in one handler don't crash the bot or lose other messages |

---

## Quick Start

### 1. Create a Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow the instructions
3. Copy the API token
4. **Important:** Send `/setprivacy` to @BotFather, select your bot, choose **Disable**

> Without disabling privacy mode, the bot can only see commands (`/`) and direct mentions. It won't log regular messages.

### 2. Install & Configure

```bash
git clone https://github.com/snjrusmn/telegram-logger-bot.git
cd telegram-logger-bot

cp .env.example .env
```

Edit `.env` and paste your bot token:

```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
DOWNLOAD_MEDIA=false
DATA_DIR=./data
```

### 3. Run

```bash
pip install -r requirements.txt
python bot.py
```

### 4. Add to Chats

Add the bot to any group chat. It will start logging immediately. No commands needed.

---

## Configuration

| Variable | Default | Description |
|:---------|:--------|:------------|
| `BOT_TOKEN` | *(required)* | Telegram Bot API token from @BotFather |
| `DOWNLOAD_MEDIA` | `false` | Download media files to disk. Accepts: `true`, `false`, `1`, `0`, `yes`, `no` |
| `DATA_DIR` | `./data` | Directory for the SQLite database and downloaded media files |

When `DOWNLOAD_MEDIA=true`, files are saved to `DATA_DIR/media/` with the naming pattern:
```
{chat_id}_{message_id}_{original_filename}
```

---

## Project Structure

```
telegram-logger-bot/
│
├── bot.py                 # Entry point: bot lifecycle, DI setup, polling
├── config.py              # Configuration loader from .env
├── db.py                  # SQLite layer: schema, upsert, insert functions
├── handlers.py            # All message/media/event handlers (aiogram Router)
│
├── tests/                 # Test suite (46 tests)
│   ├── __init__.py
│   ├── test_config.py     # Config parsing tests (17 tests)
│   ├── test_db.py         # Database operations tests (15 tests)
│   └── test_handlers.py   # Handler logic & media extraction tests (14 tests)
│
├── data/                  # Created at runtime (gitignored)
│   ├── logger.db          # SQLite database
│   └── media/             # Downloaded files (if enabled)
│
├── docs/plans/            # Implementation plans
├── .env.example           # Environment template
├── .gitignore
├── requirements.txt       # Python dependencies
├── VERSION                # Semantic version (1.0.0)
└── LICENSE                # Apache 2.0
```

### Architecture

```
Telegram API
    │
    ▼
┌─────────┐     ┌──────────────┐     ┌────────┐
│  bot.py  │────▶│ handlers.py  │────▶│ db.py  │──▶ SQLite
│          │     │  (Router)    │     │        │
│ Polling  │     │              │     │ upsert │
│ DI Setup │     │ text handler │     │ insert │
│ Startup  │     │ media handler│     │        │
│ Shutdown │     │ event handler│     └────────┘
└─────────┘     │ edit handler │
                │ catch-all    │
                └──────────────┘
                       │
                       ▼
                 ┌──────────┐
                 │config.py │
                 │ .env     │
                 └──────────┘
```

**Data flow:**
1. `bot.py` starts polling Telegram API via aiogram
2. Each incoming update is routed to the appropriate handler in `handlers.py`
3. Handlers extract structured data and call `db.py` functions
4. `db.py` writes to SQLite with WAL mode for concurrent read safety
5. Dependencies (`db`, `config`) are injected via aiogram's built-in DI system

---

## Database Schema

The database is designed for **minimal token consumption** when used with AI/LLM tools. Data is normalized into 4 tables to avoid repeating usernames, chat titles, etc. in every row.

```
┌──────────────┐       ┌──────────────────────────────────────┐
│    chats     │       │             messages                 │
├──────────────┤       ├──────────────────────────────────────┤
│ chat_id (PK) │◄──────│ chat_id (FK)                        │
│ title        │       │ user_id (FK, nullable)               │
│ type         │       │ msg_id, date, type, text             │
│ updated_at   │       │ media_file_id, media_meta (JSON)     │
└──────────────┘       │ reply_to, fwd_from, fwd_name         │
                       │ is_edit, created_at                   │
┌──────────────┐       └──────────────────────────────────────┘
│    users     │
├──────────────┤       ┌──────────────────────────────────────┐
│ user_id (PK) │       │             events                   │
│ username     │       ├──────────────────────────────────────┤
│ first_name   │       │ chat_id (FK)                         │
│ last_name    │       │ user_id, type                        │
│ updated_at   │       │ data (JSON), date, created_at        │
└──────────────┘       └──────────────────────────────────────┘
```

### What Gets Logged

| Source | Type | Stored As |
|:-------|:-----|:----------|
| Text messages | `text` | Full text in `messages.text` |
| Photos | `photo` | file_id + `{size, width, height}` in media_meta |
| Videos | `video` | file_id + `{size, mime, duration, width, height}` |
| Documents | `document` | file_id + `{size, mime, name}` |
| Audio | `audio` | file_id + `{size, mime, name, duration}` |
| Voice messages | `voice` | file_id + `{size, mime, duration}` |
| Video notes | `video_note` | file_id + `{size, duration, length}` |
| Stickers | `sticker` | file_id + `{emoji, set_name, width, height}` |
| GIFs/Animations | `animation` | file_id + `{size, mime, duration, width, height}` |
| Edited messages | any + `is_edit=1` | New row with updated content |
| Replies | any + `reply_to` | Links to original `msg_id` |
| Forwards | any + `fwd_from/fwd_name` | Origin user/chat/channel info |
| Member joined | `member_joined` event | `{username, first_name}` in events |
| Member left | `member_left` event | `{username, first_name}` in events |
| Title changed | `title_changed` event | `{new_title}` in events |
| Message pinned | `message_pinned` event | `{pinned_message_id}` in events |
| Other (polls, etc.) | `other` | content_type string in text |

### Media Metadata Format

Only non-null fields are stored to save space:

```json
{"size": 52480, "mime": "image/jpeg", "width": 1920, "height": 1080}
```

---

## Using the Database with AI

The SQLite file at `data/logger.db` can be directly consumed by AI tools. Here are example queries:

### Get all messages with authors

```sql
SELECT u.first_name, u.last_name, m.text, m.date, c.title
FROM messages m
JOIN users u ON m.user_id = u.user_id
JOIN chats c ON m.chat_id = c.chat_id
WHERE m.type = 'text'
ORDER BY m.date;
```

### Reconstruct a conversation thread

```sql
SELECT
    u.first_name AS author,
    m.text,
    ru.first_name AS reply_to_user
FROM messages m
JOIN users u ON m.user_id = u.user_id
LEFT JOIN messages rm ON m.reply_to = rm.msg_id AND m.chat_id = rm.chat_id
LEFT JOIN users ru ON rm.user_id = ru.user_id
WHERE m.chat_id = ?
ORDER BY m.date;
```

### Chat activity summary

```sql
SELECT
    c.title,
    COUNT(m.id) AS total_messages,
    COUNT(DISTINCT m.user_id) AS active_users,
    MIN(m.date) AS first_message,
    MAX(m.date) AS last_message
FROM messages m
JOIN chats c ON m.chat_id = c.chat_id
GROUP BY c.chat_id;
```

### Find who shares the most media

```sql
SELECT u.first_name, u.username, COUNT(*) AS media_count
FROM messages m
JOIN users u ON m.user_id = u.user_id
WHERE m.type IN ('photo', 'video', 'document', 'animation')
GROUP BY m.user_id
ORDER BY media_count DESC;
```

### Track message edits

```sql
SELECT m.msg_id, m.text, m.is_edit, m.created_at
FROM messages m
WHERE m.chat_id = ? AND m.msg_id = ?
ORDER BY m.created_at;
```

### Member activity timeline

```sql
SELECT e.type, u.first_name, u.username, e.date, c.title
FROM events e
LEFT JOIN users u ON e.user_id = u.user_id
JOIN chats c ON e.chat_id = c.chat_id
ORDER BY e.date;
```

---

## Testing

```bash
python -m pytest tests/ -v
```

The test suite includes 50 tests covering:
- Configuration parsing (17 tests) &mdash; env variables, defaults, edge cases
- Database operations (15 tests) &mdash; CRUD, upserts, schema validation
- Handler logic (18 tests) &mdash; message extraction, media metadata, forward parsing, filename sanitization

---

## Requirements

- Python 3.9+
- Dependencies: `aiogram`, `aiosqlite`, `python-dotenv`
- Dev dependencies: `pytest`, `pytest-asyncio`

---

## Roadmap

- [ ] `ChatMemberUpdated` handlers for large groups (requires bot admin)
- [ ] Configurable media download size limit
- [ ] Database schema migrations
- [ ] Web UI for browsing logs
- [ ] Export to CSV/JSON

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 Sanzhar Usmanov.
