"""Barcha sozlamalar muhit o'zgaruvchilaridan (environment variables) o'qiladi."""
import os
from zoneinfo import ZoneInfo


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Majburiy
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")

# Ovozli xabarlar uchun (ixtiyoriy, lekin tavsiya etiladi)
OPENAI_API_KEY = _env("OPENAI_API_KEY")
STT_MODEL = _env("STT_MODEL", "gpt-4o-transcribe")
STT_LANGUAGE = _env("STT_LANGUAGE", "uz")  # bo'sh qoldirilsa tilni o'zi aniqlaydi

# Claude
CLAUDE_MODEL = _env("CLAUDE_MODEL", "claude-opus-5-5")

# Kim botdan foydalana oladi (vergul bilan Telegram ID lar).
# Bo'sh bo'lsa - /start bosgan BIRINCHI odam egasi bo'lib qoladi.
ALLOWED_USER_IDS = {int(x) for x in _env("ALLOWED_USER_IDS").replace(" ", "").split(",") if x}

# Vaqt
TIMEZONE = ZoneInfo(_env("TIMEZONE", "Asia/Tashkent"))
MORNING_BRIEF_TIME = _env("MORNING_BRIEF_TIME", "08:00")  # bo'sh = o'chirilgan
EVENING_SUMMARY_TIME = _env("EVENING_SUMMARY_TIME", "21:00")  # bo'sh = o'chirilgan

# Ma'lumotlar bazasi fayli (Railway'da volume /data ga ulanadi)
DB_PATH = _env("DB_PATH", "/data/kotiba.db" if os.path.isdir("/data") else "kotiba.db")

# Google Sheets (ixtiyoriy)
GOOGLE_CREDENTIALS_JSON = _env("GOOGLE_CREDENTIALS_JSON")
GOOGLE_SHEET_ID = _env("GOOGLE_SHEET_ID")

DEFAULT_CURRENCY = _env("DEFAULT_CURRENCY", "UZS")
