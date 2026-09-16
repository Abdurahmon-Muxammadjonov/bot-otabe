"""Telegram Bot API bilan ishlovchi minimal, ishonchli klient (faqat stdlib)."""

from __future__ import annotations

import http.client
import json
import logging
import mimetypes
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"

# Foydalanuvchi botni bloklagan / chat topilmagan holatlar - qayta urinish shart emas.
UNREACHABLE_CODES = (400, 403)


class TelegramError(Exception):
    """Telegram API qaytargan xatolik."""

    def __init__(self, code: int, description: str, retry_after: Optional[int] = None):
        super().__init__(f"[{code}] {description}")
        self.code = code
        self.description = description or ""
        self.retry_after = retry_after

    @property
    def is_unreachable(self) -> bool:
        """Foydalanuvchiga umuman yozib bo'lmaydigan holat."""
        text = self.description.lower()
        markers = (
            "bot was blocked",
            "user is deactivated",
            "chat not found",
            "bot can't initiate conversation",
            "peer_id_invalid",
            "have no rights to send",
            "user not found",
            "kicked",
        )
        return self.code in UNREACHABLE_CODES and any(m in text for m in markers)


def _encode_multipart(
    fields: Dict[str, Any],
    files: Dict[str, Tuple[str, bytes]],
) -> Tuple[bytes, str]:
    """multipart/form-data tanasini yig'adi (fayl yuborish uchun)."""
    boundary = "----ClaudeBotBoundary" + uuid.uuid4().hex
    buf = bytearray()
    for key, value in fields.items():
        if value is None:
            continue
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        buf += f"--{boundary}\r\n".encode()
        buf += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        buf += value.encode("utf-8") + b"\r\n"
    for key, (filename, content) in files.items():
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        buf += f"--{boundary}\r\n".encode()
        buf += (
            f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
        ).encode()
        buf += f"Content-Type: {ctype}\r\n\r\n".encode()
        buf += content + b"\r\n"
    buf += f"--{boundary}--\r\n".encode()
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


class BotAPI:
    """Bitta bot uchun API klienti: qayta urinish, 429 va tarmoq xatolarini boshqaradi."""

    def __init__(self, token: str, label: str, timeout: int = 30, retries: int = 3):
        self.token = token
        self.label = label
        self.timeout = timeout
        self.retries = retries
        self._base = f"{API_ROOT}/bot{token}"
        self.username: str = ""
        self.bot_id: int = 0

    # ------------------------------------------------------------------ core
    def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        files: Optional[Dict[str, Tuple[str, bytes]]] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
    ) -> Any:
        """API metodini chaqiradi. Muvaffaqiyatda `result` ni qaytaradi."""
        url = f"{self._base}/{method}"
        max_attempts = (self.retries if retries is None else retries) + 1
        req_timeout = timeout or self.timeout
        attempt = 0

        while True:
            attempt += 1
            try:
                if files:
                    body, content_type = _encode_multipart(params or {}, files)
                else:
                    body = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
                    content_type = "application/json"
                request = urllib.request.Request(
                    url,
                    data=body,
                    headers={
                        "Content-Type": content_type,
                        "Accept": "application/json",
                        "Connection": "close",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=req_timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")
                try:
                    payload = json.loads(raw)
                except ValueError:
                    payload = {
                        "ok": False,
                        "error_code": exc.code,
                        "description": raw[:300] or exc.reason,
                    }
            except (
                urllib.error.URLError,
                http.client.HTTPException,
                socket.timeout,
                OSError,
                ValueError,
            ) as exc:
                if attempt >= max_attempts:
                    raise TelegramError(0, f"tarmoq xatosi: {exc}") from exc
                delay = min(2 ** attempt, 15) + random.random()
                log.warning(
                    "%s: %s tarmoq xatosi (%s). %.1fs dan keyin qayta urinaman.",
                    self.label, method, exc, delay,
                )
                time.sleep(delay)
                continue

            if payload.get("ok"):
                return payload.get("result")

            code = int(payload.get("error_code") or 0)
            description = str(payload.get("description") or "")
            retry_after = (payload.get("parameters") or {}).get("retry_after")
            error = TelegramError(code, description, retry_after)

            if code == 429 and attempt < max_attempts:
                delay = float(retry_after or 3) + 0.5
                log.warning("%s: limit (429). %.1fs kutaman.", self.label, delay)
                time.sleep(delay)
                continue
            if code >= 500 and attempt < max_attempts:
                delay = min(2 ** attempt, 15) + random.random()
                log.warning("%s: server xatosi %s. %.1fs kutaman.", self.label, code, delay)
                time.sleep(delay)
                continue
            raise error

    # --------------------------------------------------------------- methods
    def get_me(self) -> Dict[str, Any]:
        me = self.call("getMe", timeout=20)
        self.username = me.get("username", "")
        self.bot_id = int(me.get("id") or 0)
        return me

    def delete_webhook(self) -> None:
        try:
            self.call("deleteWebhook", {"drop_pending_updates": False}, timeout=20)
        except TelegramError as exc:
            log.warning("%s: webhook o'chirilmadi: %s", self.label, exc)

    def get_updates(self, offset: int, timeout: int, allowed: Sequence[str]) -> List[Dict[str, Any]]:
        return self.call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "limit": 100,
                "allowed_updates": list(allowed),
            },
            timeout=timeout + 20,
            retries=0,
        ) or []

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_preview: bool = True,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "link_preview_options": {"is_disabled": disable_preview},
        }
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return self.call("sendMessage", params)

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Any:
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return self.call("editMessageText", params)

    def answer_callback(self, callback_id: str, text: str = "", alert: bool = False) -> None:
        try:
            self.call(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": text[:200], "show_alert": alert},
                retries=0,
            )
        except TelegramError as exc:
            log.debug("%s: callback javobi berilmadi: %s", self.label, exc)

    def send_document(
        self,
        chat_id: int,
        filename: str,
        content: bytes,
        caption: str = "",
    ) -> Dict[str, Any]:
        return self.call(
            "sendDocument",
            {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"document": (filename, content)},
        )

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        try:
            self.call("sendChatAction", {"chat_id": chat_id, "action": action}, retries=0)
        except TelegramError:
            pass

    def set_chat_menu_button(self, text: str, url: str) -> None:
        """Chatdagi «Menyu» tugmasini Mini App ochadigan qilib qo'yadi (barcha chatlar uchun)."""
        try:
            self.call(
                "setChatMenuButton",
                {"menu_button": {"type": "web_app", "text": text[:32], "web_app": {"url": url}}},
                timeout=20,
            )
        except TelegramError as exc:
            log.warning("%s: menyu tugmasi o'rnatilmadi: %s", self.label, exc)

    def reset_chat_menu_button(self) -> None:
        try:
            self.call("setChatMenuButton", {"menu_button": {"type": "default"}}, timeout=20)
        except TelegramError as exc:
            log.debug("%s: menyu tugmasi tiklanmadi: %s", self.label, exc)

    def set_my_commands(self, commands: Iterable[Dict[str, str]]) -> None:
        try:
            self.call("setMyCommands", {"commands": list(commands)}, timeout=20)
        except TelegramError as exc:
            log.warning("%s: komandalar o'rnatilmadi: %s", self.label, exc)


def safe_send(
    api: BotAPI,
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[Dict[str, Any]] = None,
    on_unreachable: Optional[Callable[[int], None]] = None,
) -> Optional[Dict[str, Any]]:
    """Xabar yuboradi; xatolik bo'lsa dasturni to'xtatmaydi."""
    try:
        return api.send_message(chat_id, text, reply_markup=reply_markup)
    except TelegramError as exc:
        if exc.is_unreachable and on_unreachable is not None:
            on_unreachable(chat_id)
        log.warning("%s: %s ga xabar yuborilmadi: %s", api.label, chat_id, exc)
        return None
