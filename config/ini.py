"""Runtime configuration loaded from an INI file (path in BESTYET_CONFIG)."""

import configparser
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]
    csrf_trusted_origins: list[str]
    admin_path: str
    db_path: Path
    media_root: Path


def _split_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve(raw):
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / path


def load_config(path):
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise ImproperlyConfigured(f"BestYet config file not found or unreadable: {path}")
    try:
        secret_key = parser.get("django", "secret_key")
        db_path = parser.get("paths", "db")
        media_root = parser.get("paths", "media")
    except (configparser.NoSectionError, configparser.NoOptionError) as exc:
        raise ImproperlyConfigured(f"BestYet config incomplete: {exc}") from exc
    if not secret_key:
        raise ImproperlyConfigured("BestYet config: [django] secret_key must not be empty")
    return Config(
        secret_key=secret_key,
        debug=parser.getboolean("django", "debug", fallback=False),
        allowed_hosts=_split_list(parser.get("django", "allowed_hosts", fallback="")),
        csrf_trusted_origins=_split_list(parser.get("django", "csrf_trusted_origins", fallback="")),
        admin_path=parser.get("django", "admin_path", fallback="admin").strip("/"),
        db_path=_resolve(db_path),
        media_root=_resolve(media_root),
    )
