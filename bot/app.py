"""Botni yig'ish va ishga tushirish."""

from __future__ import annotations

import logging
import logging.handlers
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import admin_flow, texts as T, user_handlers
from .admin_handlers import BOT_COMMAND_LIST as ADMIN_COMMAND_LIST, handle_callback
from .config import BASE_DIR, Config, ConfigError, load_config
from .notify import Notifier
from .runner import Poller
from .service import ADMIN_BOT, Service, USER_BOT
from .storage import Storage
from .telegram import BotAPI, TelegramError

log = logging.getLogger("bot")


def setup_logging(level: str) -> None:
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Jurnalda mijoz ma'lumotlari bo'lishi mumkin - faqat egasi o'qiy olsin.
    try:
        os.chmod(log_dir, 0o700)
        os.chmod(log_dir / "bot.log", 0o600)
    except OSError:
        pass


class Application:
    """Ikkala botni birga boshqaradi."""

    def __init__(self, config: Config):
        self.config = config
        self.storage = Storage(config.db_path)
        self.stop_event = threading.Event()
        self.apis: Dict[str, BotAPI] = {}
        self.pollers: List[Poller] = []

        self.apis[USER_BOT] = BotAPI(config.user_bot_token, "So'rov boti")
        if config.admin_bot_token:
            self.apis[ADMIN_BOT] = BotAPI(config.admin_bot_token, "Admin boti")

        self.notifier = Notifier(config, self.storage, self.apis)
        self.service = Service(config, self.storage, self.notifier, self.apis)

    # ---------------------------------------------------------------- routing
    def _route(self, bot_key: str):
        api = self.apis[bot_key]

        def handler(update: Dict[str, Any]) -> None:
            if "callback_query" in update:
                handle_callback(self.service, bot_key, api, update["callback_query"])
                return
            message = update.get("message")
            if not message:
                return
            try:
                if bot_key == USER_BOT:
                    user_handlers.handle_message(self.service, api, message)
                else:
                    admin_flow.handle_message(self.service, api, message)
            except TelegramError as exc:
                log.error("%s: javob yuborilmadi: %s", api.label, exc)

        return handler

    # ---------------------------------------------------------------- startup
    def _connect(self, bot_key: str) -> bool:
        api = self.apis[bot_key]
        try:
            me = api.get_me()
        except TelegramError as exc:
            if exc.code == 401:
                log.error(
                    "%s: TOKEN NOTO'G'RI. @BotFather -> /mybots -> API Token "
                    "dan yangi tokenni oling va .env ga qo'ying.", api.label,
                )
            else:
                log.error("%s: ulanmadi: %s", api.label, exc)
            return False
        log.info("%s ulandi: @%s (id=%s)", api.label, me.get("username"), me.get("id"))
        api.delete_webhook()
        api.set_my_commands(
            user_handlers.BOT_COMMAND_LIST if bot_key == USER_BOT else ADMIN_COMMAND_LIST
        )
        return True

    def run(self) -> int:
        # Railway/Render: PORT bo'lsa health-check server'ni ENG BOSHDA ishga
        # tushiramiz - platforma portni darrov kutadi, Telegramga ulanish (getMe)
        # sekin bo'lsa ham konteyner "o'lik" deb o'chirilmasin.
        port = os.environ.get("PORT", "").strip()
        if port.isdigit():
            from .health import start_health_server

            start_health_server(int(port))

        if not self._connect(USER_BOT):
            log.error("So'rov boti ishga tushmadi. To'xtatildi.")
            return 2
        admin_ready = ADMIN_BOT in self.apis and self._connect(ADMIN_BOT)
        if ADMIN_BOT in self.apis and not admin_ready:
            self.apis.pop(ADMIN_BOT)
            log.warning(
                "Admin boti o'chirildi - zayavkalar faqat so'rov boti orqali yuboriladi."
            )
        elif ADMIN_BOT not in self.apis:
            log.warning(
                "ADMIN_BOT_TOKEN kiritilmagan - zayavkalar faqat so'rov botiga tushadi."
            )

        removed = self.storage.purge_old_sessions()
        if removed:
            log.info("%s ta eski sessiya tozalandi", removed)

        self.notifier.start()
        self._install_signals()

        for bot_key in list(self.apis):
            poller = Poller(
                self.apis[bot_key],
                self._route(bot_key),
                self.stop_event,
                timeout=self.config.poll_timeout,
                offset_getter=lambda key=bot_key: self.storage.get_offset(key),
                offset_setter=lambda value, key=bot_key: self.storage.set_offset(key, value),
                critical=(bot_key == USER_BOT),
            )
            poller.start()
            self.pollers.append(poller)

        self._print_banner()

        try:
            while not self.stop_event.is_set():
                self.stop_event.wait(2.0)
                # Poller o'lib qolgan bo'lsa - jim qolmaymiz, dasturni to'xtatamiz.
                for poller in self.pollers:
                    if not poller.is_alive() and not self.stop_event.is_set():
                        log.error(
                            "%s: poller kutilmaganda to'xtadi - dastur yopilmoqda. "
                            "Botni qayta ishga tushiring.", poller.api.label,
                        )
                        self.stop_event.set()
                        break
        except KeyboardInterrupt:
            self.stop_event.set()

        log.info("To'xtatilmoqda...")
        self.notifier.stop()
        self.notifier.join(5.0)
        for poller in self.pollers:
            poller.join(timeout=3.0)
        self.storage.flush()
        log.info("Bot to'xtadi. Xayr! 👋")
        return 0

    def _install_signals(self) -> None:
        def handle(signum, _frame):  # noqa: ANN001
            log.info("Signal %s qabul qilindi - to'xtatilmoqda", signum)
            self.stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handle)
            except (ValueError, OSError):
                pass

    def _print_banner(self) -> None:
        user_api = self.apis[USER_BOT]
        admin_api = self.apis.get(ADMIN_BOT)
        recipients_user = len(self.notifier.recipients(USER_BOT))
        recipients_admin = len(self.notifier.recipients(ADMIN_BOT)) if admin_api else 0
        dest = "admin botiga (2-bot)" if admin_api else "so'rov botiga (1-bot, zaxira)"
        lines = [
            "",
            "=" * 58,
            "  ✅ BOT ISHGA TUSHDI",
            "=" * 58,
            f"  So'rov boti : @{user_api.username}",
            f"  Admin boti  : @{admin_api.username}" if admin_api else
            "  Admin boti  : yoqilmagan (.env -> ADMIN_BOT_TOKEN)",
            f"  Zayavka boradi: {dest}",
            f"  Adminlar    : 2-botda {recipients_admin} ta, 1-botda {recipients_user} ta",
            f"  Parol       : {self.config.admin_password}",
            "-" * 58,
            "  Admin bo'lish uchun: botga /start yozing va parolni yuboring",
            "  (so'rov botida: /admin <parol>)",
            "  To'xtatish uchun: Ctrl + C",
            "=" * 58,
            "",
        ]
        print("\n".join(lines), flush=True)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"\n❌ Sozlama xatosi: {exc}\n", file=sys.stderr)
        return 2
    setup_logging(config.log_level)
    try:
        return Application(config).run()
    except Exception:  # noqa: BLE001
        log.exception("Kutilmagan xato")
        return 1
