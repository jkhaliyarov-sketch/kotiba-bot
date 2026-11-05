"""Shaxsiy kotiba Telegram boti - ishga tushirish fayli."""
import asyncio
import base64
import io
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message)

import brain
import config
import db
import tools
import voice

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kotiba")

dp = Dispatcher()
_locks: dict[int, asyncio.Lock] = {}

HELP = """Men sizning shaxsiy kotibangizman 🤝

Menga oddiy gapirib yozing yoki ovozli xabar yuboring:
• "Ertaga soat 10 da bankka borishni eslat"
• "Har dushanba 9 da hisobot topshirishni eslat"
• "Zarur ish: juma kuni soliq to'lash"
• "Taksiga 25 ming, tushlikka 60 ming berdim"
• "G'oya: kafe ochib, yetkazib berish qilish"
• "Bugun nima qilishim kerak?"
• "Shu oy qancha pul ishlatdim?"
• TZ yoki hujjat yuboring (matn, PDF, Word) — bajarib beraman
• Chek rasmini yuboring — xarajatga yozaman

Buyruqlar:
/bugun — bugungi kun tartibi
/vazifalar — ochiq vazifalar
/eslatmalar — faol eslatmalar
/xarajatlar — shu oygi xarajatlar
/excel — shu oygi xarajatlar Excel faylda
/goyalar — g'oyalar ro'yxati
/id — Telegram ID raqamingiz"""


# ---------------- ruxsat ----------------
def is_allowed(user_id: int) -> bool:
    if user_id in config.ALLOWED_USER_IDS:
        return True
    owner = db.get_setting("owner_id")
    return owner is not None and int(owner) == user_id


async def deny(message: Message) -> None:
    await message.answer(f"Bu shaxsiy bot. Sizning ID: {message.from_user.id}")


# ---------------- yordamchilar ----------------
async def send_long(bot: Bot, chat_id: int, text: str, **kw) -> None:
    while text:
        chunk = text[:4000]
        if len(text) > 4000 and "\n" in chunk:
            chunk = chunk[:chunk.rfind("\n")]
        await bot.send_message(chat_id, chunk, **kw)
        text = text[len(chunk):].lstrip("\n")


async def keep_typing(bot: Bot, chat_id: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        with suppress(Exception):
            await bot.send_chat_action(chat_id, "typing")
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=4.5)


async def process(message: Message, text: str, attachments: list[dict] | None = None, note: str = "") -> None:
    chat_id = message.chat.id
    lock = _locks.setdefault(chat_id, asyncio.Lock())
    async with lock:
        stop = asyncio.Event()
        typing = asyncio.create_task(keep_typing(message.bot, chat_id, stop))
        try:
            reply, out = await brain.handle(chat_id, text, attachments, note)
        except Exception:
            log.exception("Claude bilan xato")
            reply, out = "⚠️ Xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.", tools.TurnOutputs()
        finally:
            stop.set()
            await typing
        await send_long(message.bot, chat_id, reply)
        for fname, data in out.documents:
            await message.answer_document(BufferedInputFile(data, filename=fname))


async def download(message: Message, file_obj) -> bytes:
    buf = io.BytesIO()
    await message.bot.download(file_obj, destination=buf)
    return buf.getvalue()


# ---------------- buyruqlar ----------------
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    uid = message.from_user.id
    if not config.ALLOWED_USER_IDS and db.get_setting("owner_id") is None:
        db.set_setting("owner_id", str(uid))
        log.info("Egasi belgilandi: %s", uid)
        await message.answer("✅ Siz bu botning egasi sifatida belgilandingiz. Endi bot faqat sizga xizmat qiladi.")
    if not is_allowed(uid):
        return await deny(message)
    await message.answer(HELP)


@dp.message(Command("yordam", "help"))
async def cmd_help(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await message.answer(HELP)


@dp.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID: {message.from_user.id}")


@dp.message(Command("bugun"))
async def cmd_today(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await send_long(message.bot, message.chat.id, morning_brief_text(message.chat.id))


@dp.message(Command("vazifalar"))
async def cmd_tasks(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await send_long(message.bot, message.chat.id, tasks_text(message.chat.id) or "Ochiq vazifalar yo'q 🎉")


@dp.message(Command("eslatmalar"))
async def cmd_reminders(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    res = tools.run_tool(message.chat.id, "list_reminders", {}, tools.TurnOutputs())
    await send_long(message.bot, message.chat.id, "⏰ Faol eslatmalar:\n" + res)


@dp.message(Command("xarajatlar"))
async def cmd_expenses(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    start, end = month_range()
    res = tools.run_tool(message.chat.id, "expense_report", {"start_date": start, "end_date": end},
                         tools.TurnOutputs())
    await send_long(message.bot, message.chat.id, "💰 " + res)


@dp.message(Command("excel"))
async def cmd_excel(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    start, end = month_range()
    out = tools.TurnOutputs()
    res = tools.run_tool(message.chat.id, "export_expenses_excel", {"start_date": start, "end_date": end}, out)
    if not out.documents:
        return await message.answer(res)
    for fname, data in out.documents:
        await message.answer_document(BufferedInputFile(data, filename=fname))


@dp.message(Command("goyalar"))
async def cmd_ideas(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    res = tools.run_tool(message.chat.id, "list_ideas", {}, tools.TurnOutputs())
    await send_long(message.bot, message.chat.id, "💡 G'oyalar:\n" + res)


# ---------------- oddiy xabarlar ----------------
@dp.message(F.voice | F.audio | F.video_note)
async def on_voice(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    if not voice.enabled():
        return await message.answer("🎤 Ovozli xabarlar hali sozlanmagan (GROQ_API_KEY kerak). Hozircha matn yozing.")
    media = message.voice or message.audio or message.video_note
    data = await download(message, media)
    fname = "voice.ogg" if message.voice else ("audio.mp3" if message.audio else "video.mp4")
    try:
        text = await voice.transcribe(data, fname)
    except Exception:
        log.exception("STT xato")
        return await message.answer("⚠️ Ovozni matnga aylantirib bo'lmadi. Qayta yuboring yoki yozing.")
    if not text:
        return await message.answer("Ovozda gap eshitilmadi 🤔")
    await message.answer(f"🎤 Eshitdim: «{text}»")
    caption = message.caption or ""
    await process(message, (caption + "\n" + text).strip(), note="ovozli xabardan matn")


@dp.message(F.photo)
async def on_photo(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    data = await download(message, message.photo[-1])
    img = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.b64encode(data).decode()}}
    await process(message, message.caption or "Bu rasmni ko'rib chiq. Chek bo'lsa xarajatga yoz.", [img],
                  note="rasm yuborildi")


TEXT_EXT = (".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".html", ".css", ".sql", ".xml", ".yaml", ".yml")
IMG_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@dp.message(F.document)
async def on_document(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    doc = message.document
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        return await message.answer("Fayl juda katta (20 MB dan oshmasin).")
    name = (doc.file_name or "fayl").lower()
    mime = doc.mime_type or ""
    data = await download(message, doc)
    caption = message.caption or "Shu faylni o'qib chiq va undagi topshiriqni bajar."
    note = f"fayl: {doc.file_name}"

    if name.endswith(".pdf") or mime == "application/pdf":
        block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                  "data": base64.b64encode(data).decode()}}
        return await process(message, caption, [block], note)
    if mime in IMG_TYPES:
        block = {"type": "image", "source": {"type": "base64", "media_type": mime,
                                               "data": base64.b64encode(data).decode()}}
        return await process(message, caption, [block], note)
    if name.endswith(".docx"):
        from docx import Document

        d = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in d.paragraphs)
        for t in d.tables:
            for row in t.rows:
                text += "\n" + " | ".join(c.text for c in row.cells)
        return await process(message, f"{caption}\n\n--- {doc.file_name} ---\n{text}", note=note)
    if name.endswith(TEXT_EXT) or mime.startswith("text/"):
        text = data.decode("utf-8", errors="replace")
        return await process(message, f"{caption}\n\n--- {doc.file_name} ---\n{text}", note=note)
    await message.answer("Bu fayl turini o'qiy olmayman. Matn, PDF, Word (.docx) yoki rasm yuboring.")


@dp.message(F.text)
async def on_text(message: Message) -> None:
    if not is_allowed(message.from_user.id):
        return await deny(message)
    await process(message, message.text)


# ---------------- eslatma tugmalari ----------------
def reminder_keyboard(rid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"done:{rid}"),
        InlineKeyboardButton(text="⏰ 15 daq", callback_data=f"snz:{rid}:15"),
        InlineKeyboardButton(text="⏰ 1 soat", callback_data=f"snz:{rid}:60"),
    ]])


@dp.callback_query(F.data.startswith("done:"))
async def cb_done(cq: CallbackQuery) -> None:
    if not is_allowed(cq.from_user.id):
        return await cq.answer()
    await cq.answer("Barakalla! ✅")
    with suppress(Exception):
        await cq.message.edit_text(cq.message.text + "\n\n✅ Bajarildi")


@dp.callback_query(F.data.startswith("snz:"))
async def cb_snooze(cq: CallbackQuery) -> None:
    if not is_allowed(cq.from_user.id):
        return await cq.answer()
    _, rid, minutes = cq.data.split(":")
    rows = db.query("SELECT * FROM reminders WHERE id=?", (int(rid),))
    if not rows:
        return await cq.answer("Topilmadi")
    due = datetime.now(timezone.utc) + timedelta(minutes=int(minutes))
    db.execute("INSERT INTO reminders(chat_id,text,due_at,repeat,created_at) VALUES(?,?,?,?,?)",
               (rows[0]["chat_id"], rows[0]["text"], due.isoformat(timespec="seconds"), "none", db.now_utc_iso()))
    await cq.answer(f"{minutes} daqiqadan keyin yana eslataman")
    with suppress(Exception):
        await cq.message.edit_text(cq.message.text + f"\n\n⏰ {minutes} daqiqaga qoldirildi")


# ---------------- kunlik xulosalar ----------------
def month_range() -> tuple[str, str]:
    today = tools.now_local().date()
    return today.replace(day=1).isoformat(), today.isoformat()


def tasks_text(chat_id: int) -> str:
    today = tools.now_local().date().isoformat()
    rows = db.query("SELECT * FROM tasks WHERE chat_id=? AND status='open' ORDER BY "
                    "CASE priority WHEN 'zarur' THEN 0 ELSE 1 END, COALESCE(due_date,'9999'), id", (chat_id,))
    if not rows:
        return ""
    urgent = [r for r in rows if r["priority"] == "zarur"]
    other = [r for r in rows if r["priority"] != "zarur"]

    def line(r):
        due = r["due_date"]
        mark = ""
        if due:
            mark = " ❗️muddati o'tgan" if due < today else (" (bugun)" if due == today else f" ({due})")
        return f"  #{r['id']} {r['title']}{mark}"

    parts = []
    if urgent:
        parts.append("🔴 Zarur:\n" + "\n".join(line(r) for r in urgent))
    if other:
        parts.append("🟢 Zarur emas:\n" + "\n".join(line(r) for r in other[:15]))
    return "\n\n".join(parts)


def _reminders_between(chat_id: int, start_local: datetime, end_local: datetime) -> list[dict]:
    return db.query("SELECT * FROM reminders WHERE chat_id=? AND active=1 AND due_at>=? AND due_at<? ORDER BY due_at",
                    (chat_id, start_local.astimezone(timezone.utc).isoformat(timespec="seconds"),
                     end_local.astimezone(timezone.utc).isoformat(timespec="seconds")))


def morning_brief_text(chat_id: int) -> str:
    now = tools.now_local()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    parts = [f"☀️ Xayrli tong! Bugun {now:%d.%m.%Y}, {tools.WEEKDAYS_UZ[now.weekday()]}"]
    rems = _reminders_between(chat_id, day_start, day_start + timedelta(days=1))
    if rems:
        parts.append("⏰ Bugungi eslatmalar:\n" + "\n".join(
            f"  {datetime.fromisoformat(r['due_at']).astimezone(config.TIMEZONE):%H:%M} — {r['text']}" for r in rems))
    t = tasks_text(chat_id)
    parts.append(t if t else "Ochiq vazifalar yo'q 🎉")
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    exp = db.query("SELECT currency, SUM(amount) s FROM expenses WHERE chat_id=? AND spent_on=? GROUP BY currency",
                   (chat_id, yesterday))
    if exp:
        parts.append("💰 Kecha sarflangan: " + ", ".join(tools.fmt_money(r["s"], r["currency"]) for r in exp))
    return "\n\n".join(parts)


def evening_summary_text(chat_id: int) -> str:
    now = tools.now_local()
    today = now.date().isoformat()
    parts = ["🌙 Kun yakuni"]
    exp = db.query("SELECT * FROM expenses WHERE chat_id=? AND spent_on=?", (chat_id, today))
    if exp:
        parts.append("💰 " + tools.expense_summary_text(exp, today, today))
    else:
        parts.append("💰 Bugun xarajat yozilmadi. Biror narsa sotib olgan bo'lsangiz, hozir yozib qo'ying.")
    done = db.query("SELECT title FROM tasks WHERE chat_id=? AND status='done' AND done_at>=?",
                    (chat_id, now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
                     .isoformat(timespec="seconds")))
    if done:
        parts.append("✅ Bugun bajarilgan:\n" + "\n".join(f"  {r['title']}" for r in done))
    urgent = db.query("SELECT id,title FROM tasks WHERE chat_id=? AND status='open' AND priority='zarur'", (chat_id,))
    if urgent:
        parts.append("🔴 Hali qolgan zarur ishlar:\n" + "\n".join(f"  #{r['id']} {r['title']}" for r in urgent))
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rems = _reminders_between(chat_id, tomorrow, tomorrow + timedelta(days=1))
    if rems:
        parts.append("📅 Ertangi eslatmalar:\n" + "\n".join(
            f"  {datetime.fromisoformat(r['due_at']).astimezone(config.TIMEZONE):%H:%M} — {r['text']}" for r in rems))
    return "\n\n".join(parts)


# ---------------- rejalashtiruvchi ----------------
async def fire_due_reminders(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    due = db.query("SELECT * FROM reminders WHERE active=1 AND due_at<=? ORDER BY due_at",
                   (now.isoformat(timespec="seconds"),))
    for r in due:
        try:
            await bot.send_message(r["chat_id"], f"⏰ Eslatma: {r['text']}", reply_markup=reminder_keyboard(r["id"]))
        except Exception:
            log.exception("Eslatmani yuborib bo'lmadi #%s", r["id"])
        nxt = tools.next_occurrence(datetime.fromisoformat(r["due_at"]), r["repeat"])
        while nxt is not None and nxt <= now:
            nxt = tools.next_occurrence(nxt, r["repeat"])
        if nxt is None:
            db.execute("UPDATE reminders SET active=0 WHERE id=?", (r["id"],))
        else:
            db.execute("UPDATE reminders SET due_at=? WHERE id=?", (nxt.isoformat(timespec="seconds"), r["id"]))


async def maybe_daily(bot: Bot, key: str, hhmm: str, builder) -> None:
    if not hhmm:
        return
    now = tools.now_local()
    if now.strftime("%H:%M") < hhmm:
        return
    today = now.date().isoformat()
    if db.get_setting(key) == today:
        return
    db.set_setting(key, today)
    # Bot o'sha vaqtda o'chiq bo'lib, 2 soatdan keyin yoqilsa - eski xulosani yubormaymiz
    h, m = map(int, hhmm.split(":"))
    if now - now.replace(hour=h, minute=m, second=0, microsecond=0) > timedelta(hours=2):
        return
    for chat_id in db.owner_chat_ids():
        with suppress(Exception):
            await send_long(bot, chat_id, builder(chat_id))


async def scheduler(bot: Bot) -> None:
    while True:
        try:
            await fire_due_reminders(bot)
            await maybe_daily(bot, "last_morning", config.MORNING_BRIEF_TIME, morning_brief_text)
            await maybe_daily(bot, "last_evening", config.EVENING_SUMMARY_TIME, evening_summary_text)
        except Exception:
            log.exception("Scheduler xato")
        await asyncio.sleep(20)


async def main() -> None:
    missing = [n for n in ("TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY") if not getattr(config, n)]
    if missing:
        raise SystemExit(f"Quyidagi sozlamalar berilmagan: {', '.join(missing)}")
    db.conn()
    bot = Bot(config.TELEGRAM_BOT_TOKEN)
    task = asyncio.create_task(scheduler(bot))
    log.info("Bot ishga tushdi. Model: %s, ovoz: %s", config.CLAUDE_MODEL, "ha" if voice.enabled() else "yo'q")
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
