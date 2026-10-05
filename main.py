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
        "chat_active": "💬 <b>Suhbat faol</b>\n\nXabaringizni yozing. Tugatish uchun «🔚 Suhbatni tugatish» tugmasini bosing.",
        "chat_closed_by_user": "🔚 <b>Suhbat tugatildi!</b>\n\nYangi savol berish uchun «💬 Admin bilan aloqa» tugmasini bosing.",
        "chat_closed_by_admin": "🔚 <b>Admin suhbatni tugatdi.</b>\n\nYangi savol berish uchun «💬 Admin bilan aloqa» tugmasini bosing.",
        "chat_closed_admin_side": "🔚 <b>Suhbat tugatildi!</b>",
        "no_active_chat": "ℹ️ Sizda faol suhbat yo'q.",
        "admin_reply": "📬 <b>Admindan javob:</b>",
        "user_msg": "📩 <b>Foydalanuvchidan xabar:</b>",
    },
    "ru": {
        "flag": "🇷🇺", "name": "Русский",
        "choose_lang": "🌐 <b>Выберите язык</b>\n\nПожалуйста, выберите удобный для вас язык:",
        "lang_set": "✅ Язык успешно изменён!",
        "welcome": "👋 <b>Привет, {name}!</b>\n\n🎯 <i>Добро пожаловать в реферальный бот!</i>\n\nВыберите нужный раздел из меню 👇",
        "menu_title": "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        "profile": "👤 Профиль",
        "ref_link": "🔗 Реферальная ссылка",
        "rating": "🏆 Рейтинг",
        "withdraw": "💰 Вывод",
        "support": "💬 Связь с админом",
        "admin": "🛠 Админ панель",
        "share": "📤 Поделиться ссылкой",
        "back": "⬅️ Назад",
        "menu": "🏠 Главное меню",
        "cancel": "❌ Отмена",
        "close_chat": "🔚 Завершить чат",
        "banned": "🚫 <b>Вы забанены!</b>\n\nСвяжитесь с админом.",
        "subscribe": "📢 <b>Подпишитесь на каналы:</b>\n\nПосле подписки нажмите «✅ Проверить».",
        "check": "✅ Проверить",
        "bot_check": "🤖 <b>Подтвердите, что вы не бот</b>\n\n❓ <b>Вопрос:</b> {q}\n\nВыберите правильный ответ 👇",
        "wrong_answer": "❌ Неправильный ответ!",
        "correct": "✅ Подтверждено!",
        "wrong_ans_retry": "❌ <b>Неправильно!</b>\n\nПопробуйте снова: /start",
        "start_first": "ℹ️ Напишите /start",
        "not_enough": "❌ <b>Недостаточно!</b>",
        "min_withdraw": "❌ Минимум: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Максимум: <b>{n} ⭐</b>",
        "enter_number": "❌ Только число.",
        "choose_reward": "🎁 Выберите тип награды:",
        "stars_withdraw": "⭐ Получить Stars",
        "gift_withdraw": "🎁 Получить Telegram Gift",
        "stars_title": "⭐ <b>Вывод Stars</b>\n\n💰 У вас: <b>{bal} ⭐</b>\n📉 Мин: {min} ⭐\n📈 Макс: {max} ⭐\n\n💬 Сколько вывести?\nВведите число:",
        "gift_title": "🎁 <b>Telegram Gift</b>\n\n💰 У вас: <b>{bal} ⭐</b>\n\n👇 Выберите gift:",
        "sent_to_admin": "✅ <b>Запрос отправлен!</b>\n\n⭐ Сумма: <b>{n} ⭐</b>\n⏳ Ожидайте подтверждения...",
        "gift_sent": "✅ <b>Запрос отправлен!</b>\n\n🎁 Gift: <b>{gift}</b>\n⭐ Цена: <b>{n} ⭐</b>\n⏳ Ожидайте подтверждения...",
        "approved": "✅ <b>Ваш запрос подтверждён!</b>",
        "rejected": "❌ <b>Ваш запрос отклонён.</b>",
        "referral_reward": "🎉 <b>Новый реферал!</b>\n\n➕ +{n} ⭐ добавлено",
        "total": "Всего",
        "balance": "У вас",
        "need": "Нужно",
        "stars_added": "🎁 <b>Вам добавлены stars!</b>\n\n➕ Сумма: <b>+{n} ⭐</b>\n📝 Причина: <i>{reason}</i>\n\n💰 Всего: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>У вас списаны stars!</b>\n\n➖ Сумма: <b>{n} ⭐</b>\n📝 Причина: <i>{reason}</i>\n\n💰 Всего: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Связь с админом</b>\n\nНапишите ваш вопрос — админ скоро ответит.\n\nМожно отправить текст, фото, видео или файл.",
        "support_sent": "✅ <b>Ваш вопрос отправлен админу!</b>\n\n⏳ Ожидайте ответа...",
        "support_new_msg": "📩 <b>Новое сообщение!</b>\n\n👤 <b>User:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Время:</b> {time}",
        "reply_sent": "✅ <b>Ответ отправлен!</b>",
        "chat_active": "💬 <b>Чат активен</b>\n\nНапишите сообщение. Для завершения нажмите «🔚 Завершить чат».",
        "chat_closed_by_user": "🔚 <b>Чат завершён!</b>\n\nДля нового вопроса нажмите «💬 Связь с админом».",
        "chat_closed_by_admin": "🔚 <b>Админ завершил чат.</b>\n\nДля нового вопроса нажмите «💬 Связь с админом».",
        "chat_closed_admin_side": "🔚 <b>Чат завершён!</b>",
        "no_active_chat": "ℹ️ У вас нет активного чата.",
        "admin_reply": "📬 <b>Ответ от админа:</b>",
        "user_msg": "📩 <b>Сообщение от пользователя:</b>",
    },
    "en": {
        "flag": "🇬🇧", "name": "English",
        "choose_lang": "🌐 <b>Choose language</b>\n\nPlease select your preferred language:",
        "lang_set": "✅ Language changed successfully!",
        "welcome": "👋 <b>Hi, {name}!</b>\n\n🎯 <i>Welcome to the referral bot!</i>\n\nChoose a section from the menu below 👇",
        "menu_title": "🏠 <b>Main menu</b>\n\nChoose a section:",
        "profile": "👤 Profile",
        "ref_link": "🔗 Referral link",
        "rating": "🏆 Rating",
        "withdraw": "💰 Withdraw",
        "support": "💬 Contact admin",
        "admin": "🛠 Admin Panel",
        "share": "📤 Share link",
        "back": "⬅️ Back",
        "menu": "🏠 Main menu",
        "cancel": "❌ Cancel",
        "close_chat": "🔚 Close chat",
        "banned": "🚫 <b>You are banned!</b>\n\nContact admin.",
        "subscribe": "📢 <b>Subscribe to channels:</b>\n\nAfter subscribing, press «✅ Check».",
        "check": "✅ Check",
        "bot_check": "🤖 <b>Confirm you are not a bot</b>\n\n❓ <b>Question:</b> {q}\n\nChoose the correct answer 👇",
        "wrong_answer": "❌ Wrong answer!",
        "correct": "✅ Confirmed!",
        "wrong_ans_retry": "❌ <b>Wrong!</b>\n\nTry again: /start",
        "start_first": "ℹ️ Please send /start",
        "not_enough": "❌ <b>Not enough!</b>",
        "min_withdraw": "❌ Minimum: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Maximum: <b>{n} ⭐</b>",
        "enter_number": "❌ Numbers only.",
        "choose_reward": "🎁 Choose reward type:",
        "stars_withdraw": "⭐ Get Stars",
        "gift_withdraw": "🎁 Get Telegram Gift",
        "stars_title": "⭐ <b>Withdraw Stars</b>\n\n💰 You have: <b>{bal} ⭐</b>\n📉 Min: {min} ⭐\n📈 Max: {max} ⭐\n\n💬 How many to withdraw?\nEnter number:",
        "gift_title": "🎁 <b>Telegram Gift</b>\n\n💰 You have: <b>{bal} ⭐</b>\n\n👇 Choose gift:",
        "sent_to_admin": "✅ <b>Request sent!</b>\n\n⭐ Amount: <b>{n} ⭐</b>\n⏳ Wait for approval...",
        "gift_sent": "✅ <b>Request sent!</b>\n\n🎁 Gift: <b>{gift}</b>\n⭐ Price: <b>{n} ⭐</b>\n⏳ Wait for approval...",
        "approved": "✅ <b>Your request approved!</b>",
        "rejected": "❌ <b>Your request rejected.</b>",
        "referral_reward": "🎉 <b>New referral!</b>\n\n➕ +{n} ⭐ added",
        "total": "Total",
        "balance": "You have",
        "need": "Need",
        "stars_added": "🎁 <b>Stars added!</b>\n\n➕ Amount: <b>+{n} ⭐</b>\n📝 Reason: <i>{reason}</i>\n\n💰 Total: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Stars removed!</b>\n\n➖ Amount: <b>{n} ⭐</b>\n📝 Reason: <i>{reason}</i>\n\n💰 Total: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Contact admin</b>\n\nWrite your question — admin will reply soon.\n\nYou can send text, photo, video or file.",
        "support_sent": "✅ <b>Your question sent to admin!</b>\n\n⏳ Wait for reply...",
        "support_new_msg": "📩 <b>New message!</b>\n\n👤 <b>User:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Time:</b> {time}",
        "reply_sent": "✅ <b>Reply sent!</b>",
        "chat_active": "💬 <b>Chat active</b>\n\nSend your message. To finish, press «🔚 Close chat».",
        "chat_closed_by_user": "🔚 <b>Chat closed!</b>\n\nFor a new question press «💬 Contact admin».",
        "chat_closed_by_admin": "🔚 <b>Admin closed the chat.</b>\n\nFor a new question press «💬 Contact admin».",
        "chat_closed_admin_side": "🔚 <b>Chat closed!</b>",
        "no_active_chat": "ℹ️ You have no active chat.",
        "admin_reply": "📬 <b>Reply from admin:</b>",
        "user_msg": "📩 <b>Message from user:</b>",
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
    # Yangilangan support tizimi — status bilan
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
    defaults = {
        "stars_per_referral": "2",
        "min_withdraw": "50",
        "max_withdraw": "1000000",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    for a in SUPER_ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                  (a, a, datetime.now().isoformat()))

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

# ═══════════════════════════════════════════════════════════
# SUPPORT CHAT (yangi)
# ═══════════════════════════════════════════════════════════
def get_chat_status(user_id):
    """Suhbat holatini olish: 'open' | 'closed_by_user' | 'closed_by_admin' | None"""
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
    """Foydalanuvchi suhbatini butunlay o'chirish"""
    db_exec("DELETE FROM support_tickets WHERE user_id=?", (user_id,))
    db_exec("DELETE FROM support_chats WHERE user_id=?", (user_id,))

def get_chat_users():
    """Faol suhbatli foydalanuvchilar ro'yxati"""
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
    b.button(text=T(lang, "support"), callback_data="m_support")
    b.button(text="🌐 Til / Язык / Lang", callback_data="m_lang")
    if is_admin(uid):
        b.button(text=T(lang, "admin"), callback_data="m_admin")
    b.adjust(2, 2, 2, 1)
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
    text = (
        f"╭━━━〔 👤 <b>{T(lang, 'profile')}</b> 〕━━━╮\n\n"
        f"🆔 <b>ID:</b> <code>{user['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {user['first_name'] or 'N/A'}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"⭐ <b>Stars:</b> {user['stars']}\n"
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
    share_url = f"https://t.me/share/url?url={link}&text=🚀 Botga qo'shiling va stars yig'ing!"
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
# SUPPORT (yangi — suhbat holati bilan)
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

    # Eski suhbatni tekshirish
    chat_status = get_chat_status(uid)
    if chat_status == "open":
        # Suhbat allaqachon ochiq
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "close_chat"), callback_data="chat_close_user")
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
        try:
            await cb.message.edit_text(
                T(lang, "chat_active"),
                reply_markup=b.as_markup(),
                parse_mode="HTML"
            )
        except Exception:
            await cb.message.answer(
                T(lang, "chat_active"),
                reply_markup=b.as_markup(),
                parse_mode="HTML"
            )
        await state.set_state(US.support_msg)
        await cb.answer()
        return

    # Yangi suhbat ochish
    open_chat(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "close_chat"), callback_data="chat_close_user")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(
            T(lang, "support_title"),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "support_title"),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    await state.set_state(US.support_msg)
    await cb.answer()

@dp.callback_query(F.data == "chat_close_user")
async def chat_close_user(cb: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi suhbatni yopadi"""
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)

    if not is_chat_open(uid):
        await cb.answer(T(lang, "no_active_chat"), show_alert=True)
        return

    close_chat(uid, closed_by="user")

    # Adminga xabar
    user = get_user(uid)
    uname = f"@{user['username']}" if user and user["username"] else "—"
    for a in list_admins():
        try:
            await bot.send_message(
                a["user_id"],
                f"🔚 <b>Suhbat foydalanuvchi tomonidan tugatildi!</b>\n\n"
                f"👤 <b>User:</b> {user['first_name'] if user else 'User'}\n"
                f"🔗 <b>Username:</b> {uname}\n"
                f"🆔 <b>ID:</b> <code>{uid}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        await cb.message.edit_text(
            T(lang, "chat_closed_by_user"),
            reply_markup=back_to_menu_kb(uid),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "chat_closed_by_user"),
            reply_markup=back_to_menu_kb(uid),
            parse_mode="HTML"
        )
    await cb.answer("✅")

@dp.message(US.support_msg)
async def support_send(message: types.Message, state: FSMContext):
    """Foydalanuvchi xabarini adminga yuborish"""
    uid = message.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await message.answer(T(lang, "start_first"))
        return

    # Suhbat ochiqmi?
    if not is_chat_open(uid):
        await state.clear()
        await message.answer(
            T(lang, "chat_closed_by_admin"),
            reply_markup=back_to_menu_kb(uid),
            parse_mode="HTML"
        )
        return

    # Xabar turi aniqlash
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
    elif message.animation:
        msg_type, content = "animation", message.animation.file_id
    else:
        await message.answer("❌ Bu turdagi xabar qo'llab-quvvatlanmaydi.")
        return

    save_support_msg(uid, 0, msg_type, content, 0)

    # Adminga xabar
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
            await bot.send_message(
                a["user_id"], admin_header,
                reply_markup=kb.as_markup(), parse_mode="HTML"
            )
            await message.forward(a["user_id"])
            sent += 1
        except Exception as e:
            logger.warning(f"Adminga yuborishda xato ({a['user_id']}): {e}")

    if sent == 0:
        await message.answer("⚠️ Hech qanday admin topilmadi.")
        return

    # Foydalanuvchiga tasdiq
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "close_chat"), callback_data="chat_close_user")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    await message.answer(T(lang, "support_sent"), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
# ADMIN JAVOB BERISH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    uid = int(cb.data.replace("reply_", ""))
    user = get_user(uid)
    if not user:
        await cb.answer("❌ User topilmadi!", show_alert=True)
        return

    # Suhbat ochiqmi?
    if not is_chat_open(uid):
        await cb.answer("⚠️ Bu suhbat allaqachon yopilgan!", show_alert=True)
        return

    await state.update_data(reply_to_uid=uid)
    await cb.message.answer(
        f"✉️ <b>Javob yozing</b>\n\n"
        f"👤 {user['first_name']} (<code>{uid}</code>)\n\n"
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

    # Suhbat ochiqmi?
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
        await bot.send_message(
            uid,
            T(u_lang, "admin_reply"),
            parse_mode="HTML"
        )
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

# ═══════════════════════════════════════════════════════════
# ADMIN SUHBATNI YOPISH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("chat_close_admin_"))
async def chat_close_admin(cb: types.CallbackQuery):
    """Admin suhbatni yopadi"""
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    uid = int(cb.data.replace("chat_close_admin_", ""))
    user = get_user(uid)

    if not is_chat_open(uid):
        await cb.answer("⚠️ Suhbat allaqachon yopilgan!", show_alert=True)
        return

    close_chat(uid, closed_by="admin")

    u_lang = get_user_lang(uid)
    # Foydalanuvchiga xabar
    try:
        await bot.send_message(
            uid,
            T(u_lang, "chat_closed_by_admin"),
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n🔚 <b>SUHBAT TUGATILDI</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await cb.answer("✅ Suhbat tugatildi")

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

    min_w = int(get_setting("min_withdraw", "50"))
    if user["stars"] < min_w:
        await cb.answer(
            f"{T(lang, 'not_enough')}\n📉 Min: {min_w} ⭐\n💰 {T(lang, 'balance')}: {user['stars']} ⭐",
            show_alert=True
        )
        return

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "stars_withdraw"), callback_data="w_stars")
    b.button(text=T(lang, "gift_withdraw"), callback_data="w_gift")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)

    try:
        await cb.message.edit_text(
            f"╭━━━〔 💰 <b>{T(lang, 'withdraw')}</b> 〕━━━╮\n\n"
            f"⭐ <b>Sizda:</b> {user['stars']} ⭐\n\n"
            f"{T(lang, 'choose_reward')}\n\n"
            f"╰━━━━━━━━━━━━━━━━━╯",
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            f"╭━━━〔 💰 <b>{T(lang, 'withdraw')}</b> 〕━━━╮\n\n"
            f"⭐ <b>Sizda:</b> {user['stars']} ⭐\n\n"
            f"{T(lang, 'choose_reward')}\n\n"
            f"╰━━━━━━━━━━━━━━━━━╯",
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
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

    try:
        await cb.message.edit_text(
            T(lang, "stars_title", bal=user["stars"], min=min_w, max=f"{max_w:,}"),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        await cb.message.answer(
            T(lang, "stars_title", bal=user["stars"], min=min_w, max=f"{max_w:,}"),
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
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
    await message.answer(
        T(lang, "menu_title"),
        reply_markup=main_menu(uid),
        parse_mode="HTML"
    )

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

    text = T(lang, "gift_title", bal=user["stars"]) + "\n\n"
    b = InlineKeyboardBuilder()
    for g in gifts:
        text += f"{g['emoji']} <b>{g['name']}</b> — {g['stars']} ⭐\n"
        b.button(
            text=f"{g['emoji']} {g['name']} — {g['stars']}⭐",
            callback_data=f"gift_{g['key']}"
        )
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

    try:
        await cb.message.edit_text(
            f"╭━━━〔 💰 <b>{T(lang, 'withdraw')}</b> 〕━━━╮\n\n"
            f"⭐ <b>Sizda:</b> {user['stars']} ⭐\n\n"
            f"{T(lang, 'choose_reward')}\n\n"
            f"╰━━━━━━━━━━━━━━━━━╯",
            reply_markup=b.as_markup(),
            parse_mode="HTML"
        )
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
            f"{T(lang, 'not_enough')}\n{T(lang, 'need')}: {gift['stars']} ⭐\n{T(lang, 'balance')}: {user['stars']} ⭐",
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
        "📢 <b>Kanal username kiriting</b>\n\n"
        "Misol: <code>@mychannel</code> yoki <code>mychannel</code>",
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
    await message.answer("✅ <b>To'g'ri javobni kiriting:</b>", parse_mode="HTML")
    await state.set_state(AS.q_correct)

@dp.message(AS.q_correct)
async def add_q_correct(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_correct=message.text.strip())
    await message.answer("❌ <b>1-xato javobni kiriting:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong1)

@dp.message(AS.q_wrong1)
async def add_q_wrong1(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_wrong1=message.text.strip())
    await message.answer("❌ <b>2-xato javobni kiriting:</b>", parse_mode="HTML")
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
        text += f"{g['emoji']} <b>{g['name']}</b> — {g['stars']} ⭐ (<code>{g['key']}</code>)\n"
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
    await cb.message.edit_text(
        "🎁 <b>Gift kalit so'zini kiriting</b>\n\n"
        "Misol: <code>star_gift</code>, <code>unicorn</code>",
        parse_mode="HTML"
    )
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
        await message.answer("❌ Bu kalit allaqachon bor.")
        return
    await state.update_data(gift_key=key)
    await message.answer("😀 <b>Emoji kiriting:</b>", parse_mode="HTML")
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
        await message.answer("📝 <b>Yangi nomini kiriting (yoki /skip):</b>", parse_mode="HTML")
        await state.set_state(AS.gift_name)
    else:
        await state.update_data(gift_emoji=message.text.strip())
        await message.answer("📝 <b>Gift nomini kiriting:</b>", parse_mode="HTML")
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
        await message.answer("⭐ <b>Yangi narxni kiriting (yoki /skip):</b>", parse_mode="HTML")
        await state.set_state(AS.gift_stars)
    else:
        await state.update_data(gift_name=message.text.strip())
        await message.answer("⭐ <b>Stars narxini kiriting:</b>", parse_mode="HTML")
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
                await message.answer("❌ Raqam kiriting.")
                return
        await state.clear()
        await message.answer("✅ <b>Tahrirlandi!</b>", parse_mode="HTML")
        await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))
    else:
        try:
            stars = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Raqam kiriting.")
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
        f"Yangi emojini kiriting (yoki /skip):",
        parse_mode="HTML"
    )
    await state.set_state(AS.gift_emoji)
    await cb.answer()

# ---------- Sozlamalar ----------
@dp.callback_query(F.data == "a_settings")
async def a_settings(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    text = (
        f"╭━━━〔 ⚙️ <b>SOZLAMALAR</b> 〕━━━╮\n\n"
        f"🎯 1 referal = <b>{get_setting('stars_per_referral')} ⭐</b>\n"
        f"💰 Min yechish = <b>{get_setting('min_withdraw')} ⭐</b>\n"
        f"💎 Max yechish = <b>{get_setting('max_withdraw')} ⭐</b>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal stars", callback_data="set_ref")
    b.button(text="💰 Min yechish", callback_data="set_minw")
    b.button(text="💎 Max yechish", callback_data="set_maxw")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.in_({"set_ref", "set_minw", "set_maxw"}))
async def set_val_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    mapping = {
        "set_ref": ("stars_per_referral", "🎯 <b>1 referal uchun nechta stars?</b>"),
        "set_minw": ("min_withdraw", "💰 <b>Minimal yechish (stars):</b>"),
        "set_maxw": ("max_withdraw", "💎 <b>Maksimal yechish (stars):</b>"),
    }
    key, prompt = mapping[cb.data]
    await state.update_data(setting_key=key)
    await cb.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(AS.setting_val)
    await cb.answer()

@dp.message(AS.setting_val)
async def set_val_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
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
    susp = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_suspicious=1", fetch=True)["c"]
    pend = db_exec("SELECT COUNT(*) AS c FROM withdrawals WHERE status='pending'", fetch=True)["c"]
    total_stars = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM users", fetch=True)["s"]
    open_chats = db_exec("SELECT COUNT(*) AS c FROM support_chats WHERE status='open'", fetch=True)["c"]
    text = (
        f"╭━━━〔 📊 <b>STATISTIKA</b> 〕━━━╮\n\n"
        f"👥 <b>Jami:</b> {total}\n"
        f"✅ <b>Tasdiqlangan:</b> {ver}\n"
        f"🚫 <b>Ban:</b> {ban}\n"
        f"⚠️ <b>Shubhali:</b> {susp}\n"
        f"💸 <b>Pending:</b> {pend}\n"
        f"⭐ <b>Jami stars:</b> {total_stars}\n"
        f"💬 <b>Faol suhbatlar:</b> {open_chats}\n\n"
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
        "📨 <b>Broadcast</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring:\n\n"
        "✅ Oddiy matn\n"
        "✅ Rasm / Video / Fayl\n"
        "✅ Forward qilingan xabar\n"
        "✅ Albom (bir nechta rasm)\n\n"
        "<i>Barcha turdagi xabarlar avtomatik aniqlanadi.</i>",
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
    has_media = bool(
        message.photo or message.video or message.document or
        message.audio or message.voice or message.sticker or
        message.animation or message.video_note
    )
    is_poll = bool(message.poll)
    is_location = bool(message.location or message.venue)
    is_contact = bool(message.contact)

    for i, u in enumerate(users, 1):
        try:
            if is_forward:
                await bot.forward_message(
                    chat_id=u["user_id"],
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
            elif is_poll or is_location or is_contact:
                await message.copy_to(chat_id=u["user_id"])
            elif has_media:
                await message.copy_to(chat_id=u["user_id"])
            else:
                await message.copy_to(chat_id=u["user_id"])
            ok += 1
        except TelegramForbiddenError:
            blocked += 1
            fail += 1
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "blocked" in err or "chat not found" in err or "initiate" in err:
                blocked += 1
            else:
                logger.warning(f"Xato ({u['user_id']}): {e}")
            fail += 1
        except Exception as e:
            logger.warning(f"Xato ({u['user_id']}): {e}")
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

# ---------- Yechib olish ----------
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
    text = "╭━━━〔 💸 <b>PENDING SO'ROVLAR</b> 〕━━━╮\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        if r["reward_type"] == "gift":
            g = get_gift(r["gift_key"]) or {}
            info = f"{g.get('emoji', '🎁')} {g.get('name', 'Gift')} ({r['stars']}⭐)"
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
                T(u_lang, "approved") + f"\n\n⭐ <b>{w['stars']} ⭐</b>\n\n<i>To'lovni qabul qiling!</i>",
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
        if w["reward_type"] == "gift":
            g = get_gift(w["gift_key"]) or {}
            info = f"{g.get('emoji', '🎁')} {g.get('name', 'Gift')}"
        else:
            info = f"{w['stars']} ⭐"
        await bot.send_message(
            w["user_id"],
            T(u_lang, "rejected") + f"\n\n{info}",
            parse_mode="HTML"
        )
    except Exception:
        pass

# ---------- Suhbatlar (yangi) ----------
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
        # Holat belgisi
        status_icon = "🟢" if c["status"] == "open" else "🔴"
        status_text = c["status"].replace("closed_by_", "closed: ")
        text += f"{status_icon} {c['first_name'] or 'User'} ({uname})\n  <code>{c['user_id']}</code> — {status_text}\n\n"
        b.button(
            text=f"💬 {c['first_name'] or 'User'}",
            callback_data=f"chat_open_{c['user_id']}"
        )
        b.button(
            text=f"🗑 O'chirish",
            callback_data=f"chat_del_{c['user_id']}"
        )
    text += "╰━━━━━━━━━━━━━━━━━╯"
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("chat_open_"))
async def chat_open(cb: types.CallbackQuery):
    """Admin suhbatni ochadi va javob yozishi mumkin"""
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("chat_open_", ""))
    user = get_user(uid)
    if not user:
        await cb.answer("❌ User topilmadi!", show_alert=True)
        return

    # Suhbat ochiqmi?
    if not is_chat_open(uid):
        # Qayta ochish
        open_chat(uid)
        u_lang = get_user_lang(uid)
        try:
            await bot.send_message(
                uid,
                "🔄 <b>Admin suhbatni qayta ochdi.</b>\n\nYozishingiz mumkin.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    # Suhbat tarixini ko'rsatish
    rows = db_exec(
        "SELECT * FROM support_tickets WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (uid,), fetchall=True
    ) or []
    history = f"╭━━━〔 💬 <b>SUHBAT TARIXI</b> 〕━━━╮\n\n"
    history += f"👤 <b>{user['first_name']}</b> (<code>{uid}</code>)\n\n"
    for r in reversed(rows):
        who = "👑 Admin" if r["is_from_admin"] else "👤 User"
        content = r["content"]
        if r["message_type"] != "text":
            content = f"[{r['message_type']}]"
        elif len(content) > 100:
            content = content[:100] + "..."
        history += f"{who}: {content}\n"
    history += "\n╰━━━━━━━━━━━━━━━━━╯"

    b = InlineKeyboardBuilder()
    b.button(text="✉️ Javob berish", callback_data=f"reply_{uid}")
    b.button(text="🔚 Suhbatni tugatish", callback_data=f"chat_close_admin_{uid}")
    b.button(text="🗑 Suhbatni o'chirish", callback_data=f"chat_del_{uid}")
    b.button(text="⬅️ Orqaga", callback_data="a_chats")
    b.adjust(1)

    try:
        await cb.message.edit_text(history, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(history, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("chat_del_"))
async def chat_del(cb: types.CallbackQuery):
    """Admin suhbatni butunlay o'chiradi"""
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("chat_del_", ""))
    delete_chat(uid)
    await cb.answer("✅ Suhbat o'chirildi!")
    try:
        await cb.message.edit_text(
            "✅ <b>Suhbat butunlay o'chirildi!</b>\n\n"
            "Foydalanuvchi qaytadan yozishi mumkin.",
            reply_markup=InlineKeyboardBuilder().button(
                text="⬅️ Orqaga", callback_data="a_chats"
            ).as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass

# ---------- User boshqarish ----------
@dp.callback_query(F.data == "a_users")
async def a_users(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "👤 <b>Foydalanuvchi ID sini kiriting:</b>",
        parse_mode="HTML"
    )
    await state.set_state(AS.user_id)
    await cb.answer()

@dp.message(AS.user_id)
async def user_info(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    user = get_user(uid)
    if not user:
        await message.answer("❌ Topilmadi.")
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(
        text="🚫 Ban" if not user["is_banned"] else "✅ Unban",
        callback_data=f"tog_{uid}"
    )
    b.button(text="➕ Stars qo'shish", callback_data=f"adp_{uid}")
    b.button(text="➖ Stars ayirish", callback_data=f"rem_{uid}")
    b.button(text="✉️ Xabar yuborish", callback_data=f"msg_{uid}")
    b.button(text="💬 Suhbat", callback_data=f"chat_open_{uid}")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 1, 1)
    uname = f"@{user['username']}" if user["username"] else "—"
    ban_text = "Ha" if user["is_banned"] else "Yo'q"
    ver_text = "Ha" if user["is_verified"] else "Yo'q"
    text = (
        f"╭━━━〔 👤 <b>USER INFO</b> 〕━━━╮\n\n"
        f"🆔 <b>ID:</b> <code>{user['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {user['first_name']}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"⭐ <b>Stars:</b> {user['stars']}\n"
        f"🚫 <b>Ban:</b> {ban_text}\n"
        f"✅ <b>Tasdiqlangan:</b> {ver_text}\n"
        f"🌐 <b>Til:</b> {user.get('language', 'uz')}\n\n"
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

# ---------- Stars qo'shish/ayirish ----------
@dp.callback_query(F.data.startswith("adp_"))
async def add_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("adp_", ""))
    await state.update_data(target_uid=uid, action="add")
    await cb.message.edit_text(
        "➕ <b>Qancha stars qo'shilsin?</b>\n\n"
        "Faqat raqam kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(AS.stars_amount)
    await cb.answer()

@dp.callback_query(F.data.startswith("rem_"))
async def remove_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("rem_", ""))
    await state.update_data(target_uid=uid, action="remove")
    await cb.message.edit_text(
        "➖ <b>Qancha stars ayirilsin?</b>\n\n"
        "Faqat raqam kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(AS.stars_amount)
    await cb.answer()

@dp.message(AS.stars_amount)
async def stars_amount_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return
    if amount <= 0:
        await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak.")
        return
    data = await state.get_data()
    action = data.get("action", "add")
    await state.update_data(stars_amount=amount)
    prompt = (
        "📝 <b>Sababni kiriting:</b>\n\n"
        "Masalan: <i>«Referal bonusi»</i>, <i>«Admin sovg'asi»</i>"
        if action == "add"
        else
        "📝 <b>Ayirish sababini kiriting:</b>\n\n"
        "Masalan: <i>«Qoidabuzarlik»</i>, <i>«Xato»</i>"
    )
    await message.answer(prompt, parse_mode="HTML")
    await state.set_state(AS.stars_reason)

@dp.message(AS.stars_reason)
async def stars_reason_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    reason = message.text.strip()
    if not reason:
        await message.answer("❌ Sabab bo'sh bo'lmasligi kerak.")
        return

    data = await state.get_data()
    uid = data["target_uid"]
    amount = data["stars_amount"]
    action = data.get("action", "add")

    user = get_user(uid)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()
        return

    if action == "add":
        new_stars = user["stars"] + amount
    else:
        if amount > user["stars"]:
            await message.answer(
                f"❌ Foydalanuvchida faqat <b>{user['stars']} ⭐</b> bor.\n"
                f"Ayirish mumkin emas.",
                parse_mode="HTML"
            )
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
    except Exception as e:
        logger.warning(f"Xabar yuborishda xato: {e}")

    sign = "➕" if action == "add" else "➖"
    await message.answer(
        f"✅ <b>Bajarildi!</b>\n\n"
        f"{sign} <b>{amount} ⭐</b>\n"
        f"📝 <i>{reason}</i>\n"
        f"💰 Yangi balans: <b>{new_stars} ⭐</b>",
        parse_mode="HTML"
    )
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("msg_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("✉️ <b>Yubormoqchi bo'lgan xabaringizni yozing:</b>", parse_mode="HTML")
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
    b.button(text="➕ Qo'shish", callback_data="add_admin")
    b.button(text="➖ O'chirish", callback_data="del_admin_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👑 <b>Admin ID sini kiriting:</b>", parse_mode="HTML")
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
        await message.answer("❌ User topilmadi.")
        return
    if uid in SUPER_ADMIN_IDS:
        await message.answer("❌ Super admin.")
        return
    add_admin(uid, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ <b>{user['first_name']}</b> admin qilindi!", parse_mode="HTML")
    try:
        await bot.send_message(uid, "🎉 <b>Siz admin etib tayinlandingiz!</b>\n\n/admin buyrug'ini yuboring.", parse_mode="HTML")
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
        b.button(text=f"❌ {name} ({a['user_id']})", callback_data=f"deladmin_{a['user_id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_admins")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
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
