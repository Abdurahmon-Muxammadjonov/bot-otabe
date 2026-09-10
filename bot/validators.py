"""Foydalanuvchi kiritgan ism va telefon raqamni tekshirish/tozalash."""

from __future__ import annotations

import re
from typing import Optional, Tuple

NAME_MIN = 2
NAME_MAX = 60

# Apostrof variantlari (o', g', oʻ, gʻ ...) va harflar uchun ruxsat.
_ALLOWED_NAME_EXTRA = set(" -.'‘’ʻʼ`´")
_URL_RE = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/|@[A-Za-z0-9_]{3,})", re.I)
_DIGIT_RE = re.compile(r"\d")
_SPACE_RE = re.compile(r"\s+")

# O'zbekiston mobil operator kodlari.
UZ_OPERATOR_CODES = {
    "20", "33", "50", "55", "61", "62", "63", "65", "66", "67", "69",
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
    "88", "90", "91", "93", "94", "95", "97", "98", "99",
}


def clean_name(raw: str) -> Tuple[Optional[str], str]:
    """Ismni tekshiradi.

    Qaytaradi: (tozalangan_ism | None, xato_kodi).
    Xato kodlari: "empty", "short", "long", "digits", "link", "letters".
    """
    if raw is None:
        return None, "empty"
    text = _SPACE_RE.sub(" ", str(raw).replace("\n", " ")).strip()
    if not text:
        return None, "empty"
    if text.startswith("/"):
        return None, "empty"
    if _URL_RE.search(text):
        return None, "link"
    if _DIGIT_RE.search(text):
        return None, "digits"
    if len(text) < NAME_MIN:
        return None, "short"
    if len(text) > NAME_MAX:
        return None, "long"
    letters = sum(1 for ch in text if ch.isalpha())
    if letters < NAME_MIN:
        return None, "letters"
    for ch in text:
        if ch.isalpha() or ch in _ALLOWED_NAME_EXTRA:
            continue
        return None, "letters"
    # Har bir so'zning birinchi harfini kattalashtiramiz (Otabek Sobirov).
    pretty = " ".join(part[:1].upper() + part[1:] if part else part for part in text.split(" "))
    return pretty, ""


def normalize_phone(raw: str) -> Tuple[Optional[str], str]:
    """Telefon raqamni xalqaro formatga keltiradi (+998901234567).

    Qaytaradi: (raqam | None, xato_kodi).
    Xato kodlari: "empty", "chars", "short", "long", "operator".
    """
    if raw is None:
        return None, "empty"
    text = str(raw).strip()
    if not text:
        return None, "empty"

    # Ba'zi telefonlar arab/fors raqamlarini yuboradi - ularni ham qo'llab-quvvatlaymiz.
    # isdecimal() faqat haqiqiy o'nlik raqamlar uchun True (² kabi belgilar int() ni buzadi).
    text = "".join(
        str(int(ch)) if (not ch.isascii() and ch.isdecimal()) else ch for ch in text
    )
    # Ko'rinish belgilarini olib tashlaymiz.
    stripped = re.sub(r"[\s()\-–—./\\]", "", text)
    if stripped.startswith("00"):
        stripped = "+" + stripped[2:]
    has_plus = stripped.startswith("+")
    digits = re.sub(r"\D", "", stripped)

    if re.search(r"[^\d+]", stripped):
        return None, "chars"
    if not digits:
        return None, "empty"

    if has_plus:
        if len(digits) < 8:
            return None, "short"
        if len(digits) > 15:
            return None, "long"
        if digits.startswith("998"):
            return _uz(digits[3:])
        return "+" + digits, ""

    if digits.startswith("998") and len(digits) == 12:
        return _uz(digits[3:])
    if len(digits) == 9:
        return _uz(digits)
    if len(digits) == 10 and digits.startswith("0"):
        return _uz(digits[1:])
    if len(digits) == 11 and digits.startswith("8"):
        # Rossiya formati: 8XXXXXXXXXX -> +7XXXXXXXXXX
        return "+7" + digits[1:], ""
    if 10 <= len(digits) <= 15:
        return "+" + digits, ""
    if len(digits) < 9:
        return None, "short"
    return None, "long"


def _uz(local: str) -> Tuple[Optional[str], str]:
    """O'zbekiston raqamining 9 xonali qismini tekshiradi."""
    if len(local) != 9:
        return None, "short" if len(local) < 9 else "long"
    if local[:2] not in UZ_OPERATOR_CODES:
        return None, "operator"
    return "+998" + local, ""


def pretty_phone(phone: str) -> str:
    """+998901234567 -> +998 90 123 45 67"""
    if phone.startswith("+998") and len(phone) == 13:
        rest = phone[4:]
        return f"+998 {rest[:2]} {rest[2:5]} {rest[5:7]} {rest[7:]}"
    return phone
