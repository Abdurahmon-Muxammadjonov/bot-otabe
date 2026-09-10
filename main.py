#!/usr/bin/env python3
"""So'rov (zayavka) boti - ishga tushirish nuqtasi.

Ishlatish:
    python3 main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
