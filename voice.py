"""Ovozli xabarni matnga aylantirish (OpenAI transcription API)."""
import config

_client = None

# Modelga o'zbekcha so'zlarni yaxshiroq tanishga yordam beradigan namuna matn
PROMPT_HINT = ("O'zbek tilida gapirilmoqda. Ba'zan ruscha so'zlar aralashadi. "
               "Masalan: eslatib qo'y, ertaga soat o'nda, vazifa, zarur, xarajat, ming so'm, "
               "million, taksiga, g'oya, TZ, texnik topshiriq.")


def enabled() -> bool:
    return bool(config.OPENAI_API_KEY)


async def transcribe(audio: bytes, filename: str = "voice.ogg") -> str:
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    kwargs = {"model": config.STT_MODEL, "file": (filename, audio), "prompt": PROMPT_HINT}
    if config.STT_LANGUAGE:
        kwargs["language"] = config.STT_LANGUAGE
    result = await _client.audio.transcriptions.create(**kwargs)
    return (result.text or "").strip()
