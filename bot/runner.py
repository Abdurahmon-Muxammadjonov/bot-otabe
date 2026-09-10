"""Long polling: har bir bot uchun alohida oqim (thread)."""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Callable, Dict, Sequence

from .telegram import BotAPI, TelegramError

log = logging.getLogger(__name__)

ALLOWED_UPDATES: Sequence[str] = ("message", "callback_query", "my_chat_member")


class Poller(threading.Thread):
    """getUpdates sikli. Xatoliklarda o'zi tiklanadi, hech qachon o'lmaydi."""

    def __init__(
        self,
        api: BotAPI,
        handler: Callable[[Dict[str, Any]], None],
        stop_event: threading.Event,
        *,
        timeout: int = 25,
        offset_getter: Callable[[], int],
        offset_setter: Callable[[int], None],
        critical: bool = False,
    ):
        super().__init__(name=f"poller-{api.label}", daemon=True)
        self.api = api
        self.handler = handler
        self.stop_event = stop_event
        self.timeout = timeout
        self._get_offset = offset_getter
        self._set_offset = offset_setter
        # critical=True bo'lsa (so'rov boti), token o'lganda butun dastur to'xtaydi.
        self.critical = critical

    def run(self) -> None:
        offset = self._get_offset()
        failures = 0
        log.info("%s: kutish rejimida (offset=%s)", self.api.label, offset)

        # Butun sikl keng himoyada: hech qanday xato bu oqimni o'ldira olmaydi.
        while not self.stop_event.is_set():
            try:
                try:
                    updates = self.api.get_updates(offset, self.timeout, ALLOWED_UPDATES)
                    failures = 0
                except TelegramError as exc:
                    if exc.code == 409:
                        log.error(
                            "%s: bu bot boshqa joyda ham ishlayapti (409 Conflict). "
                            "Eski nusxani to'xtating!", self.api.label,
                        )
                    elif exc.code == 401:
                        log.error(
                            "%s: token noto'g'ri (401). Poller to'xtatildi.", self.api.label
                        )
                        if self.critical:
                            self.stop_event.set()
                        return
                    else:
                        log.warning("%s: getUpdates xatosi: %s", self.api.label, exc)
                    failures += 1
                    self.stop_event.wait(min(2 ** min(failures, 5), 30) + random.random())
                    continue

                for update in updates:
                    if self.stop_event.is_set():
                        break
                    update_id = int(update.get("update_id") or 0)
                    try:
                        self.handler(update)
                    except Exception:  # noqa: BLE001 - bitta xato botni to'xtatmasin
                        log.exception("%s: update %s da xato", self.api.label, update_id)
                    # Xatolik bo'lsa ham offsetni oldinga suramiz - "zaharli" update
                    # cheksiz takrorlanmasin.
                    offset = update_id + 1
                    self._set_offset(offset)
            except Exception:  # noqa: BLE001 - http.client va boshqa kutilmagan xatolar
                failures += 1
                log.exception(
                    "%s: pollerda kutilmagan xato (qayta urinaman)", self.api.label
                )
                self.stop_event.wait(min(2 ** min(failures, 5), 30) + random.random())

        log.info("%s: to'xtatildi", self.api.label)
