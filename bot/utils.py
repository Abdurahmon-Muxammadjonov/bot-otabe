"""Yordamchi funksiyalar: HTML himoyasi, vaqt formati, klaviaturalar."""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

MAX_MESSAGE_LEN = 3900


def esc(value: Any) -> str:
    """HTML uchun xavfsiz matn (foydalanuvchi kiritgan har qanday matn shu yerdan o'tadi)."""
    return html.escape(str(value if value is not None else ""), quote=False)


def tz(offset_hours: int) -> timezone:
    return timezone(timedelta(hours=offset_hours))


def fmt_dt(timestamp: float, offset_hours: int = 5) -> str:
    """Unix vaqtni "11.09.2026 14:33" ko'rinishida qaytaradi."""
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(float(timestamp), tz(offset_hours)).strftime("%d.%m.%Y %H:%M")


def day_start_ts(offset_hours: int = 5) -> float:
    """Bugungi kun boshlanishi (mahalliy vaqt bo'yicha) unix vaqtda."""
    now = datetime.now(tz(offset_hours))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp()


def clip(text: str, limit: int = MAX_MESSAGE_LEN) -> str:
    """Telegram chegarasidan oshib ketmasligi uchun matnni qisqartiradi."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n\n... (qisqartirildi)"


# ------------------------------------------------------------------ keyboards
def contact_keyboard(button_text: str, cancel_text: str) -> Dict[str, Any]:
    """Telefon raqamni bir bosishda yuborish uchun klaviatura."""
    return {
        "keyboard": [
            [{"text": button_text, "request_contact": True}],
            [{"text": cancel_text}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
        "is_persistent": False,
    }


def restart_keyboard(button_text: str) -> Dict[str, Any]:
    return {
        "keyboard": [[{"text": button_text}]],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def remove_keyboard() -> Dict[str, Any]:
    return {"remove_keyboard": True}


def application_keyboard(app_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Adminlar uchun zayavka ostidagi tugmalar."""
    rows: List[List[Dict[str, Any]]] = [
        [
            {"text": "✅ Bog'landim", "callback_data": f"app:contacted:{app_id}"},
            {"text": "❌ Bekor", "callback_data": f"app:cancelled:{app_id}"},
        ]
    ]
    if user_id:
        rows.append([{"text": "💬 Mijozga yozish", "url": f"tg://user?id={user_id}"}])
    return {"inline_keyboard": rows}
