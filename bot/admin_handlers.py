"""Admin buyruqlari va tugmalari - ikkala bot uchun umumiy."""

from __future__ import annotations

import csv
import io
import logging
import time
from typing import Any, Dict, List, Optional

from . import texts as T
from .notify import render_application
from .service import Service
from .storage import STATUS_CANCELLED, STATUS_CONTACTED, STATUS_NEW
from .telegram import BotAPI, TelegramError
from .utils import clip, day_start_ts, esc, fmt_dt
from .validators import pretty_phone

log = logging.getLogger(__name__)

ADMIN_COMMANDS = {
    "/statistika", "/stats", "/oxirgi", "/yangi", "/eksport", "/export",
    "/chiqish", "/logout",
}

BOT_COMMAND_LIST = [
    {"command": "start", "description": "Boshlash"},
    {"command": "statistika", "description": "Umumiy hisobot"},
    {"command": "oxirgi", "description": "Oxirgi 10 ta zayavka"},
    {"command": "yangi", "description": "Javob berilmagan zayavkalar"},
    {"command": "eksport", "description": "Barcha zayavkalar (CSV)"},
    {"command": "id", "description": "Chat ID"},
    {"command": "yordam", "description": "Yordam"},
]


def display_name(user: Dict[str, Any]) -> str:
    """Telegram foydalanuvchisining ko'rinadigan ismi."""
    parts = [user.get("first_name") or "", user.get("last_name") or ""]
    name = " ".join(part for part in parts if part).strip()
    return name or (user.get("username") or f"ID {user.get('id')}")


def _sanitize_cell(value: Any) -> str:
    """CSV formulalar hujumidan himoya (Excel `=`, `+`, `-`, `@` bilan boshlanishi)."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def build_csv(service: Service) -> bytes:
    """Barcha zayavkalarni Excel ochadigan CSV ga aylantiradi."""
    rows = service.storage.all_applications()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "ID", "Ism", "Kompaniya", "Telefon", "Username", "Telegram ID", "Manba",
        "Audit balli", "Audit xulosasi", "Holat", "Sana", "Kim", "Qachon",
    ])
    tz_offset = service.config.tz_offset_hours
    for item in rows:
        audit_info = item.get("audit") if isinstance(item.get("audit"), dict) else {}
        writer.writerow([
            _sanitize_cell(item.get("id")),
            _sanitize_cell(item.get("name")),
            _sanitize_cell(item.get("company") or ""),
            _sanitize_cell(item.get("phone")),
            _sanitize_cell(("@" + item["username"]) if item.get("username") else ""),
            _sanitize_cell(item.get("user_id")),
            _sanitize_cell("Mini App audit" if item.get("source") == "webapp" else "Bot"),
            _sanitize_cell(audit_info.get("score", "")),
            _sanitize_cell(audit_info.get("band", "")),
            _sanitize_cell(T.STATUS_LABELS.get(item.get("status", ""), item.get("status", ""))),
            _sanitize_cell(fmt_dt(item.get("created_at"), tz_offset)),
            _sanitize_cell(item.get("handled_by_name") or ""),
            _sanitize_cell(fmt_dt(item.get("handled_at"), tz_offset) if item.get("handled_at") else ""),
        ])
    # BOM - Excel kirill/lotin harflarni to'g'ri ochishi uchun.
    return "﻿".encode("utf-8") + buffer.getvalue().encode("utf-8")


def render_list(service: Service, items: List[Dict[str, Any]], title: str) -> str:
    if not items:
        return T.LIST_EMPTY
    tz_offset = service.config.tz_offset_hours
    chunks = [T.LIST_HEADER.format(title=title, count=len(items))]
    for item in items:
        username = item.get("username")
        chunks.append(
            T.LIST_ITEM.format(
                id=item["id"],
                status=T.STATUS_LABELS.get(item.get("status", ""), ""),
                name=esc(item.get("name")),
                phone=esc(pretty_phone(item.get("phone", ""))),
                time=fmt_dt(item.get("created_at"), tz_offset),
                tg=f"\n👥 @{esc(username)}" if username else "",
            )
        )
    return clip("".join(chunks))


def handle_admin_command(
    service: Service,
    bot_key: str,
    api: BotAPI,
    chat_id: int,
    user: Dict[str, Any],
    command: str,
) -> bool:
    """Admin buyrug'ini bajaradi. Buyruq tanilsa True qaytaradi."""
    user_id = int(user.get("id") or 0)
    if command not in ADMIN_COMMANDS:
        return False
    if not service.is_admin(bot_key, user_id):
        api.send_message(chat_id, T.ADMIN_ONLY)
        return True

    tz_offset = service.config.tz_offset_hours
    now = fmt_dt(time.time(), tz_offset)

    if command in ("/statistika", "/stats"):
        stats = service.storage.stats(day_start_ts(tz_offset))
        api.send_message(chat_id, T.STATS.format(time=now, **stats))
    elif command == "/oxirgi":
        items = service.storage.list_applications(limit=10)
        api.send_message(chat_id, render_list(service, items, "Oxirgi zayavkalar"))
    elif command == "/yangi":
        items = service.storage.list_applications(limit=20, status=STATUS_NEW)
        api.send_message(chat_id, render_list(service, items, "Yangi zayavkalar"))
    elif command in ("/eksport", "/export"):
        data = build_csv(service)
        count = len(service.storage.all_applications())
        if not count:
            api.send_message(chat_id, T.EXPORT_EMPTY)
        else:
            try:
                api.send_document(
                    chat_id,
                    "zayavkalar.csv",
                    data,
                    caption=T.EXPORT_CAPTION.format(count=count, time=now),
                )
            except TelegramError as exc:
                log.error("%s: eksport yuborilmadi: %s", api.label, exc)
                api.send_message(chat_id, "❌ Faylni yuborib bo'lmadi. Keyinroq urinib ko'ring.")
    elif command in ("/chiqish", "/logout"):
        service.storage.remove_admin(bot_key, user_id)
        api.send_message(chat_id, T.ADMIN_LOGGED_OUT)
    return True


def try_login(
    service: Service,
    bot_key: str,
    api: BotAPI,
    chat_id: int,
    user: Dict[str, Any],
    password: str,
) -> bool:
    """Parolni tekshirib, adminni ro'yxatga qo'shadi."""
    user_id = int(user.get("id") or 0)
    if password.strip() != service.config.admin_password:
        return False
    service.storage.add_admin(bot_key, user_id)
    service.storage.clear_session(service.session_key(bot_key, user_id))
    api.send_message(
        chat_id,
        T.ADMIN_WELCOME.format(name=esc(display_name(user)), commands=T.ADMIN_COMMANDS),
    )
    log.info("%s: yangi admin ulandi: %s (%s)", api.label, user_id, display_name(user))
    return True


def handle_callback(service: Service, bot_key: str, api: BotAPI, callback: Dict[str, Any]) -> None:
    """Zayavka ostidagi tugmalar (✅ Bog'landim / ❌ Bekor)."""
    callback_id = callback.get("id", "")
    data = callback.get("data") or ""
    user = callback.get("from") or {}
    user_id = int(user.get("id") or 0)
    message = callback.get("message") or {}

    if not data.startswith("app:"):
        api.answer_callback(callback_id)
        return
    if not service.is_admin(bot_key, user_id):
        api.answer_callback(callback_id, T.CB_NO_RIGHTS, alert=True)
        return

    parts = data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        api.answer_callback(callback_id, T.CB_NOT_FOUND, alert=True)
        return
    action, app_id = parts[1], int(parts[2])
    status = {"contacted": STATUS_CONTACTED, "cancelled": STATUS_CANCELLED}.get(action)
    if status is None:
        api.answer_callback(callback_id, T.CB_NOT_FOUND, alert=True)
        return

    existing = service.storage.get_application(app_id)
    if existing is None:
        api.answer_callback(callback_id, T.CB_NOT_FOUND, alert=True)
        return

    updated = service.storage.set_status(
        app_id, status, by_id=user_id, by_name=display_name(user)
    )
    if updated is None:
        api.answer_callback(callback_id, T.CB_ALREADY)
        return

    api.answer_callback(callback_id, T.CB_DONE)
    service.notifier.refresh_status(updated)
