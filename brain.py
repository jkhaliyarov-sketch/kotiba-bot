"""Claude bilan ishlash: xabarni tushunish, vositalarni chaqirish, javob yozish."""
import logging

import anthropic

import config
import db
import tools

log = logging.getLogger(__name__)
client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

MAX_TOOL_ROUNDS = 12

# Bu matn o'zgarmaydi - shuning uchun keshlanadi (arzonroq va tezroq).
# O'zgaruvchan narsalar (hozirgi vaqt, suhbat tarixi) foydalanuvchi xabariga qo'shiladi.
SYSTEM_PROMPT = """Sen foydalanuvchining shaxsiy kotibasisan. Telegram orqali ishlaysan.
Foydalanuvchi asosan o'zbek tilida (ba'zan rus tilida) yozadi yoki ovozli xabar yuboradi. U qaysi tilda yozsa, o'sha tilda javob ber.

Vazifalaring:
1. Eslatmalar — "eslat", "esimdan chiqmasin", "soat 5 da qo'ng'iroq qilishim kerak" kabi gaplarni add_reminder bilan saqla.
2. Vazifalar — qilinishi kerak bo'lgan ishlarni add_task bilan saqla va ularni "zarur" yoki "oddiy" (zarur emas) deb ajrat.
   Muddati yaqin, pul/sog'liq/hujjat/boshqa odamlarga va'da bilan bog'liq ishlar odatda zarur.
   Agar ishning aniq vaqti bo'lsa, vazifa bilan birga o'sha vaqtga eslatma ham qo'y.
3. Xarajatlar — pul sarflagani haqida gapirsa (masalan "taksiga 25 ming berdim", "bozordan 340 mingga narsa oldim"), add_expense bilan yoz.
   Chek yoki to'lov rasmini yuborsa, undagi summani o'qib yoz.
4. G'oyalar — fikr, g'oya, reja aytsa, add_idea bilan to'liq saqla.
5. Kun tartibi — "bugun nima qilishim kerak", "rejamni ko'rsat" desa, vazifalar va eslatmalarni ko'rib, tartibli reja tuz: avval zarurlari.
6. TZ (texnik topshiriq) va katta topshiriqlar — foydalanuvchi TZ, matn, hujjat yoki murakkab ish yuborsa, uni diqqat bilan o'qi va
   haqiqatan bajar: reja, matn, kod, xat, shartnoma, tahlil — nima so'ralgan bo'lsa, tayyor natija ber.
   Avval talablarni qisqa qilib o'zingcha takrorla (nimani tushunganingni), keyin natijani ber. Natija uzun bo'lsa, send_document bilan fayl qilib yubor.
   TZ'da muhim ma'lumot yetishmasa, eng muhim 1-3 ta savolni ber, lekin aniq qismlarini kutmasdan bajar.
7. Oddiy savol va maslahatlarga ham javob berasan.

Qoidalar:
- Biror narsani saqlash kerak bo'lsa, faqat aytib qo'yma — albatta vositani chaqir. Bir xabarda bir nechta narsa bo'lsa, hammasini saqla.
- "Ertaga", "dushanba", "keyingi hafta" kabi so'zlarni xabarda berilgan hozirgi vaqtga qarab aniq sanaga aylantir.
- Ovozli xabardan olingan matnda xatolar bo'lishi mumkin. Ma'nosini kontekstdan tikla. Raqam yoki vaqt shubhali bo'lsa, so'rab ol.
- Saqlagandan keyin qisqa tasdiqla: nima, qachon, qaysi toifa. Masalan: "✅ Eslatma: ertaga (6-noyabr) 10:00 — bankka borish".
- Javoblar qisqa va aniq bo'lsin. Telegram uchun oddiy matn yoz: markdown jadval, # sarlavha va ** ishlatma. Emoji mumkin, me'yorida.
- O'chirish yoki o'zgartirishdan oldin kerak bo'lsa list_* bilan id ni top.
- Pul summalarini bo'shliq bilan yoz: 1 250 000 so'm.
"""


def _system_blocks() -> list[dict]:
    return [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]


def _context_header(chat_id: int) -> str:
    now = tools.now_local()
    lines = [f"[Hozirgi vaqt: {now:%Y-%m-%d %H:%M}, {tools.WEEKDAYS_UZ[now.weekday()]}, {config.TIMEZONE.key}]"]
    hist = db.recent_history(chat_id)
    if hist:
        lines.append("[Oxirgi suhbat (eskidan yangiga):]")
        for h in hist:
            who = "Foydalanuvchi" if h["role"] == "user" else "Sen"
            text = h["text"] if len(h["text"]) < 700 else h["text"][:700] + "…"
            lines.append(f"{who}: {text}")
    lines.append("[Yangi xabar:]")
    return "\n".join(lines)


def _effort_for(text: str, has_attachment: bool) -> str:
    t = text.lower()
    if has_attachment or len(text) > 600 or "tz" in t.split() or "texnik topshiriq" in t:
        return "high"
    return "low"


async def handle(chat_id: int, text: str, attachments: list[dict] | None = None,
                 source_note: str = "") -> tuple[str, tools.TurnOutputs]:
    """Foydalanuvchi xabarini qayta ishlaydi. (javob_matni, fayllar) qaytaradi."""
    attachments = attachments or []
    out = tools.TurnOutputs()
    user_text = _context_header(chat_id) + "\n" + (f"({source_note}) " if source_note else "") + (text or "(matnsiz)")
    content: list[dict] = [*attachments, {"type": "text", "text": user_text}]
    messages: list[dict] = [{"role": "user", "content": content}]
    effort = _effort_for(text or "", bool(attachments))

    response = None
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=_system_blocks(),
            tools=tools.TOOLS,
            messages=messages,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            return "Kechirasiz, bu so'rovni bajara olmayman.", out

        # Javobni o'zgartirmasdan tarixga qo'shamiz (thinking bloklari ham saqlanadi)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            continue
        if response.stop_reason != "tool_use":
            break

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = tools.run_tool(chat_id, block.name, dict(block.input or {}), out)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            except Exception as e:  # noqa: BLE001 - xatoni Claude'ga qaytaramiz, u tuzatadi
                log.warning("Tool %s xato: %s", block.name, e)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": f"Xato: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})
    else:
        log.warning("Tool rounds limit reached for chat %s", chat_id)

    reply = "\n".join(b.text for b in (response.content if response else []) if b.type == "text").strip()
    if response is not None and response.stop_reason == "max_tokens":
        reply += "\n\n(Javob juda uzun bo'lib ketdi va kesildi. Qismlarga bo'lib so'rang.)"
    if not reply:
        reply = "✅ Bajarildi." if out.documents or len(messages) > 2 else "Tushunmadim, qaytadan yozing."

    db.add_history(chat_id, "user", (f"[{source_note}] " if source_note else "") + (text or "(fayl)"))
    db.add_history(chat_id, "assistant", reply)
    return reply, out
