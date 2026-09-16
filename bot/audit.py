"""Sotuv auditi (Mini App): savollar bazasi, ballni hisoblash, hisobot matnlari.

Savollar `webapp/audit.json` da - frontend ham, server ham bitta manbadan
o'qiydi. Mijoz yuborgan javob indekslaridan ball SERVERDA qayta hisoblanadi -
brauzerdan kelgan raqamlarga ishonilmaydi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import BASE_DIR
from .utils import esc

WEBAPP_DIR = BASE_DIR / "webapp"
AUDIT_PATH = WEBAPP_DIR / "audit.json"

# initData imzosi shundan eski bo'lsa - qabul qilinmaydi (soniya).
INIT_DATA_MAX_AGE = 24 * 3600


class AuditError(Exception):
    """Mijoz yuborgan ma'lumot noto'g'ri (400)."""


# ------------------------------------------------------------------ savollar
_cache: Dict[str, Any] = {}


def load_bank() -> Dict[str, Any]:
    """audit.json ni o'qiydi (fayl o'zgarsa qayta yuklaydi)."""
    try:
        mtime = AUDIT_PATH.stat().st_mtime
    except OSError as exc:
        raise AuditError(f"audit.json topilmadi: {exc}") from exc
    if _cache.get("mtime") != mtime:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        _cache.update(mtime=mtime, data=data)
    return _cache["data"]


# ---------------------------------------------------------------- initData
def verify_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """Telegram Mini App initData imzosini tekshiradi va foydalanuvchini qaytaradi.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or len(init_data) > 8192:
        raise AuditError("initData yo'q")
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    fields = dict(pairs)
    received_hash = fields.pop("hash", "")
    if not received_hash:
        raise AuditError("initData imzosi yo'q")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise AuditError("initData imzosi noto'g'ri")

    try:
        auth_date = int(fields.get("auth_date") or 0)
    except ValueError:
        auth_date = 0
    if not auth_date or time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise AuditError("initData eskirgan - ilovani qayta oching")

    try:
        user = json.loads(fields.get("user") or "{}")
    except ValueError:
        user = {}
    if not isinstance(user, dict) or not user.get("id"):
        raise AuditError("initData ichida foydalanuvchi yo'q")
    return user


# --------------------------------------------------------------- hisoblash
def _as_index(value: Any, upper: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditError(f"{what}: indeks butun son bo'lishi kerak")
    if value < 0 or value >= upper:
        raise AuditError(f"{what}: indeks chegaradan tashqarida")
    return value


def compute(profile_raw: Any, answers_raw: Any) -> Dict[str, Any]:
    """Javob indekslaridan to'liq natijani hisoblaydi.

    Qaytaradi: {score, band, profile:{key:{label,index,n}}, blocks:[...], gaps:[...]}
    """
    bank = load_bank()
    questions: List[Dict[str, Any]] = bank["questions"]

    if not isinstance(answers_raw, list) or len(answers_raw) != len(questions):
        raise AuditError("Javoblar soni savollar soniga mos emas")
    answers = [
        _as_index(value, len(questions[i]["a"]), f"{i + 1}-savol")
        for i, value in enumerate(answers_raw)
    ]

    if not isinstance(profile_raw, dict):
        raise AuditError("Profil noto'g'ri")
    profile: Dict[str, Dict[str, Any]] = {}
    for item in bank["profile"]:
        key = item["key"]
        idx = _as_index(profile_raw.get(key), len(item["o"]), key)
        entry: Dict[str, Any] = {"index": idx, "label": item["o"][idx]}
        if item.get("v"):
            entry["n"] = item["v"][idx]
        profile[key] = entry

    blocks: List[Dict[str, Any]] = []
    total = 0.0
    for block in bank["blocks"]:
        got = 0.0
        maximum = 0
        for question, idx in zip(questions, answers):
            if question["b"] != block["id"]:
                continue
            maximum += question["w"]
            got += question["w"] * float(question["a"][idx][1])
        total += got
        blocks.append(
            {
                "id": block["id"],
                "name": block["name"],
                "note": block["note"],
                "got": round(got, 1),
                "max": maximum,
                "pct": round(100 * got / maximum) if maximum else 0,
            }
        )

    gaps: List[Dict[str, Any]] = []
    for i, (question, idx) in enumerate(zip(questions, answers)):
        lost = question["w"] * (1 - float(question["a"][idx][1]))
        if lost <= 0.01:
            continue
        gaps.append(
            {
                "i": i,
                "block": question["b"],
                "q": question["t"],
                "answer": question["a"][idx][0],
                "fix": question["fix"],
                "lost": round(lost, 1),
            }
        )
    gaps.sort(key=lambda g: (-g["lost"], g["i"]))

    score = int(round(total))
    band = next(b for b in bank["bands"] if score >= b["min"])
    return {
        "score": score,
        "band": band["t"],
        "band_text": band["d"],
        "profile": profile,
        "blocks": blocks,
        "gaps": gaps,
        "answers": answers,
    }


def estimate_money(result: Dict[str, Any], avg_check: int) -> Tuple[int, int]:
    """(qo'shimcha bitimlar soni, oylik summa) - saytdagi konservativ formula."""
    leads = int(result["profile"].get("leads", {}).get("n") or 120)
    extra = max(1, round(leads * ((100 - result["score"]) / 100) * 0.05))
    return extra, extra * avg_check


def fmt_money(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


# -------------------------------------------------------------- hisobotlar
def profile_line(result: Dict[str, Any]) -> str:
    parts = [
        result["profile"].get("sector", {}).get("label"),
        result["profile"].get("team", {}).get("label"),
        result["profile"].get("leads", {}).get("label"),
    ]
    return " · ".join(esc(p) for p in parts if p)


def _bar(pct: int, width: int = 8) -> str:
    filled = round(width * pct / 100)
    return "▰" * filled + "▱" * (width - filled)


def render_admin_summary(audit: Dict[str, Any]) -> str:
    """Admin kartasiga qo'shiladigan qisqa audit bloki (HTML)."""
    lines = [
        f"📊 <b>Audit natijasi: {audit['score']}/100</b> — {esc(audit['band'])}",
        f"🏷 {profile_line(audit)}",
    ]
    if audit.get("avg_check"):
        extra, total = estimate_money(audit, int(audit["avg_check"]))
        lines.append(
            f"💰 O'rtacha chek: {fmt_money(audit['avg_check'])} so'm → "
            f"~{extra} bitim / ~{fmt_money(total)} so'm oyiga"
        )
    lines.append("")
    for block in audit["blocks"]:
        lines.append(f"{_bar(block['pct'])} {block['pct']:>3}%  {esc(block['name'])}")
    top = audit["gaps"][:3]
    if top:
        lines.append("")
        lines.append("🔻 <b>Eng zaif nuqtalar:</b>")
        for n, gap in enumerate(top, 1):
            lines.append(f"{n}. {esc(gap['q'])} — <i>{esc(gap['answer'])}</i> (−{gap['lost']})")
    return "\n".join(lines)


def render_user_report(audit: Dict[str, Any], company_name: str) -> List[str]:
    """Mijozga yuboriladigan to'liq hisobot - Telegram limitiga mos bo'laklarda."""
    bank = load_bank()
    head = [
        f"📋 <b>{esc(bank['title'])} — to'liq hisobot</b>",
        "",
        f"🎯 <b>Umumiy ball: {audit['score']}/100</b> — {esc(audit['band'])}",
        esc(audit["band_text"]),
        "",
        "<b>Bloklar bo'yicha:</b>",
    ]
    for block in audit["blocks"]:
        head.append(f"{_bar(block['pct'])} {block['pct']:>3}%  {esc(block['name'])}")

    chunks: List[str] = ["\n".join(head)]
    gaps = audit["gaps"]
    if not gaps:
        chunks.append(
            "✅ <b>Zaif nuqta topilmadi.</b> Barcha bandlarda maksimal ball. "
            "Endi diqqatni suhbat sifatini chuqurroq o'lchashga qarating."
        )
    else:
        current = f"🔻 <b>Zaif nuqtalar ({len(gaps)} ta), ta'siri katta bo'lganidan boshlab:</b>\n"
        for n, gap in enumerate(gaps, 1):
            block_name = next((b["name"] for b in audit["blocks"] if b["id"] == gap["block"]), "")
            item = (
                f"\n<b>{n}. {esc(gap['q'])}</b>\n"
                f"<i>{esc(block_name)} · sizning javobingiz: {esc(gap['answer'])} · −{gap['lost']} ball</i>\n"
                f"{esc(gap['fix'])}\n"
            )
            if len(current) + len(item) > 3800:
                chunks.append(current)
                current = ""
            current += item
        if current.strip():
            chunks.append(current)

    chunks.append(
        f"🤝 <b>{esc(company_name)}</b> jamoasi natijangizni ko'rdi va tez orada "
        "siz bilan bog'lanadi. Savollaringiz bo'lsa — shu chatga yozing."
    )
    return chunks


def summary_for_storage(result: Dict[str, Any], avg_check: Optional[int]) -> Dict[str, Any]:
    """Bazada saqlanadigan ixcham ko'rinish (CSV/statistika uchun)."""
    return {
        "score": result["score"],
        "band": result["band"],
        "band_text": result["band_text"],
        "profile": result["profile"],
        "blocks": result["blocks"],
        "gaps": result["gaps"],
        "answers": result["answers"],
        "avg_check": avg_check,
    }
