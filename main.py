import os
import asyncio
import sqlite3
import logging
import random
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web

# ═══════════════════════════════════════════════════════════
# SOZLAMALAR
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SUPER_ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
PORT = int(os.environ.get("PORT", 8080))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN o'rnatilmagan!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "bot_data.db"
MIN_STARS = 50
MAX_STARS = 1_000_000

# ═══════════════════════════════════════════════════════════
# DARAJALAR
# ═══════════════════════════════════════════════════════════
DEFAULT_LEVELS = [
    {"name": "Bronza",  "emoji": "🥉", "min": 0,   "max": 10},
    {"name": "Kumush",  "emoji": "🥈", "min": 11,  "max": 50},
    {"name": "Oltin",   "emoji": "🥇", "min": 51,  "max": 200},
    {"name": "Platina", "emoji": "💎", "min": 201, "max": 500},
    {"name": "Olmos",   "emoji": "👑", "min": 501, "max": 999999999},
]

def get_levels():
    rows = db_exec("SELECT * FROM levels ORDER BY min_stars ASC", fetchall=True)
    return [dict(r) for r in rows] if rows else DEFAULT_LEVELS

def get_user_level(stars):
    for lvl in get_levels():
        if lvl["min_stars"] <= stars <= lvl["max_stars"]:
            return lvl
    levels = get_levels()
    return levels[-1] if levels else DEFAULT_LEVELS[-1]

# ═══════════════════════════════════════════════════════════
# TILLAR
# ═══════════════════════════════════════════════════════════
LANGS = {
    "uz": {
        "flag": "🇺🇿", "name": "O'zbekcha",
        "choose_lang": "🌐 <b>Tilni tanlang</b>\n\nIltimos, o'zingizga qulay tilni tanlang:",
        "lang_set": "✅ Til muvaffaqiyatli o'zgartirildi!",
        "welcome": "👋 <b>Salom, {name}!</b>\n\n🎯 <i>Referal botga xush kelibsiz!</i>\n\nQuyidagi menyudan kerakli bo'limni tanlang 👇",
        "menu_title": "🏠 <b>Asosiy menyu</b>\n\nKerakli bo'limni tanlang:",
        "profile": "👤 Profilim",
        "ref_link": "🔗 Referal linkim",
        "rating": "🏆 Reyting",
        "withdraw": "💰 Yechib olish",
        "support": "💬 Admin bilan aloqa",
        "gift_stars": "🎁 Stars sovg'a qilish",
        "review": "⭐ Sharh qoldirish",
        "admin": "🛠 Admin Panel",
        "share": "📤 Havolani ulashish",
        "back": "⬅️ Orqaga",
        "menu": "🏠 Asosiy menyu",
        "cancel": "❌ Bekor qilish",
        "close_chat": "🔚 Suhbatni tugatish",
        "banned": "🚫 <b>Siz banlangansiz!</b>\n\nAdmin bilan bog'laning.",
        "subscribe": "📢 <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>\n\nObuna bo'lgach, «✅ Tekshirish» tugmasini bosing.",
        "check": "✅ Tekshirish",
        "bot_check": "🤖 <b>Bot emasligingizni tasdiqlang</b>\n\n❓ <b>Savol:</b> {q}\n\nTo'g'ri javobni tanlang 👇",
        "wrong_answer": "❌ Noto'g'ri javob!",
        "correct": "✅ Tasdiqlandi!",
        "wrong_ans_retry": "❌ <b>Noto'g'ri javob!</b>\n\nQaytadan urinib ko'ring: /start",
        "start_first": "ℹ️ Iltimos, /start buyrug'ini bosing.",
        "not_enough": "❌ <b>Yetarli emas!</b>",
        "min_withdraw": "❌ Minimal: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Maksimal: <b>{n} ⭐</b>",
        "enter_number": "❌ Faqat raqam kiriting.",
        "choose_reward": "🎁 Mukofot turini tanlang:",
        "stars_withdraw": "⭐ To'liq Stars olish",
        "gift_withdraw": "🎁 Telegram Gift olish",
        "stars_title": "⭐ <b>Stars yechib olish</b>\n\n💰 Sizda: <b>{bal} ⭐</b>\n📉 Min: {min} ⭐\n📈 Max: {max} ⭐\n\n💬 Nechta stars yechib olmoqchisiz?\nRaqamni kiriting:",
        "gift_title": "🎁 <b>Telegram Gift olish</b>\n\n💰 Sizda: <b>{bal} ⭐</b>\n\n👇 Giftni tanlang:",
        "sent_to_admin": "✅ <b>So'rov yuborildi!</b>\n\n⭐ Miqdor: <b>{n} ⭐</b>\n⏳ Admin tasdiqlashini kuting...",
        "gift_sent": "✅ <b>So'rov yuborildi!</b>\n\n🎁 Gift: <b>{gift}</b>\n⭐ Narx: <b>{n} ⭐</b>\n⏳ Admin tasdiqlashini kuting...",
        "approved": "✅ <b>So'rovingiz tasdiqlandi!</b>",
        "rejected": "❌ <b>So'rovingiz rad etildi.</b>",
        "referral_reward": "🎉 <b>Yangi referal!</b>\n\n➕ +{n} ⭐ qo'shildi",
        "total": "Jami",
        "balance": "Sizda",
        "need": "Kerak",
        "stars_added": "🎁 <b>Sizga stars qo'shildi!</b>\n\n➕ Miqdor: <b>+{n} ⭐</b>\n📝 Sabab: <i>{reason}</i>\n\n💰 Jami: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Sizdan stars ayirildi!</b>\n\n➖ Miqdor: <b>{n} ⭐</b>\n📝 Sabab: <i>{reason}</i>\n\n💰 Jami: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Admin bilan aloqa</b>\n\nSavolingizni yozing — admin tez orada javob beradi.\n\nMatn, rasm, video yoki fayl yuborishingiz mumkin.",
        "support_sent": "✅ <b>Savolingiz adminga yuborildi!</b>\n\n⏳ Javobni kuting...",
        "support_new_msg": "📩 <b>Yangi murojaat!</b>\n\n👤 <b>User:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Vaqt:</b> {time}",
        "reply_sent": "✅ <b>Javob yuborildi!</b>",
        "chat_active": "💬 <b>Suhbat faol</b>\n\nXabaringizni yozing.",
        "chat_closed_by_admin": "🔚 <b>Admin suhbatni tugatdi.</b>",
        "no_active_chat": "ℹ️ Sizda faol suhbat yo'q.",
        "admin_reply": "📬 <b>Admindan javob:</b>",
        "user_msg": "📩 <b>Foydalanuvchidan xabar:</b>",
        "gift_stars_title": "🎁 <b>Stars sovg'a qilish</b>\n\n💰 Sizda: <b>{bal} ⭐</b>\n\nFoydalanuvchi <b>username</b> yoki <b>ID</b> sini kiriting:",
        "gift_stars_amount": "👤 Qabul qiluvchi: <b>{name}</b>\n\nNechta stars sovg'a qilasiz?",
        "gift_stars_confirm": "🎁 <b>Tasdiqlang</b>\n\n👤 Kimga: <b>{name}</b>\n⭐ Miqdor: <b>{n} ⭐</b>\n\nTasdiqlaysizmi?",
        "gift_stars_sent": "✅ <b>{n} ⭐ {name} ga yuborildi!</b>",
        "gift_stars_received": "🎁 <b>Sizga stars sovg'a qilindi!</b>\n\n👤 Kimdan: <b>{name}</b>\n⭐ Miqdor: <b>+{n} ⭐</b>\n\n💰 Jami: <b>{total} ⭐</b>",
        "gift_stars_not_found": "❌ Foydalanuvchi topilmadi.",
        "gift_stars_self": "❌ O'zingizga sovg'a qila olmaysiz.",
        "review_title": "⭐ <b>Sharh qoldirish</b>\n\nBot haqida fikringizni yozing — admin tasdiqlasa kanalga chiqadi:",
        "review_sent": "✅ <b>Sharhingiz yuborildi!</b>\n\n⏳ Admin tasdiqlashini kuting.",
        "review_approved": "✅ <b>Sharhingiz tasdiqlandi va kanalga chiqdi!</b>\n\nRahmat! 🎉",
        "review_rejected": "❌ <b>Sharhingiz rad etildi.</b>",
        "level": "Daraja",
    },
    "ru": {
        "flag": "🇷🇺", "name": "Русский",
        "choose_lang": "🌐 <b>Выберите язык</b>\n\nПожалуйста, выберите удобный для вас язык:",
        "lang_set": "✅ Язык успешно изменён!",
        "welcome": "👋 <b>Привет, {name}!</b>\n\n🎯 <i>Добро пожаловать!</i>\n\nВыберите раздел 👇",
        "menu_title": "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        "profile": "👤 Профиль",
        "ref_link": "🔗 Реф. ссылка",
        "rating": "🏆 Рейтинг",
        "withdraw": "💰 Вывод",
        "support": "💬 Связь с админом",
        "gift_stars": "🎁 Подарить Stars",
        "review": "⭐ Оставить отзыв",
        "admin": "🛠 Админ панель",
        "share": "📤 Поделиться",
        "back": "⬅️ Назад",
        "menu": "🏠 Главное меню",
        "cancel": "❌ Отмена",
        "close_chat": "🔚 Завершить чат",
        "banned": "🚫 <b>Вы забанены!</b>",
        "subscribe": "📢 <b>Подпишитесь на каналы:</b>",
        "check": "✅ Проверить",
        "bot_check": "🤖 <b>Подтвердите, что вы не бот</b>\n\n❓ <b>Вопрос:</b> {q}",
        "wrong_answer": "❌ Неправильный ответ!",
        "correct": "✅ Подтверждено!",
        "wrong_ans_retry": "❌ <b>Неправильно!</b> /start",
        "start_first": "ℹ️ Напишите /start",
        "not_enough": "❌ <b>Недостаточно!</b>",
        "min_withdraw": "❌ Минимум: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Максимум: <b>{n} ⭐</b>",
        "enter_number": "❌ Только число.",
        "choose_reward": "🎁 Выберите тип награды:",
        "stars_withdraw": "⭐ Получить Stars",
        "gift_withdraw": "🎁 Получить Telegram Gift",
        "stars_title": "⭐ <b>Вывод Stars</b>\n\n💰 У вас: <b>{bal} ⭐</b>\n📉 Мин: {min} ⭐\n📈 Макс: {max} ⭐\n\n💬 Сколько вывести?",
        "gift_title": "🎁 <b>Telegram Gift</b>\n\n💰 У вас: <b>{bal} ⭐</b>\n\n👇 Выберите gift:",
        "sent_to_admin": "✅ <b>Запрос отправлен!</b>\n\n⭐ Сумма: <b>{n} ⭐</b>",
        "gift_sent": "✅ <b>Запрос отправлен!</b>\n\n🎁 Gift: <b>{gift}</b>",
        "approved": "✅ <b>Подтверждено!</b>",
        "rejected": "❌ <b>Отклонено.</b>",
        "referral_reward": "🎉 <b>Новый реферал!</b>\n\n➕ +{n} ⭐",
        "total": "Всего",
        "balance": "У вас",
        "need": "Нужно",
        "stars_added": "🎁 <b>Вам добавлены stars!</b>\n\n➕ <b>+{n} ⭐</b>\n📝 <i>{reason}</i>\n\n💰 Всего: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Списаны stars!</b>\n\n➖ <b>{n} ⭐</b>\n📝 <i>{reason}</i>\n\n💰 Всего: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Связь с админом</b>\n\nНапишите вопрос:",
        "support_sent": "✅ <b>Отправлено админу!</b>",
        "support_new_msg": "📩 <b>Новое сообщение!</b>\n\n👤 {name}\n🔗 {username}\n🆔 <code>{uid}</code>\n📅 {time}",
        "reply_sent": "✅ <b>Ответ отправлен!</b>",
        "chat_active": "💬 <b>Чат активен</b>",
        "chat_closed_by_admin": "🔚 <b>Админ завершил чат.</b>",
        "no_active_chat": "ℹ️ Нет активного чата.",
        "admin_reply": "📬 <b>Ответ от админа:</b>",
        "user_msg": "📩 <b>От пользователя:</b>",
        "gift_stars_title": "🎁 <b>Подарить Stars</b>\n\n💰 У вас: <b>{bal} ⭐</b>\n\nВведите username или ID:",
        "gift_stars_amount": "👤 Получатель: <b>{name}</b>\n\nСколько stars подарить?",
        "gift_stars_confirm": "🎁 <b>Подтвердите</b>\n\n👤 Кому: <b>{name}</b>\n⭐ Сумма: <b>{n} ⭐</b>",
        "gift_stars_sent": "✅ <b>{n} ⭐ отправлено {name}!</b>",
        "gift_stars_received": "🎁 <b>Вам подарили stars!</b>\n\n👤 От: <b>{name}</b>\n⭐ <b>+{n} ⭐</b>\n\n💰 Всего: <b>{total} ⭐</b>",
        "gift_stars_not_found": "❌ Пользователь не найден.",
        "gift_stars_self": "❌ Нельзя подарить себе.",
        "review_title": "⭐ <b>Оставить отзыв</b>\n\nНапишите отзыв — админ одобрит:",
        "review_sent": "✅ <b>Отзыв отправлен!</b>",
        "review_approved": "✅ <b>Ваш отзыв одобрен и опубликован!</b>",
        "review_rejected": "❌ <b>Ваш отзыв отклонён.</b>",
        "level": "Уровень",
    },
    "en": {
        "flag": "🇬🇧", "name": "English",
        "choose_lang": "🌐 <b>Choose language</b>:",
        "lang_set": "✅ Language changed!",
        "welcome": "👋 <b>Hi, {name}!</b>\n\n🎯 <i>Welcome!</i>",
        "menu_title": "🏠 <b>Main menu</b>:",
        "profile": "👤 Profile",
        "ref_link": "🔗 Referral",
        "rating": "🏆 Rating",
        "withdraw": "💰 Withdraw",
        "support": "💬 Contact admin",
        "gift_stars": "🎁 Gift Stars",
        "review": "⭐ Leave review",
        "admin": "🛠 Admin Panel",
        "share": "📤 Share",
        "back": "⬅️ Back",
        "menu": "🏠 Main menu",
        "cancel": "❌ Cancel",
        "close_chat": "🔚 Close chat",
        "banned": "🚫 <b>You are banned!</b>",
        "subscribe": "📢 <b>Subscribe:</b>",
        "check": "✅ Check",
        "bot_check": "🤖 <b>Confirm you're not a bot</b>\n\n❓ <b>Question:</b> {q}",
        "wrong_answer": "❌ Wrong answer!",
        "correct": "✅ Confirmed!",
        "wrong_ans_retry": "❌ <b>Wrong!</b> /start",
        "start_first": "ℹ️ Send /start",
        "not_enough": "❌ <b>Not enough!</b>",
        "min_withdraw": "❌ Min: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Max: <b>{n} ⭐</b>",
        "enter_number": "❌ Numbers only.",
        "choose_reward": "🎁 Choose reward:",
        "stars_withdraw": "⭐ Get Stars",
        "gift_withdraw": "🎁 Get Telegram Gift",
        "stars_title": "⭐ <b>Withdraw Stars</b>\n\n💰 You have: <b>{bal} ⭐</b>\n📉 Min: {min} ⭐\n📈 Max: {max} ⭐\n\n💬 How many?",
        "gift_title": "🎁 <b>Telegram Gift</b>\n\n💰 You have: <b>{bal} ⭐</b>\n\n👇 Choose:",
        "sent_to_admin": "✅ <b>Sent!</b>\n\n⭐ <b>{n} ⭐</b>",
        "gift_sent": "✅ <b>Sent!</b>\n\n🎁 <b>{gift}</b>",
        "approved": "✅ <b>Approved!</b>",
        "rejected": "❌ <b>Rejected.</b>",
        "referral_reward": "🎉 <b>New referral!</b>\n\n➕ +{n} ⭐",
        "total": "Total",
        "balance": "You have",
        "need": "Need",
        "stars_added": "🎁 <b>Stars added!</b>\n\n➕ <b>+{n} ⭐</b>\n📝 <i>{reason}</i>\n\n💰 Total: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Stars removed!</b>\n\n➖ <b>{n} ⭐</b>\n📝 <i>{reason}</i>",
        "support_title": "💬 <b>Contact admin</b>:",
        "support_sent": "✅ <b>Sent to admin!</b>",
        "support_new_msg": "📩 <b>New message!</b>\n\n👤 {name}\n🔗 {username}\n🆔 <code>{uid}</code>\n📅 {time}",
        "reply_sent": "✅ <b>Reply sent!</b>",
        "chat_active": "💬 <b>Chat active</b>",
        "chat_closed_by_admin": "🔚 <b>Admin closed the chat.</b>",
        "no_active_chat": "ℹ️ No active chat.",
        "admin_reply": "📬 <b>Reply from admin:</b>",
        "user_msg": "📩 <b>From user:</b>",
        "gift_stars_title": "🎁 <b>Gift Stars</b>\n\n💰 You have: <b>{bal} ⭐</b>\n\nEnter username or ID:",
        "gift_stars_amount": "👤 To: <b>{name}</b>\n\nHow many stars?",
        "gift_stars_confirm": "🎁 <b>Confirm</b>\n\n👤 To: <b>{name}</b>\n⭐ Amount: <b>{n} ⭐</b>",
        "gift_stars_sent": "✅ <b>{n} ⭐ sent to {name}!</b>",
        "gift_stars_received": "🎁 <b>You received stars!</b>\n\n👤 From: <b>{name}</b>\n⭐ <b>+{n} ⭐</b>\n\n💰 Total: <b>{total} ⭐</b>",
        "gift_stars_not_found": "❌ User not found.",
        "gift_stars_self": "❌ Can't gift yourself.",
        "review_title": "⭐ <b>Leave review</b>\n\nWrite review — admin approves:",
        "review_sent": "✅ <b>Review sent!</b>",
        "review_approved": "✅ <b>Your review approved and published!</b>",
        "review_rejected": "❌ <b>Your review rejected.</b>",
        "level": "Level",
    },
}

def T(lang, key, **kwargs):
    lang = lang if lang in LANGS else "uz"
    text = LANGS[lang].get(key, LANGS["uz"].get(key, key))
    try:
        return text.format(**kwargs)
    except Exception:
        return text

# ═══════════════════════════════════════════════════════════
# DB
# ═══════════════════════════════════════════════════════════
def db_exec(query, params=(), fetch=False, fetchall=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(query, params)
    result = None
    if fetch:
        result = c.fetchone()
    elif fetchall:
        result = c.fetchall()
    conn.commit()
    conn.close()
    return result

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language TEXT DEFAULT 'uz',
        stars INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        is_suspicious INTEGER DEFAULT 0,
        joined_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_username TEXT UNIQUE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        correct_answer TEXT,
        wrong1 TEXT,
        wrong2 TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS gifts (
        key TEXT PRIMARY KEY,
        emoji TEXT,
        name TEXT,
        stars INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        stars INTEGER,
        reward_type TEXT,
        gift_key TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        added_by INTEGER,
        added_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        admin_id INTEGER,
        message_type TEXT,
        content TEXT,
        is_from_admin INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS support_chats (
        user_id INTEGER PRIMARY KEY,
        status TEXT DEFAULT 'open',
        admin_id INTEGER DEFAULT 0,
        updated_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        emoji TEXT,
        min_stars INTEGER,
        max_stars INTEGER
    )""")

    defaults = {
        "stars_per_referral": "2",
        "min_withdraw": "50",
        "max_withdraw": "1000000",
        "review_channel": "",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    for a in SUPER_ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                  (a, a, datetime.now().isoformat()))

    c.execute("SELECT COUNT(*) FROM levels")
    if c.fetchone()[0] == 0:
        for lvl in DEFAULT_LEVELS:
            c.execute("INSERT INTO levels (name, emoji, min_stars, max_stars) VALUES (?, ?, ?, ?)",
                      (lvl["name"], lvl["emoji"], lvl["min"], lvl["max"]))

    c.execute("SELECT COUNT(*) FROM gifts")
    if c.fetchone()[0] == 0:
        default_gifts = [
            ("heart",     "💝", "Heart",      15),
            ("teddy",     "🧸", "Teddy Bear", 15),
            ("giftbox",   "🎁", "Gift Box",   25),
            ("rose",      "🌹", "Rose",       25),
            ("cake",      "🎂", "Cake",       50),
            ("bouquet",   "💐", "Bouquet",    50),
            ("rocket",    "🚀", "Rocket",     50),
            ("champagne", "🍾", "Champagne",  50),
            ("trophy",    "🏆", "Trophy",     100),
            ("ring",      "💍", "Ring",       100),
            ("diamond",   "💎", "Diamond",    100),
        ]
        for key, emoji, name, stars in default_gifts:
            c.execute("INSERT OR IGNORE INTO gifts (key, emoji, name, stars) VALUES (?, ?, ?, ?)",
                      (key, emoji, name, stars))

    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        default_qs = [
            ("2 + 2 nechaga teng?", "4", "5", "3"),
            ("O'zbekiston poytaxti?", "Toshkent", "Samarqand", "Buxoro"),
            ("10 - 3 nechaga teng?", "7", "6", "8"),
            ("Quyosh qaysi tomondan chiqadi?", "Sharq", "G'arb", "Shimol"),
            ("5 * 5 nechaga teng?", "25", "20", "30"),
        ]
        for q, correct, w1, w2 in default_qs:
            c.execute("""INSERT INTO questions (question, correct_answer, wrong1, wrong2) 
                        VALUES (?, ?, ?, ?)""", (q, correct, w1, w2))

    conn.commit()
    conn.close()
    logger.info("DB tayyor")

def get_setting(key, default=None):
    row = db_exec("SELECT value FROM settings WHERE key=?", (key,), fetch=True)
    return row["value"] if row else default

def set_setting(key, value):
    db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

def get_user(user_id):
    row = db_exec("SELECT * FROM users WHERE user_id=?", (user_id,), fetch=True)
    return dict(row) if row else None

def get_user_by_username(username):
    uname = username.lstrip("@").lower()
    row = db_exec("SELECT * FROM users WHERE LOWER(username)=?", (uname,), fetch=True)
    return dict(row) if row else None

def get_user_lang(user_id):
    u = get_user(user_id)
    return u["language"] if u and u.get("language") in LANGS else "uz"

def update_user(user_id, **kwargs):
    if not kwargs:
        return
    fields = ", ".join([f"{k}=?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    db_exec(f"UPDATE users SET {fields} WHERE user_id=?", values)

def create_user(user_id, username, first_name, last_name, referrer_id=0):
    db_exec("""INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, referrer_id, joined_at) 
        VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, username, first_name, last_name, referrer_id, datetime.now().isoformat()))

def is_admin(user_id):
    if user_id in SUPER_ADMIN_IDS:
        return True
    row = db_exec("SELECT 1 FROM admins WHERE user_id=?", (user_id,), fetch=True)
    return row is not None

def is_super_admin(user_id):
    return user_id in SUPER_ADMIN_IDS

def add_admin(user_id, added_by):
    db_exec("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
            (user_id, added_by, datetime.now().isoformat()))

def remove_admin(user_id):
    db_exec("DELETE FROM admins WHERE user_id=?", (user_id,))

def list_admins():
    rows = db_exec("SELECT * FROM admins", fetchall=True)
    return [dict(r) for r in rows] if rows else []

def get_channels():
    rows = db_exec("SELECT channel_username FROM channels", fetchall=True)
    return [r["channel_username"] for r in rows] if rows else []

def add_channel(ch):
    db_exec("INSERT OR IGNORE INTO channels (channel_username) VALUES (?)", (ch,))

def remove_channel(ch):
    db_exec("DELETE FROM channels WHERE channel_username=?", (ch,))

def get_random_question():
    row = db_exec("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1", fetch=True)
    return dict(row) if row else None

def get_question(q_id):
    row = db_exec("SELECT * FROM questions WHERE id=?", (q_id,), fetch=True)
    return dict(row) if row else None

def add_question(q, correct, wrong1, wrong2):
    db_exec("""INSERT INTO questions (question, correct_answer, wrong1, wrong2) 
               VALUES (?, ?, ?, ?)""", (q, correct, wrong1, wrong2))

def remove_question(q_id):
    db_exec("DELETE FROM questions WHERE id=?", (q_id,))

def get_questions():
    rows = db_exec("SELECT * FROM questions", fetchall=True)
    return [dict(r) for r in rows] if rows else []

def get_all_gifts():
    rows = db_exec("SELECT * FROM gifts ORDER BY stars", fetchall=True)
    return [dict(r) for r in rows] if rows else []

def get_gift(key):
    row = db_exec("SELECT * FROM gifts WHERE key=?", (key,), fetch=True)
    return dict(row) if row else None

def add_gift(key, emoji, name, stars):
    db_exec("INSERT OR REPLACE INTO gifts (key, emoji, name, stars) VALUES (?, ?, ?, ?)",
            (key, emoji, name, stars))

def remove_gift(key):
    db_exec("DELETE FROM gifts WHERE key=?", (key,))

def get_chat_status(user_id):
    row = db_exec("SELECT status FROM support_chats WHERE user_id=?", (user_id,), fetch=True)
    return row["status"] if row else None

def open_chat(user_id):
    db_exec("""INSERT OR REPLACE INTO support_chats (user_id, status, admin_id, updated_at)
               VALUES (?, 'open', 0, ?)""", (user_id, datetime.now().isoformat()))

def close_chat(user_id, closed_by="user"):
    status = f"closed_by_{closed_by}"
    db_exec("UPDATE support_chats SET status=?, updated_at=? WHERE user_id=?",
            (status, datetime.now().isoformat(), user_id))

def is_chat_open(user_id):
    return get_chat_status(user_id) == "open"

def save_support_msg(user_id, admin_id, msg_type, content, is_from_admin):
    db_exec("""INSERT INTO support_tickets (user_id, admin_id, message_type, content, is_from_admin, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, admin_id, msg_type, content, is_from_admin, datetime.now().isoformat()))

def delete_chat(user_id):
    db_exec("DELETE FROM support_tickets WHERE user_id=?", (user_id,))
    db_exec("DELETE FROM support_chats WHERE user_id=?", (user_id,))

def get_chat_users():
    rows = db_exec(
        "SELECT sc.user_id, sc.status, sc.updated_at, u.first_name, u.username "
        "FROM support_chats sc LEFT JOIN users u ON sc.user_id=u.user_id "
        "ORDER BY sc.updated_at DESC",
        fetchall=True
    )
    return [dict(r) for r in rows] if rows else []

# ═══════════════════════════════════════════════════════════
# BOT
# ═══════════════════════════════════════════════════════════
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class US(StatesGroup):
    answer = State()
    withdraw_stars = State()
    support_msg = State()
    gift_username = State()
    gift_amount = State()
    review_text = State()

class AS(StatesGroup):
    channel = State()
    q_text = State()
    q_correct = State()
    q_wrong1 = State()
    q_wrong2 = State()
    broadcast = State()
    setting_val = State()
    user_id = State()
    stars_amount = State()
    stars_reason = State()
    user_msg = State()
    add_admin_id = State()
    gift_key = State()
    gift_emoji = State()
    gift_name = State()
    gift_stars = State()
    reply_to_user = State()
    review_channel = State()
    level_name = State()
    level_emoji = State()
    level_min = State()
    level_max = State()

# ═══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════════════
def main_menu(uid):
    lang = get_user_lang(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "profile"), callback_data="m_profile")
    b.button(text=T(lang, "ref_link"), callback_data="m_reflink")
    b.button(text=T(lang, "rating"), callback_data="m_rating")
    b.button(text=T(lang, "withdraw"), callback_data="m_withdraw")
    b.button(text=T(lang, "gift_stars"), callback_data="m_gift")
    b.button(text=T(lang, "review"), callback_data="m_review")
    b.button(text=T(lang, "support"), callback_data="m_support")
    b.button(text="🌐 Til / Язык / Lang", callback_data="m_lang")
    if is_admin(uid):
        b.button(text=T(lang, "admin"), callback_data="m_admin")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()

def admin_menu(uid):
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanallar", callback_data="a_channels")
    b.button(text="❓ Savollar", callback_data="a_questions")
    b.button(text="🎁 Giftlar", callback_data="a_gifts")
    b.button(text="⚙️ Sozlamalar", callback_data="a_settings")
    b.button(text="📊 Statistika", callback_data="a_stats")
    b.button(text="📨 Broadcast", callback_data="a_broadcast")
    b.button(text="💸 Yechib olish", callback_data="a_withdrawals")
    b.button(text="👤 User boshqarish", callback_data="a_users")
    b.button(text="💬 Suhbatlar", callback_data="a_chats")
    b.button(text="⭐ Sharhlar", callback_data="a_reviews")
    b.button(text="🏅 Darajalar", callback_data="a_levels")
    if is_super_admin(uid):
        b.button(text="👑 Adminlar", callback_data="a_admins")
    b.button(text="🏠 Asosiy menyu", callback_data="m_menu")
    b.adjust(2)
    return b.as_markup()

def lang_keyboard():
    b = InlineKeyboardBuilder()
    for code, info in LANGS.items():
        b.button(text=f"{info['flag']} {info['name']}", callback_data=f"lang_{code}")
    b.adjust(1)
    return b.as_markup()

def back_to_menu_kb(uid):
    lang = get_user_lang(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    return b.as_markup()

# ═══════════════════════════════════════════════════════════
# OBUNA
# ═══════════════════════════════════════════════════════════
async def check_subs(uid):
    channels = get_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=uid)
            if member.status in ("left", "kicked"):
                return False
        except TelegramBadRequest as e:
            logger.warning(f"Kanal {ch}: {e}")
            continue
        except Exception as e:
            logger.warning(f"Kanal {ch} xato: {e}")
            continue
    return True

async def subs_kb(uid):
    lang = get_user_lang(uid)
    channels = get_channels()
    b = InlineKeyboardBuilder()
    for ch in channels:
        try:
            chat = await bot.get_chat(ch)
            link = chat.invite_link or f"https://t.me/{ch.replace('@', '')}"
        except Exception:
            link = f"https://t.me/{ch.replace('@', '')}"
        b.button(text=f"📢 {ch}", url=link)
    b.button(text=T(lang, "check"), callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()

# ═══════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    uname = message.from_user.username
    fname = message.from_user.first_name or "User"
    lname = message.from_user.last_name

    args = message.text.split(maxsplit=1)
    ref_id = 0
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            r = int(args[1].replace("ref_", ""))
            if r != uid:
                ref_id = r
        except ValueError:
            pass

    user = get_user(uid)
    if user is None:
        susp = 0 if uname else 1
        create_user(uid, uname, fname, lname, ref_id)
        if susp:
            update_user(uid, is_suspicious=1)
        await message.answer(
            T("uz", "choose_lang"),
            reply_markup=lang_keyboard(),
            parse_mode="HTML"
        )
        return

    lang = get_user_lang(uid)

    if user["is_banned"]:
        await message.answer(T(lang, "banned"), parse_mode="HTML")
        return

    if not await check_subs(uid):
        kb = await subs_kb(uid)
        await message.answer(T(lang, "subscribe"), reply_markup=kb, parse_mode="HTML")
        return

    if user["is_verified"]:
        await message.answer(
            T(lang, "welcome", name=fname),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await message.answer(
            T(lang, "welcome", name=fname),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    answers = [
        (q["correct_answer"], True),
        (q["wrong1"], False),
        (q["wrong2"], False),
    ]
    random.shuffle(answers)

    b = InlineKeyboardBuilder()
    for ans, is_correct in answers:
        b.button(
            text=ans,
            callback_data=f"ans_{q['id']}_{'1' if is_correct else '0'}"
        )
    b.adjust(1)

    await state.update_data(q_id=q["id"], ref_id=ref_id)
    await state.set_state(US.answer)
    await message.answer(
        T(lang, "bot_check", q=q["question"]),
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════════
# MENYU
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_menu")
async def cb_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(
            T(lang, "menu_title"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "menu_title"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
    await cb.answer()

@dp.callback_query(F.data == "m_profile")
async def cb_profile(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    refs = db_exec(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND is_verified=1",
        (uid,), fetch=True
    )
    ref_count = refs["c"] if refs else 0
    uname = f"@{user['username']}" if user["username"] else "—"
    ver = "✅" if user["is_verified"] else "❌"
    joined = user["joined_at"][:10] if user["joined_at"] else "—"
    lvl = get_user_level(user["stars"])
    lvl_text = f"{lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>"
    text = (
        f"╭━━━〔 👤 <b>{T(lang, 'profile')}</b> 〕━━━╮\n\n"
        f"🆔 <b>ID:</b> <code>{user['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {user['first_name'] or 'N/A'}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"⭐ <b>Stars:</b> {user['stars']}\n"
        f"🏅 <b>{T(lang, 'level')}:</b> {lvl_text}\n"
        f"👥 <b>Referallar:</b> {ref_count}\n"
        f"✅ <b>Tasdiqlangan:</b> {ver}\n"
        f"📅 <b>Qo'shilgan:</b> {joined}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb(uid))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu_kb(uid))
    await cb.answer()

@dp.callback_query(F.data == "m_reflink")
async def cb_reflink(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    refs = db_exec(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND is_verified=1",
        (uid,), fetch=True
    )
    ref_count = refs["c"] if refs else 0
    reward = int(get_setting("stars_per_referral", "2"))
    user = get_user(uid)
    text = (
        f"╭━━━〔 🔗 <b>{T(lang, 'ref_link')}</b> 〕━━━╮\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 <b>Taklif qilganlar:</b> {ref_count}\n"
        f"⭐ <b>Stars:</b> {user['stars'] if user else 0}\n"
        f"🎁 <b>Har bir referal:</b> +{reward} ⭐\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    share_url = f"https://t.me/share/url?url={link}&text=🚀 Botga qo'shiling!"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "share"), url=share_url)
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "m_rating")
async def cb_rating(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    rows = db_exec(
        "SELECT first_name, stars FROM users WHERE is_verified=1 AND is_banned=0 ORDER BY stars DESC LIMIT 10",
        fetchall=True
    )
    text = f"╭━━━〔 🏆 <b>{T(lang, 'rating')}</b> 〕━━━╮\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {r['first_name'] or 'N/A'} — <b>{r['stars']} ⭐</b>\n"
    else:
        text += "—"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb(uid))
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu_kb(uid))
    await cb.answer()

@dp.callback_query(F.data == "m_lang")
async def cb_lang(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_text(
            "🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>",
            reply_markup=lang_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            "🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>",
            reply_markup=lang_keyboard(),
            parse_mode="HTML"
        )
    await cb.answer()

# ═══════════════════════════════════════════════════════════
# TIL
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb: types.CallbackQuery, state: FSMContext):
    code = cb.data.replace("lang_", "")
    if code not in LANGS:
        return
    uid = cb.from_user.id
    update_user(uid, language=code)
    user = get_user(uid)
    lang = code

    await cb.answer(T(lang, "lang_set"))
    try:
        await cb.message.delete()
    except Exception:
        pass

    if user["is_banned"]:
        await cb.message.answer(T(lang, "banned"), parse_mode="HTML")
        return

    if not await check_subs(uid):
        kb = await subs_kb(uid)
        await cb.message.answer(T(lang, "subscribe"), reply_markup=kb, parse_mode="HTML")
        return

    if user["is_verified"]:
        await cb.message.answer(
            T(lang, "welcome", name=user["first_name"] or "User"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await cb.message.answer(
            T(lang, "welcome", name=user["first_name"] or "User"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    answers = [
        (q["correct_answer"], True),
        (q["wrong1"], False),
        (q["wrong2"], False),
    ]
    random.shuffle(answers)
    b = InlineKeyboardBuilder()
    for ans, is_correct in answers:
        b.button(text=ans, callback_data=f"ans_{q['id']}_{'1' if is_correct else '0'}")
    b.adjust(1)

    await state.update_data(q_id=q["id"], ref_id=user["referrer_id"])
    await state.set_state(US.answer)
    await cb.message.answer(
        T(lang, "bot_check", q=q["question"]),
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════════
# SAVOL JAVOBI
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("ans_"))
async def check_ans(cb: types.CallbackQuery, state: FSMContext):
    parts = cb.data.split("_")
    if len(parts) != 3:
        return
    q_id = int(parts[1])
    is_correct = parts[2] == "1"

    uid = cb.from_user.id
    lang = get_user_lang(uid)
    data = await state.get_data()
    ref_id = data.get("ref_id", 0)

    if not is_correct:
        await cb.answer(T(lang, "wrong_answer"), show_alert=True)
        await state.clear()
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(T(lang, "wrong_ans_retry"), parse_mode="HTML")
        return

    update_user(uid, is_verified=1)

    if ref_id and ref_id != uid:
        ref = get_user(ref_id)
        if ref and not ref["is_banned"]:
            reward = int(get_setting("stars_per_referral", "2"))
            update_user(ref_id, stars=ref["stars"] + reward)
            ref_lang = get_user_lang(ref_id)
            try:
                await bot.send_message(
                    ref_id,
                    T(ref_lang, "referral_reward", n=reward) + f"\n💰 {T(ref_lang, 'total')}: <b>{ref['stars'] + reward} ⭐</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await state.clear()
    await cb.answer(T(lang, "correct"))
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(
        T(lang, "welcome", name=cb.from_user.first_name or "User"),
        reply_markup=main_menu(uid),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════════
# OBUNA
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)

    if not await check_subs(uid):
        await cb.answer(T(lang, "not_enough"), show_alert=True)
        return

    await cb.answer(T(lang, "correct"))
    try:
        await cb.message.delete()
    except Exception:
        pass

    user = get_user(uid)
    if user and user["is_verified"]:
        await cb.message.answer(
            T(lang, "welcome", name=user["first_name"] or "User"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await cb.message.answer(T(lang, "welcome", name=user["first_name"] or "User"),
                                reply_markup=main_menu(uid), parse_mode="HTML")
        return

    answers = [
        (q["correct_answer"], True),
        (q["wrong1"], False),
        (q["wrong2"], False),
    ]
    random.shuffle(answers)
    b = InlineKeyboardBuilder()
    for ans, is_correct in answers:
        b.button(text=ans, callback_data=f"ans_{q['id']}_{'1' if is_correct else '0'}")
    b.adjust(1)

    await state.update_data(q_id=q["id"], ref_id=user["referrer_id"] if user else 0)
    await state.set_state(US.answer)
    await cb.message.answer(
        T(lang, "bot_check", q=q["question"]),
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════════
# SUPPORT
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_support")
async def cb_support(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    chat_status = get_chat_status(uid)
    if chat_status == "open":
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
        try:
            await cb.message.edit_text(T(lang, "chat_active"), reply_markup=b.as_markup(), parse_mode="HTML")
        except Exception:
            await cb.message.answer(T(lang, "chat_active"), reply_markup=b.as_markup(), parse_mode="HTML")
        await state.set_state(US.support_msg)
        await cb.answer()
        return

    open_chat(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(T(lang, "support_title"), reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "support_title"), reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.support_msg)
    await cb.answer()

@dp.message(US.support_msg)
async def support_send(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await message.answer(T(lang, "start_first"))
        return

    if not is_chat_open(uid):
        await state.clear()
        await message.answer(T(lang, "chat_closed_by_admin"),
                             reply_markup=back_to_menu_kb(uid), parse_mode="HTML")
        return

    if message.text:
        msg_type, content = "text", message.text
    elif message.photo:
        msg_type, content = "photo", message.photo[-1].file_id
    elif message.video:
        msg_type, content = "video", message.video.file_id
    elif message.document:
        msg_type, content = "document", message.document.file_id
    elif message.voice:
        msg_type, content = "voice", message.voice.file_id
    elif message.audio:
        msg_type, content = "audio", message.audio.file_id
    elif message.sticker:
        msg_type, content = "sticker", message.sticker.file_id
    else:
        await message.answer("❌ Bu turdagi xabar qo'llab-quvvatlanmaydi.")
        return

    save_support_msg(uid, 0, msg_type, content, 0)

    uname = f"@{user['username']}" if user["username"] else "—"
    admin_header = T("uz", "user_msg") + "\n\n" + T("uz", "support_new_msg",
                     name=user["first_name"] or "User",
                     username=uname,
                     uid=uid,
                     time=datetime.now().strftime("%Y-%m-%d %H:%M"))

    kb = InlineKeyboardBuilder()
    kb.button(text="✉️ Javob berish", callback_data=f"reply_{uid}")
    kb.button(text="🔚 Suhbatni tugatish", callback_data=f"chat_close_admin_{uid}")
    kb.adjust(1)

    sent = 0
    for a in list_admins():
        try:
            await bot.send_message(a["user_id"], admin_header,
                                   reply_markup=kb.as_markup(), parse_mode="HTML")
            await message.forward(a["user_id"])
            sent += 1
        except Exception as e:
            logger.warning(f"Adminga yuborishda xato ({a['user_id']}): {e}")

    if sent == 0:
        await message.answer("⚠️ Hech qanday admin topilmadi.")
        return

    await message.answer(T(lang, "support_sent"), parse_mode="HTML")

@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    uid = int(cb.data.replace("reply_", ""))
    user = get_user(uid)
    if not user:
        await cb.answer("❌ User topilmadi!", show_alert=True)
        return

    if not is_chat_open(uid):
        await cb.answer("⚠️ Suhbat yopilgan!", show_alert=True)
        return

    await state.update_data(reply_to_uid=uid)
    await cb.message.answer(
        f"✉️ <b>Javob yozing</b>\n\n👤 {user['first_name']} (<code>{uid}</code>)\n\n"
        f"Matn, rasm, video yoki fayl yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(AS.reply_to_user)
    await cb.answer()

@dp.message(AS.reply_to_user)
async def reply_send(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid = data.get("reply_to_uid")
    if not uid:
        await state.clear()
        return

    user = get_user(uid)
    if not user:
        await message.answer("❌ User topilmadi.")
        await state.clear()
        return

    if not is_chat_open(uid):
        await message.answer("⚠️ Bu suhbat yopilgan.")
        await state.clear()
        return

    if message.text:
        msg_type, content = "text", message.text
    elif message.photo:
        msg_type, content = "photo", message.photo[-1].file_id
    elif message.video:
        msg_type, content = "video", message.video.file_id
    elif message.document:
        msg_type, content = "document", message.document.file_id
    elif message.voice:
        msg_type, content = "voice", message.voice.file_id
    else:
        msg_type, content = "text", "(media)"

    save_support_msg(uid, message.from_user.id, msg_type, content, 1)

    u_lang = get_user_lang(uid)
    try:
        await bot.send_message(uid, T(u_lang, "admin_reply"), parse_mode="HTML")
        await message.copy_to(chat_id=uid)
    except TelegramForbiddenError:
        await message.answer("❌ Foydalanuvchi botni bloklagan.")
        await state.clear()
        return
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ <b>Javob yuborildi!</b>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("chat_close_admin_"))
async def chat_close_admin(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    uid = int(cb.data.replace("chat_close_admin_", ""))
    if not is_chat_open(uid):
        await cb.answer("⚠️ Suhbat yopilgan!", show_alert=True)
        return

    close_chat(uid, closed_by="admin")

    u_lang = get_user_lang(uid)
    try:
        await bot.send_message(uid, T(u_lang, "chat_closed_by_admin"), parse_mode="HTML")
    except Exception:
        pass

    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n🔚 <b>SUHBAT TUGATILDI</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await cb.answer("✅")

# ═══════════════════════════════════════════════════════════
# STARS SOVG'A QILISH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_gift")
async def cb_gift_stars(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="gift_cancel")
    b.adjust(1)

    try:
        await cb.message.edit_text(
            T(lang, "gift_stars_title", bal=user["stars"]),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "gift_stars_title", bal=user["stars"]),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    await state.set_state(US.gift_username)
    await cb.answer()

@dp.callback_query(F.data == "gift_cancel")
async def gift_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(
            T(lang, "menu_title"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer("OK")

@dp.message(US.gift_username)
async def gift_username_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    text = message.text.strip()

    target = None
    if text.startswith("@") or text.replace("_", "").isalnum():
        target = get_user_by_username(text)
    if not target and text.isdigit():
        target = get_user(int(text))

    if not target:
        await message.answer(T(lang, "gift_stars_not_found"))
        return

    if target["user_id"] == uid:
        await message.answer(T(lang, "gift_stars_self"))
        return

    await state.update_data(gift_target=target["user_id"])
    await message.answer(
        T(lang, "gift_stars_amount", name=target["first_name"] or "User"),
        parse_mode="HTML"
    )
    await state.set_state(US.gift_amount)

@dp.message(US.gift_amount)
async def gift_amount_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer(T(lang, "enter_number"))
        return
    if amount <= 0:
        await message.answer(T(lang, "enter_number"))
        return

    user = get_user(uid)
    if amount > user["stars"]:
        await message.answer(
            f"{T(lang, 'not_enough')}\n💰 {T(lang, 'balance')}: <b>{user['stars']} ⭐</b>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    target_id = data.get("gift_target")
    target = get_user(target_id)
    if not target:
        await state.clear()
        await message.answer(T(lang, "gift_stars_not_found"))
        return

    await state.update_data(gift_amount=amount)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data="gift_confirm")
    b.button(text=T(lang, "cancel"), callback_data="gift_cancel")
    b.adjust(2)

    await message.answer(
        T(lang, "gift_stars_confirm", name=target["first_name"] or "User", n=amount),
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "gift_confirm")
async def gift_confirm(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    data = await state.get_data()
    target_id = data.get("gift_target")
    amount = data.get("gift_amount")

    if not target_id or not amount:
        await cb.answer("Xato", show_alert=True)
        return

    user = get_user(uid)
    target = get_user(target_id)
    if not user or not target:
        await cb.answer("Xato", show_alert=True)
        return

    if amount > user["stars"]:
        await cb.answer(T(lang, "not_enough"), show_alert=True)
        return

    update_user(uid, stars=user["stars"] - amount)
    update_user(target_id, stars=target["stars"] + amount)

    await cb.message.edit_text(
        T(lang, "gift_stars_sent", n=amount, name=target["first_name"] or "User"),
        parse_mode="HTML"
    )

    target_lang = get_user_lang(target_id)
    try:
        await bot.send_message(
            target_id,
            T(target_lang, "gift_stars_received",
              name=user["first_name"] or "User",
              n=amount,
              total=target["stars"] + amount),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await state.clear()
    await cb.answer("✅")

# ═══════════════════════════════════════════════════════════
# SHARH QOLDIRISH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_review")
async def cb_review(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="review_cancel")
    b.adjust(1)

    try:
        await cb.message.edit_text(
            T(lang, "review_title"),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "review_title"),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    await state.set_state(US.review_text)
    await cb.answer()

@dp.callback_query(F.data == "review_cancel")
async def review_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(
            T(lang, "menu_title"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer("OK")

@dp.message(US.review_text)
async def review_text_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("❌ Sharh juda qisqa. Kamida 5 ta belgi.")
        return

    db_exec(
        "INSERT INTO reviews (user_id, text, status, created_at) VALUES (?, ?, 'pending', ?)",
        (uid, text, datetime.now().isoformat())
    )
    last = db_exec("SELECT MAX(id) AS id FROM reviews", fetch=True)
    r_id = last["id"] if last else 0

    await state.clear()
    await message.answer(T(lang, "review_sent"), parse_mode="HTML")
    await message.answer(
        T(lang, "menu_title"),
        reply_markup=main_menu(uid),
        parse_mode="HTML"
    )

    user = get_user(uid)
    uname = f"@{user['username']}" if user and user["username"] else "—"
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"revappr_{r_id}")
    kb.button(text="❌ Rad etish", callback_data=f"revrej_{r_id}")
    kb.adjust(2)

    for a in list_admins():
        try:
            await bot.send_message(
                a["user_id"],
                f"⭐ <b>Yangi sharh!</b>\n\n"
                f"👤 {user['first_name'] if user else 'User'} ({uname})\n"
                f"🆔 <code>{uid}</code>\n\n"
                f"💬 <i>{text}</i>",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
# YECHIB OLISH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_withdraw")
async def cb_withdraw(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "stars_withdraw"), callback_data="w_stars")
    b.button(text=T(lang, "gift_withdraw"), callback_data="w_gift")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)

    text = (
        f"╭━━━〔 💰 <b>{T(lang, 'withdraw')}</b> 〕━━━╮\n\n"
        f"⭐ <b>{T(lang, 'balance')}:</b> {user['stars']} ⭐\n\n"
        f"{T(lang, 'choose_reward')}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )

    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "w_cancel")
async def w_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(
            T(lang, "menu_title"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer("OK")

@dp.callback_query(F.data == "w_stars")
async def w_stars(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    min_w = int(get_setting("min_withdraw", "50"))
    max_w = int(get_setting("max_withdraw", "1000000"))

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)

    text = (
        f"╭━━━〔 ⭐ <b>Stars yechib olish</b> 〕━━━╮\n\n"
        f"💰 <b>{T(lang, 'balance')}:</b> {user['stars']} ⭐\n"
        f"📉 <b>Min:</b> {min_w} ⭐\n"
        f"📈 <b>Max:</b> {max_w:,} ⭐\n\n"
        f"💬 Nechta stars yechib olmoqchisiz?\n"
        f"<i>Raqamni kiriting:</i>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )

    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.withdraw_stars)
    await cb.answer()

@dp.message(US.withdraw_stars)
async def w_stars_process(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    text = message.text.strip().replace(" ", "").replace(",", "")
    try:
        amount = int(text)
    except ValueError:
        await message.answer(T(lang, "enter_number"))
        return

    min_w = int(get_setting("min_withdraw", "50"))
    max_w = int(get_setting("max_withdraw", "1000000"))

    if amount < min_w:
        await message.answer(T(lang, "min_withdraw", n=min_w), parse_mode="HTML")
        return
    if amount > max_w:
        await message.answer(T(lang, "max_withdraw", n=f"{max_w:,}"), parse_mode="HTML")
        return

    user = get_user(uid)
    if amount > user["stars"]:
        await message.answer(
            f"{T(lang, 'not_enough')}\n\n"
            f"💰 {T(lang, 'balance')}: <b>{user['stars']} ⭐</b>\n"
            f"📊 {T(lang, 'need')}: <b>{amount} ⭐</b>",
            parse_mode="HTML"
        )
        return

    db_exec(
        "INSERT INTO withdrawals (user_id, stars, reward_type, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (uid, amount, "stars", "pending", datetime.now().isoformat())
    )
    last = db_exec("SELECT MAX(id) AS id FROM withdrawals", fetch=True)
    w_id = last["id"] if last else 0

    await state.clear()
    await message.answer(T(lang, "sent_to_admin", n=amount), parse_mode="HTML")
    await message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")

    uname = f"@{user['username']}" if user["username"] else "—"
    admin_text = (
        f"╭━━━〔 💸 <b>YANGI STARS SO'ROVI</b> 〕━━━╮\n\n"
        f"🆔 <b>So'rov:</b> <code>#{w_id}</code>\n"
        f"👤 <b>User:</b> {user['first_name']}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"⭐ <b>Miqdor:</b> <b>{amount} stars</b>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"appr_{w_id}")
    kb.button(text="❌ Rad etish", callback_data=f"rej_{w_id}")
    kb.adjust(2)

    for a in list_admins():
        try:
            await bot.send_message(a["user_id"], admin_text,
                                   reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Adminga xabar: {e}")

@dp.callback_query(F.data == "w_gift")
async def w_gift(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)

    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("❌ Giftlar yo'q!", show_alert=True)
        return

    text = (
        f"╭━━━〔 🎁 <b>Telegram Gift olish</b> 〕━━━╮\n\n"
        f"💰 <b>{T(lang, 'balance')}:</b> {user['stars']} ⭐\n\n"
        f"<i>Giftni tanlang:</i>\n\n"
    )
    b = InlineKeyboardBuilder()
    for g in gifts:
        text += f"{g['emoji']} <b>{g['name']}</b> — {g['stars']} ⭐\n"
        b.button(
            text=f"{g['emoji']} {g['name']} — {g['stars']}⭐",
            callback_data=f"gift_{g['key']}"
        )
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b.button(text=T(lang, "back"), callback_data="w_back")
    b.adjust(1)

    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "w_back")
async def w_back(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "stars_withdraw"), callback_data="w_stars")
    b.button(text=T(lang, "gift_withdraw"), callback_data="w_gift")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)

    text = (
        f"╭━━━〔 💰 <b>{T(lang, 'withdraw')}</b> 〕━━━╮\n\n"
        f"⭐ <b>{T(lang, 'balance')}:</b> {user['stars']} ⭐\n\n"
        f"{T(lang, 'choose_reward')}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )

    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()

@dp.callback_query(F.data.startswith("gift_"))
async def gift_select(cb: types.CallbackQuery, state: FSMContext):
    key = cb.data.replace("gift_", "")
    gift = get_gift(key)
    uid = cb.from_user.id
    lang = get_user_lang(uid)

    if not gift:
        await cb.answer("Topilmadi!", show_alert=True)
        return

    user = get_user(uid)
    if gift["stars"] > user["stars"]:
        await cb.answer(
            f"{T(lang, 'not_enough')}\n{T(lang, 'need')}: {gift['stars']} ⭐",
            show_alert=True
        )
        return

    db_exec(
        "INSERT INTO withdrawals (user_id, stars, reward_type, gift_key, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, gift["stars"], "gift", key, "pending", datetime.now().isoformat())
    )
    last = db_exec("SELECT MAX(id) AS id FROM withdrawals", fetch=True)
    w_id = last["id"] if last else 0

    await state.clear()
    try:
        await cb.message.edit_text(
            T(lang, "gift_sent", gift=f"{gift['emoji']} {gift['name']}", n=gift["stars"]),
            reply_markup=back_to_menu_kb(uid),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "gift_sent", gift=f"{gift['emoji']} {gift['name']}", n=gift["stars"]),
            reply_markup=back_to_menu_kb(uid),
            parse_mode="HTML"
        )
    await cb.answer("✅")

    uname = f"@{user['username']}" if user["username"] else "—"
    admin_text = (
        f"╭━━━〔 🎁 <b>YANGI GIFT SO'ROVI</b> 〕━━━╮\n\n"
        f"🆔 <b>So'rov:</b> <code>#{w_id}</code>\n"
        f"👤 <b>User:</b> {user['first_name']}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"🎁 <b>Gift:</b> {gift['emoji']} <b>{gift['name']}</b>\n"
        f"⭐ <b>Narx:</b> <b>{gift['stars']} stars</b>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"appr_{w_id}")
    kb.button(text="❌ Rad etish", callback_data=f"rej_{w_id}")
    kb.adjust(2)

    for a in list_admins():
        try:
            await bot.send_message(a["user_id"], admin_text,
                                   reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Adminga xabar: {e}")

# ═══════════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════════
@dp.message(Command("admin"))
async def admin_panel_cmd(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer(
        "╭━━━〔 🛠 <b>ADMIN PANEL</b> 〕━━━╮\n\n"
        "Kerakli bo'limni tanlang:\n\n"
        "╰━━━━━━━━━━━━━━━━━╯",
        reply_markup=admin_menu(message.from_user.id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "m_admin")
async def cb_admin(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    await state.clear()
    try:
        await cb.message.edit_text(
            "╭━━━〔 🛠 <b>ADMIN PANEL</b> 〕━━━╮\n\n"
            "Kerakli bo'limni tanlang:\n\n"
            "╰━━━━━━━━━━━━━━━━━╯",
            reply_markup=admin_menu(cb.from_user.id),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            "╭━━━〔 🛠 <b>ADMIN PANEL</b> 〕━━━╮\n\n"
            "Kerakli bo'limni tanlang:\n\n"
            "╰━━━━━━━━━━━━━━━━━╯",
            reply_markup=admin_menu(cb.from_user.id),
            parse_mode="HTML"
        )
    await cb.answer()

@dp.callback_query(F.data == "a_back")
async def a_back(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    try:
        await cb.message.edit_text(
            "╭━━━〔 🛠 <b>ADMIN PANEL</b> 〕━━━╮\n\n"
            "Kerakli bo'limni tanlang:\n\n"
            "╰━━━━━━━━━━━━━━━━━╯",
            reply_markup=admin_menu(cb.from_user.id),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer()

# ---------- Kanallar ----------
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    text = "╭━━━〔 📢 <b>KANALLAR</b> 〕━━━╮\n\n"
    if channels:
        for ch in channels:
            text += f"• {ch}\n"
    else:
        text += "— Kanallar yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_ch")
    b.button(text="➖ O'chirish", callback_data="del_ch_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_ch")
async def add_ch_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "📢 <b>Kanal username kiriting</b>\n\nMisol: <code>@mychannel</code>",
        parse_mode="HTML"
    )
    await state.set_state(AS.channel)
    await cb.answer()

@dp.message(AS.channel)
async def add_ch_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    add_channel(ch)
    await state.clear()
    await message.answer(f"✅ <b>{ch}</b> qo'shildi!", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_ch_list")
async def del_ch_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    if not channels:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.button(text=f"❌ {ch}", callback_data=f"delch_{ch}")
    b.button(text="⬅️ Orqaga", callback_data="a_channels")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("delch_"))
async def del_ch_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    ch = cb.data.replace("delch_", "")
    remove_channel(ch)
    await cb.answer("✅")
    await a_channels(cb)

# ---------- Savollar ----------
@dp.callback_query(F.data == "a_questions")
async def a_questions(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    qs = get_questions()
    text = "╭━━━〔 ❓ <b>SAVOLLAR</b> 〕━━━╮\n\n"
    if qs:
        for q in qs:
            text += f"📝 {q['question']}\n  ✅ {q['correct_answer']}\n  ❌ {q['wrong1']} | {q['wrong2']}\n\n"
    else:
        text += "— Savollar yo'q\n"
    text += "╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_q")
    b.button(text="➖ O'chirish", callback_data="del_q_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_q")
async def add_q_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("❓ <b>Savolni kiriting:</b>", parse_mode="HTML")
    await state.set_state(AS.q_text)
    await cb.answer()

@dp.message(AS.q_text)
async def add_q_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_text=message.text.strip())
    await message.answer("✅ <b>To'g'ri javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_correct)

@dp.message(AS.q_correct)
async def add_q_correct(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_correct=message.text.strip())
    await message.answer("❌ <b>1-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong1)

@dp.message(AS.q_wrong1)
async def add_q_wrong1(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_wrong1=message.text.strip())
    await message.answer("❌ <b>2-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong2)

@dp.message(AS.q_wrong2)
async def add_q_wrong2(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    add_question(data["q_text"], data["q_correct"], data["q_wrong1"], message.text.strip())
    await state.clear()
    await message.answer("✅ <b>Savol qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_q_list")
async def del_q_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    qs = get_questions()
    if not qs:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for q in qs:
        b.button(text=f"❌ {q['question'][:40]}", callback_data=f"delq_{q['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_questions")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("delq_"))
async def del_q_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    q_id = int(cb.data.replace("delq_", ""))
    remove_question(q_id)
    await cb.answer("✅")
    await a_questions(cb)

# ---------- Giftlar ----------
@dp.callback_query(F.data == "a_gifts")
async def a_gifts(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    gifts = get_all_gifts()
    text = "╭━━━〔 🎁 <b>GIFTLAR</b> 〕━━━╮\n\n"
    for g in gifts:
        text += f"{g['emoji']} <b>{g['name']}</b> — {g['stars']} ⭐\n"
    if not gifts:
        text += "— Giftlar yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_gift")
    b.button(text="✏️ Tahrirlash", callback_data="edit_gift_list")
    b.button(text="➖ O'chirish", callback_data="del_gift_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_gift")
async def add_gift_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🎁 <b>Kalit so'z:</b>", parse_mode="HTML")
    await state.set_state(AS.gift_key)
    await cb.answer()

@dp.message(AS.gift_key)
async def gift_key_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    key = message.text.strip().lower().replace(" ", "_")
    if not key or not key.replace("_", "").isalnum():
        await message.answer("❌ Faqat harflar va raqamlar.")
        return
    if get_gift(key):
        await message.answer("❌ Allaqachon bor.")
        return
    await state.update_data(gift_key=key)
    await message.answer("😀 <b>Emoji:</b>", parse_mode="HTML")
    await state.set_state(AS.gift_emoji)

@dp.message(AS.gift_emoji)
async def gift_emoji_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET emoji=? WHERE key=?",
                    (message.text.strip(), data["edit_gift_key"]))
        await message.answer("📝 <b>Nom (yoki /skip):</b>", parse_mode="HTML")
        await state.set_state(AS.gift_name)
    else:
        await state.update_data(gift_emoji=message.text.strip())
        await message.answer("📝 <b>Nom:</b>", parse_mode="HTML")
        await state.set_state(AS.gift_name)

@dp.message(AS.gift_name)
async def gift_name_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET name=? WHERE key=?",
                    (message.text.strip(), data["edit_gift_key"]))
        await message.answer("⭐ <b>Narx (yoki /skip):</b>", parse_mode="HTML")
        await state.set_state(AS.gift_stars)
    else:
        await state.update_data(gift_name=message.text.strip())
        await message.answer("⭐ <b>Narx:</b>", parse_mode="HTML")
        await state.set_state(AS.gift_stars)

@dp.message(AS.gift_stars)
async def gift_stars_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            try:
                stars = int(message.text.strip())
                db_exec("UPDATE gifts SET stars=? WHERE key=?",
                        (stars, data["edit_gift_key"]))
            except ValueError:
                await message.answer("❌ Raqam.")
                return
        await state.clear()
        await message.answer("✅ <b>Tahrirlandi!</b>", parse_mode="HTML")
        await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))
    else:
        try:
            stars = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Raqam.")
            return
        if stars < 1:
            await message.answer("❌ Kamida 1.")
            return
        add_gift(data["gift_key"], data["gift_emoji"], data["gift_name"], stars)
        await state.clear()
        await message.answer("✅ <b>Gift qo'shildi!</b>", parse_mode="HTML")
        await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_gift_list")
async def del_gift_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for g in gifts:
        b.button(text=f"❌ {g['emoji']} {g['name']}", callback_data=f"delgift_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("delgift_"))
async def del_gift_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    key = cb.data.replace("delgift_", "")
    remove_gift(key)
    await cb.answer("✅")
    await a_gifts(cb)

@dp.callback_query(F.data == "edit_gift_list")
async def edit_gift_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for g in gifts:
        b.button(text=f"✏️ {g['emoji']} {g['name']}", callback_data=f"editgift_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("✏️ <b>Tahrirlash:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("editgift_"))
async def edit_gift_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    key = cb.data.replace("editgift_", "")
    gift = get_gift(key)
    if not gift:
        await cb.answer("—", show_alert=True)
        return
    await state.update_data(edit_gift_key=key)
    await cb.message.edit_text(
        f"✏️ <b>{gift['emoji']} {gift['name']}</b> ({gift['stars']}⭐)\n\n"
        f"Yangi emoji (yoki /skip):",
        parse_mode="HTML"
    )
    await state.set_state(AS.gift_emoji)
    await cb.answer()

# ---------- Sozlamalar ----------
@dp.callback_query(F.data == "a_settings")
async def a_settings(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    review_ch_display = get_setting("review_channel") or "yo'q"
    text = (
        f"╭━━━〔 ⚙️ <b>SOZLAMALAR</b> 〕━━━╮\n\n"
        f"🎯 1 referal = <b>{get_setting('stars_per_referral')} ⭐</b>\n"
        f"💰 Min yechish = <b>{get_setting('min_withdraw')} ⭐</b>\n"
        f"💎 Max yechish = <b>{get_setting('max_withdraw')} ⭐</b>\n"
        f"📢 Sharh kanali: <b>{review_ch_display}</b>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal", callback_data="set_ref")
    b.button(text="💰 Min", callback_data="set_minw")
    b.button(text="💎 Max", callback_data="set_maxw")
    b.button(text="📢 Sharh kanali", callback_data="set_rev_ch")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.in_({"set_ref", "set_minw", "set_maxw"}))
async def set_val_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    mapping = {
        "set_ref": ("stars_per_referral", "🎯 <b>1 referal uchun nechta stars?</b>"),
        "set_minw": ("min_withdraw", "💰 <b>Minimal yechish:</b>"),
        "set_maxw": ("max_withdraw", "💎 <b>Maksimal yechish:</b>"),
    }
    key, prompt = mapping[cb.data]
    await state.update_data(setting_key=key)
    await cb.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(AS.setting_val)
    await cb.answer()

@dp.callback_query(F.data == "set_rev_ch")
async def set_rev_ch_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "📢 <b>Sharh kanali username kiriting</b>\n\n"
        "Misol: <code>@my_reviews</code>\n\n"
        "Bot kanalga <b>admin</b> qilingan bo'lishi kerak!",
        parse_mode="HTML"
    )
    await state.set_state(AS.review_channel)
    await cb.answer()

@dp.message(AS.review_channel)
async def set_rev_ch_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    set_setting("review_channel", ch)
    await state.clear()
    await message.answer(f"✅ Sharh kanali: <b>{ch}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.message(AS.setting_val)
async def set_val_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    set_setting(data["setting_key"], val)
    await state.clear()
    await message.answer(f"✅ <b>{data['setting_key']} = {val}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ---------- Statistika ----------
@dp.callback_query(F.data == "a_stats")
async def a_stats(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    total = db_exec("SELECT COUNT(*) AS c FROM users", fetch=True)["c"]
    ver = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_verified=1", fetch=True)["c"]
    ban = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_banned=1", fetch=True)["c"]
    pend = db_exec("SELECT COUNT(*) AS c FROM withdrawals WHERE status='pending'", fetch=True)["c"]
    total_stars = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM users", fetch=True)["s"]
    open_chats = db_exec("SELECT COUNT(*) AS c FROM support_chats WHERE status='open'", fetch=True)["c"]
    pend_reviews = db_exec("SELECT COUNT(*) AS c FROM reviews WHERE status='pending'", fetch=True)["c"]
    text = (
        f"╭━━━〔 📊 <b>STATISTIKA</b> 〕━━━╮\n\n"
        f"👥 <b>Jami:</b> {total}\n"
        f"✅ <b>Tasdiqlangan:</b> {ver}\n"
        f"🚫 <b>Ban:</b> {ban}\n"
        f"💸 <b>Pending:</b> {pend}\n"
        f"⭐ <b>Jami stars:</b> {total_stars}\n"
        f"💬 <b>Faol suhbatlar:</b> {open_chats}\n"
        f"⭐ <b>Pending sharhlar:</b> {pend_reviews}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# ---------- Broadcast ----------
@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "📨 <b>Broadcast</b>\n\nXabar yuboring (matn/rasm/video/forward):",
        parse_mode="HTML"
    )
    await state.set_state(AS.broadcast)
    await cb.answer()

@dp.message(AS.broadcast)
async def broadcast_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    users = db_exec("SELECT user_id FROM users WHERE is_banned=0", fetchall=True) or []
    if not users:
        await message.answer("❌ Foydalanuvchilar yo'q!")
        return

    total = len(users)
    status = await message.answer(f"📨 Yuborilmoqda... 0/{total}")

    ok = 0
    fail = 0
    blocked = 0
    is_forward = message.forward_date is not None

    for i, u in enumerate(users, 1):
        try:
            if is_forward:
                await bot.forward_message(
                    chat_id=u["user_id"],
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
            else:
                await message.copy_to(chat_id=u["user_id"])
            ok += 1
        except TelegramForbiddenError:
            blocked += 1
            fail += 1
        except Exception:
            fail += 1

        if i % 25 == 0:
            try:
                await status.edit_text(f"📨 Yuborilmoqda... {i}/{total}")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    result = (
        f"╭━━━〔 📨 <b>BROADCAST TUGADI</b> 〕━━━╮\n\n"
        f"✅ <b>Yuborildi:</b> {ok}\n"
        f"❌ <b>Xato:</b> {fail}\n"
        f"🚫 <b>Bloklagan:</b> {blocked}\n"
        f"👥 <b>Jami:</b> {total}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    try:
        await status.edit_text(result, parse_mode="HTML")
    except Exception:
        await message.answer(result, parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ---------- Yechib olish (admin) ----------
@dp.callback_query(F.data == "a_withdrawals")
async def a_withdrawals(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec(
        "SELECT w.*, u.first_name, u.username FROM withdrawals w "
        "JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.id DESC",
        fetchall=True
    ) or []
    if not rows:
        await cb.answer("—", show_alert=True)
        return
    text = "╭━━━〔 💸 <b>PENDING</b> 〕━━━╮\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        if r["reward_type"] == "gift":
            g = get_gift(r["gift_key"]) or {}
            info = f"{g.get('emoji', '🎁')} {g.get('name', 'Gift')}"
        else:
            info = f"{r['stars']} ⭐"
        uname = f"@{r['username']}" if r["username"] else "—"
        text += f"• #{r['id']} {r['first_name']} ({uname}) — {info}\n"
        b.button(text=f"✅ #{r['id']}", callback_data=f"appr_{r['id']}")
        b.button(text=f"❌ #{r['id']}", callback_data=f"rej_{r['id']}")
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("appr_"))
async def approve_w(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    w_id = int(cb.data.replace("appr_", ""))
    w = db_exec("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetch=True)
    if not w or w["status"] != "pending":
        await cb.answer("—", show_alert=True)
        return
    user = get_user(w["user_id"])
    if not user:
        await cb.answer("—", show_alert=True)
        return
    if user["stars"] < w["stars"]:
        await cb.answer(f"❌ Kerak: {w['stars']}, bor: {user['stars']}", show_alert=True)
        return

    update_user(w["user_id"], stars=user["stars"] - w["stars"])
    db_exec("UPDATE withdrawals SET status='approved' WHERE id=?", (w_id,))

    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n✅ <b>TASDIQLANGAN</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    u_lang = get_user_lang(w["user_id"])

    review_ch = get_setting("review_channel", "")
    if review_ch:
        try:
            if w["reward_type"] == "stars":
                text = f"🎉 <b>{user['first_name']}</b> {w['stars']} ⭐ yechib oldi!"
            else:
                g = get_gift(w["gift_key"]) or {}
                text = f"🎉 <b>{user['first_name']}</b> {g.get('emoji', '🎁')} <b>{g.get('name', 'Gift')}</b> oldi!"
            await bot.send_message(review_ch, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Otziv kanalga post: {e}")

    if w["reward_type"] == "stars":
        try:
            await bot.send_invoice(
                chat_id=w["user_id"],
                title=f"{w['stars']} Stars",
                description=f"Siz {w['stars']} ⭐ yechib oldingiz!",
                payload=f"stars_{w_id}",
                provider_token="",
                currency="XTR",
                prices=[types.LabeledPrice(label="Stars", amount=w["stars"])],
            )
            await bot.send_message(
                w["user_id"],
                T(u_lang, "approved") + f"\n\n⭐ <b>{w['stars']} ⭐</b>",
                parse_mode="HTML"
            )
            await cb.answer("✅")
        except Exception as e:
            update_user(w["user_id"], stars=user["stars"])
            db_exec("UPDATE withdrawals SET status='pending' WHERE id=?", (w_id,))
            await cb.answer(f"❌ {e}", show_alert=True)
            return
    else:
        g = get_gift(w["gift_key"]) or {}
        await bot.send_message(
            w["user_id"],
            T(u_lang, "approved") + f"\n\n{g.get('emoji', '🎁')} <b>{g.get('name', 'Gift')}</b>",
            parse_mode="HTML"
        )
        await cb.answer("✅")

@dp.callback_query(F.data.startswith("rej_"))
async def reject_w(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    w_id = int(cb.data.replace("rej_", ""))
    w = db_exec("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetch=True)
    if not w or w["status"] != "pending":
        await cb.answer("—", show_alert=True)
        return
    db_exec("UPDATE withdrawals SET status='rejected' WHERE id=?", (w_id,))
    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n❌ <b>RAD ETILGAN</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer("❌")
    try:
        u_lang = get_user_lang(w["user_id"])
        await bot.send_message(w["user_id"], T(u_lang, "rejected"), parse_mode="HTML")
    except Exception:
        pass

# ---------- Suhbatlar ----------
@dp.callback_query(F.data == "a_chats")
async def a_chats(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    chats = get_chat_users()
    if not chats:
        await cb.answer("— Suhbatlar yo'q", show_alert=True)
        return
    text = "╭━━━〔 💬 <b>SUHBATLAR</b> 〕━━━╮\n\n"
    b = InlineKeyboardBuilder()
    for c in chats[:20]:
        uname = f"@{c['username']}" if c["username"] else "—"
        status_icon = "🟢" if c["status"] == "open" else "🔴"
        text += f"{status_icon} {c['first_name'] or 'User'} ({uname})\n  <code>{c['user_id']}</code>\n\n"
        b.button(text=f"💬 {c['first_name'] or 'User'}", callback_data=f"chat_open_{c['user_id']}")
        b.button(text=f"🗑", callback_data=f"chat_del_{c['user_id']}")
    text += "╰━━━━━━━━━━━━━━━━━╯"
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("chat_open_"))
async def chat_open(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("chat_open_", ""))
    user = get_user(uid)
    if not user:
        await cb.answer("❌", show_alert=True)
        return

    if not is_chat_open(uid):
        open_chat(uid)

    rows = db_exec(
        "SELECT * FROM support_tickets WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (uid,), fetchall=True
    ) or []
    history = f"╭━━━〔 💬 <b>TARIX</b> 〕━━━╮\n\n👤 <b>{user['first_name']}</b> (<code>{uid}</code>)\n\n"
    for r in reversed(rows):
        who = "👑" if r["is_from_admin"] else "👤"
        c = r["content"]
        if r["message_type"] != "text":
            c = f"[{r['message_type']}]"
        elif len(c) > 80:
            c = c[:80] + "..."
        history += f"{who} {c}\n"
    history += "\n╰━━━━━━━━━━━━━━━━━╯"

    b = InlineKeyboardBuilder()
    b.button(text="✉️ Javob", callback_data=f"reply_{uid}")
    b.button(text="🔚 Tugatish", callback_data=f"chat_close_admin_{uid}")
    b.button(text="🗑 O'chirish", callback_data=f"chat_del_{uid}")
    b.button(text="⬅️", callback_data="a_chats")
    b.adjust(1)

    try:
        await cb.message.edit_text(history, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(history, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("chat_del_"))
async def chat_del(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("chat_del_", ""))
    delete_chat(uid)
    await cb.answer("✅")
    await a_chats(cb)

# ---------- Sharhlar ----------
@dp.callback_query(F.data == "a_reviews")
async def a_reviews(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec(
        "SELECT r.*, u.first_name, u.username FROM reviews r "
        "LEFT JOIN users u ON r.user_id=u.user_id "
        "WHERE r.status='pending' ORDER BY r.id DESC LIMIT 20",
        fetchall=True
    ) or []
    if not rows:
        await cb.answer("— Pending sharhlar yo'q", show_alert=True)
        return
    text = "╭━━━〔 ⭐ <b>PENDING SHARHLAR</b> 〕━━━╮\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        uname = f"@{r['username']}" if r["username"] else "—"
        text += f"👤 {r['first_name'] or 'User'} ({uname})\n💬 <i>{r['text'][:150]}</i>\n\n"
        b.button(text=f"✅ #{r['id']}", callback_data=f"revappr_{r['id']}")
        b.button(text=f"❌ #{r['id']}", callback_data=f"revrej_{r['id']}")
    text += "╰━━━━━━━━━━━━━━━━━╯"
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("revappr_"))
async def review_approve(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    r_id = int(cb.data.replace("revappr_", ""))
    r = db_exec("SELECT * FROM reviews WHERE id=?", (r_id,), fetch=True)
    if not r or r["status"] != "pending":
        await cb.answer("—", show_alert=True)
        return

    db_exec("UPDATE reviews SET status='approved' WHERE id=?", (r_id,))
    user = get_user(r["user_id"])

    review_ch = get_setting("review_channel", "")
    if review_ch and user:
        try:
            uname = f"@{user['username']}" if user["username"] else "—"
            await bot.send_message(
                review_ch,
                f"⭐ <b>Yangi sharh!</b>\n\n"
                f"👤 {user['first_name']} ({uname})\n\n"
                f"💬 <i>{r['text']}</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Otziv kanal: {e}")

    try:
        u_lang = get_user_lang(r["user_id"])
        await bot.send_message(r["user_id"], T(u_lang, "review_approved"), parse_mode="HTML")
    except Exception:
        pass

    try:
        await cb.message.edit_text(
            cb.message.html_text + f"\n\n✅ <b>#{r_id} TASDIQLANDI</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer("✅")

@dp.callback_query(F.data.startswith("revrej_"))
async def review_reject(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    r_id = int(cb.data.replace("revrej_", ""))
    r = db_exec("SELECT * FROM reviews WHERE id=?", (r_id,), fetch=True)
    if not r or r["status"] != "pending":
        await cb.answer("—", show_alert=True)
        return

    db_exec("UPDATE reviews SET status='rejected' WHERE id=?", (r_id,))
    try:
        u_lang = get_user_lang(r["user_id"])
        await bot.send_message(r["user_id"], T(u_lang, "review_rejected"), parse_mode="HTML")
    except Exception:
        pass

    try:
        await cb.message.edit_text(
            cb.message.html_text + f"\n\n❌ <b>#{r_id} RAD ETILDI</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer("❌")

# ---------- Darajalar ----------
@dp.callback_query(F.data == "a_levels")
async def a_levels(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    lvls = get_levels()
    text = "╭━━━〔 🏅 <b>DARAJALAR</b> 〕━━━╮\n\n"
    for lvl in lvls:
        text += f"{lvl.get('emoji', '')} <b>{lvl.get('name', '')}</b>: {lvl.get('min_stars', 0)}-{lvl.get('max_stars', 0)} ⭐\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"

    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi daraja", callback_data="add_level")
    b.button(text="🗑 O'chirish", callback_data="del_level_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_level")
async def add_level_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🏅 <b>Daraja nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.level_name)
    await cb.answer()

@dp.message(AS.level_name)
async def level_name_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(level_name=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>", parse_mode="HTML")
    await state.set_state(AS.level_emoji)

@dp.message(AS.level_emoji)
async def level_emoji_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(level_emoji=message.text.strip())
    await message.answer("📉 <b>Min stars:</b>", parse_mode="HTML")
    await state.set_state(AS.level_min)

@dp.message(AS.level_min)
async def level_min_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(level_min=val)
    await message.answer("📈 <b>Max stars:</b>", parse_mode="HTML")
    await state.set_state(AS.level_max)

@dp.message(AS.level_max)
async def level_max_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    db_exec("INSERT INTO levels (name, emoji, min_stars, max_stars) VALUES (?, ?, ?, ?)",
            (data["level_name"], data["level_emoji"], data["level_min"], val))
    await state.clear()
    await message.answer("✅ <b>Daraja qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_level_list")
async def del_level_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    lvls = get_levels()
    b = InlineKeyboardBuilder()
    for lvl in lvls:
        b.button(text=f"❌ {lvl.get('emoji', '')} {lvl.get('name', '')}", callback_data=f"dellvl_{lvl['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_levels")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("dellvl_"))
async def del_level_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    lvl_id = int(cb.data.replace("dellvl_", ""))
    db_exec("DELETE FROM levels WHERE id=?", (lvl_id,))
    await cb.answer("✅")
    await a_levels(cb)

# ---------- User boshqarish ----------
@dp.callback_query(F.data == "a_users")
async def a_users(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👤 <b>User ID:</b>", parse_mode="HTML")
    await state.set_state(AS.user_id)
    await cb.answer()

@dp.message(AS.user_id)
async def user_info(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌")
        return
    user = get_user(uid)
    if not user:
        await message.answer("❌ Topilmadi.")
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Ban" if not user["is_banned"] else "✅ Unban", callback_data=f"tog_{uid}")
    b.button(text="➕ Stars", callback_data=f"adp_{uid}")
    b.button(text="➖ Stars", callback_data=f"rem_{uid}")
    b.button(text="✉️ Xabar", callback_data=f"msg_{uid}")
    b.button(text="💬 Suhbat", callback_data=f"chat_open_{uid}")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2, 2, 1, 1)
    uname = f"@{user['username']}" if user["username"] else "—"
    lvl = get_user_level(user["stars"])
    lvl_text = f"{lvl.get('emoji', '')} {lvl.get('name', '')}"
    ban_text = "Ha" if user["is_banned"] else "Yo'q"
    ver_text = "Ha" if user["is_verified"] else "Yo'q"
    text = (
        f"╭━━━〔 👤 <b>USER INFO</b> 〕━━━╮\n\n"
        f"🆔 <code>{user['user_id']}</code>\n"
        f"👤 {user['first_name']}\n"
        f"🔗 {uname}\n"
        f"⭐ {user['stars']}\n"
        f"🏅 {lvl_text}\n"
        f"🚫 Ban: {ban_text}\n"
        f"✅ Ver: {ver_text}\n"
        f"🌐 {user.get('language', 'uz')}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    await message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tog_"))
async def toggle_ban(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("tog_", ""))
    user = get_user(uid)
    if not user:
        return
    update_user(uid, is_banned=0 if user["is_banned"] else 1)
    await cb.answer("✅")

@dp.callback_query(F.data.startswith("adp_"))
async def add_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("adp_", ""))
    await state.update_data(target_uid=uid, action="add")
    await cb.message.edit_text("➕ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()

@dp.callback_query(F.data.startswith("rem_"))
async def remove_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("rem_", ""))
    await state.update_data(target_uid=uid, action="remove")
    await cb.message.edit_text("➖ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()

@dp.message(AS.stars_amount)
async def stars_amount_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌")
        return
    if amount <= 0:
        await message.answer("❌ >0")
        return
    data = await state.get_data()
    action = data.get("action", "add")
    await state.update_data(stars_amount=amount)
    await message.answer("📝 <b>Sabab:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_reason)

@dp.message(AS.stars_reason)
async def stars_reason_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    reason = message.text.strip()
    if not reason:
        await message.answer("❌")
        return

    data = await state.get_data()
    uid = data["target_uid"]
    amount = data["stars_amount"]
    action = data.get("action", "add")

    user = get_user(uid)
    if not user:
        await message.answer("❌")
        await state.clear()
        return

    if action == "add":
        new_stars = user["stars"] + amount
    else:
        if amount > user["stars"]:
            await message.answer(f"❌ Faqat {user['stars']} ⭐")
            return
        new_stars = user["stars"] - amount

    update_user(uid, stars=new_stars)
    await state.clear()

    u_lang = get_user_lang(uid)
    try:
        if action == "add":
            notify = T(u_lang, "stars_added", n=amount, reason=reason, total=new_stars)
        else:
            notify = T(u_lang, "stars_removed", n=amount, reason=reason, total=new_stars)
        await bot.send_message(uid, notify, parse_mode="HTML")
    except Exception:
        pass

    sign = "➕" if action == "add" else "➖"
    await message.answer(
        f"✅ {sign} <b>{amount} ⭐</b>\n📝 {reason}\n💰 <b>{new_stars} ⭐</b>",
        parse_mode="HTML"
    )
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("msg_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("✉️ <b>Xabar:</b>", parse_mode="HTML")
    await state.set_state(AS.user_msg)
    await cb.answer()

@dp.message(AS.user_msg)
async def user_msg_send(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid = data["target_uid"]
    try:
        await message.copy_to(chat_id=uid)
        await message.answer("✅")
    except Exception as e:
        await message.answer(f"❌ {e}")
    await state.clear()
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ---------- Adminlar ----------
@dp.callback_query(F.data == "a_admins")
async def a_admins(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    admins = list_admins()
    text = "╭━━━〔 👑 <b>ADMINLAR</b> 〕━━━╮\n\n"
    for a in admins:
        u = get_user(a["user_id"])
        name = u["first_name"] if u else "N/A"
        tag = " 👑" if a["user_id"] in SUPER_ADMIN_IDS else ""
        text += f"• {name} — <code>{a['user_id']}</code>{tag}\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕", callback_data="add_admin")
    b.button(text="➖", callback_data="del_admin_list")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👑 <b>Admin ID:</b>", parse_mode="HTML")
    await state.set_state(AS.add_admin_id)
    await cb.answer()

@dp.message(AS.add_admin_id)
async def add_admin_do(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌")
        return
    user = get_user(uid)
    if not user:
        await message.answer("❌")
        return
    if uid in SUPER_ADMIN_IDS:
        await message.answer("❌")
        return
    add_admin(uid, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ <b>{user['first_name']}</b> admin!", parse_mode="HTML")
    try:
        await bot.send_message(uid, "🎉 <b>Siz admin!</b>\n\n/admin", parse_mode="HTML")
    except Exception:
        pass
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_admin_list")
async def del_admin_list(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        return
    admins = list_admins()
    b = InlineKeyboardBuilder()
    for a in admins:
        if a["user_id"] in SUPER_ADMIN_IDS:
            continue
        u = get_user(a["user_id"])
        name = u["first_name"] if u else "N/A"
        b.button(text=f"❌ {name}", callback_data=f"deladmin_{a['user_id']}")
    b.button(text="⬅️", callback_data="a_admins")
    b.adjust(1)
    await cb.message.edit_text("🗑", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("deladmin_"))
async def del_admin_do(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("deladmin_", ""))
    if uid in SUPER_ADMIN_IDS:
        await cb.answer("❌", show_alert=True)
        return
    remove_admin(uid)
    await cb.answer("✅")
    await a_admins(cb)

# ═══════════════════════════════════════════════════════════
# HEALTH + POLLING
# ═══════════════════════════════════════════════════════════
async def health(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health portda: {PORT}")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling...")
    asyncio.create_task(start_web())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
