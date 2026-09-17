"""Umumiy servis konteyneri (sozlamalar, ombor, xabarnoma)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .config import Config
from .notify import Notifier
from .storage import Storage
from .telegram import BotAPI

USER_BOT = "user_bot"
ADMIN_BOT = "admin_bot"


@dataclass
class Service:
    config: Config
    storage: Storage
    notifier: Notifier
    apis: Dict[str, BotAPI]

    def is_admin(self, bot_key: str, user_id: int) -> bool:
        return user_id in self.config.admin_ids or self.storage.is_admin(bot_key, user_id)

    def can_manage(self, bot_key: str, user_id: int, chat_id: int) -> bool:
        """Foydalanuvchi o'zi admin YOKI ro'yxatdagi admin guruhida yozyapti."""
        return self.is_admin(bot_key, user_id) or (chat_id != user_id and self.is_admin(bot_key, chat_id))

    def session_key(self, bot_key: str, user_id: int) -> str:
        return f"{bot_key}:{user_id}"
