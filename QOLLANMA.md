# Shaxsiy kotiba bot: ishga tushirish qo'llanmasi

Hammasi brauzer va sichqoncha bilan qilinadi, dasturlash bilimi kerak emas.

## 1-qadam. Telegram bot yaratish (bepul)
1. Telegram'da **@BotFather** ni oching va `/newbot` deb yozing.
2. Botga nom bering, so'ng oxiri `bot` bilan tugaydigan username bering.
3. BotFather bergan **tokenni** saqlab qo'ying.

## 2-qadam. Claude API kaliti (bir marta 5$, bir necha oyga yetadi)
1. https://console.anthropic.com ga kiring.
2. **Billing** → kartani qo'shing (Visa/Mastercard) → **5$** to'ldiring.
   **Limits** bo'limida oylik chegara qo'ying, masalan 5$.
3. **API Keys** → **Create Key** → `sk-ant-...` kalitni saqlang. U faqat bir marta ko'rsatiladi.

Bot **Claude Haiku 5.5** modelida ishlaydi. Kuniga 30 ta xabar yozilsa, oyiga taxminan 1$ ketadi.

## 3-qadam. Ovoz uchun Groq kaliti (bepul, kartasiz)
1. https://console.groq.com ga kiring (Google hisobi bilan kirsa bo'ladi).
2. **API Keys** → **Create API Key** → `gsk_...` kalitni saqlang.

## 4-qadam. Python o'rnatish (bir marta)
1. https://www.python.org/downloads/ → **Download Python** tugmasini bosing.
2. O'rnatuvchining birinchi oynasida pastdagi **"Add python.exe to PATH"** belgisini **albatta** qo'ying, keyin **Install Now** ni bosing.

## 5-qadam. Botni kompyuterga yuklab olish
1. https://github.com/jkhaliyarov-sketch/kotiba-bot ni oching.
2. Yashil **Code** tugmasi → **Download ZIP**.
3. ZIP faylni o'ng tugma bilan bosing → **Extract All** (Извлечь все) → masalan `C:\kotiba-bot` papkasiga chiqaring.

## 6-qadam. Ishga tushirish
1. Papkadagi **start.bat** faylini ikki marta bosing.
   Windows "Windows protected your PC" deb chiqarsa: **More info** → **Run anyway** ni bosing.
2. Birinchi marta qora oyna 3 ta kalitni so'raydi. Har birini nusxalang, oynada **sichqonchaning o'ng tugmasini** bosing (shunda matn joylashadi), keyin **Enter** ni bosing.
3. `Bot ishga tushdi` yozuvi chiqsa, hammasi tayyor. Bu oynani yopmang, kichraytirib qo'ysangiz bo'ladi.
4. Telegram'da botingizni oching va **/start** bosing. Birinchi /start bosgan odam botning egasi bo'ladi.

### Kompyuter yoqilganda bot o'zi ishga tushsin desangiz
1. `Win + R` bosing, `shell:startup` deb yozing va Enter bosing.
2. Ochilgan papkaga **start.bat** ning yorlig'ini (ярлык) qo'ying: start.bat ni o'ng tugma bilan bosing → **Create shortcut**, keyin yorliqni shu papkaga ko'chiring.

### Muhim
- Bot faqat kompyuter yoniq va internet bor paytda ishlaydi.
- Kompyuter o'chiq paytga to'g'ri kelgan eslatmalar kompyuter yoqilishi bilan keladi.
- Kalitlar papkadagi `.env` faylida saqlanadi. Bu faylni hech kimga bermang.
- Kalitni almashtirmoqchi bo'lsangiz, `.env` faylini o'chirib, start.bat ni qayta ishga tushiring.

---

## Qanday foydalaniladi
- **Ovoz yoki matn:** "Ertaga soat 10 da bankka borishni eslat", "Taksiga 25 ming berdim", "Zarur ish: juma kuni soliq to'lash".
- **Chek rasmi:** summani o'qib, xarajatga yozadi.
- **Har kuni ertalab 08:00 da** reja, **kechqurun 21:00 da** xulosa keladi.
- **Buyruqlar:** /bugun, /vazifalar, /eslatmalar, /xarajatlar, /excel, /goyalar
- **Katta TZ'lar:** ularni Claude ilovasida to'g'ridan-to'g'ri Claude'ga bering. Bu Pro obunangiz ichida, qo'shimcha to'lovsiz.

## Keyinchalik kuchaytirish
Kuchliroq model kerak bo'lsa, `.env` faylidagi `CLAUDE_MODEL=claude-haiku-5-5` qatorini `claude-sonnet-5-5` yoki `claude-opus-5-5` ga o'zgartiring va botni qayta ishga tushiring.
24 soat ishlashi kerak bo'lsa, botni serverga (Railway yoki Oracle) ko'chirish mumkin. Dockerfile tayyor.
