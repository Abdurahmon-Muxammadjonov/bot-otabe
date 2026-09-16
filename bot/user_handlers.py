"""So'rov boti (1-bot): mijoz bilan muloqot - ism -> telefon -> zayavka."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from . import texts as T
from .admin_handlers import display_name, handle_admin_command, try_login
from .service import Service, USER_BOT
from .telegram import BotAPI, safe_send
from .utils import contact_keyboard, esc, remove_keyboard, restart_keyboard, webapp_keyboard
from .validators import clean_name, normalize_phone, pretty_phone

log = logging.getLogger(__name__)

STATE_NAME = "name"
STATE_PHONE = "phone"

BOT_COMMAND_LIST = [
    {"command": "start", "description": "So'rov qoldirish"},
    {"command": "audit", "description": "Sotuv bo'limi auditi (6 daqiqa)"},
    {"command": "bekor", "description": "Bekor qilish"},
    {"command": "yordam", "description": "Yordam"},
]


def _contact_hint(service: Service) -> str:
    contact = service.config.contact_info
    return f"\n📞 Aloqa: {esc(contact)}" if contact else ""


def start_flow(service: Service, api: BotAPI, chat_id: int, user: Dict[str, Any]) -> None:
    """/start - ismni so'rash. Limitga tushsa, jarayon boshlanmaydi."""
    user_id = int(user.get("id") or 0)

    # Spam/limit tekshiruvi ENG BOSHDA - mijoz bekorga ism-telefon yozib chiqmasin.
    limit = _limit_message(service, user_id)
    if limit:
        service.storage.clear_session(service.session_key(USER_BOT, user_id))
        api.send_message(chat_id, limit, reply_markup=remove_keyboard())
        return

    returning = service.storage.last_submission_ts(user_id) > 0
    service.storage.set_session(
        service.session_key(USER_BOT, user_id), state=STATE_NAME, name=None
    )
    text = (T.GREETING_AGAIN if returning else T.GREETING).format(
        company=esc(service.config.company_name)
    )
    if not returning and service.config.webapp_enabled:
        # Birinchi kelgan mijozga auditni ham taklif qilamiz - bitta xabarda,
        # inline tugma bilan (ism so'rovi holati buzilmaydi).
        api.send_message(
            chat_id,
            text + T.GREETING_AUDIT_HINT,
            reply_markup=webapp_keyboard(T.BTN_OPEN_AUDIT, service.config.audit_url),
        )
        return
    api.send_message(chat_id, text, reply_markup=remove_keyboard())


def send_audit_invite(service: Service, api: BotAPI, chat_id: int) -> bool:
    """Mini App'ni ochadigan tugmali xabar. WEBAPP_URL bo'lmasa False."""
    if not service.config.webapp_enabled:
        return False
    api.send_message(
        chat_id,
        T.AUDIT_INVITE,
        reply_markup=webapp_keyboard(T.BTN_OPEN_AUDIT, service.config.audit_url),
    )
    return True


def _ask_phone(api: BotAPI, chat_id: int, name: str) -> None:
    api.send_message(
        chat_id,
        T.ASK_PHONE.format(name=esc(name), btn=T.BTN_SEND_CONTACT),
        reply_markup=contact_keyboard(T.BTN_SEND_CONTACT, T.BTN_CANCEL),
    )


def _limit_message(service: Service, user_id: int) -> Optional[str]:
    """Spamga qarshi: sovish vaqti va kunlik limit."""
    config = service.config
    if config.submit_cooldown_sec > 0:
        last = service.storage.last_submission_ts(user_id)
        waited = time.time() - last
        if last and waited < config.submit_cooldown_sec:
            return T.COOLDOWN.format(seconds=int(config.submit_cooldown_sec - waited) + 1)
    if config.max_per_day > 0:
        if service.storage.count_recent_by_user(user_id, 24 * 3600) >= config.max_per_day:
            return T.DAILY_LIMIT.format(limit=config.max_per_day)
    return None


def submit(
    service: Service,
    api: BotAPI,
    chat_id: int,
    user: Dict[str, Any],
    name: str,
    phone: str,
    phone_source: str,
) -> None:
    """Zayavkani saqlaydi, mijozga javob beradi va adminlarga uzatadi."""
    user_id = int(user.get("id") or 0)
    application = service.storage.add_application(
        user_id=user_id,
        chat_id=chat_id,
        name=name,
        phone=phone,
        username=user.get("username") or "",
        full_name=display_name(user),
        language_code=user.get("language_code") or "",
        phone_source=phone_source,
    )
    service.storage.clear_session(service.session_key(USER_BOT, user_id))

    # AVVAL adminga uzatamiz (enqueue hech qachon xato bermaydi), KEYIN mijozga
    # javob beramiz. Aks holda javob yuborish xato bersa zayavka yo'qolib ketardi.
    service.notifier.enqueue(application)
    log.info("Yangi zayavka #%s qabul qilindi (user %s)", application["id"], user_id)

    text = T.SUCCESS.format(name=esc(name), phone=esc(pretty_phone(phone)))
    if service.config.contact_info:
        text += T.SUCCESS_CONTACT.format(contact=esc(service.config.contact_info))
    if safe_send(api, chat_id, text, reply_markup=restart_keyboard(T.BTN_NEW_REQUEST)) is None:
        log.warning(
            "Zayavka #%s: mijozga tasdiq yuborilmadi, lekin adminga uzatildi",
            application["id"],
        )


def handle_message(service: Service, api: BotAPI, message: Dict[str, Any]) -> None:
    """So'rov botidagi har bir xabar shu yerdan o'tadi."""
    user = message.get("from") or {}
    user_id = int(user.get("id") or 0)
    chat = message.get("chat") or {}
    chat_id = int(chat.get("id") or 0)
    if not user_id or not chat_id or chat.get("type") != "private":
        return

    session_key = service.session_key(USER_BOT, user_id)
    session = service.storage.get_session(session_key)
    state = session.get("state")
    text = (message.get("text") or "").strip()
    contact = message.get("contact")

    # ---------------------------------------------------------- buyruqlar
    if text.startswith("/"):
        command = text.split()[0].split("@")[0].lower()
        argument = text[len(text.split()[0]):].strip()

        if command == "/start":
            start_flow(service, api, chat_id, user)
            return
        if command in ("/bekor", "/cancel", "/stop"):
            service.storage.clear_session(session_key)
            api.send_message(chat_id, T.CANCELLED, reply_markup=remove_keyboard())
            return
        if command in ("/yordam", "/help"):
            api.send_message(chat_id, T.HELP_USER.format(contact=_contact_hint(service)))
            return
        if command in ("/audit", "/app"):
            if not send_audit_invite(service, api, chat_id):
                api.send_message(chat_id, T.AUDIT_DISABLED)
            return
        if command == "/id":
            api.send_message(
                chat_id,
                T.ID_INFO.format(user_id=user_id, chat_id=chat_id, bot=esc(api.username)),
            )
            return
        if command == "/admin":
            if try_login(service, USER_BOT, api, chat_id, user, argument):
                return
            api.send_message(chat_id, T.ADMIN_WRONG_PASSWORD)
            return
        if handle_admin_command(service, USER_BOT, api, chat_id, user, command):
            return
        # Notanish buyruq - jarayonni buzmaymiz.
        if state == STATE_NAME:
            api.send_message(chat_id, T.NAME_ERRORS["empty"])
        elif state == STATE_PHONE:
            api.send_message(chat_id, T.NEED_TEXT_PHONE.format(btn=T.BTN_SEND_CONTACT))
        else:
            api.send_message(chat_id, T.UNKNOWN_USER_MSG.format(btn=T.BTN_NEW_REQUEST))
        return

    # ------------------------------------------------------ tugma matnlari
    if text == T.BTN_CANCEL:
        service.storage.clear_session(session_key)
        api.send_message(chat_id, T.CANCELLED, reply_markup=remove_keyboard())
        return
    if text == T.BTN_NEW_REQUEST:
        start_flow(service, api, chat_id, user)
        return

    # ------------------------------------------------------------- kontakt
    if contact:
        if state == STATE_NAME:
            # Mijoz ismdan oldin raqamini yubordi - avval ismni so'raymiz.
            api.send_message(chat_id, T.NEED_TEXT_NAME)
            return
        if state != STATE_PHONE or not session.get("name"):
            start_flow(service, api, chat_id, user)
            return
        owner_id = contact.get("user_id")
        if owner_id and int(owner_id) != user_id:
            api.send_message(chat_id, T.FOREIGN_CONTACT)
            return
        phone, error = normalize_phone(contact.get("phone_number") or "")
        if not phone:
            api.send_message(chat_id, T.PHONE_ERRORS.get(error, T.PHONE_ERRORS["empty"]))
            return
        # Limit /start bosilganda tekshirilgan - bu yergacha kelgan zayavka saqlanadi.
        submit(service, api, chat_id, user, session["name"], phone, "contact")
        return

    # ---------------------------------------------------------- matn holati
    if not text:
        if state == STATE_NAME:
            api.send_message(chat_id, T.NEED_TEXT_NAME)
        elif state == STATE_PHONE:
            api.send_message(chat_id, T.NEED_TEXT_PHONE.format(btn=T.BTN_SEND_CONTACT))
        else:
            api.send_message(chat_id, T.UNKNOWN_USER_MSG.format(btn=T.BTN_NEW_REQUEST))
        return

    if state == STATE_NAME:
        name, error = clean_name(text)
        if not name:
            api.send_message(chat_id, T.NAME_ERRORS.get(error, T.NAME_ERRORS["empty"]))
            return
        service.storage.set_session(session_key, state=STATE_PHONE, name=name)
        _ask_phone(api, chat_id, name)
        return

    if state == STATE_PHONE:
        phone, error = normalize_phone(text)
        if not phone:
            api.send_message(chat_id, T.PHONE_ERRORS.get(error, T.PHONE_ERRORS["empty"]))
            return
        name = session.get("name")
        if not name:
            start_flow(service, api, chat_id, user)
            return
        # Limit /start bosilganda tekshirilgan - bu yergacha kelgan zayavka saqlanadi.
        submit(service, api, chat_id, user, name, phone, "text")
        return

    # Sessiya yo'q - boshlashni taklif qilamiz.
    api.send_message(
        chat_id,
        T.UNKNOWN_USER_MSG.format(btn=T.BTN_NEW_REQUEST),
        reply_markup=restart_keyboard(T.BTN_NEW_REQUEST),
    )
