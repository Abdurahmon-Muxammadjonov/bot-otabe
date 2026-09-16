"""Botning barcha matnlari (o'zbek tilida). Bir joydan tahrirlanadi."""

from __future__ import annotations

# ------------------------------------------------------------- tugma matnlari
BTN_SEND_CONTACT = "📱 Raqamni yuborish"
BTN_CANCEL = "🚫 Bekor qilish"
BTN_NEW_REQUEST = "📝 Yangi so'rov qoldirish"
BTN_OPEN_AUDIT = "🔍 Sotuv auditini boshlash"
MENU_BUTTON_AUDIT = "🔍 Audit"

# ----------------------------------------------------- foydalanuvchi boti
GREETING = (
    "Assalomu alaykum! 👋\n\n"
    "<b>{company}</b> xizmatiga xush kelibsiz.\n"
    "So'rov (zayavka) qoldirish uchun iltimos <b>ismingizni kiriting</b>:"
)

GREETING_AGAIN = (
    "Assalomu alaykum, yana xush kelibsiz! 👋\n\n"
    "Yangi so'rov qoldirish uchun <b>ismingizni kiriting</b>:"
)

ASK_PHONE = (
    "Rahmat, <b>{name}</b>! 🙏\n\n"
    "Endi <b>telefon raqamingizni</b> yuboring.\n"
    "Pastdagi «{btn}» tugmasini bosing yoki qo'lda yozing:\n"
    "<code>+998 90 123 45 67</code>"
)

SUCCESS = (
    "✅ <b>Zayavkangiz qabul qilindi!</b>\n\n"
    "👤 Ism: <b>{name}</b>\n"
    "📞 Telefon: <code>{phone}</code>\n\n"
    "Tez orada siz bilan <b>aloqaga chiqamiz</b>. Murojaatingiz uchun rahmat! 🤝"
)

SUCCESS_CONTACT = "\n\nSavollaringiz bo'lsa: {contact}"

# ------------------------------------------------------------- Mini App
GREETING_AUDIT_HINT = (
    "\n\n🔍 Yoki avval <b>6 daqiqalik sotuv auditi</b>dan o'ting — "
    "sotuvingiz qayerda pul yo'qotayotganini ko'rsatamiz 👇"
)
AUDIT_INVITE = (
    "🔍 <b>Sotuv bo'limi auditi</b>\n\n"
    "28 ta savol · 6 daqiqa · bepul.\n"
    "Sotuv bo'limingizning qaysi bo'g'ini pul yo'qotayotganini ko'rsatadi: "
    "6 blok bo'yicha ball, eng zaif nuqtalar va har biri uchun aniq yechim.\n\n"
    "Pastdagi tugmani bosing 👇"
)
AUDIT_DISABLED = (
    "🔍 Audit hozircha yoqilmagan.\n"
    "So'rov qoldirish uchun /start bosing."
)
WEBAPP_SUCCESS = (
    "✅ <b>Audit natijangiz qabul qilindi!</b>  (zayavka #{id})\n\n"
    "👤 Ism: <b>{name}</b>\n"
    "📞 Telefon: <code>{phone}</code>\n"
    "🎯 Ball: <b>{score}/100</b> — {band}\n\n"
    "To'liq hisobot quyida 👇 Tez orada siz bilan <b>aloqaga chiqamiz</b>. 🤝"
)

# --------------------------------------------------------------- xatoliklar
NAME_ERRORS = {
    "empty": "❌ Iltimos, <b>ismingizni matn ko'rinishida</b> yozing.",
    "short": "❌ Ism juda qisqa. Kamida 2 ta harf bo'lsin.",
    "long": "❌ Ism juda uzun. 60 ta belgidan oshmasin.",
    "digits": "❌ Ismda raqam bo'lmasligi kerak. Faqat ismingizni yozing.",
    "link": "❌ Havola yoki username emas — <b>ismingizni</b> yozing.",
    "letters": "❌ Ismda faqat harflar bo'lsin. Masalan: <b>Otabek</b>",
}

PHONE_ERRORS = {
    "empty": "❌ Raqam ko'rinmadi. Masalan: <code>+998 90 123 45 67</code>",
    "chars": "❌ Raqamda ortiqcha belgilar bor. Faqat raqam yozing: <code>+998901234567</code>",
    "short": "❌ Raqam to'liq emas. Masalan: <code>+998 90 123 45 67</code>",
    "long": "❌ Raqam juda uzun. Masalan: <code>+998 90 123 45 67</code>",
    "operator": "❌ Bunday operator kodi yo'q. Masalan: <code>+998 90 123 45 67</code>",
}

NEED_TEXT_NAME = "❌ Iltimos, ismingizni <b>matn</b> ko'rinishida yuboring."
NEED_TEXT_PHONE = (
    "❌ Iltimos, telefon raqamingizni yuboring.\n"
    "«{btn}» tugmasini bossangiz — avtomatik yuboriladi."
)
FOREIGN_CONTACT = (
    "❌ Bu boshqa odamning raqami. Iltimos, <b>o'z raqamingizni</b> yuboring."
)

NOT_STARTED = "Boshlash uchun /start buyrug'ini bosing."
CANCELLED = "🚫 Bekor qilindi. Qaytadan boshlash uchun /start bosing."

COOLDOWN = (
    "⏳ Siz hozirgina so'rov qoldirdingiz.\n"
    "Yangi so'rov uchun <b>{seconds} soniya</b> kuting yoki biz bilan aloqani kuting."
)
DAILY_LIMIT = (
    "⚠️ Bugun siz {limit} ta so'rov qoldirdingiz.\n"
    "Operatorlarimiz tez orada bog'lanishadi. Rahmat! 🤝"
)

HELP_USER = (
    "ℹ️ <b>Yordam</b>\n\n"
    "Bu bot orqali so'rov (zayavka) qoldirasiz:\n"
    "1️⃣ Ismingizni yozasiz\n"
    "2️⃣ Telefon raqamingizni yuborasiz\n"
    "3️⃣ Operatorlarimiz siz bilan bog'lanadi\n\n"
    "Buyruqlar:\n"
    "/start — yangi so'rov\n"
    "/audit — sotuv bo'limi auditi (6 daqiqa)\n"
    "/bekor — jarayonni bekor qilish\n"
    "/yordam — shu yordam\n"
    "{contact}"
)

UNKNOWN_USER_MSG = (
    "🤖 Sizni tushunmadim.\n"
    "So'rov qoldirish uchun /start bosing yoki «{btn}» tugmasidan foydalaning."
)

# ------------------------------------------------------------- admin qismi
ADMIN_ASK_PASSWORD = (
    "🔐 <b>Xizmat boti</b>\n\n"
    "Bu bot faqat xodimlar uchun. Kirish uchun <b>parolni</b> yuboring:"
)
ADMIN_WRONG_PASSWORD = "❌ Parol noto'g'ri. Qaytadan urinib ko'ring."
ADMIN_WELCOME = (
    "✅ <b>Xush kelibsiz, {name}!</b>\n\n"
    "Endi barcha yangi zayavkalar shu yerga tushadi.\n\n"
    "{commands}"
)
ADMIN_COMMANDS = (
    "<b>Buyruqlar:</b>\n"
    "/statistika — umumiy hisobot\n"
    "/oxirgi — oxirgi 10 ta zayavka\n"
    "/yangi — javob berilmagan zayavkalar\n"
    "/eksport — barcha zayavkalar (CSV/Excel)\n"
    "/id — chat ID raqamim\n"
    "/chiqish — bildirishnomalarni o'chirish\n"
    "/yordam — shu ro'yxat"
)
ADMIN_ONLY = "⛔️ Bu buyruq faqat adminlar uchun. /start bosing va parolni kiriting."
ADMIN_LOGGED_OUT = "👋 Bildirishnomalar o'chirildi. Qayta ulanish uchun /start bosing."
ADMIN_ALREADY = "✅ Siz allaqachon ulangansiz.\n\n{commands}"

NEW_APPLICATION = (
    "🆕 <b>Yangi zayavka #{id}</b>{source}\n\n"
    "👤 <b>Ism:</b> {name}\n"
    "{company}"
    "📞 <b>Telefon:</b> <code>{phone}</code>\n"
    "👥 <b>Telegram:</b> {tg}\n"
    "🆔 <b>ID:</b> <code>{user_id}</code>\n"
    "🕒 <b>Vaqt:</b> {time}"
)

SOURCE_WEBAPP = "  ·  🔍 Sotuv auditi"
PHONE_PENDING = "hali kiritilmadi"
AUDIT_NO_PHONE = (
    "\n\n⏳ <b>Mijoz hali telefon qoldirmadi</b> — auditni tugatdi, forma to'ldirilsa "
    "bu karta yangilanadi. Hozircha Telegram orqali yozish mumkin."
)
AUDIT_REPORT_HEADER = "📋 <b>Zayavka #{id} — to'liq audit hisoboti</b>\n"
COMPANY_LINE = "🏢 <b>Kompaniya:</b> {company}\n"
AUDIT_BLOCK = "\n\n{summary}"

STATUS_LABELS = {
    "new": "🆕 Yangi",
    "contacted": "✅ Bog'lanildi",
    "cancelled": "❌ Bekor qilindi",
}

STATUS_FOOTER = "\n\n<b>Holat:</b> {status} — {who} ({time})"

STATS = (
    "📊 <b>Statistika</b>\n\n"
    "Jami zayavkalar: <b>{total}</b>\n"
    "Bugun: <b>{today}</b>\n\n"
    "🆕 Yangi: <b>{new}</b>\n"
    "✅ Bog'lanilgan: <b>{contacted}</b>\n"
    "❌ Bekor qilingan: <b>{cancelled}</b>\n\n"
    "🕒 {time}"
)

LIST_EMPTY = "📭 Hozircha zayavkalar yo'q."
LIST_HEADER = "🗂 <b>{title}</b> ({count} ta)\n"
LIST_ITEM = (
    "\n<b>#{id}</b> {status}\n"
    "👤 {name} — <code>{phone}</code>\n"
    "🕒 {time}{tg}"
)

EXPORT_CAPTION = "📎 Barcha zayavkalar: <b>{count}</b> ta\n🕒 {time}"
EXPORT_EMPTY = "📭 Eksport qilish uchun ma'lumot yo'q."

ID_INFO = (
    "🆔 <b>Sizning ma'lumotlaringiz</b>\n\n"
    "User ID: <code>{user_id}</code>\n"
    "Chat ID: <code>{chat_id}</code>\n"
    "Bot: @{bot}"
)

CB_DONE = "✅ Holat yangilandi"
CB_ALREADY = "ℹ️ Bu zayavka allaqachon shu holatda"
CB_NOT_FOUND = "❌ Zayavka topilmadi"
CB_NO_RIGHTS = "⛔️ Sizda ruxsat yo'q"
