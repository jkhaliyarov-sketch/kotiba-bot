"""Ovozli xabarni matnga aylantirish (Groq yoki OpenAI transcription API)."""
import config

_client = None

# Modelga o'zbekcha so'zlarni yaxshiroq tanishga yordam beradigan namuna matn
PROMPT_HINT = ("O'zbek tilida gapirilmoqda. Ba'zan ruscha so'zlar aralashadi. "
               "Masalan: eslatib qo'y, ertaga soat o'nda, vazifa, zarur, xarajat, ming so'm, "
               "million, taksiga, g'oya, TZ, texnik topshiriq.")


GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def enabled() -> bool:
    return bool(config.GROQ_API_KEY or config.OPENAI_API_KEY)


async def transcribe(audio: bytes, filename: str = "voice.ogg") -> str:
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        if config.GROQ_API_KEY:  # Groq - OpenAI bilan bir xil API, bepul tarifi bor
            _client = AsyncOpenAI(api_key=config.GROQ_API_KEY, base_url=GROQ_BASE_URL)
        else:
            _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    kwargs = {"model": config.STT_MODEL, "file": (filename, audio), "prompt": PROMPT_HINT}
    if config.STT_LANGUAGE:
        kwargs["language"] = config.STT_LANGUAGE
    result = await _client.audio.transcriptions.create(**kwargs)
    return (result.text or "").strip()
