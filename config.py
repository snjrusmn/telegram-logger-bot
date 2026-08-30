import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, Optional

from dotenv import load_dotenv


@dataclass
class Config:
    bot_token: str
    download_media: bool
    data_dir: Path
    allowed_chat_ids: FrozenSet[int] = field(default_factory=frozenset)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "logger.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def load_config(env_path: Optional[str] = None) -> Config:
    load_dotenv(env_path)

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN is required. Set it in .env file.")

    download_media_raw = os.getenv("DOWNLOAD_MEDIA", "false").strip().lower()
    download_media = download_media_raw in ("true", "1", "yes")

    data_dir = Path(os.getenv("DATA_DIR", "./data"))

    allowed_chat_ids = _parse_chat_ids(os.getenv("ALLOWED_CHAT_IDS", ""))

    return Config(
        bot_token=bot_token,
        download_media=download_media,
        data_dir=data_dir,
        allowed_chat_ids=allowed_chat_ids,
    )


def _parse_chat_ids(raw: str) -> FrozenSet[int]:
    """Parse a comma-separated chat id list. Empty means: log every chat."""
    ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise ValueError(
                f"ALLOWED_CHAT_IDS: {part!r} is not a chat id. "
                "Expected comma-separated integers, e.g. -1001234567890,-4228822135"
            )
    return frozenset(ids)
