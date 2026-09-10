"""Admin boti (2-bot): zayavkalar shu yerga tushadi, boshqaruv buyruqlari."""

from __future__ import annotations

import logging
from typing import Any, Dict

from . import texts as T
from .admin_handlers import handle_admin_command, try_login
from .service import ADMIN_BOT, Service
from .telegram import BotAPI
from .utils import esc, remove_keyboard

log = logging.getLogger(__name__)

STATE_PASSWORD = "password"


def handle_message(service: Service, api: BotAPI, message: Dict[str, Any]) -> None:
    user = message.get("from") or {}
    user_id = int(user.get("id") or 0)
    chat = message.get("chat") or {}
    chat_id = int(chat.get("id") or 0)
    if not user_id or not chat_id:
        return
    # Guruhga qo'shilsa - faqat adminlar ro'yxatiga qo'shish uchun /start ishlaydi.
    if chat.get("type") != "private" and not service.is_admin(ADMIN_BOT, chat_id):
        return

    text = (message.get("text") or "").strip()
    session_key = service.session_key(ADMIN_BOT, user_id)
    is_admin = service.is_admin(ADMIN_BOT, user_id)

    if text.startswith("/"):
        command = text.split()[0].split("@")[0].lower()
        argument = text[len(text.split()[0]):].strip()

        if command == "/start":
            if is_admin:
                api.send_message(
                    chat_id,
                    T.ADMIN_ALREADY.format(commands=T.ADMIN_COMMANDS),
                    reply_markup=remove_keyboard(),
                )
                return
            if argument and try_login(service, ADMIN_BOT, api, chat_id, user, argument):
                return
            service.storage.set_session(session_key, state=STATE_PASSWORD)
            api.send_message(chat_id, T.ADMIN_ASK_PASSWORD, reply_markup=remove_keyboard())
            return

        if command == "/id":
            api.send_message(
                chat_id,
                T.ID_INFO.format(user_id=user_id, chat_id=chat_id, bot=esc(api.username)),
            )
            return

        if command in ("/yordam", "/help"):
            if is_admin:
                api.send_message(chat_id, T.ADMIN_COMMANDS)
            else:
                api.send_message(chat_id, T.ADMIN_ONLY)
            return

        if handle_admin_command(service, ADMIN_BOT, api, chat_id, user, command):
            return

        api.send_message(chat_id, T.ADMIN_COMMANDS if is_admin else T.ADMIN_ONLY)
        return

    if is_admin:
        api.send_message(chat_id, T.ADMIN_COMMANDS)
        return

    # Parol kutilyapti.
    session = service.storage.get_session(session_key)
    if session.get("state") == STATE_PASSWORD and text:
        if try_login(service, ADMIN_BOT, api, chat_id, user, text):
            return
        api.send_message(chat_id, T.ADMIN_WRONG_PASSWORD)
        return

    service.storage.set_session(session_key, state=STATE_PASSWORD)
    api.send_message(chat_id, T.ADMIN_ASK_PASSWORD)
