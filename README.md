# 📋 Zayavka (so'rov) boti

Mijoz **1-botga** (so'rov boti) **/start** bosadi → bot ismini so'raydi → telefon
raqamini so'raydi → «Zayavkangiz qabul qilindi, tez orada aloqaga chiqamiz» deb javob beradi.
Yig'ilgan ma'lumot esa **2-botga (admin boti)** tushadi — o'sha yerda adminlar ko'radi.

> Agar 2-bot hali sozlanmagan bo'lsa (token bo'sh), zayavka yo'qolmasligi uchun
> **zaxira sifatida 1-bot adminlariga** boradi. 2-bot ulanishi bilan hammasi 2-botga o'tadi.

Botning ichida **Mini App** ham bor — «🔍 Sotuv bo'limi auditi» (28 savol, 6 daqiqa).
Mijoz auditdan o'tib, ism/telefonini qoldiradi → bu ham **zayavka** sifatida adminlarga
tushadi, lekin audit natijasi (ball, zaif nuqtalar) bilan birga. Batafsil: [7-bo'lim](#-7-mini-app-sotuv-auditi).

Hech qanday kutubxona o'rnatish shart emas: faqat **Python 3.8+** kerak.

---

## 🚀 1. Ishga tushirish (3 qadam)

### 1-qadam. Admin bot tokenini qo'ying

`.env` faylini oching va `ADMIN_BOT_TOKEN=` qatoriga 2-botning tokenini yozing:

```
ADMIN_BOT_TOKEN=8860610719:AAG...
```

> ⚠️ Siz yuborgan 2-bot tokeni **noto'g'ri** edi (ichida `Ø` belgisi bor edi, Telegram uni
> rad etdi). To'g'ri tokenni [@BotFather](https://t.me/BotFather) → `/mybots` → botni tanlang
> → **API Token** dan oling.
>
> Agar bu qatorni bo'sh qoldirsangiz — bot baribir ishlaydi, lekin zayavkalar faqat
> **so'rov botiga** tushadi.

### 2-qadam. Botni yoqing

Terminalda:

```bash
cd "/Users/macbook/new bot"
python3 main.py
```

yoki `ishga_tushirish.command` faylini **ikki marta bosing**.

To'xtatish uchun: `Ctrl + C`.

### 3-qadam. O'zingizni admin qiling

Zayavkalarni ko'rish uchun har bir botga ulanishingiz kerak:

| Bot | Nima qilish kerak |
|---|---|
| **Admin boti** (2-bot) | Botga `/start` yozing → parolni yuboring |
| **So'rov boti** (1-bot) | Botga `/admin <parol>` deb yozing |

Parol `.env` faylidagi `ADMIN_PASSWORD` da — uni albatta o'zgartiring.

---

## 👤 2. Mijoz nimani ko'radi

```
/start
  → Assalomu alaykum! 👋
    Otabek Sobirov xizmatiga xush kelibsiz.
    So'rov (zayavka) qoldirish uchun iltimos ismingizni kiriting:

Otabek
  → Rahmat, Otabek! 🙏
    Endi telefon raqamingizni yuboring.
    [📱 Raqamni yuborish]  ← bir bosishda yuboradi
    [🚫 Bekor qilish]

+998 90 123 45 67
  → ✅ Zayavkangiz qabul qilindi!
    👤 Ism: Otabek
    📞 Telefon: +998 90 123 45 67
    Tez orada siz bilan aloqaga chiqamiz. Murojaatingiz uchun rahmat! 🤝
```

Mijoz buyruqlari: `/start`, `/audit` (Mini App), `/bekor`, `/yordam`.

---

## 🔔 3. Admin nimani ko'radi

Har bir yangi zayavka **2-botga (admin boti)** shu ko'rinishda tushadi:

```
🆕 Yangi zayavka #12

👤 Ism: Otabek Sobirov
📞 Telefon: +998 90 123 45 67
👥 Telegram: @otabek
🆔 ID: 555001
🕒 Vaqt: 11.09.2026 14:33

[✅ Bog'landim]  [❌ Bekor]
[💬 Mijozga yozish]
```

- **✅ Bog'landim** — zayavka «bajarildi» deb belgilanadi (matn avtomatik yangilanadi,
  xabar avtomatik yangilanadi).
- **💬 Mijozga yozish** — to'g'ridan-to'g'ri mijoz bilan chatni ochadi.

### Admin buyruqlari

| Buyruq | Vazifasi |
|---|---|
| `/statistika` | Jami / bugungi / yangi / bog'lanilgan zayavkalar soni |
| `/oxirgi` | Oxirgi 10 ta zayavka |
| `/yangi` | Hali javob berilmagan zayavkalar |
| `/eksport` | Barcha zayavkalar — Excel ochadigan CSV fayl |
| `/id` | O'z Telegram ID ingiz |
| `/chiqish` | Bildirishnomalarni o'chirish |

---

## ⚙️ 4. Sozlamalar (`.env`)

| Sozlama | Ma'nosi |
|---|---|
| `USER_BOT_TOKEN` | 1-bot (mijozlar uchun) tokeni — **majburiy** |
| `ADMIN_BOT_TOKEN` | 2-bot (adminlar uchun) tokeni |
| `ADMIN_PASSWORD` | Admin bo'lish uchun parol |
| `ADMIN_IDS` | Doimiy adminlar ID lari, vergul bilan (ixtiyoriy) |
| `COMPANY_NAME` | Salomlashuvda ko'rinadigan nom |
| `CONTACT_INFO` | Mijozga ko'rsatiladigan aloqa (telefon/manzil) |
| `SUBMIT_COOLDOWN_SEC` | Ikki so'rov orasidagi eng kam vaqt (spamga qarshi) |
| `MAX_PER_DAY` | Bir mijoz kuniga nechta so'rov qoldira oladi |
| `TZ_OFFSET_HOURS` | Vaqt mintaqasi (Toshkent = 5) |
| `WEBAPP_URL` | Mini App ochiq HTTPS manzili (Railway'da avtomatik) |
| `SITE_URL` | Portfolio sayt manbai (Netlify) — Mini App bosh sahifasi |

Matnlarni o'zgartirmoqchi bo'lsangiz — hammasi **`bot/texts.py`** faylida, bir joyda.

---

## 🗂 5. Fayllar

```
main.py                  ← ishga tushirish
bot/
  app.py                 ← ikkala botni yig'adi va boshqaradi
  config.py              ← .env o'qish
  telegram.py            ← Telegram API (qayta urinish, limitlar)
  runner.py              ← xabarlarni kutish (long polling)
  storage.py             ← ma'lumotlar bazasi (JSON)
  notify.py              ← zayavkani 2 botga tarqatish
  user_handlers.py       ← mijoz oqimi: ism → telefon → zayavka
  admin_flow.py          ← admin boti
  admin_handlers.py      ← admin buyruqlari va tugmalari
  validators.py          ← ism/telefon tekshiruvi
  texts.py               ← BARCHA MATNLAR shu yerda
  utils.py               ← klaviaturalar, sana, HTML himoyasi
  web.py                 ← HTTP server: health-check + Mini App + /api/lead
  audit.py               ← audit ballini hisoblash, initData imzosini tekshirish
webapp/
  index.html             ← Audit Mini App sahifasi (dizayn + logika, bitta fayl)
  site.html              ← Portfolio sayt nusxasi (Netlify ishlamasa zaxira)
  audit.json             ← 28 savol, bloklar, tavsiyalar (matnlarni shu yerda tahrirlang)
data/db.json             ← zayavkalar saqlanadi (nusxa olib turing!)
logs/bot.log             ← ish jurnali
```

---

## ❓ 6. Tez-tez uchraydigan savollar

**Zayavka kelmayapti?**
Admin sifatida ro'yxatdan o'tganingizni tekshiring: botga `/start` bosib parolni yuboring.
Terminalda `zayavka #N uchun qabul qiluvchi yo'q` degan ogohlantirish chiqsa — shu sabab.

**«409 Conflict» xatosi?**
Bot ikki joyda bir vaqtda ishlayapti. Eski oynani yoping.

**«Token noto'g'ri (401)»?**
`.env` dagi tokenni @BotFather dan qayta nusxalang (bo'sh joysiz, bir qatorda).

**Kompyuter o'chsa bot to'xtaydimi?**
Ha. Doimiy ishlashi uchun botni serverga (VPS) joylash kerak — kerak bo'lsa aytasiz,
`systemd` sozlamasini tayyorlab beraman.

**Ma'lumotlar qayerda?**
`data/db.json` faylida. `/eksport` buyrug'i bilan Excel'ga chiqarib olasiz.

---

## 🔍 7. Mini App (sayt + sotuv auditi)

Mini App ikki qismdan iborat, ikkalasi ham botning o'zidan xizmat qilinadi:

| Manzil | Nima | Qayerdan ochiladi |
|---|---|---|
| `/` | **Portfolio sayt** — `SITE_URL` (Netlify) dan avtomatik olinadi, 10 daqiqada yangilanadi; Netlify javob bermasa `webapp/site.html` nusxasi | Chatdagi **Menyu** tugmasi |
| `/audit` | **Sotuv bo'limi auditi** (28 savol) | `/audit` buyrug'i, `/start` dagi tugma, saytdagi «Biznes Audit» tugmalari |

Saytni Netlify'da tahrirlashda davom etasiz — bot uni o'zi olib, Telegram uchun
moslaydi (SDK qo'shadi, «Biznes Audit» tugmalarini `/audit` ga yo'naltiradi,
t.me havolalarini Telegram ichida ochadi). Nusxani yangilash:
`curl -sL https://otabeksobirovv.netlify.app/ -o webapp/site.html`.

Audit oqimi:

```
Kirish  →  3 ta kontekst savoli  →  28 savol (6 blok)  →  Natija:
  • umumiy ball (0–100) va xulosa
  • 6 blok bo'yicha diagramma
  • eng zaif 3 nuqta + yechimi
  • «bu qancha pulga tushmoqda» kalkulyatori
  • Ism / kompaniya / telefon formasi  →  to'liq hisobot ochiladi
```

Forma yuborilgach:
- **Adminlarga** oddiy zayavka kartasi keladi, lekin `🔍 Sotuv auditi` belgisi,
  kompaniya nomi, ball, bloklar diagrammasi va eng zaif 3 nuqta bilan.
- **Mijozning chatiga** to'liq hisobot (barcha zaif nuqtalar + tavsiyalar) yuboriladi.
- `/eksport` CSV'da `Kompaniya`, `Manba`, `Audit balli`, `Audit xulosasi` ustunlari bor.

Texnik jihatlar:
- Sahifa **botning o'zidan** xizmat qilinadi (`webapp/index.html`), alohida hosting kerak emas.
- Telegram yuborgan `initData` imzosi bot tokeni bilan **serverda tekshiriladi** —
  begona joydan zayavka yuborib bo'lmaydi. Ball ham serverda qayta hisoblanadi.
- Botdagi spam-limitlar (`SUBMIT_COOLDOWN_SEC`, `MAX_PER_DAY`) Mini App'ga ham tegishli.
- Yarim qolgan audit Telegram CloudStorage'da saqlanadi — mijoz keyin davom ettiradi.
- Telefonni «📱» tugmasi bilan Telegram'dan bir bosishda olish mumkin.
- Savollar/tavsiyalar matnini `webapp/audit.json` da o'zgartirasiz — bot qayta ishga
  tushirilmasa ham yangi matn darrov ishlaydi (ball og'irliklari yig'indisi 100 bo'lsin).

**Lokal kompyuterda sinash.** Telegram faqat HTTPS manzilni ochadi, shuning uchun tunnel kerak:

```bash
PORT=8080 python3 main.py            # 1-terminal
ngrok http 8080                      # 2-terminal  (yoki: cloudflared tunnel --url http://localhost:8080)
```

Tunnel bergan `https://....` manzilni `.env` ga `WEBAPP_URL=` qatoriga yozib botni qayta
ishga tushiring. Brauzerda `http://localhost:8080` ochsangiz ilova ko'rinadi, lekin forma
yuborilmaydi (imzo yo'q) — bu normal.

**Ixtiyoriy:** @BotFather → `/newapp` orqali ilovaga qisqa nom bersangiz,
`https://t.me/<bot>/<nom>` ko'rinishidagi to'g'ridan-to'g'ri havola ham ishlaydi
(reklama/Instagram uchun qulay). URL sifatida o'sha `WEBAPP_URL` ni bering.

---

## 🔒 Xavfsizlik

- `.env` faylini hech kimga bermang, skrinshot qilmang — u tokenlarni saqlaydi.
- Token boshqa birovga ma'lum bo'lsa: @BotFather → `/revoke` → yangi token oling.
- `ADMIN_PASSWORD` ni o'zgartiring va faqat xodimlarga ayting.

---

## ☁️ Railway'ga joylash (24/7 ishlashi uchun)

Bot doimiy ishlashi uchun uni Railway'ga qo'yish mumkin. Loyihada kerakli
fayllar bor (`Procfile`, `railway.json`, `requirements.txt`), shuning uchun
Railway avtomatik quradi va ishga tushiradi.

### 1) Repozitoriyni ulash
Railway → **New Project** → **Deploy from GitHub repo** → shu repozitoriyni tanlang.

### 2) Muhit o'zgaruvchilarini (Variables) kiriting
Railway'da **Variables** bo'limiga o'ting va quyidagilarni qo'shing
(bu yerda `.env` ishlatilmaydi — tokenlar shu yerga yoziladi):

| O'zgaruvchi | Qiymat |
|---|---|
| `USER_BOT_TOKEN` | So'rov botining tokeni (@BotFather) |
| `ADMIN_BOT_TOKEN` | Admin botining tokeni |
| `ADMIN_PASSWORD` | Admin paroli (o'zingiz tanlang) |
| `COMPANY_NAME` | Kompaniya nomi |
| `CONTACT_INFO` | Aloqa (ixtiyoriy) |
| `DATA_DIR` | `/data` (pastdagi Volume bilan birga) |
| `WEBAPP_URL` | bo'sh qoldiring — Railway domeni avtomatik olinadi (3a-qadam) |

### 3a) Mini App ishlashi uchun domen yarating
Railway → xizmat → **Settings** → **Networking** → **Generate Domain**.
Port so'rasa **8080** yozing (bot `PORT` berilmasa shu portda ishlaydi).
Shu bilan Railway `RAILWAY_PUBLIC_DOMAIN` o'zgaruvchisini o'zi qo'yadi va bot
Mini App tugmalarini avtomatik yoqadi. Domen yaratilgandan keyin bir marta
**Redeploy** qiling. Loglarda `Mini App : https://...` ko'rinadi.

> `https://<domen>/health` ochilganda `OK - bot ishlayapti` chiqishi kerak.
> **502** chiqsa — domen porti bilan bot porti mos emas: Networking'da domen
> yonidagi portni `8080` qiling (yoki Variables'ga `PORT=8080` qo'shing).

### 3) Ma'lumot saqlanishi uchun Volume qo'shing ⚠️ MUHIM
Railway'da fayl tizimi har deploy'da **o'chib ketadi**. Zayavkalar va
ro'yxatdan o'tgan adminlar yo'qolmasligi uchun:

Railway → xizmat → **Settings** → **Volumes** → **New Volume** →
**Mount path** ni `/data` qilib qo'ying. Keyin `DATA_DIR=/data` o'zgaruvchisi
o'sha volumega ma'lumotni yozadi.

> Volume qo'ymasangiz ham bot ishlaydi, lekin har deploy'dan keyin adminlar
> qayta `/start` + parol yuborishi kerak bo'ladi.

### 4) Faqat BITTA nusxa ishlasin
Bir tokenli bot ikki joyda (masalan lokal kompyuter + Railway) bir vaqtda
ishlasa, Telegram **409 Conflict** beradi. Railway'da ishga tushirgach,
lokal botni (`python3 main.py`) **to'xtating**.

Deploy tugagach, Railway loglarida `✅ BOT ISHGA TUSHDI` ko'rinadi —
demak tayyor.
