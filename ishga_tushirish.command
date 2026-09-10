#!/bin/bash
# macOS: shu faylni ikki marta bosing - bot ishga tushadi.
cd "$(dirname "$0")" || exit 1
echo "Bot ishga tushmoqda... To'xtatish uchun Ctrl+C"
exec python3 main.py
