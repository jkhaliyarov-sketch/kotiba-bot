# Shaxsiy kotiba bot: ishga tushirish qo'llanmasi

Hammasi brauzer orqali qilinadi, dasturlash bilimi kerak emas. Taxminan 30–40 daqiqa oladi.

## 1-qadam. Telegram bot yaratish (bepul)
1. Telegram'da **@BotFather** ni oching va `/newbot` deb yozing.
2. Botga nom bering (masalan: `Mening Kotibam`).
3. Username bering, oxiri `bot` bilan tugashi kerak (masalan: `jahon_kotiba_bot`).
4. BotFather sizga **token** beradi (`123456789:AAH...` ko'rinishida). Uni saqlab qo'ying va hech kimga bermang.

## 2-qadam. Claude API kaliti
1. https://console.anthropic.com ga kiring va ro'yxatdan o'ting.
2. **Billing** bo'limida kartangizni ulang va 10$ atrofida balans to'ldiring.
3. **API Keys** → **Create Key**. `sk-ant-...` bilan boshlanadigan kalitni saqlab qo'ying.

## 3-qadam. Ovozli xabarlar uchun kalit
1. https://platform.openai.com ga kiring.
2. **Billing** bo'limida 5$ to'ldiring. Bu bir necha oyga yetadi, chunki 1 daqiqa ovoz taxminan 0.6 sent turadi.
3. **API keys** → **Create new secret key**. `sk-...` kalitni saqlang.

> Bu kalit faqat ovozni matnga aylantirish uchun kerak. Ovozdan olingan matnni keyin Claude tushunadi va bajaradi.

## 4-qadam. Kodni GitHub'ga joylash
Kodni sizning GitHub hisobingizga Claude joylab beradi, shunchaki ruxsat bering.
O'zingiz qilmoqchi bo'lsangiz: github.com → **New repository** → `kotiba-bot` (Private) → **uploading an existing file** → shu papkadagi barcha fayllarni tashlang.

## 5-qadam. Serverga qo'yish (Railway, oyiga ~5$)
1. https://railway.com ga kiring → **Login with GitHub**.
2. **New Project** → **Deploy from GitHub repo** → `kotiba-bot` ni tanlang.
3. Loyiha ichida servisni bosing → **Variables** bo'limiga quyidagilarni qo'shing:
   | Nomi | Qiymati |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | 1-qadamdagi token |
   | `ANTHROPIC_API_KEY` | 2-qadamdagi kalit |
   | `OPENAI_API_KEY` | 3-qadamdagi kalit |
4. Ma'lumotlar o'chib ketmasligi uchun servisga **Volume** qo'shing: servisni o'ng tugma bilan bosing (yoki **+ New** → **Volume**), **Mount path** ga `/data` yozing.
5. **Deploy** tugmasini bosing. **Deployments → Logs** da `Bot ishga tushdi` yozuvi chiqsa, hammasi joyida.

## 6-qadam. Botni yoqish
Telegram'da botingizni oching va **/start** bosing. Birinchi /start bosgan odam botning egasi bo'ladi, boshqalar bot bilan gaplasha olmaydi.

---

## Qanday foydalaniladi
- **Ovoz yoki matn:** "Ertaga soat 10 da bankka borishni eslat", "Taksiga 25 ming berdim", "Zarur ish: juma kuni soliq to'lash".
- **TZ:** matn qilib yozing yoki fayl yuboring (.txt, .pdf, .docx). Bot TZ ni o'qib, bajarib beradi. Javob uzun bo'lsa, fayl qilib yuboradi.
- **Chek rasmi:** rasmni yuborsangiz, summani o'qib xarajatga yozadi.
- **Har kuni ertalab 08:00 da** bugungi reja keladi. **Kechqurun 21:00 da** kunlik xarajatlar va qolgan ishlar haqida xulosa keladi.
- **Buyruqlar:** /bugun, /vazifalar, /eslatmalar, /xarajatlar, /excel, /goyalar

## Xarajatlar (taxminiy)
| Nima | Narxi |
|---|---|
| Railway server | ~5$/oy |
| Claude (Opus 5.5) | ishlatishga qarab. Kuniga 20–30 xabar bo'lsa, oyiga taxminan 15–35$ |
| Ovoz (OpenAI) | oyiga 1$ dan kam |

**Arzonroq qilish:** Railway Variables'ga `CLAUDE_MODEL` = `claude-sonnet-5-5` qo'shing. Taxminan 2 baravar arzon bo'ladi, kundalik ishlar uchun yetarli.
console.anthropic.com da oylik limit ham qo'yib qo'yish mumkin, shunda hech qachon belgilangan summadan oshmaydi.

## Qo'shimcha: xarajatlarni Google Sheets'ga yozish (ixtiyoriy)
Buni keyinroq qilsa ham bo'ladi, Claude bosqichma-bosqich ko'rsatib beradi. Qisqacha:
1. Google Cloud'da service account yarating va JSON kalitini yuklab oling.
2. Google Sheets'da jadval oching va uni service account email'iga **Editor** qilib ulashing.
3. Railway Variables'ga `GOOGLE_SHEET_ID` (jadval havolasidagi uzun ID) va `GOOGLE_CREDENTIALS_JSON` (JSON fayl matni) qo'shing.

Excel fayl esa hech qanday sozlamasiz ishlaydi: /excel buyrug'ini yuboring.
