"""SQLite ma'lumotlar bazasi: eslatmalar, vazifalar, xarajatlar, g'oyalar, suhbat tarixi."""
import sqlite3
from datetime import datetime, timezone

import config

_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    due_at TEXT NOT NULL,            -- UTC ISO
    repeat TEXT NOT NULL DEFAULT 'none',  -- none|daily|weekdays|weekly|monthly
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    notes TEXT,
    priority TEXT NOT NULL DEFAULT 'oddiy',  -- zarur|oddiy
    due_date TEXT,                    -- YYYY-MM-DD (mahalliy)
    status TEXT NOT NULL DEFAULT 'open',     -- open|done
    created_at TEXT NOT NULL,
    done_at TEXT
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    category TEXT NOT NULL,
    note TEXT,
    spent_on TEXT NOT NULL,           -- YYYY-MM-DD (mahalliy)
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    tags TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL,               -- user|assistant
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders(active, due_at);
CREATE INDEX IF NOT EXISTS idx_exp_chat ON expenses(chat_id, spent_on);
"""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    c = conn()
    cur = c.execute(sql, params)
    c.commit()
    return cur


def query(sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn().execute(sql, params).fetchall()]


# --- settings ---
def get_setting(key: str) -> str | None:
    rows = query("SELECT value FROM settings WHERE key=?", (key,))
    return rows[0]["value"] if rows else None


def set_setting(key: str, value: str) -> None:
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value))


# --- history ---
def add_history(chat_id: int, role: str, text: str) -> None:
    execute("INSERT INTO history(chat_id,role,text,created_at) VALUES(?,?,?,?)",
            (chat_id, role, text, now_utc_iso()))
    # faqat oxirgi 200 tasini saqlaymiz
    execute("DELETE FROM history WHERE chat_id=? AND id NOT IN "
            "(SELECT id FROM history WHERE chat_id=? ORDER BY id DESC LIMIT 200)", (chat_id, chat_id))


def recent_history(chat_id: int, limit: int = 12) -> list[dict]:
    rows = query("SELECT role,text,created_at FROM history WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                 (chat_id, limit))
    return list(reversed(rows))


def owner_chat_ids() -> list[int]:
    ids = set(config.ALLOWED_USER_IDS)
    owner = get_setting("owner_id")
    if owner:
        ids.add(int(owner))
    return sorted(ids)
