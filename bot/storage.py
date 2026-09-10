"""Ma'lumotlarni saqlash: zayavkalar, sessiyalar, adminlar (JSON fayl)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

STATUS_NEW = "new"
STATUS_CONTACTED = "contacted"
STATUS_CANCELLED = "cancelled"

_DEFAULT: Dict[str, Any] = {
    "version": 1,
    "counters": {"application_id": 0},
    "applications": [],
    "sessions": {},
    "admins": {"user_bot": [], "admin_bot": []},
    "offsets": {},
}


class Storage:
    """Thread-safe JSON ombor. Har o'zgarishda atomik saqlaydi."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data = self._load()
        self._offset_saved_at = 0.0

    # ------------------------------------------------------------- internals
    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return deepcopy(_DEFAULT)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            backup = self.path.with_suffix(".corrupt.json")
            log.error("Baza o'qilmadi (%s). Nusxa: %s", exc, backup)
            try:
                self.path.replace(backup)
            except OSError:
                pass
            return deepcopy(_DEFAULT)
        data = deepcopy(_DEFAULT)
        if isinstance(raw, dict):
            for key, value in raw.items():
                data[key] = value
        data.setdefault("counters", {}).setdefault("application_id", 0)
        admins = data.setdefault("admins", {})
        admins.setdefault("user_bot", [])
        admins.setdefault("admin_bot", [])
        data.setdefault("applications", [])
        data.setdefault("sessions", {})
        data.setdefault("offsets", {})
        return data

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(self.path.parent), prefix=".db-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            log.error("Bazani saqlab bo'lmadi: %s", exc)
            try:
                os.unlink(tmp_name)
            except OSError:
                pass

    # -------------------------------------------------------------- sessions
    def get_session(self, key: str) -> Dict[str, Any]:
        """key - "bot_key:user_id" ko'rinishida (botlar sessiyasi aralashmasligi uchun)."""
        with self._lock:
            return deepcopy(self._data["sessions"].get(str(key), {}))

    def set_session(self, key: str, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            session = self._data["sessions"].setdefault(str(key), {})
            session.update(fields)
            session["updated_at"] = time.time()
            self._save_locked()
            return deepcopy(session)

    def clear_session(self, key: str) -> None:
        with self._lock:
            if self._data["sessions"].pop(str(key), None) is not None:
                self._save_locked()

    def purge_old_sessions(self, max_age_sec: int = 7 * 24 * 3600) -> int:
        """Uzoq vaqt tegilmagan yarim tugallangan sessiyalarni tozalaydi."""
        cutoff = time.time() - max_age_sec
        with self._lock:
            stale = [
                key for key, value in self._data["sessions"].items()
                if float(value.get("updated_at") or 0) < cutoff
            ]
            for key in stale:
                self._data["sessions"].pop(key, None)
            if stale:
                self._save_locked()
            return len(stale)

    # ---------------------------------------------------------- applications
    def add_application(
        self,
        *,
        user_id: int,
        chat_id: int,
        name: str,
        phone: str,
        username: str = "",
        full_name: str = "",
        language_code: str = "",
        phone_source: str = "text",
    ) -> Dict[str, Any]:
        with self._lock:
            counters = self._data["counters"]
            counters["application_id"] = int(counters.get("application_id") or 0) + 1
            record = {
                "id": counters["application_id"],
                "user_id": user_id,
                "chat_id": chat_id,
                "name": name,
                "phone": phone,
                "username": username,
                "full_name": full_name,
                "language_code": language_code,
                "phone_source": phone_source,
                "status": STATUS_NEW,
                "created_at": time.time(),
                "handled_by": None,
                "handled_by_name": "",
                "handled_at": None,
                "notifications": [],
            }
            self._data["applications"].append(record)
            self._save_locked()
            return deepcopy(record)

    def get_application(self, app_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            for record in self._data["applications"]:
                if record["id"] == app_id:
                    return deepcopy(record)
            return None

    def add_notification(self, app_id: int, bot_key: str, chat_id: int, message_id: int) -> None:
        with self._lock:
            for record in self._data["applications"]:
                if record["id"] == app_id:
                    record.setdefault("notifications", []).append(
                        {"bot": bot_key, "chat_id": chat_id, "message_id": message_id}
                    )
                    self._save_locked()
                    return

    def set_status(
        self,
        app_id: int,
        status: str,
        *,
        by_id: Optional[int] = None,
        by_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Statusni o'zgartiradi. Allaqachon o'sha statusda bo'lsa None qaytaradi."""
        with self._lock:
            for record in self._data["applications"]:
                if record["id"] != app_id:
                    continue
                if record.get("status") == status:
                    return None
                record["status"] = status
                record["handled_by"] = by_id
                record["handled_by_name"] = by_name
                record["handled_at"] = time.time()
                self._save_locked()
                return deepcopy(record)
            return None

    def list_applications(self, limit: int = 10, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = self._data["applications"]
            if status:
                items = [item for item in items if item.get("status") == status]
            return [deepcopy(item) for item in items[-limit:][::-1]]

    def all_applications(self) -> List[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._data["applications"])

    def count_recent_by_user(self, user_id: int, since_sec: float) -> int:
        cutoff = time.time() - since_sec
        with self._lock:
            return sum(
                1
                for item in self._data["applications"]
                if item.get("user_id") == user_id and float(item.get("created_at") or 0) >= cutoff
            )

    def last_submission_ts(self, user_id: int) -> float:
        with self._lock:
            stamps = [
                float(item.get("created_at") or 0)
                for item in self._data["applications"]
                if item.get("user_id") == user_id
            ]
            return max(stamps) if stamps else 0.0

    def stats(self, day_start_ts: float) -> Dict[str, int]:
        with self._lock:
            items = self._data["applications"]
            return {
                "total": len(items),
                "today": sum(1 for i in items if float(i.get("created_at") or 0) >= day_start_ts),
                "new": sum(1 for i in items if i.get("status") == STATUS_NEW),
                "contacted": sum(1 for i in items if i.get("status") == STATUS_CONTACTED),
                "cancelled": sum(1 for i in items if i.get("status") == STATUS_CANCELLED),
            }

    # --------------------------------------------------------------- offsets
    def get_offset(self, bot_key: str) -> int:
        with self._lock:
            try:
                return int(self._data["offsets"].get(bot_key) or 0)
            except (TypeError, ValueError):
                return 0

    def set_offset(self, bot_key: str, value: int) -> None:
        """Update offsetini saqlaydi (diskka ko'pi bilan 5 soniyada bir marta)."""
        with self._lock:
            self._data["offsets"][bot_key] = int(value)
            now = time.time()
            if now - self._offset_saved_at >= 5.0:
                self._offset_saved_at = now
                self._save_locked()

    def flush(self) -> None:
        with self._lock:
            self._save_locked()

    # ---------------------------------------------------------------- admins
    def admins(self, bot_key: str) -> List[int]:
        with self._lock:
            return list(self._data["admins"].get(bot_key, []))

    def add_admin(self, bot_key: str, chat_id: int) -> bool:
        with self._lock:
            bucket = self._data["admins"].setdefault(bot_key, [])
            if chat_id in bucket:
                return False
            bucket.append(chat_id)
            self._save_locked()
            return True

    def remove_admin(self, bot_key: str, chat_id: int) -> bool:
        with self._lock:
            bucket = self._data["admins"].setdefault(bot_key, [])
            if chat_id not in bucket:
                return False
            bucket.remove(chat_id)
            self._save_locked()
            return True

    def is_admin(self, bot_key: str, chat_id: int) -> bool:
        with self._lock:
            return chat_id in self._data["admins"].get(bot_key, [])
