"""Ixtiyoriy: har bir xarajatni Google Sheets jadvaliga ham yozish.

GOOGLE_CREDENTIALS_JSON va GOOGLE_SHEET_ID berilmasa, hech narsa qilmaydi.
"""
import asyncio
import json
import logging

import config

log = logging.getLogger(__name__)
_ws = None


def enabled() -> bool:
    return bool(config.GOOGLE_CREDENTIALS_JSON and config.GOOGLE_SHEET_ID)


def _worksheet():
    global _ws
    if _ws is None:
        import gspread

        gc = gspread.service_account_from_dict(json.loads(config.GOOGLE_CREDENTIALS_JSON))
        sh = gc.open_by_key(config.GOOGLE_SHEET_ID)
        try:
            _ws = sh.worksheet("Xarajatlar")
        except gspread.WorksheetNotFound:
            _ws = sh.add_worksheet("Xarajatlar", rows=1000, cols=6)
            _ws.append_row(["Sana", "Summa", "Valyuta", "Toifa", "Izoh"])
    return _ws


def _append(row: list) -> None:
    try:
        _worksheet().append_row(row, value_input_option="USER_ENTERED")
    except Exception:  # Sheets ishlamasa ham bot to'xtamasin
        log.exception("Google Sheets'ga yozib bo'lmadi")


def append_expense_async(spent_on: str, amount: float, currency: str, category: str, note: str) -> None:
    if not enabled():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _append([spent_on, amount, currency, category, note])
        return
    loop.run_in_executor(None, _append, [spent_on, amount, currency, category, note])
