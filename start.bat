@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title Shaxsiy kotiba bot

if not exist .env (
  echo ============================================
  echo   Birinchi sozlash. Kalitlarni kiriting.
  echo   Joylash: sichqonchaning O'NG tugmasini bosing.
  echo ============================================
  set /p TG=1. Telegram bot tokeni: 
  set /p AK=2. Claude API kaliti ^(sk-ant-...^): 
  set /p GK=3. Groq API kaliti ^(gsk_...^), bo'lmasa Enter: 
  call :writeenv
)

if not exist .venv\Scripts\python.exe (
  echo Birinchi marta o'rnatilmoqda, 1-3 daqiqa kuting...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if not exist .venv\Scripts\python.exe (
    echo XATO: Python topilmadi. python.org dan o'rnating va "Add python.exe to PATH" ni belgilang.
    pause
    exit /b 1
  )
)
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt

:loop
echo Bot ishga tushmoqda... Bu oynani yopmang. To'xtatish uchun oynani yoping.
.venv\Scripts\python bot.py
echo Bot to'xtadi. 15 soniyadan keyin qayta ishga tushadi...
timeout /t 15 >nul
goto loop

:writeenv
setlocal EnableDelayedExpansion
(
  echo TELEGRAM_BOT_TOKEN=!TG!
  echo ANTHROPIC_API_KEY=!AK!
  echo GROQ_API_KEY=!GK!
  echo CLAUDE_MODEL=claude-haiku-5-5
) > .env
endlocal
echo Sozlamalar .env fayliga saqlandi.
exit /b 0
