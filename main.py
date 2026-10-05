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
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web

# ==================== SOZLAMALAR ====================
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

# ==================== TILLAR ====================
LANGS = {
    "uz": {
        "flag": "🇺🇿", "name": "O'zbekcha",
        "welcome": "Salom, {name}! 👋\n\nAsosiy menyu:",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til O'zbekchaga o'zgartirildi!",
        "profile": "👤 Profilim",
        "ref_link": "🔗 Referal linkim",
        "rating": "🏆 Reyting",
        "withdraw": "💰 Yechib olish",
        "admin": "🛠 Admin Panel",
        "share": "📤 Havolani ulashish",
        "back": "⬅️ Orqaga",
        "cancel": "❌ Bekor qilish",
        "banned": "❌ Siz banlangansiz.",
        "subscribe": "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        "check": "✅ Tekshirish",
        "bot_check": "🤖 Iltimos, bot emasligingizni tasdiqlang:\n\n❓ {q}",
        "wrong_answer": "❌ Noto'g'ri javob!",
        "correct": "✅ Tasdiqlandi!",
        "wrong_ans_retry": "❌ Noto'g'ri javob. Qaytadan: /start",
        "start_first": "Iltimos, /start buyrug'ini bosing.",
        "not_enough": "❌ Yetarli emas!",
        "min_withdraw": "❌ Minimal: {n} ⭐",
        "max_withdraw": "❌ Maksimal: {n} ⭐",
        "enter_number": "❌ Faqat raqam kiriting.",
        "choose_reward": "Mukofot turini tanlang:",
        "stars_withdraw": "⭐ To'liq Stars olish",
        "gift_withdraw": "🎁 Telegram Gift olish",
        "stars_title": "⭐ <b>Stars yechib olish</b>\n\nSizda: <b>{bal} ⭐</b>\nMin: {min} ⭐\nMax: {max} ⭐\n\nNechta stars yechib olmoqchisiz?\nRaqamni kiriting:",
        "gift_title": "🎁 <b>Telegram Gift olish</b>\n\nSizda: <b>{bal} ⭐</b>\n\nGiftni tanlang:",
        "sent_to_admin": "✅ <b>{n} ⭐</b> yechib olish so'rovi yuborildi.\nAdmin tasdiqlashini kuting.",
        "gift_sent": "✅ <b>{gift}</b> ({n}⭐) so'rovingiz yuborildi.\n\nAdmin tasdiqlashini kuting.",
        "approved": "✅ Tasdiqlandi!",
        "rejected": "❌ Rad etildi!",
        "referral_reward": "🎉 Yangi referal! +{n} ⭐",
        "total": "Jami",
        "hello": "Salom",
        "user": "Foydalanuvchi",
        "balance": "Sizda",
        "need": "Kerak",
    },
    "ru": {
        "flag": "🇷🇺", "name": "Русский",
        "welcome": "Привет, {name}! 👋\n\nГлавное меню:",
        "choose_lang": "🌐 Выберите язык:",
        "lang_set": "✅ Язык изменён на Русский!",
        "profile": "👤 Профиль",
        "ref_link": "🔗 Реферальная ссылка",
        "rating": "🏆 Рейтинг",
        "withdraw": "💰 Вывод",
        "admin": "🛠 Админ панель",
        "share": "📤 Поделиться ссылкой",
        "back": "⬅️ Назад",
        "cancel": "❌ Отмена",
        "banned": "❌ Вы забанены.",
        "subscribe": "⚠️ Подпишитесь на каналы:",
        "check": "✅ Проверить",
        "bot_check": "🤖 Подтвердите, что вы не бот:\n\n❓ {q}",
        "wrong_answer": "❌ Неправильный ответ!",
        "correct": "✅ Подтверждено!",
        "wrong_ans_retry": "❌ Неправильно. Заново: /start",
        "start_first": "Напишите /start",
        "not_enough": "❌ Недостаточно!",
        "min_withdraw": "❌ Минимум: {n} ⭐",
        "max_withdraw": "❌ Максимум: {n} ⭐",
        "enter_number": "❌ Только число.",
        "choose_reward": "Выберите тип награды:",
        "stars_withdraw": "⭐ Получить Stars",
        "gift_withdraw": "🎁 Получить Telegram Gift",
        "stars_title": "⭐ <b>Вывод Stars</b>\n\nУ вас: <b>{bal} ⭐</b>\nМин: {min} ⭐\nМакс: {max} ⭐\n\nСколько stars вывести?\nВведите число:",
        "gift_title": "🎁 <b>Telegram Gift</b>\n\nУ вас: <b>{bal} ⭐</b>\n\nВыберите gift:",
        "sent_to_admin": "✅ Запрос на <b>{n} ⭐</b> отправлен.\nОжидайте подтверждения.",
        "gift_sent": "✅ Запрос на <b>{gift}</b> ({n}⭐) отправлен.",
        "approved": "✅ Подтверждено!",
        "rejected": "❌ Отклонено!",
        "referral_reward": "🎉 Новый реферал! +{n} ⭐",
        "total": "Всего",
        "hello": "Привет",
        "user": "Пользователь",
        "balance": "У вас",
        "need": "Нужно",
    },
    "en": {
        "flag": "🇬🇧", "name": "English",
        "welcome": "Hi, {name}! 👋\n\nMain menu:",
        "choose_lang": "🌐 Choose language:",
        "lang_set": "✅ Language changed to English!",
        "profile": "👤 Profile",
        "ref_link": "🔗 Referral link",
        "rating": "🏆 Rating",
        "withdraw": "💰 Withdraw",
        "admin": "🛠 Admin Panel",
        "share": "📤 Share link",
        "back": "⬅️ Back",
        "cancel": "❌ Cancel",
        "banned": "❌ You are banned.",
        "subscribe": "⚠️ Subscribe to channels:",
        "check": "✅ Check",
        "bot_check": "🤖 Please confirm you are not a bot:\n\n❓ {q}",
        "wrong_answer": "❌ Wrong answer!",
        "correct": "✅ Confirmed!",
        "wrong_ans_retry": "❌ Wrong. Try again: /start",
        "start_first": "Please send /start",
        "not_enough": "❌ Not enough!",
        "min_withdraw": "❌ Minimum: {n} ⭐",
        "max_withdraw": "❌ Maximum: {n} ⭐",
        "enter_number": "❌ Numbers only.",
        "choose_reward": "Choose reward type:",
        "stars_withdraw": "⭐ Get Stars",
        "gift_withdraw": "🎁 Get Telegram Gift",
        "stars_title": "⭐ <b>Withdraw Stars</b>\n\nYou have: <b>{bal} ⭐</b>\nMin: {min} ⭐\nMax: {max} ⭐\n\nHow many stars to withdraw?\nEnter number:",
        "gift_title": "🎁 <b>Telegram Gift</b>\n\nYou have: <b>{bal} ⭐</b>\n\nChoose gift:",
        "sent_to_admin": "✅ Request for <b>{n} ⭐</b> sent.\nWait for admin approval.",
        "gift_sent": "✅ Request for <b>{gift}</b> ({n}⭐) sent.",
        "approved": "✅ Approved!",
        "rejected": "❌ Rejected!",
        "referral_reward": "🎉 New referral! +{n} ⭐",
        "total": "Total",
        "hello": "Hello",
        "user": "User",
        "balance": "You have",
        "need": "Need",
    },
}

def T(lang, key, **kwargs):
    lang = lang if lang in LANGS else "uz"
    text = LANGS[lang].get(key, LANGS["uz"].get(key, key))
    try:
        return text.format(**kwargs)
    except Exception:
        return text

# ==================== DB ====================
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

# ==================== BOT ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class US(StatesGroup):
    answer = State()
    withdraw_stars = State()

class AS(StatesGroup):
    channel = State()
    q_text = State()
    q_correct = State()
    q_wrong1 = State()
    q_wrong2 = State()
    broadcast = State()
    setting_val = State()
    user_id = State()
    stars_val = State()
    user_msg = State()
    add_admin_id = State()
    gift_key = State()
    gift_emoji = State()
    gift_name = State()
    gift_stars = State()

# ==================== KLAVIATURALAR ====================
def main_menu(uid):
    lang = get_user_lang(uid)
    b = ReplyKeyboardBuilder()
    b.button(text=T(lang, "profile"))
    b.button(text=T(lang, "ref_link"))
    b.button(text=T(lang, "rating"))
    b.button(text=T(lang, "withdraw"))
    b.button(text="🌐 Til / Язык / Lang")
    if is_admin(uid):
        b.button(text=T(lang, "admin"))
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)

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
    if is_super_admin(uid):
        b.button(text="👑 Adminlar", callback_data="a_admins")
    b.adjust(2)
    return b.as_markup()

def lang_keyboard():
    b = InlineKeyboardBuilder()
    for code, info in LANGS.items():
        b.button(text=f"{info['flag']} {info['name']}", callback_data=f"lang_{code}")
    b.adjust(1)
    return b.as_markup()

# ==================== OBUNA ====================
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

# ==================== /start ====================
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
            "🌐 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=lang_keyboard()
        )
        return

    lang = get_user_lang(uid)

    if user["is_banned"]:
        await message.answer(T(lang, "banned"))
        return

    if not await check_subs(uid):
        kb = await subs_kb(uid)
        await message.answer(T(lang, "subscribe"), reply_markup=kb)
        return

    if user["is_verified"]:
        await message.answer(
            T(lang, "welcome", name=fname),
            reply_markup=main_menu(uid)
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await message.answer(
            T(lang, "welcome", name=fname),
            reply_markup=main_menu(uid)
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
        reply_markup=b.as_markup()
    )

# ==================== TIL CALLBACK ====================
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
        await cb.message.answer(T(lang, "banned"))
        return

    if not await check_subs(uid):
        kb = await subs_kb(uid)
        await cb.message.answer(T(lang, "subscribe"), reply_markup=kb)
        return

    if user["is_verified"]:
        await cb.message.answer(
            T(lang, "welcome", name=user["first_name"] or "User"),
            reply_markup=main_menu(uid)
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await cb.message.answer(
            T(lang, "welcome", name=user["first_name"] or "User"),
            reply_markup=main_menu(uid)
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
        reply_markup=b.as_markup()
    )

# ==================== SAVOLGA JAVOB ====================
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
        await cb.message.answer(T(lang, "wrong_ans_retry"))
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
                    T(ref_lang, "referral_reward", n=reward) + f"\n{T(ref_lang, 'total')}: {ref['stars'] + reward} ⭐"
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
        reply_markup=main_menu(uid)
    )

# ==================== OBUNA CALLBACK ====================
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
            reply_markup=main_menu(uid)
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await cb.message.answer(T(lang, "welcome", name=user["first_name"] or "User"),
                                reply_markup=main_menu(uid))
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
        reply_markup=b.as_markup()
    )

# ==================== TIL TUGMASI ====================
@dp.message(F.text == "🌐 Til / Язык / Lang")
async def lang_menu(message: types.Message):
    await message.answer("🌐 Tilni tanlang / Выберите язык / Choose language:",
                         reply_markup=lang_keyboard())

# ==================== MENYU ====================
@dp.message(F.text.in_({LANGS[c]["profile"] for c in LANGS}))
async def profile(message: types.Message):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await message.answer(T(lang, "start_first"))
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
        f"👤 <b>{T(lang, 'profile')}</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 {user['first_name'] or 'N/A'}\n"
        f"🔗 {uname}\n"
        f"⭐ Stars: <b>{user['stars']}</b>\n"
        f"👥 Referallar: {ref_count}\n"
        f"{ver}\n"
        f"📅 {joined}"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text.in_({LANGS[c]["ref_link"] for c in LANGS}))
async def ref_link(message: types.Message):
    uid = message.from_user.id
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
        f"🔗 <b>{T(lang, 'ref_link')}</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 {ref_count}\n"
        f"⭐ {user['stars'] if user else 0}\n\n"
        f"+{reward} ⭐ / referral"
    )
    share_url = f"https://t.me/share/url?url={link}&text=Botga qo'shiling!"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "share"), url=share_url)
    await message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())

@dp.message(F.text.in_({LANGS[c]["rating"] for c in LANGS}))
async def leaderboard(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    rows = db_exec(
        "SELECT first_name, stars FROM users WHERE is_verified=1 AND is_banned=0 ORDER BY stars DESC LIMIT 10",
        fetchall=True
    )
    text = f"🏆 <b>{T(lang, 'rating')}</b>\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {r['first_name'] or 'N/A'} — {r['stars']} ⭐\n"
    else:
        text += "—"
    await message.answer(text, parse_mode="HTML")

# ==================== YECHIB OLISH ====================
@dp.message(F.text.in_({LANGS[c]["withdraw"] for c in LANGS}))
async def withdraw_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await message.answer(T(lang, "start_first"))
        return

    min_w = int(get_setting("min_withdraw", "50"))
    if user["stars"] < min_w:
        await message.answer(
            f"{T(lang, 'not_enough')}\n"
            f"Min: {min_w} ⭐\n"
            f"{T(lang, 'balance')}: {user['stars']} ⭐"
        )
        return

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "stars_withdraw"), callback_data="w_stars")
    b.button(text=T(lang, "gift_withdraw"), callback_data="w_gift")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)

    await message.answer(
        f"💰 <b>{T(lang, 'withdraw')}</b>\n\n"
        f"⭐ {user['stars']}\n\n"
        f"{T(lang, 'choose_reward')}",
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "w_cancel")
async def w_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer("OK")

# ========== STARS ==========
@dp.callback_query(F.data == "w_stars")
async def w_stars(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    min_w = int(get_setting("min_withdraw", "50"))
    max_w = int(get_setting("max_withdraw", "1000000"))

    await cb.message.edit_text(
        T(lang, "stars_title", bal=user["stars"], min=min_w, max=f"{max_w:,}"),
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
        await message.answer(T(lang, "min_withdraw", n=min_w))
        return
    if amount > max_w:
        await message.answer(T(lang, "max_withdraw", n=f"{max_w:,}"))
        return

    user = get_user(uid)
    if amount > user["stars"]:
        await message.answer(
            f"{T(lang, 'not_enough')}\n"
            f"{T(lang, 'balance')}: {user['stars']} ⭐\n"
            f"{T(lang, 'need')}: {amount} ⭐"
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

    uname = f"@{user['username']}" if user["username"] else "—"
    admin_text = (
        f"💸 <b>Yangi STARS so'rovi!</b>\n\n"
        f"🆔 So'rov: <code>#{w_id}</code>\n"
        f"👤 {user['first_name']} (<code>{uid}</code>)\n"
        f"🔗 Username: {uname}\n"
        f"⭐ Miqdor: <b>{amount} stars</b>"
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

# ========== GIFT ==========
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
        text += f"{g['emoji']} {g['name']} — {g['stars']} ⭐\n"
        b.button(
            text=f"{g['emoji']} {g['name']} — {g['stars']}⭐",
            callback_data=f"gift_{g['key']}"
        )
    b.button(text=T(lang, "back"), callback_data="w_back")
    b.adjust(1)

    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
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

    await cb.message.edit_text(
        f"💰 <b>{T(lang, 'withdraw')}</b>\n\n"
        f"⭐ {user['stars']}\n\n"
        f"{T(lang, 'choose_reward')}",
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )
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
    await cb.message.edit_text(
        T(lang, "gift_sent", gift=f"{gift['emoji']} {gift['name']}", n=gift["stars"]),
        parse_mode="HTML"
    )
    await cb.answer("✅")

    uname = f"@{user['username']}" if user["username"] else "—"
    admin_text = (
        f"🎁 <b>Yangi GIFT so'rovi!</b>\n\n"
        f"🆔 So'rov: <code>#{w_id}</code>\n"
        f"👤 {user['first_name']} (<code>{uid}</code>)\n"
        f"🔗 Username: {uname}\n"
        f"🎁 Gift: {gift['emoji']} <b>{gift['name']}</b>\n"
        f"⭐ Narx: <b>{gift['stars']} stars</b>"
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

# ==================== ADMIN PANEL ====================
@dp.message(Command("admin"))
@dp.message(F.text.in_({LANGS[c]["admin"] for c in LANGS}))
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌")
        return
    await state.clear()
    await message.answer("🛠 <b>Admin Panel</b>",
                         reply_markup=admin_menu(message.from_user.id),
                         parse_mode="HTML")

@dp.callback_query(F.data == "a_back")
async def a_back(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text("🛠 <b>Admin Panel</b>",
                               reply_markup=admin_menu(cb.from_user.id),
                               parse_mode="HTML")
    await cb.answer()

# ---------- Kanallar ----------
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    text = "📢 <b>Kanallar:</b>\n\n"
    text += "\n".join([f"• {ch}" for ch in channels]) if channels else "—"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_ch")
    b.button(text="➖ O'chirish", callback_data="del_ch_list")
    b.button(text="⬅️", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_ch")
async def add_ch_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📢 Kanal username (@mychannel):")
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
    await message.answer(f"✅ {ch}")
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

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
    b.button(text="⬅️", callback_data="a_channels")
    b.adjust(1)
    await cb.message.edit_text("O'chirish:", reply_markup=b.as_markup())
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
    text = "❓ <b>Savollar:</b>\n\n"
    if qs:
        for q in qs:
            text += f"• {q['question']}\n  ✅ {q['correct_answer']}\n  ❌ {q['wrong1']} | {q['wrong2']}\n\n"
    else:
        text += "—"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_q")
    b.button(text="➖ O'chirish", callback_data="del_q_list")
    b.button(text="⬅️", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_q")
async def add_q_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("❓ Savolni kiriting:")
    await state.set_state(AS.q_text)
    await cb.answer()

@dp.message(AS.q_text)
async def add_q_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_text=message.text.strip())
    await message.answer("✅ To'g'ri javobni kiriting:")
    await state.set_state(AS.q_correct)

@dp.message(AS.q_correct)
async def add_q_correct(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_correct=message.text.strip())
    await message.answer("❌ 1-xato javobni kiriting:")
    await state.set_state(AS.q_wrong1)

@dp.message(AS.q_wrong1)
async def add_q_wrong1(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(q_wrong1=message.text.strip())
    await message.answer("❌ 2-xato javobni kiriting:")
    await state.set_state(AS.q_wrong2)

@dp.message(AS.q_wrong2)
async def add_q_wrong2(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    add_question(data["q_text"], data["q_correct"], data["q_wrong1"], message.text.strip())
    await state.clear()
    await message.answer("✅ Savol qo'shildi!")
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

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
    b.button(text="⬅️", callback_data="a_questions")
    b.adjust(1)
    await cb.message.edit_text("O'chirish:", reply_markup=b.as_markup())
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
    text = "🎁 <b>Giftlar:</b>\n\n"
    for g in gifts:
        text += f"{g['emoji']} <b>{g['name']}</b> — {g['stars']} ⭐ (<code>{g['key']}</code>)\n"
    if not gifts:
        text += "—"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_gift")
    b.button(text="✏️ Tahrirlash", callback_data="edit_gift_list")
    b.button(text="➖ O'chirish", callback_data="del_gift_list")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_gift")
async def add_gift_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "🎁 Gift <b>kalit so'zini</b> kiriting (lotin, bo'sh joysiz):\n\n"
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
    await message.answer("😀 Emoji kiriting:")
    await state.set_state(AS.gift_emoji)

@dp.message(AS.gift_emoji)
async def gift_emoji_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(gift_emoji=message.text.strip())
    await message.answer("📝 Gift nomini kiriting:")
    await state.set_state(AS.gift_name)

@dp.message(AS.gift_name)
async def gift_name_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(gift_name=message.text.strip())
    await message.answer("⭐ Stars narxini kiriting (raqam):")
    await state.set_state(AS.gift_stars)

@dp.message(AS.gift_stars)
async def gift_stars_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        stars = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return
    if stars < 1:
        await message.answer("❌ Kamida 1.")
        return
    data = await state.get_data()
    add_gift(data["gift_key"], data["gift_emoji"], data["gift_name"], stars)
    await state.clear()
    await message.answer("✅ Gift qo'shildi!")
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

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
    b.button(text="⬅️", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("O'chirish:", reply_markup=b.as_markup())
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
    b.button(text="⬅️", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("Tahrirlash:", reply_markup=b.as_markup())
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
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🎯 1 referal = {get_setting('stars_per_referral')} ⭐\n"
        f"💰 Min yechish = {get_setting('min_withdraw')} ⭐\n"
        f"💎 Max yechish = {get_setting('max_withdraw')} ⭐"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal stars", callback_data="set_ref")
    b.button(text="💰 Min yechish", callback_data="set_minw")
    b.button(text="💎 Max yechish", callback_data="set_maxw")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.in_({"set_ref", "set_minw", "set_maxw"}))
async def set_val_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    mapping = {
        "set_ref": ("stars_per_referral", "🎯 1 referal uchun nechta stars?"),
        "set_minw": ("min_withdraw", "💰 Minimal yechish (stars):"),
        "set_maxw": ("max_withdraw", "💎 Maksimal yechish (stars):"),
    }
    key, prompt = mapping[cb.data]
    await state.update_data(setting_key=key)
    await cb.message.edit_text(prompt)
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
    await message.answer(f"✅ {data['setting_key']} = {val}")
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

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
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami: {total}\n"
        f"✅ Tasdiqlangan: {ver}\n"
        f"🚫 Ban: {ban}\n"
        f"⚠️ Shubhali: {susp}\n"
        f"💸 Pending: {pend}\n"
        f"⭐ Jami stars: {total_stars}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# ---------- Broadcast ----------
@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📨 Xabarni yuboring:")
    await state.set_state(AS.broadcast)
    await cb.answer()

@dp.message(AS.broadcast)
async def broadcast_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users = db_exec("SELECT user_id FROM users WHERE is_banned=0", fetchall=True) or []
    ok = fail = 0
    for u in users:
        try:
            await message.copy_to(chat_id=u["user_id"])
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await message.answer(f"📨 ✅ {ok} / ❌ {fail}")
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

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
    text = "💸 <b>Pending:</b>\n\n"
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
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2)
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
        await cb.message.edit_text(cb.message.html_text + "\n\n✅ <b>TASDIQLANGAN</b>", parse_mode="HTML")
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
            await bot.send_message(w["user_id"], T(u_lang, "approved") + f"\n{w['stars']} ⭐")
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
            T(u_lang, "approved") + f"\n{g.get('emoji', '🎁')} {g.get('name', 'Gift')}"
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
        await cb.message.edit_text(cb.message.html_text + "\n\n❌ <b>RAD ETILGAN</b>", parse_mode="HTML")
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
        await bot.send_message(w["user_id"], T(u_lang, "rejected") + f"\n{info}")
    except Exception:
        pass

# ---------- User boshqarish ----------
@dp.callback_query(F.data == "a_users")
async def a_users(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👤 User ID sini kiriting:")
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
        await message.answer("❌")
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Ban" if not user["is_banned"] else "✅ Unban", callback_data=f"tog_{uid}")
    b.button(text="➕ Stars", callback_data=f"adp_{uid}")
    b.button(text="✉️ Xabar", callback_data=f"msg_{uid}")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2)
    uname = f"@{user['username']}" if user["username"] else "—"
    ban_text = "Ha" if user["is_banned"] else "Yo'q"
    ver_text = "Ha" if user["is_verified"] else "Yo'q"
    text = (
        f"👤 <b>User:</b>\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Ism: {user['first_name']}\n"
        f"Username: {uname}\n"
        f"⭐ {user['stars']}\n"
        f"Ban: {ban_text}\n"
        f"Ver: {ver_text}\n"
        f"Til: {user.get('language', 'uz')}"
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
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("➕ Qancha stars? (manfiy ham mumkin)")
    await state.set_state(AS.stars_val)
    await cb.answer()

@dp.message(AS.stars_val)
async def add_stars_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌")
        return
    data = await state.get_data()
    uid = data["target_uid"]
    user = get_user(uid)
    if not user:
        await message.answer("❌")
        return
    new_stars = max(0, user["stars"] + amount)
    update_user(uid, stars=new_stars)
    await state.clear()
    await message.answer(f"✅ Yangi: {new_stars} ⭐")
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("msg_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("✉️ Xabar:")
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
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

# ---------- Adminlar ----------
@dp.callback_query(F.data == "a_admins")
async def a_admins(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    admins = list_admins()
    text = "👑 <b>Adminlar:</b>\n\n"
    for a in admins:
        u = get_user(a["user_id"])
        name = u["first_name"] if u else "N/A"
        tag = " (SUPER)" if a["user_id"] in SUPER_ADMIN_IDS else ""
        text += f"• {name} — <code>{a['user_id']}</code>{tag}\n"
    b = InlineKeyboardBuilder()
    b.button(text="➕", callback_data="add_admin")
    b.button(text="➖", callback_data="del_admin_list")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👑 Admin ID:")
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
    await message.answer(f"✅ {user['first_name']} admin!")
    try:
        await bot.send_message(uid, "🎉 Siz admin! /admin")
    except Exception:
        pass
    await message.answer("🛠 Admin", reply_markup=admin_menu(message.from_user.id))

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
    b.button(text="⬅️", callback_data="a_admins")
    b.adjust(1)
    await cb.message.edit_text("O'chirish:", reply_markup=b.as_markup())
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

# ==================== HEALTH + POLLING ====================
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
