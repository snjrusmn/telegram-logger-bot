import logging
import os
import re
from typing import Optional, Tuple

import aiosqlite
from aiogram import Router, F
from aiogram.enums import ContentType
from aiogram.types import Message, MessageOriginUser, MessageOriginChat, MessageOriginHiddenUser, MessageOriginChannel

from config import Config
from db import upsert_chat, upsert_user, insert_message, insert_event, commit

logger = logging.getLogger(__name__)

MEDIA_CONTENT_TYPES = {
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.DOCUMENT,
    ContentType.AUDIO,
    ContentType.VOICE,
    ContentType.VIDEO_NOTE,
    ContentType.STICKER,
    ContentType.ANIMATION,
}

SERVICE_CONTENT_TYPES = {
    ContentType.NEW_CHAT_MEMBERS,
    ContentType.LEFT_CHAT_MEMBER,
    ContentType.NEW_CHAT_TITLE,
    ContentType.PINNED_MESSAGE,
}


def _extract_forward_info(message: Message) -> Tuple[Optional[int], Optional[str]]:
    """Extract forward origin info from message."""
    origin = message.forward_origin
    if origin is None:
        return None, None

    if isinstance(origin, MessageOriginUser):
        return origin.sender_user.id, origin.sender_user.full_name
    elif isinstance(origin, MessageOriginHiddenUser):
        return None, origin.sender_user_name
    elif isinstance(origin, MessageOriginChat):
        return origin.sender_chat.id, origin.sender_chat.title
    elif isinstance(origin, MessageOriginChannel):
        return origin.chat.id, origin.chat.title

    return None, None


def _extract_media_meta(message: Message) -> Tuple[Optional[str], Optional[dict], str]:
    """Extract media metadata, file_id, and content type string from message.

    Returns: (file_id, media_meta_dict, type_string)
    """
    ct = message.content_type

    if ct == ContentType.PHOTO and message.photo:
        photo = message.photo[-1]  # largest size
        return photo.file_id, {
            "size": photo.file_size,
            "width": photo.width,
            "height": photo.height,
        }, "photo"

    if ct == ContentType.VIDEO and message.video:
        v = message.video
        return v.file_id, {
            "size": v.file_size,
            "mime": v.mime_type,
            "name": v.file_name,
            "duration": v.duration,
            "width": v.width,
            "height": v.height,
        }, "video"

    if ct == ContentType.DOCUMENT and message.document:
        d = message.document
        return d.file_id, {
            "size": d.file_size,
            "mime": d.mime_type,
            "name": d.file_name,
        }, "document"

    if ct == ContentType.AUDIO and message.audio:
        a = message.audio
        return a.file_id, {
            "size": a.file_size,
            "mime": a.mime_type,
            "name": a.file_name,
            "duration": a.duration,
        }, "audio"

    if ct == ContentType.VOICE and message.voice:
        v = message.voice
        return v.file_id, {
            "size": v.file_size,
            "mime": v.mime_type,
            "duration": v.duration,
        }, "voice"

    if ct == ContentType.VIDEO_NOTE and message.video_note:
        vn = message.video_note
        return vn.file_id, {
            "size": vn.file_size,
            "duration": vn.duration,
            "length": vn.length,
        }, "video_note"

    if ct == ContentType.STICKER and message.sticker:
        s = message.sticker
        return s.file_id, {
            "emoji": s.emoji,
            "set_name": s.set_name,
            "width": s.width,
            "height": s.height,
        }, "sticker"

    if ct == ContentType.ANIMATION and message.animation:
        a = message.animation
        return a.file_id, {
            "size": a.file_size,
            "mime": a.mime_type,
            "name": a.file_name,
            "duration": a.duration,
            "width": a.width,
            "height": a.height,
        }, "animation"

    return None, None, str(ct) if ct else "unknown"


def _sanitize_filename(name: str) -> str:
    """Remove unsafe characters from filename."""
    name = os.path.basename(name)
    return re.sub(r'[^\w\-.]', '_', name)


async def _save_chat_and_user(db: aiosqlite.Connection, message: Message) -> None:
    """Upsert chat and user info from a message."""
    await upsert_chat(db, message.chat.id, message.chat.title, message.chat.type)
    if message.from_user:
        await upsert_user(
            db, message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )


async def _log_message(
    db: aiosqlite.Connection,
    message: Message,
    msg_type: str,
    text: Optional[str] = None,
    media_file_id: Optional[str] = None,
    media_meta: Optional[dict] = None,
    is_edit: bool = False,
) -> None:
    """Common message logging logic."""
    fwd_from, fwd_name = _extract_forward_info(message)
    user_id = message.from_user.id if message.from_user else None

    await insert_message(
        db,
        msg_id=message.message_id,
        chat_id=message.chat.id,
        user_id=user_id,
        date=message.date.isoformat(),
        msg_type=msg_type,
        text=text,
        media_file_id=media_file_id,
        media_meta=media_meta,
        reply_to=message.reply_to_message.message_id if message.reply_to_message else None,
        fwd_from=fwd_from,
        fwd_name=fwd_name,
        is_edit=is_edit,
    )
    await commit(db)


def setup_router() -> Router:
    """Create and return a router with all handlers registered."""
    router = Router()

    # --- Text messages ---
    @router.message(F.text, ~F.text.startswith("/"))
    async def on_text(message: Message, db: aiosqlite.Connection, config: Config) -> None:
        try:
            await _save_chat_and_user(db, message)
            await _log_message(db, message, msg_type="text", text=message.text)
        except Exception:
            logger.exception("Error logging text message %s in chat %s", message.message_id, message.chat.id)

    # --- Media messages ---
    @router.message(F.content_type.in_(MEDIA_CONTENT_TYPES))
    async def on_media(message: Message, db: aiosqlite.Connection, config: Config) -> None:
        try:
            await _save_chat_and_user(db, message)
            file_id, meta, msg_type = _extract_media_meta(message)

            if config.download_media and file_id:
                try:
                    file = await message.bot.get_file(file_id)
                    media_dir = config.media_dir
                    os.makedirs(media_dir, exist_ok=True)
                    safe_name = _sanitize_filename(file.file_path.split('/')[-1])
                    dest = os.path.join(media_dir, f"{message.chat.id}_{message.message_id}_{safe_name}")
                    await message.bot.download_file(file.file_path, dest)
                except Exception:
                    logger.exception("Error downloading media for message %s", message.message_id)

            await _log_message(
                db, message, msg_type=msg_type,
                text=message.caption,
                media_file_id=file_id,
                media_meta=meta,
            )
        except Exception:
            logger.exception("Error logging media message %s in chat %s", message.message_id, message.chat.id)

    # --- Service events ---
    @router.message(F.content_type.in_(SERVICE_CONTENT_TYPES))
    async def on_service(message: Message, db: aiosqlite.Connection, config: Config) -> None:
        try:
            await _save_chat_and_user(db, message)
            date = message.date.isoformat()

            if message.new_chat_members:
                for member in message.new_chat_members:
                    await upsert_user(db, member.id, member.username, member.first_name, member.last_name)
                    await insert_event(
                        db, chat_id=message.chat.id, event_type="member_joined",
                        date=date, user_id=member.id,
                        data={"username": member.username, "first_name": member.first_name},
                    )

            elif message.left_chat_member:
                member = message.left_chat_member
                await insert_event(
                    db, chat_id=message.chat.id, event_type="member_left",
                    date=date, user_id=member.id,
                    data={"username": member.username, "first_name": member.first_name},
                )

            elif message.new_chat_title:
                await upsert_chat(db, message.chat.id, message.new_chat_title, message.chat.type)
                await insert_event(
                    db, chat_id=message.chat.id, event_type="title_changed",
                    date=date, user_id=message.from_user.id if message.from_user else None,
                    data={"new_title": message.new_chat_title},
                )

            elif message.pinned_message:
                await insert_event(
                    db, chat_id=message.chat.id, event_type="message_pinned",
                    date=date, user_id=message.from_user.id if message.from_user else None,
                    data={"pinned_message_id": message.pinned_message.message_id},
                )

            await commit(db)

        except Exception:
            logger.exception("Error logging service event in chat %s", message.chat.id)

    # --- Edited messages ---
    @router.edited_message(F.text)
    async def on_edited_text(message: Message, db: aiosqlite.Connection, config: Config) -> None:
        try:
            await _save_chat_and_user(db, message)
            await _log_message(db, message, msg_type="text", text=message.text, is_edit=True)
        except Exception:
            logger.exception("Error logging edited text message %s in chat %s", message.message_id, message.chat.id)

    @router.edited_message(F.content_type.in_(MEDIA_CONTENT_TYPES))
    async def on_edited_media(message: Message, db: aiosqlite.Connection, config: Config) -> None:
        try:
            await _save_chat_and_user(db, message)
            file_id, meta, msg_type = _extract_media_meta(message)
            await _log_message(
                db, message, msg_type=msg_type,
                text=message.caption,
                media_file_id=file_id,
                media_meta=meta,
                is_edit=True,
            )
        except Exception:
            logger.exception("Error logging edited media message %s in chat %s", message.message_id, message.chat.id)

    # --- Catch-all for unknown message types ---
    @router.message()
    async def on_other(message: Message, db: aiosqlite.Connection, config: Config) -> None:
        try:
            await _save_chat_and_user(db, message)
            await _log_message(
                db, message, msg_type="other",
                text=str(message.content_type),
            )
        except Exception:
            logger.exception("Error logging unknown message type in chat %s", message.chat.id)

    return router
