"""Zayavkalarni ikkala botga (so'rov boti + admin boti) yetkazish."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Dict, List, Optional

from .config import Config
from .storage import Storage
from .telegram import BotAPI, TelegramError
from .texts import NEW_APPLICATION, STATUS_FOOTER, STATUS_LABELS
from .utils import esc, fmt_dt
from .validators import pretty_phone

log = logging.getLogger(__name__)

# Bot kalitlari (service.py bilan bir xil - aylanma importdan qochish uchun).
USER_BOT = "user_bot"
ADMIN_BOT = "admin_bot"

# tg://user?id= havolali tugma faqat mijoz gaplashgan botda ishlaydi; boshqa
# botda Telegram butun xabarni "BUTTON_USER_INVALID" bilan rad etadi.
BUTTON_ERRORS = ("button_user_invalid", "button_url_invalid")


def _contact_button(app: Dict[str, Any], bot_key: str) -> Optional[Dict[str, str]]:
    """Mijoz bilan bog'lanish tugmasi - faqat ishlaydigan havola bo'lsa qo'shiladi.

    @username bor bo'lsa - t.me havolasi (hamma botda ishlaydi).
    Aks holda tg://user?id= faqat mijoz gaplashgan so'rov botida (1-bot) ishlaydi;
    admin botida bunday havolani Telegram rad etadi, shuning uchun qo'shmaymiz.
    """
    username = (app.get("username") or "").lstrip("@")
    if username:
        return {"text": "💬 Mijozga yozish", "url": f"https://t.me/{username}"}
    if bot_key == USER_BOT:
        uid = int(app.get("user_id") or 0)
        if uid:
            return {"text": "💬 Mijozga yozish", "url": f"tg://user?id={uid}"}
    return None


def _build_markup(
    app: Dict[str, Any], bot_key: str, with_contact: bool = True
) -> Optional[Dict[str, Any]]:
    """Zayavka ostidagi tugmalar (bot va holatga qarab)."""
    rows: List[List[Dict[str, Any]]] = []
    if app.get("status", "new") == "new":
        rows.append(
            [
                {"text": "✅ Bog'landim", "callback_data": f"app:contacted:{app['id']}"},
                {"text": "❌ Bekor", "callback_data": f"app:cancelled:{app['id']}"},
            ]
        )
    if with_contact:
        button = _contact_button(app, bot_key)
        if button:
            rows.append([button])
    return {"inline_keyboard": rows} if rows else None


def telegram_link(app: Dict[str, Any]) -> str:
    """Mijozning Telegram profiliga havola (HTML)."""
    username = (app.get("username") or "").lstrip("@")
    label = esc(app.get("full_name") or app.get("name") or "mijoz")
    if username:
        return f'<a href="https://t.me/{esc(username)}">@{esc(username)}</a>'
    return f'<a href="tg://user?id={int(app.get("user_id") or 0)}">{label}</a>'


def render_application(app: Dict[str, Any], tz_offset: int) -> str:
    """Admin uchun zayavka matnini yig'adi."""
    text = NEW_APPLICATION.format(
        id=app["id"],
        name=esc(app.get("name")),
        phone=esc(pretty_phone(app.get("phone", ""))),
        tg=telegram_link(app),
        user_id=int(app.get("user_id") or 0),
        time=fmt_dt(app.get("created_at"), tz_offset),
    )
    status = app.get("status", "new")
    if status != "new":
        who = esc(app.get("handled_by_name") or "admin")
        text += STATUS_FOOTER.format(
            status=STATUS_LABELS.get(status, status),
            who=who,
            time=fmt_dt(app.get("handled_at"), tz_offset),
        )
    return text


class Notifier:
    """Zayavkalarni navbat orqali fon oqimida tarqatadi (mijoz kutib qolmaydi)."""

    def __init__(self, config: Config, storage: Storage, apis: Dict[str, BotAPI]):
        self.config = config
        self.storage = storage
        self.apis = apis
        self._queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="notifier", daemon=True)
        self._started = False

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if not self._started:
            self._started = True
            self._worker.start()

    def stop(self) -> None:
        if self._started:
            self._queue.put(None)

    def join(self, timeout: float = 5.0) -> None:
        if self._started:
            self._worker.join(timeout=timeout)

    # ----------------------------------------------------------------- queue
    def enqueue(self, app: Dict[str, Any]) -> None:
        self._queue.put(app)

    def _run(self) -> None:
        while True:
            app = self._queue.get()
            if app is None:
                return
            try:
                self.deliver(app)
            except Exception:  # noqa: BLE001 - fon oqimi hech qachon o'lmasin
                log.exception("Zayavka #%s yuborishda kutilmagan xato", app.get("id"))

    # -------------------------------------------------------------- delivery
    def recipients(self, bot_key: str) -> List[int]:
        """Ushbu botda xabar oladigan chat ID lar (ro'yxatdan o'tgan + .env dagi)."""
        ids: List[int] = []
        for chat_id in self.storage.admins(bot_key) + list(self.config.admin_ids):
            if chat_id not in ids:
                ids.append(chat_id)
        return ids

    def _target_bots(self, app_id: int) -> List[str]:
        """Zayavka qaysi bot(lar)ga boradi.

        Asosiy manzil - ADMIN BOTI (2-bot): mijoz 1-botga zayavka qoldiradi,
        u 2-botga (adminlarga) tushadi. Agar admin boti hali sozlanmagan yoki
        unda birorta admin ro'yxatdan o'tmagan bo'lsa, zayavka yo'qolmasligi
        uchun so'rov boti (1-bot) adminlariga tashlanadi (zaxira yo'l).
        """
        if ADMIN_BOT in self.apis:
            if self.recipients(ADMIN_BOT):
                return [ADMIN_BOT]
            if self.recipients(USER_BOT):
                log.warning(
                    "Zayavka #%s: admin botida (2-bot) admin yo'q - so'rov boti "
                    "adminlariga yuborildi. Admin 2-botga /start bosib parolni kiritsin.",
                    app_id,
                )
                return [USER_BOT]
            return [ADMIN_BOT]
        # Admin boti umuman sozlanmagan (token .env da bo'sh) - so'rov botiga zaxira.
        return [USER_BOT]

    def deliver(self, app: Dict[str, Any]) -> int:
        """Zayavkani admin botiga (2-bot) yuboradi. Yetkazilganlar sonini qaytaradi."""
        delivered = 0

        for bot_key in self._target_bots(app["id"]):
            api = self.apis.get(bot_key)
            if api is None:
                continue
            targets = self.recipients(bot_key)
            if not targets:
                log.warning(
                    "%s: zayavka #%s uchun qabul qiluvchi yo'q "
                    "(admin /start bosib parolni kiritishi kerak)",
                    api.label, app["id"],
                )
                continue
            for chat_id in targets:
                # Har yuborishdan oldin yangi holatni o'qib olamiz (fan-out paytida
                # admin tugma bossa, eski "yangi" kartani yubormaslik uchun).
                current = self.storage.get_application(app["id"]) or app
                text = render_application(current, self.config.tz_offset_hours)
                sent = self._send_with_fallback(api, bot_key, chat_id, current, text)
                if sent is None:
                    continue
                delivered += 1
                self.storage.add_notification(
                    app["id"], bot_key, chat_id, int(sent.get("message_id") or 0)
                )
        log.info("Zayavka #%s: %s ta adminga yetkazildi", app["id"], delivered)

        # Fan-out davomida holat o'zgargan bo'lsa, yuborilgan kartalarni tekislaymiz.
        final = self.storage.get_application(app["id"])
        if final and final.get("status") != "new":
            self.refresh_status(final)
        return delivered

    def _send_with_fallback(
        self,
        api: BotAPI,
        bot_key: str,
        chat_id: int,
        app: Dict[str, Any],
        text: str,
    ) -> Optional[Dict[str, Any]]:
        """Xabarni yuboradi; tugma havolasi rad etilsa, tugmasiz qayta yuboradi."""
        markup = _build_markup(app, bot_key)
        try:
            return api.send_message(chat_id, text, reply_markup=markup)
        except TelegramError as exc:
            desc = exc.description.lower()
            if any(marker in desc for marker in BUTTON_ERRORS):
                # Havola tugmasi ishlamadi - zayavka yo'qolmasin, tugmasiz yuboramiz.
                try:
                    return api.send_message(
                        chat_id, text, reply_markup=_build_markup(app, bot_key, with_contact=False)
                    )
                except TelegramError as exc2:
                    exc = exc2
            if exc.is_unreachable:
                log.warning(
                    "%s: %s ga yuborilmadi (%s) - ro'yxatdan chiqarildi",
                    api.label, chat_id, exc.description,
                )
                self.storage.remove_admin(bot_key, chat_id)
            else:
                log.error("%s: %s ga yuborilmadi: %s", api.label, chat_id, exc)
            return None

    def refresh_status(self, app: Dict[str, Any], skip: Optional[Dict[str, int]] = None) -> None:
        """Status o'zgarganda barcha botlardagi xabarlarni yangilaydi."""
        # Kechikib qo'shilgan bildirishnomalarni ham qamrab olish uchun qayta o'qiymiz.
        app = self.storage.get_application(app["id"]) or app
        text = render_application(app, self.config.tz_offset_hours)
        for note in app.get("notifications", []):
            bot_key = note.get("bot", "")
            api = self.apis.get(bot_key)
            if api is None:
                continue
            if skip and skip.get("chat_id") == note.get("chat_id") and skip.get(
                "message_id"
            ) == note.get("message_id"):
                continue
            markup = _build_markup(app, bot_key)
            try:
                api.edit_message_text(
                    int(note["chat_id"]), int(note["message_id"]), text, reply_markup=markup
                )
            except TelegramError as exc:
                if "not modified" not in exc.description.lower():
                    log.debug("%s: xabar yangilanmadi: %s", api.label, exc)
