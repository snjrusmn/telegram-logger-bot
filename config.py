import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    bot_token: str
    download_media: bool
    data_dir: Path

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

    return Config(
        bot_token=bot_token,
        download_media=download_media,
        data_dir=data_dir,
    )
