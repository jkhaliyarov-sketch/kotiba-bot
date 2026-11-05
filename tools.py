"""Claude chaqira oladigan vositalar (tools) va ularning bajarilishi."""
import calendar
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import config
import db
import sheets

TZ = config.TIMEZONE
WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


# ---------------- vaqt yordamchilari ----------------
def now_local() -> datetime:
    return datetime.now(TZ)


def parse_local_dt(s: str) -> datetime:
    """'YYYY-MM-DD HH:MM' (mahalliy vaqt) -> timezone-aware UTC."""
    s = s.strip().replace("T", " ")
    dt = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=TZ).astimezone(timezone.utc)


def utc_iso_to_local_str(s: str) -> str:
    dt = datetime.fromisoformat(s).astimezone(TZ)
    return f"{dt:%Y-%m-%d %H:%M} ({WEEKDAYS_UZ[dt.weekday()]})"


def next_occurrence(due_utc: datetime, repeat: str) -> datetime | None:
    local = due_utc.astimezone(TZ)
    if repeat == "daily":
        nxt = local + timedelta(days=1)
    elif repeat == "weekdays":
        nxt = local + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
    elif repeat == "weekly":
        nxt = local + timedelta(weeks=1)
    elif repeat == "monthly":
        y, m = (local.year + (local.month // 12), local.month % 12 + 1)
        d = min(local.day, calendar.monthrange(y, m)[1])
        nxt = local.replace(year=y, month=m, day=d)
    else:
        return None
    # mahalliy soatni saqlash uchun qayta yig'amiz
    nxt = datetime(nxt.year, nxt.month, nxt.day, local.hour, local.minute, tzinfo=TZ)
    return nxt.astimezone(timezone.utc)


def fmt_money(amount: float, currency: str) -> str:
    s = f"{amount:,.0f}".replace(",", " ") if amount == int(amount) else f"{amount:,.2f}".replace(",", " ")
    return f"{s} {'so‘m' if currency == 'UZS' else currency}"


# ---------------- natija konteyneri ----------------
@dataclass
class TurnOutputs:
    """Bitta xabarni qayta ishlash davomida botga yuboriladigan fayllar."""
    documents: list[tuple[str, bytes]] = field(default_factory=list)


# ---------------- vositalar ta'rifi ----------------
def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


DATE_DESC = "Sana 'YYYY-MM-DD' formatida (mahalliy vaqt)."

TOOLS = [
    {
        "name": "add_reminder",
        "description": "Eslatma qo'shadi. Bot belgilangan vaqtda foydalanuvchiga xabar yuboradi. "
                       "Vaqt aytilmagan bo'lsa, foydalanuvchidan so'ra (taxmin qilma), faqat 'ertalab' kabi "
                       "noaniq bo'lsa oqilona vaqt tanla (ertalab=09:00, tushda=13:00, kechqurun=19:00).",
        "input_schema": _obj({
            "text": {"type": "string", "description": "Nimani eslatish kerak (qisqa, aniq)."},
            "due_at": {"type": "string", "description": "Mahalliy vaqt 'YYYY-MM-DD HH:MM'."},
            "repeat": {"type": "string", "enum": ["none", "daily", "weekdays", "weekly", "monthly"],
                       "description": "Takrorlanish. Odatda 'none'."},
        }, ["text", "due_at", "repeat"]),
    },
    {
        "name": "list_reminders",
        "description": "Faol (hali yuborilmagan yoki takrorlanadigan) eslatmalar ro'yxati.",
        "input_schema": _obj({}, []),
    },
    {
        "name": "delete_reminder",
        "description": "Eslatmani o'chiradi (bekor qiladi).",
        "input_schema": _obj({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "add_task",
        "description": "Vazifa (ish) qo'shadi. priority: 'zarur' - muhim/shoshilinch, kechiktirib bo'lmaydi; "
                       "'oddiy' - qilsa yaxshi, lekin zarur emas. Foydalanuvchi aytmasa, mazmunidan aniqla.",
        "input_schema": _obj({
            "title": {"type": "string"},
            "priority": {"type": "string", "enum": ["zarur", "oddiy"]},
            "due_date": {"type": ["string", "null"], "description": DATE_DESC + " Muddat bo'lmasa null."},
            "notes": {"type": ["string", "null"]},
        }, ["title", "priority"]),
    },
    {
        "name": "list_tasks",
        "description": "Vazifalar ro'yxati.",
        "input_schema": _obj({
            "status": {"type": "string", "enum": ["open", "done", "all"], "description": "Odatda 'open'."},
        }, ["status"]),
    },
    {
        "name": "update_task",
        "description": "Vazifani o'zgartiradi yoki bajarildi deb belgilaydi (status='done').",
        "input_schema": _obj({
            "id": {"type": "integer"},
            "title": {"type": ["string", "null"]},
            "priority": {"type": ["string", "null"], "enum": ["zarur", "oddiy", None]},
            "due_date": {"type": ["string", "null"]},
            "notes": {"type": ["string", "null"]},
            "status": {"type": ["string", "null"], "enum": ["open", "done", None]},
        }, ["id"]),
    },
    {
        "name": "delete_task",
        "description": "Vazifani butunlay o'chiradi.",
        "input_schema": _obj({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "add_expense",
        "description": "Xarajat yozadi. '25 ming' = 25000, '1.5 mln' / 'bir yarim million' = 1500000. "
                       "Bitta xabarda bir nechta xarajat bo'lsa, har biri uchun alohida chaqir. "
                       "Toifalar (shulardan birini tanla, mos kelmasa yangi qisqa nom): Oziq-ovqat, Kafe/restoran, "
                       "Transport, Uy/kommunal, Aloqa/internet, Kiyim, Sog'liq, Ta'lim, Ko'ngilochar, "
                       "Biznes, Sovg'a, Qarz berildi, Boshqa.",
        "input_schema": _obj({
            "amount": {"type": "number"},
            "currency": {"type": "string", "description": "UZS, USD, RUB, EUR ... Aytilmasa UZS."},
            "category": {"type": "string"},
            "note": {"type": ["string", "null"], "description": "Nima uchun (qisqa)."},
            "spent_on": {"type": ["string", "null"], "description": DATE_DESC + " Aytilmasa null (bugun)."},
        }, ["amount", "currency", "category"]),
    },
    {
        "name": "expense_report",
        "description": "Davr bo'yicha xarajatlar hisobi: jami, toifalar bo'yicha, eng katta xarajatlar.",
        "input_schema": _obj({
            "start_date": {"type": "string", "description": DATE_DESC},
            "end_date": {"type": "string", "description": DATE_DESC + " (shu kun ham kiradi)"},
        }, ["start_date", "end_date"]),
    },
    {
        "name": "list_expenses",
        "description": "Davr bo'yicha xarajatlar ro'yxati (id lari bilan) - tahrirlash/o'chirish uchun kerak.",
        "input_schema": _obj({
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
        }, ["start_date", "end_date"]),
    },
    {
        "name": "delete_expense",
        "description": "Xarajat yozuvini o'chiradi (masalan, xato yozilgan bo'lsa).",
        "input_schema": _obj({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "export_expenses_excel",
        "description": "Davr bo'yicha xarajatlarni Excel faylga chiqarib, foydalanuvchiga yuboradi.",
        "input_schema": _obj({
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
        }, ["start_date", "end_date"]),
    },
    {
        "name": "add_idea",
        "description": "G'oyani saqlaydi. Foydalanuvchi g'oya, fikr, reja aytganda ishlat.",
        "input_schema": _obj({
            "text": {"type": "string", "description": "G'oya matni (foydalanuvchi fikrini to'liq saqla)."},
            "tags": {"type": ["string", "null"], "description": "Vergul bilan teglar, masalan 'biznes, bot'."},
        }, ["text"]),
    },
    {
        "name": "list_ideas",
        "description": "Saqlangan g'oyalar. search berilsa, matn/teg bo'yicha qidiradi.",
        "input_schema": _obj({"search": {"type": ["string", "null"]}}, []),
    },
    {
        "name": "delete_idea",
        "description": "G'oyani o'chiradi.",
        "input_schema": _obj({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "send_document",
        "description": "Uzun natijani (TZ bo'yicha hujjat, reja, kod, maqola, shartnoma va h.k.) fayl qilib "
                       "foydalanuvchiga yuboradi. Natija ~3000 belgidan uzun bo'lsa yoki kod bo'lsa shuni ishlat, "
                       "chatga esa qisqa xulosa yoz.",
        "input_schema": _obj({
            "filename": {"type": "string", "description": "Masalan 'reja.md', 'bot.py', 'tz_javob.md'."},
            "content": {"type": "string", "description": "Faylning to'liq matni."},
        }, ["filename", "content"]),
    },
]


# ---------------- bajarish ----------------
def _today() -> str:
    return now_local().date().isoformat()


def _check_date(s: str) -> str:
    date.fromisoformat(s)
    return s


def run_tool(chat_id: int, name: str, args: dict, out: TurnOutputs) -> str:
    """Vositani bajaradi va Claude uchun matnli natija qaytaradi. Xatoda ValueError ko'taradi."""
    if name == "add_reminder":
        due = parse_local_dt(args["due_at"])
        repeat = args.get("repeat") or "none"
        if due < datetime.now(timezone.utc) - timedelta(minutes=1) and repeat == "none":
            raise ValueError("Bu vaqt allaqachon o'tib ketgan. Kelajakdagi vaqtni ber.")
        cur = db.execute("INSERT INTO reminders(chat_id,text,due_at,repeat,created_at) VALUES(?,?,?,?,?)",
                         (chat_id, args["text"], due.isoformat(timespec="seconds"), repeat, db.now_utc_iso()))
        return f"Eslatma #{cur.lastrowid} saqlandi: {utc_iso_to_local_str(due.isoformat())}, takror={repeat}"

    if name == "list_reminders":
        rows = db.query("SELECT * FROM reminders WHERE chat_id=? AND active=1 ORDER BY due_at", (chat_id,))
        if not rows:
            return "Faol eslatmalar yo'q."
        return "\n".join(f"#{r['id']} | {utc_iso_to_local_str(r['due_at'])} | {r['text']} | takror={r['repeat']}"
                         for r in rows)

    if name == "delete_reminder":
        cur = db.execute("UPDATE reminders SET active=0 WHERE id=? AND chat_id=?", (args["id"], chat_id))
        return "O'chirildi." if cur.rowcount else "Bunday eslatma topilmadi."

    if name == "add_task":
        due = args.get("due_date")
        if due:
            _check_date(due)
        cur = db.execute("INSERT INTO tasks(chat_id,title,notes,priority,due_date,created_at) VALUES(?,?,?,?,?,?)",
                         (chat_id, args["title"], args.get("notes"), args["priority"], due, db.now_utc_iso()))
        return f"Vazifa #{cur.lastrowid} qo'shildi ({args['priority']}, muddat: {due or 'yo‘q'})."

    if name == "list_tasks":
        status = args.get("status", "open")
        sql = "SELECT * FROM tasks WHERE chat_id=?"
        params: tuple = (chat_id,)
        if status != "all":
            sql += " AND status=?"
            params += (status,)
        sql += " ORDER BY status, CASE priority WHEN 'zarur' THEN 0 ELSE 1 END, COALESCE(due_date,'9999'), id"
        rows = db.query(sql, params)
        if not rows:
            return "Vazifalar yo'q."
        return "\n".join(
            f"#{r['id']} | {r['priority']} | {r['status']} | muddat: {r['due_date'] or '-'} | {r['title']}"
            + (f" | izoh: {r['notes']}" if r["notes"] else "") for r in rows)

    if name == "update_task":
        fields, params = [], []
        for k in ("title", "priority", "due_date", "notes", "status"):
            if args.get(k) is not None:
                if k == "due_date":
                    _check_date(args[k])
                fields.append(f"{k}=?")
                params.append(args[k])
        if args.get("status") == "done":
            fields.append("done_at=?")
            params.append(db.now_utc_iso())
        if not fields:
            raise ValueError("O'zgartirish uchun hech narsa berilmadi.")
        cur = db.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=? AND chat_id=?",
                         (*params, args["id"], chat_id))
        return "Yangilandi." if cur.rowcount else "Bunday vazifa topilmadi."

    if name == "delete_task":
        cur = db.execute("DELETE FROM tasks WHERE id=? AND chat_id=?", (args["id"], chat_id))
        return "O'chirildi." if cur.rowcount else "Bunday vazifa topilmadi."

    if name == "add_expense":
        amount = float(args["amount"])
        if amount <= 0:
            raise ValueError("Summa musbat bo'lishi kerak.")
        currency = (args.get("currency") or config.DEFAULT_CURRENCY).upper()
        spent_on = _check_date(args["spent_on"]) if args.get("spent_on") else _today()
        cur = db.execute(
            "INSERT INTO expenses(chat_id,amount,currency,category,note,spent_on,created_at) VALUES(?,?,?,?,?,?,?)",
            (chat_id, amount, currency, args["category"], args.get("note"), spent_on, db.now_utc_iso()))
        sheets.append_expense_async(spent_on, amount, currency, args["category"], args.get("note") or "")
        today_total = db.query("SELECT currency, SUM(amount) s FROM expenses WHERE chat_id=? AND spent_on=? "
                               "GROUP BY currency", (chat_id, spent_on))
        totals = ", ".join(fmt_money(r["s"], r["currency"]) for r in today_total)
        return (f"Xarajat #{cur.lastrowid} yozildi: {fmt_money(amount, currency)}, {args['category']}, {spent_on}. "
                f"Shu kungi jami: {totals}")

    if name in ("expense_report", "list_expenses", "export_expenses_excel"):
        start, end = _check_date(args["start_date"]), _check_date(args["end_date"])
        rows = db.query("SELECT * FROM expenses WHERE chat_id=? AND spent_on BETWEEN ? AND ? ORDER BY spent_on, id",
                        (chat_id, start, end))
        if not rows:
            return f"{start} — {end} oralig'ida xarajat yo'q."
        if name == "list_expenses":
            return "\n".join(f"#{r['id']} | {r['spent_on']} | {fmt_money(r['amount'], r['currency'])} | "
                             f"{r['category']} | {r['note'] or ''}" for r in rows[-100:])
        if name == "export_expenses_excel":
            out.documents.append((f"xarajatlar_{start}_{end}.xlsx", build_excel(rows)))
            return f"Excel fayl tayyorlandi ({len(rows)} ta yozuv) va yuboriladi."
        return expense_summary_text(rows, start, end)

    if name == "add_idea":
        cur = db.execute("INSERT INTO ideas(chat_id,text,tags,created_at) VALUES(?,?,?,?)",
                         (chat_id, args["text"], args.get("tags"), db.now_utc_iso()))
        return f"G'oya #{cur.lastrowid} saqlandi."

    if name == "list_ideas":
        q = args.get("search")
        if q:
            rows = db.query("SELECT * FROM ideas WHERE chat_id=? AND (text LIKE ? OR tags LIKE ?) ORDER BY id DESC",
                            (chat_id, f"%{q}%", f"%{q}%"))
        else:
            rows = db.query("SELECT * FROM ideas WHERE chat_id=? ORDER BY id DESC LIMIT 50", (chat_id,))
        if not rows:
            return "G'oyalar topilmadi."
        return "\n".join(f"#{r['id']} | {r['created_at'][:10]} | {r['text']}" +
                         (f" [{r['tags']}]" if r["tags"] else "") for r in rows)

    if name == "delete_idea":
        cur = db.execute("DELETE FROM ideas WHERE id=? AND chat_id=?", (args["id"], chat_id))
        return "O'chirildi." if cur.rowcount else "Bunday g'oya topilmadi."

    if name == "send_document":
        fname = args["filename"].replace("/", "_").strip() or "hujjat.md"
        out.documents.append((fname, args["content"].encode("utf-8")))
        return f"'{fname}' fayli yuboriladi."

    raise ValueError(f"Noma'lum vosita: {name}")


# ---------------- hisobot yordamchilari ----------------
def expense_summary_text(rows: list[dict], start: str, end: str) -> str:
    by_cur: dict[str, float] = {}
    by_cat: dict[tuple[str, str], float] = {}
    for r in rows:
        by_cur[r["currency"]] = by_cur.get(r["currency"], 0) + r["amount"]
        key = (r["category"], r["currency"])
        by_cat[key] = by_cat.get(key, 0) + r["amount"]
    lines = [f"Davr: {start} — {end}, yozuvlar: {len(rows)}",
             "Jami: " + ", ".join(fmt_money(v, k) for k, v in by_cur.items()), "Toifalar bo'yicha:"]
    for (cat, cur), v in sorted(by_cat.items(), key=lambda x: -x[1]):
        share = v / by_cur[cur] * 100 if by_cur[cur] else 0
        lines.append(f"  - {cat}: {fmt_money(v, cur)} ({share:.0f}%)")
    top = sorted(rows, key=lambda r: -r["amount"])[:5]
    lines.append("Eng katta xarajatlar:")
    lines += [f"  - {r['spent_on']}: {fmt_money(r['amount'], r['currency'])} — {r['category']} {r['note'] or ''}"
              for r in top]
    return "\n".join(lines)


def build_excel(rows: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Xarajatlar"
    ws.append(["Sana", "Summa", "Valyuta", "Toifa", "Izoh"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([r["spent_on"], r["amount"], r["currency"], r["category"], r["note"] or ""])
    for col, w in zip("ABCDE", (12, 14, 9, 18, 40)):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("Toifalar")
    ws2.append(["Toifa", "Valyuta", "Jami"])
    for c in ws2[1]:
        c.font = Font(bold=True)
    agg: dict[tuple[str, str], float] = {}
    for r in rows:
        agg[(r["category"], r["currency"])] = agg.get((r["category"], r["currency"]), 0) + r["amount"]
    for (cat, cur), v in sorted(agg.items(), key=lambda x: -x[1]):
        ws2.append([cat, cur, v])
    ws2.column_dimensions["A"].width = 20

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def tool_input_json(args: dict) -> str:
    return json.dumps(args, ensure_ascii=False)
