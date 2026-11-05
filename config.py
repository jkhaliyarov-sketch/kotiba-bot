"""Barcha sozlamalar muhit o'zgaruvchilaridan (environment variables) o'qiladi."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_dotenv() -> None:
    """Loyiha papkasidagi .env faylini o'qiydi (kompyuterda ishga tushirish uchun)."""
    path = Path(__file__).with_name(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Majburiy
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")

# Ovozli xabarlar uchun: GROQ (bepul) yoki OPENAI kaliti
GROQ_API_KEY = _env("GROQ_API_KEY")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
STT_MODEL = _env("STT_MODEL", "whisper-large-v3" if GROQ_API_KEY else "gpt-4o-transcribe")
STT_LANGUAGE = _env("STT_LANGUAGE", "uz")  # bo'sh qoldirilsa tilni o'zi aniqlaydi

# Claude
# Arzon va tez: claude-haiku-5-5. Kuchliroq: claude-sonnet-5-5 yoki claude-opus-5-5
CLAUDE_MODEL = _env("CLAUDE_MODEL", "claude-haiku-5-5")

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
