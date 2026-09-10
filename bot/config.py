"""Konfiguratsiya: .env faylidan sozlamalarni o'qish va tekshirish."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"

TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")


class ConfigError(Exception):
    """Sozlamalardagi xatolik."""


def load_env_file(path: Path = ENV_PATH) -> None:
    """.env faylini o'qib, os.environ ga joylaydi (mavjud env ustun turadi)."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_ids(key: str) -> List[int]:
    raw = _env(key)
    if not raw:
        return []
    ids: List[int] = []
    for chunk in re.split(r"[,\s;]+", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            continue
    return ids


def _clean_token(raw: str) -> str:
    """Token ichidagi tasodifiy bo'sh joy/qator uzilishlarini olib tashlaydi."""
    return re.sub(r"\s+", "", raw or "")


@dataclass
class Config:
    """Botning barcha sozlamalari."""

    user_bot_token: str
    admin_bot_token: str
    admin_ids: List[int] = field(default_factory=list)
    admin_password: str = "admin"
    company_name: str = "Xizmat"
    contact_info: str = ""
    poll_timeout: int = 25
    submit_cooldown_sec: int = 45
    max_per_day: int = 5
    tz_offset_hours: int = 5
    log_level: str = "INFO"
    db_path: Path = field(default_factory=lambda: DATA_DIR / "db.json")

    @property
    def admin_bot_enabled(self) -> bool:
        return bool(self.admin_bot_token)


def load_config() -> Config:
    """Sozlamalarni yuklaydi. Asosiy bot tokeni bo'lmasa xato beradi."""
    load_env_file()

    user_token = _clean_token(_env("USER_BOT_TOKEN"))
    admin_token = _clean_token(_env("ADMIN_BOT_TOKEN"))

    if not user_token:
        raise ConfigError(
            "USER_BOT_TOKEN topilmadi. `.env` faylida USER_BOT_TOKEN=... ni to'ldiring."
        )
    if not TOKEN_RE.match(user_token):
        raise ConfigError(
            "USER_BOT_TOKEN noto'g'ri formatda. Namuna: 1234567890:AAF...35ta_belgi"
        )
    if admin_token and not TOKEN_RE.match(admin_token):
        # Admin token buzuq bo'lsa - butun botni to'xtatmaymiz, shunchaki o'chirib qo'yamiz.
        logging.getLogger(__name__).warning(
            "ADMIN_BOT_TOKEN noto'g'ri formatda - admin boti o'chirildi. "
            "@BotFather -> /mybots -> API Token dan to'g'ri tokenni .env ga qo'ying."
        )
        admin_token = ""
    if admin_token and admin_token == user_token:
        logging.getLogger(__name__).warning(
            "ADMIN_BOT_TOKEN va USER_BOT_TOKEN bir xil - admin boti o'chirildi."
        )
        admin_token = ""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    return Config(
        user_bot_token=user_token,
        admin_bot_token=admin_token,
        admin_ids=_env_ids("ADMIN_IDS"),
        admin_password=_env("ADMIN_PASSWORD", "admin"),
        company_name=_env("COMPANY_NAME", "Xizmat"),
        contact_info=_env("CONTACT_INFO", ""),
        poll_timeout=_env_int("POLL_TIMEOUT", 25),
        submit_cooldown_sec=_env_int("SUBMIT_COOLDOWN_SEC", 45),
        max_per_day=_env_int("MAX_PER_DAY", 5),
        tz_offset_hours=_env_int("TZ_OFFSET_HOURS", 5),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        db_path=DATA_DIR / _env("DB_FILE", "db.json"),
    )
