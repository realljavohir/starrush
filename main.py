import os
import io
import re
import html
import hmac
import time
import json
import asyncio
import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    BufferedInputFile, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web

from telethon import TelegramClient, functions, types as tt
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

# ═══════════════════════════════════════════════════════════
# SOZLAMALAR
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SUPER_ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
DATABASE_URL = os.environ.get("DATABASE_URL", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
PORT = int(os.environ.get("PORT", 8080))

API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
tg_client = None
gift_lock = asyncio.Lock()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN o'rnatilmagan!")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL o'rnatilmagan!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

UZ_TZ = timezone(timedelta(hours=5))

def now_uz():
    return datetime.now(UZ_TZ).replace(tzinfo=None)

BOT_NAME = "StarRush Bot"
BOT_USERNAME = "StarRushUZBot"

MIN_STARS = 50
MAX_STARS = 1_000_000
UZ_PHONE_RE = re.compile(r"^998\d{9}$")

# ═══════════════════════════════════════════════════════════
# DARAJALAR
# ═══════════════════════════════════════════════════════════
DEFAULT_LEVELS = [
    {"name": "Bronza",  "emoji": "🥉", "min_stars": 0,   "max_stars": 10},
    {"name": "Kumush",  "emoji": "🥈", "min_stars": 11,  "max_stars": 50},
    {"name": "Oltin",   "emoji": "🥇", "min_stars": 51,  "max_stars": 200},
    {"name": "Platina", "emoji": "💎", "min_stars": 201, "max_stars": 500},
    {"name": "Olmos",   "emoji": "👑", "min_stars": 501, "max_stars": 999999999},
]

def get_levels():
    rows = db_exec("SELECT * FROM levels ORDER BY min_stars ASC", fetchall=True)
    return [dict(r) for r in rows] if rows else DEFAULT_LEVELS

def get_user_level(stars):
    levels = get_levels()
    for lvl in levels:
        if lvl["min_stars"] <= stars <= lvl["max_stars"]:
            return lvl
    best = None
    for lvl in levels:
        if lvl["min_stars"] <= stars:
            best = lvl
    return best or (levels[0] if levels else DEFAULT_LEVELS[0])

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
        "stats": "📊 Statistika",
        "banner": "🎨 Banner",
        "webapp": "🚀 Mini App",
        "ref_link": "🔗 Referal linkim",
        "rating": "🏆 Reyting",
        "withdraw": "💰 Yechib olish",
        "donate": "💝 Donat qilish",
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
        "sent_to_admin": "✅ <b>So'rov yuborildi!</b>\n\n⭐ Miqdor: <b>{n} ⭐</b>\n⏳ Admin tasdiqlashini kuting...",
        "gift_processing": "⏳ <b>Gift yuborilmoqda...</b>\n\n{gift} — <b>{n} ⭐</b>",
        "gift_done": "🎉 <b>Gift yuborildi!</b>\n\n{gift}\n⭐ Narx: <b>{n} ⭐</b>\n\n🎁 Telegram profilingizni tekshiring!",
        "gift_failed": "⚠️ <b>Giftni yuborib bo'lmadi.</b>\n\n{gift}\n\n💰 <b>{n} ⭐</b> balansingizga qaytarildi. Birozdan so'ng qayta urinib ko'ring.",
        "gift_ask_anon": "{gift} — <b>{n} ⭐</b>\n\n🕶 Gift <b>anonim</b> yuborilsinmi?",
        "gift_anon_yes": "🕶 Anonim",
        "gift_anon_no": "👤 Ismim ko'rinsin",
        "gift_ask_comment": "💬 <b>Gift ostiga qanday izoh yozilsin?</b>\n\nMatn yuboring (maks. 120 belgi) yoki «Izohsiz» ni bosing.",
        "gift_no_comment": "➡️ Izohsiz",
        "approved": "✅ <b>So'rovingiz tasdiqlandi!</b>",
        "rejected": "❌ <b>So'rovingiz rad etildi.</b>",
        "referral_reward": "🎉 <b>Yangi referal!</b>\n\n➕ +{n} ⭐ qo'shildi",
        "total": "Jami",
        "balance": "Sizda",
        "need": "Kerak",
        "stars_added": "🎁 <b>Sizga stars qo'shildi!</b>\n\n➕ Miqdor: <b>+{n} ⭐</b>\n📝 Sabab: <i>{reason}</i>\n\n💰 Jami: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Sizdan stars ayirildi!</b>\n\n➖ Miqdor: <b>{n} ⭐</b>\n📝 Sabab: <i>{reason}</i>\n\n💰 Jami: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Admin bilan aloqa</b>\n\nSavolingizni yozing — admin tez orada javob beradi.",
        "support_sent": "✅ <b>Savolingiz adminga yuborildi!</b>",
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
        "review_sent": "✅ <b>Sharhingiz yuborildi!</b>",
        "review_approved": "✅ <b>Sharhingiz tasdiqlandi!</b>",
        "review_rejected": "❌ <b>Sharhingiz rad etildi.</b>",
        "level": "Daraja",
        "stars_will_send": "✅ <b>So'rovingiz tasdiqlandi!</b>\n\n⭐ Miqdor: <b>{n} ⭐</b>\n\n<i>Admin tez orada sizga Stars yuboradi!</i>",
        "level_up": "🎉 <b>TABRIKLAYMIZ!</b>\n\nSiz {emoji} <b>{name}</b> darajasiga chiqdingiz!\n\n⬆️ Keyingi: {next_emoji} <b>{next_name}</b>\n📊 Kerak: <b>{need} ⭐</b>",
        "banner_caption": "🎨 <b>Sizning shaxsiy baneringiz</b>",
        "ask_phone": "📱 <b>Telefon raqamingizni tasdiqlang</b>\n\nFaqat 🇺🇿 <b>+998</b> raqamlari qabul qilinadi.\nPastdagi tugmani bosing 👇",
        "share_phone": "📱 Raqamni yuborish",
        "phone_not_own": "❌ Faqat o'zingizning raqamingizni yuboring.",
        "phone_only_uz": "❌ Faqat O'zbekiston raqamlari (+998 XX XXX XX XX).",
        "phone_used": "❌ Bu raqam boshqa akkauntga bog'langan.",
        "phone_use_button": "ℹ️ Iltimos, pastdagi «📱 Raqamni yuborish» tugmasidan foydalaning.",
        "donate_title": "💝 <b>Donat qilish</b>\n\nDonat — botni qo'llab-quvvatlash. Donatingiz maxsus donat reytingida ko'rinadi!\n\n💰 Sizda: <b>{bal} ⭐</b>\n\nNechta star donat qilasiz? (min 1)",
        "donate_ok": "💝 <b>Rahmat!</b>\n\nSiz <b>{n} ⭐</b> donat qildingiz!\n\n🏆 Donat reytingida ko'rinasiz!",
        "rating_choose": "🏆 <b>Reyting</b>\n\nQaysi reytingni ko'rmoqchisiz?",
        "rating_stars": "⭐ Eng ko'p stars egalari",
        "rating_donate": "💝 Eng ko'p donat qilganlar",
        "rating_ref": "👥 Eng ko'p referal yig'ganlar",
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
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(1, 10, DATABASE_URL)
    return _pool

def db_exec(query, params=(), fetch=False, fetchall=False):
    pool = _get_pool()
    conn = pool.getconn()
    broken = False
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute(query.replace("?", "%s"), params)
            if fetch:
                return c.fetchone()
            if fetchall:
                return c.fetchall()
            return None
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    finally:
        pool.putconn(conn, close=broken)


def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language TEXT DEFAULT 'uz',
        stars INTEGER DEFAULT 0,
        referrer_id BIGINT DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        is_suspicious INTEGER DEFAULT 0,
        joined_at TEXT
    )""")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")

    c.execute("""CREATE TABLE IF NOT EXISTS channels (
        id SERIAL PRIMARY KEY,
        channel_username TEXT UNIQUE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id SERIAL PRIMARY KEY,
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
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        stars INTEGER,
        reward_type TEXT,
        gift_key TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    c.execute("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS is_anon INTEGER DEFAULT 0")
    c.execute("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS comment TEXT")
    c.execute("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS error TEXT")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins (
        user_id BIGINT PRIMARY KEY,
        added_by BIGINT,
        added_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        admin_id BIGINT,
        message_type TEXT,
        content TEXT,
        is_from_admin INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS support_chats (
        user_id BIGINT PRIMARY KEY,
        status TEXT DEFAULT 'open',
        admin_id BIGINT DEFAULT 0,
        updated_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        text TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS levels (
        id SERIAL PRIMARY KEY,
        name TEXT,
        emoji TEXT,
        min_stars INTEGER,
        max_stars INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS donations (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        stars INTEGER,
        status TEXT DEFAULT 'received',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS games (
        id SERIAL PRIMARY KEY,
        title TEXT,
        metric TEXT,
        starts_at TEXT,
        ends_at TEXT,
        prize INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )""")

    defaults = {
        "stars_per_referral": "2",
        "min_withdraw": "50",
        "max_withdraw": "1000000",
        "review_channel": "",
    }
    for k, v in defaults.items():
        c.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v))

    for a in SUPER_ADMIN_IDS:
        c.execute("""INSERT INTO admins (user_id, added_by, added_at)
                     VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING""",
                  (a, a, now_uz().isoformat()))

    c.execute("SELECT COUNT(*) FROM levels")
    if c.fetchone()[0] == 0:
        for lvl in DEFAULT_LEVELS:
            c.execute("INSERT INTO levels (name, emoji, min_stars, max_stars) VALUES (%s, %s, %s, %s)",
                      (lvl["name"], lvl["emoji"], lvl["min_stars"], lvl["max_stars"]))

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
            c.execute("""INSERT INTO gifts (key, emoji, name, stars)
                         VALUES (%s, %s, %s, %s) ON CONFLICT (key) DO NOTHING""",
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
                        VALUES (%s, %s, %s, %s)""", (q, correct, w1, w2))

    c.close()
    conn.close()
    logger.info("PostgreSQL DB tayyor")

# ═══════════════════════════════════════════════════════════
# YORDAMCHI
# ═══════════════════════════════════════════════════════════
def get_setting(key, default=None):
    row = db_exec("SELECT value FROM settings WHERE key=%s", (key,), fetch=True)
    return row["value"] if row else default

def set_setting(key, value):
    db_exec("""INSERT INTO settings (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
            (key, str(value)))

def _clean_user(row):
    if not row:
        return None
    d = dict(row)
    for k in ("first_name", "last_name", "username"):
        if d.get(k):
            d[k] = html.escape(d[k])
    return d

def get_user(user_id):
    row = db_exec("SELECT * FROM users WHERE user_id=%s", (user_id,), fetch=True)
    return _clean_user(row)

def get_user_by_username(username):
    uname = username.lstrip("@").lower()
    row = db_exec("SELECT * FROM users WHERE LOWER(username)=%s", (uname,), fetch=True)
    return _clean_user(row)

def get_user_lang(user_id):
    row = db_exec("SELECT language FROM users WHERE user_id=%s", (user_id,), fetch=True)
    return row["language"] if row and row.get("language") in LANGS else "uz"

def update_user(user_id, **kwargs):
    if not kwargs:
        return
    fields = ", ".join([f"{k}=%s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    db_exec(f"UPDATE users SET {fields} WHERE user_id=%s", values)

def create_user(user_id, username, first_name, last_name, referrer_id=0):
    db_exec("""INSERT INTO users
        (user_id, username, first_name, last_name, referrer_id, joined_at)
        VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING""",
        (user_id, username, first_name, last_name, referrer_id, now_uz().isoformat()))

def spend_stars(user_id, n):
    row = db_exec(
        "UPDATE users SET stars = stars - %s WHERE user_id=%s AND stars >= %s RETURNING stars",
        (n, user_id, n), fetch=True)
    return row["stars"] if row else None

def add_stars(user_id, n):
    row = db_exec(
        "UPDATE users SET stars = stars + %s WHERE user_id=%s RETURNING stars",
        (n, user_id), fetch=True)
    return row["stars"] if row else None

def pending_total(user_id):
    row = db_exec(
        "SELECT COALESCE(SUM(stars), 0) AS s FROM withdrawals WHERE user_id=%s AND status='pending'",
        (user_id,), fetch=True)
    return int(row["s"]) if row else 0

def total_donated(user_id):
    row = db_exec(
        "SELECT COALESCE(SUM(stars), 0) AS s FROM donations WHERE user_id=%s",
        (user_id,), fetch=True)
    return int(row["s"]) if row else 0

def bot_donate_balance():
    row = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM donations", fetch=True)
    return int(row["s"]) if row else 0

def is_admin(user_id):
    if user_id in SUPER_ADMIN_IDS:
        return True
    row = db_exec("SELECT 1 FROM admins WHERE user_id=%s", (user_id,), fetch=True)
    return row is not None

def is_super_admin(user_id):
    return user_id in SUPER_ADMIN_IDS

def add_admin(user_id, added_by):
    db_exec("""INSERT INTO admins (user_id, added_by, added_at) VALUES (%s, %s, %s)
               ON CONFLICT (user_id) DO NOTHING""",
            (user_id, added_by, now_uz().isoformat()))

def remove_admin(user_id):
    db_exec("DELETE FROM admins WHERE user_id=%s", (user_id,))

def list_admins():
    rows = db_exec("SELECT * FROM admins", fetchall=True)
    return [dict(r) for r in rows] if rows else []

def get_channels():
    rows = db_exec("SELECT channel_username FROM channels", fetchall=True)
    return [r["channel_username"] for r in rows] if rows else []

def add_channel(ch):
    db_exec("INSERT INTO channels (channel_username) VALUES (%s) ON CONFLICT DO NOTHING", (ch,))

def remove_channel(ch):
    db_exec("DELETE FROM channels WHERE channel_username=%s", (ch,))

def get_random_question():
    row = db_exec("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1", fetch=True)
    return dict(row) if row else None

def add_question(q, correct, wrong1, wrong2):
    db_exec("""INSERT INTO questions (question, correct_answer, wrong1, wrong2)
               VALUES (%s, %s, %s, %s)""", (q, correct, wrong1, wrong2))

def remove_question(q_id):
    db_exec("DELETE FROM questions WHERE id=%s", (q_id,))

def get_questions():
    rows = db_exec("SELECT * FROM questions ORDER BY id", fetchall=True)
    return [dict(r) for r in rows] if rows else []

def get_all_gifts():
    rows = db_exec("SELECT * FROM gifts ORDER BY stars", fetchall=True)
    return [dict(r) for r in rows] if rows else []

def get_gift(key):
    row = db_exec("SELECT * FROM gifts WHERE key=%s", (key,), fetch=True)
    return dict(row) if row else None

def add_gift(key, emoji, name, stars):
    db_exec("""INSERT INTO gifts (key, emoji, name, stars) VALUES (%s, %s, %s, %s)
               ON CONFLICT (key) DO UPDATE SET emoji=EXCLUDED.emoji, name=EXCLUDED.name, stars=EXCLUDED.stars""",
            (key, emoji, name, stars))

def remove_gift(key):
    db_exec("DELETE FROM gifts WHERE key=%s", (key,))

def get_chat_status(user_id):
    row = db_exec("SELECT status FROM support_chats WHERE user_id=%s", (user_id,), fetch=True)
    return row["status"] if row else None

def open_chat(user_id):
    db_exec("""INSERT INTO support_chats (user_id, status, admin_id, updated_at)
               VALUES (%s, 'open', 0, %s)
               ON CONFLICT (user_id) DO UPDATE SET status='open', updated_at=EXCLUDED.updated_at""",
            (user_id, now_uz().isoformat()))

def close_chat(user_id, closed_by="user"):
    status = f"closed_by_{closed_by}"
    db_exec("UPDATE support_chats SET status=%s, updated_at=%s WHERE user_id=%s",
            (status, now_uz().isoformat(), user_id))

def is_chat_open(user_id):
    return get_chat_status(user_id) == "open"

def save_support_msg(user_id, admin_id, msg_type, content, is_from_admin):
    db_exec("""INSERT INTO support_tickets (user_id, admin_id, message_type, content, is_from_admin, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, admin_id, msg_type, content, is_from_admin, now_uz().isoformat()))

def delete_chat(user_id):
    db_exec("DELETE FROM support_tickets WHERE user_id=%s", (user_id,))
    db_exec("DELETE FROM support_chats WHERE user_id=%s", (user_id,))

def get_chat_users():
    rows = db_exec(
        "SELECT sc.user_id, sc.status, sc.updated_at, u.first_name, u.username "
        "FROM support_chats sc LEFT JOIN users u ON sc.user_id=u.user_id "
        "ORDER BY sc.updated_at DESC",
        fetchall=True
    )
    return [dict(r) for r in rows] if rows else []

def esc(s):
    return html.escape(str(s)) if s is not None else ""

# ═══════════════════════════════════════════════════════════
# BOT
# ═══════════════════════════════════════════════════════════
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class US(StatesGroup):
    phone = State()
    answer = State()
    withdraw_stars = State()
    support_msg = State()
    gift_username = State()
    gift_amount = State()
    review_text = State()
    gift_comment = State()
    donate_amount = State()

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
    userbot_api = State()
    userbot_hash = State()
    userbot_session = State()

# ═══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════════════
def main_menu(uid):
    lang = get_user_lang(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "profile"), callback_data="m_profile")
    b.button(text=T(lang, "stats"), callback_data="m_stats")
    b.button(text=T(lang, "banner"), callback_data="m_banner")
    b.button(text=T(lang, "ref_link"), callback_data="m_reflink")
    b.button(text=T(lang, "rating"), callback_data="m_rating")
    b.button(text=T(lang, "donate"), callback_data="m_donate")
    b.button(text=T(lang, "withdraw"), callback_data="m_withdraw")
    b.button(text=T(lang, "gift_stars"), callback_data="m_gift")
    b.button(text=T(lang, "review"), callback_data="m_review")
    b.button(text=T(lang, "support"), callback_data="m_support")

    if WEBAPP_URL:
        b.button(text=T(lang, "webapp"), web_app=WebAppInfo(url=WEBAPP_URL))

    b.button(text="🌐 Til / Язык / Lang", callback_data="m_lang")
    if is_admin(uid):
        b.button(text=T(lang, "admin"), callback_data="m_admin")
    b.adjust(2, 2, 2, 2, 2, 1)
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
    b.button(text="🤖 Userbot", callback_data="a_userbot")
    b.button(text="💝 Donatlar", callback_data="a_donations")
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
# HUMAN CHECK
# ═══════════════════════════════════════════════════════════
async def send_human_check(target: types.Message, state: FSMContext, uid: int, lang: str, user: dict):
    if not user.get("phone"):
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=T(lang, "share_phone"), request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await state.set_state(US.phone)
        await target.answer(T(lang, "ask_phone"), reply_markup=kb, parse_mode="HTML")
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await target.answer(
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

    await state.update_data(q_id=q["id"], ref_id=user["referrer_id"] or 0)
    await state.set_state(US.answer)
    await target.answer(
        T(lang, "bot_check", q=esc(q["question"])),
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )


@dp.message(US.phone, F.contact)
async def phone_received(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    c = message.contact

    if c.user_id != uid:
        await message.answer(T(lang, "phone_not_own"))
        return

    phone = re.sub(r"\D", "", c.phone_number or "")
    if not UZ_PHONE_RE.match(phone):
        await message.answer(T(lang, "phone_only_uz"))
        return

    if db_exec("SELECT 1 FROM users WHERE phone=%s AND user_id<>%s", (phone, uid), fetch=True):
        await message.answer(T(lang, "phone_used"))
        return

    update_user(uid, phone=phone)
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    user = get_user(uid)
    await send_human_check(message, state, uid, lang, user)


@dp.message(US.phone)
async def phone_other(message: types.Message, state: FSMContext):
    await message.answer(T(get_user_lang(message.from_user.id), "phone_use_button"))

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

    args = (message.text or "").split(maxsplit=1)
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

    if not user["is_verified"] and not user["referrer_id"] and ref_id:
        update_user(uid, referrer_id=ref_id)
        user["referrer_id"] = ref_id

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
            T(lang, "welcome", name=user["first_name"] or html.escape(fname)),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    await send_human_check(message, state, uid, lang, user)

# ═══════════════════════════════════════════════════════════
# ASOSIY MENYU
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


@dp.callback_query(F.data == "m_lang")
async def cb_lang(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    txt = "🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>"
    try:
        await cb.message.edit_text(txt, reply_markup=lang_keyboard(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=lang_keyboard(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb: types.CallbackQuery, state: FSMContext):
    code = cb.data.replace("lang_", "")
    if code not in LANGS:
        return
    uid = cb.from_user.id
    if not get_user(uid):
        await cb.answer(T(code, "start_first"), show_alert=True)
        return
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

    await send_human_check(cb.message, state, uid, lang, user)


@dp.callback_query(F.data.startswith("ans_"))
async def check_ans(cb: types.CallbackQuery, state: FSMContext):
    parts = cb.data.split("_")
    if len(parts) != 3:
        return

    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    is_correct = parts[2] == "1"

    if not is_correct:
        await cb.answer(T(lang, "wrong_answer"), show_alert=True)
        await state.clear()
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(T(lang, "wrong_ans_retry"), parse_mode="HTML")
        return

    if not user.get("phone"):
        await state.clear()
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.answer()
        await send_human_check(cb.message, state, uid, lang, user)
        return

    if not user["is_verified"]:
        update_user(uid, is_verified=1)
        ref_id = user["referrer_id"] or 0

        if ref_id and ref_id != uid:
            ref = get_user(ref_id)
            if ref and not ref["is_banned"]:
                reward = int(get_setting("stars_per_referral", "2"))
                new_stars = add_stars(ref_id, reward)
                if new_stars is not None:
                    old_stars = new_stars - reward
                    ref_lang = get_user_lang(ref_id)
                    try:
                        await bot.send_message(
                            ref_id,
                            T(ref_lang, "referral_reward", n=reward)
                            + f"\n💰 {T(ref_lang, 'total')}: <b>{new_stars} ⭐</b>",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                    await check_level_up(ref_id, old_stars, new_stars)

    await state.clear()
    await cb.answer(T(lang, "correct"))
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(
        T(lang, "welcome", name=user["first_name"] or "User"),
        reply_markup=main_menu(uid),
        parse_mode="HTML"
    )


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
    if not user:
        await cb.message.answer(T(lang, "start_first"))
        return

    if user["is_verified"]:
        await cb.message.answer(
            T(lang, "welcome", name=user["first_name"] or "User"),
            reply_markup=main_menu(uid),
            parse_mode="HTML"
        )
        return

    await send_human_check(cb.message, state, uid, lang, user)


async def check_level_up(user_id, old_stars, new_stars):
    old_lvl = get_user_level(old_stars)
    new_lvl = get_user_level(new_stars)

    if old_lvl.get("name") == new_lvl.get("name"):
        return

    lang = get_user_lang(user_id)

    levels = get_levels()
    next_lvl = None
    for l in levels:
        if l["min_stars"] > new_stars:
            next_lvl = l
            break

    if next_lvl:
        next_emoji = next_lvl.get("emoji", "")
        next_name = next_lvl.get("name", "")
        need = next_lvl["min_stars"] - new_stars
    else:
        next_emoji = "👑"
        next_name = "MAX"
        need = 0

    try:
        await bot.send_message(
            user_id,
            T(lang, "level_up",
              emoji=new_lvl.get("emoji", ""), name=new_lvl.get("name", ""),
              next_emoji=next_emoji, next_name=next_name, need=need),
            parse_mode="HTML",
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
# PROFIL / STATISTIKA
# ═══════════════════════════════════════════════════════════
def _next_level(stars):
    for l in get_levels():
        if l["min_stars"] > stars:
            return l
    return None


@dp.callback_query(F.data == "m_profile")
async def cb_profile(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
    ref_count = refs["c"] if refs else 0
    rank_row = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0",
        (user["stars"],), fetch=True)
    rank = rank_row["rank"] if rank_row else "—"
    donated = total_donated(uid)

    uname = f"@{user['username']}" if user["username"] else "—"
    ver = "✅ Ha" if user["is_verified"] else "❌ Yo'q"
    ban = "🚫 Ha" if user["is_banned"] else "✅ Yo'q"
    joined = user["joined_at"][:10] if user["joined_at"] else "—"

    lvl = get_user_level(user["stars"])
    nxt = _next_level(user["stars"])
    next_text = (f"{nxt.get('emoji', '')} {nxt.get('name', '')} — {nxt['min_stars']} ⭐"
                 if nxt else "👑 <b>Eng yuqori daraja!</b>")

    text = (
        f"╭━━━〔 👤 <b>PROFIL</b> 〕━━━╮\n\n"
        f"🆔 <b>ID:</b> <code>{user['user_id']}</code>\n"
        f"👤 <b>Ism:</b> {user['first_name'] or 'N/A'}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🌐 <b>Til:</b> {user.get('language', 'uz').upper()}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>MOLIYAVIY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ <b>Stars:</b> <b>{user['stars']}</b> ⭐\n"
        f"💝 <b>Donat:</b> <b>{donated}</b> ⭐\n"
        f"🏅 <b>Daraja:</b> {lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n"
        f"⬆️ <b>Keyingi:</b> {next_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>REFERALLAR</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Taklif qilganlar:</b> <b>{ref_count}</b> ta\n"
        f"🏆 <b>O'rningiz:</b> <b>#{rank}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"ℹ️ <b>HOLAT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Tasdiqlangan:</b> {ver}\n"
        f"🚫 <b>Ban:</b> {ban}\n"
        f"📅 <b>Qo'shilgan:</b> {joined}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="m_profile")
    b.button(text="🏠 Asosiy menyu", callback_data="m_menu")
    b.adjust(1, 1)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()


@dp.callback_query(F.data == "m_stats")
async def cb_stats(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
    ref_count = refs["c"] if refs else 0
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    week_refs = db_exec(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s",
        (uid, week_ago), fetch=True)
    week_ref_count = week_refs["c"] if week_refs else 0
    rank_row = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0",
        (user["stars"],), fetch=True)
    rank = rank_row["rank"] if rank_row else "—"
    donated = total_donated(uid)

    lvl = get_user_level(user["stars"])
    lvl_min = lvl.get("min_stars", 0)
    lvl_max = lvl.get("max_stars", 10)
    total = lvl_max - lvl_min
    progress = int(((user["stars"] - lvl_min) / total) * 10) if total > 0 else 10
    progress = max(0, min(10, progress))
    progress_bar = "▰" * progress + "▱" * (10 - progress)

    nxt = _next_level(user["stars"])
    if nxt:
        next_text = f"{nxt.get('emoji', '')} <b>{nxt.get('name', '')}</b>"
        need = nxt["min_stars"] - user["stars"]
    else:
        next_text = "👑 <b>ENG YUQORI DARAJA!</b>"
        need = 0

    text = (
        f"╭━━━〔 📊 <b>STATISTIKA</b> 〕━━━╮\n\n"
        f"👤 <b>{user['first_name']}</b>\n\n"
        f"⭐ <b>Stars:</b> <b>{user['stars']} ⭐</b>\n"
        f"💝 <b>Donat:</b> <b>{donated} ⭐</b>\n"
        f"👥 <b>Referallar:</b> {ref_count} ta\n"
        f"📈 <b>Bu hafta:</b> +{week_ref_count} ta\n"
        f"🏆 <b>O'rningiz:</b> #{rank}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏅 <b>DARAJA</b>\n"
        f"{lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n"
        f"{progress_bar}\n"
        f"📊 <b>{user['stars']}</b> / {lvl_max} ⭐\n"
        f"⬆️ Keyingi: {next_text}\n"
        f"📉 Kerak: <b>{need} ⭐</b>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="m_stats")
    b.button(text="🏠 Menyu", callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()

# ═══════════════════════════════════════════════════════════
# BANNER
# ═══════════════════════════════════════════════════════════
def _load_font(size, bold=False):
    names = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for p in names:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def generate_banner(user, ref_link):
    W, H = 900, 500
    img = Image.new("RGB", (W, H), (10, 15, 30))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        r = int(10 + (y / H) * 40)
        g = int(15 + (y / H) * 30)
        b = int(40 + (y / H) * 80)
        draw.rectangle([0, y, W, y + 1], fill=(r, g, b))

    font_title = _load_font(72, bold=True)
    font_big = _load_font(36, bold=True)
    font_med = _load_font(28)
    font_small = _load_font(22)

    draw.text((50, 40), "STAR RUSH", font=font_title, fill=(255, 215, 0))
    draw.rectangle([50, 140, 850, 145], fill=(255, 215, 0))
    name = html.unescape(user["first_name"] or "User")
    draw.text((50, 180), name, font=font_big, fill=(255, 255, 255))
    draw.text((50, 240), f"{user['stars']} Stars", font=font_big, fill=(255, 215, 0))
    lvl = get_user_level(user["stars"])
    draw.text((50, 300), f"{lvl.get('name', 'Bronza')} darajasi", font=font_med, fill=(200, 220, 255))
    draw.text((50, 380), "Referal link:", font=font_small, fill=(180, 180, 180))
    draw.text((50, 415), ref_link, font=font_med, fill=(100, 200, 255))
    draw.rectangle([0, H - 10, W, H], fill=(255, 215, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@dp.callback_query(F.data == "m_banner")
async def cb_banner(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    await cb.answer("🎨 Banner yaratilmoqda...")
    msg = await cb.message.answer("🎨 <b>Banner yaratilmoqda...</b>", parse_mode="HTML")
    me = await bot.get_me()
    ref_link = f"t.me/{me.username}?start=ref_{uid}"
    try:
        banner = await asyncio.to_thread(generate_banner, user, ref_link)
        b = InlineKeyboardBuilder()
        b.button(text="🔄 Qayta", callback_data="m_banner")
        b.button(text="🏠 Menyu", callback_data="m_menu")
        b.adjust(2)
        await msg.delete()
        await cb.message.answer_photo(
            photo=BufferedInputFile(banner.getvalue(), filename="banner.png"),
            caption=T(lang, "banner_caption"), parse_mode="HTML", reply_markup=b.as_markup())
    except Exception as e:
        logger.error(f"Banner xato: {e}")
        await msg.edit_text(f"❌ Banner xato: {esc(e)}", parse_mode="HTML")


@dp.callback_query(F.data == "m_reflink")
async def cb_reflink(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
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

# ═══════════════════════════════════════════════════════════
# REYTING — 3 INLINE
# ═══════════════════════════════════════════════════════════
def rating_menu_kb(lang):
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "rating_stars"), callback_data="rt_stars")
    b.button(text=T(lang, "rating_donate"), callback_data="rt_donate")
    b.button(text=T(lang, "rating_ref"), callback_data="rt_ref")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    return b.as_markup()


@dp.callback_query(F.data == "m_rating")
async def cb_rating(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(T(lang, "rating_choose"), reply_markup=rating_menu_kb(lang), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "rating_choose"), reply_markup=rating_menu_kb(lang), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "rt_stars")
async def rt_stars(cb: types.CallbackQuery):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    rows = db_exec(
        "SELECT first_name, stars FROM users WHERE is_verified=1 AND is_banned=0 ORDER BY stars DESC LIMIT 10",
        fetchall=True) or []
    text = f"╭━━━〔 {T(lang, 'rating_stars')} 〕━━━╮\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {esc(r['first_name'] or 'N/A')} — <b>{r['stars']} ⭐</b>\n"
    else:
        text += "—"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "back"), callback_data="m_rating")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()


@dp.callback_query(F.data == "rt_donate")
async def rt_donate(cb: types.CallbackQuery):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    rows = db_exec(
        "SELECT u.first_name, COALESCE(SUM(d.stars),0) AS total FROM donations d "
        "JOIN users u ON d.user_id=u.user_id "
        "GROUP BY u.user_id, u.first_name ORDER BY total DESC LIMIT 10",
        fetchall=True) or []
    text = f"╭━━━〔 {T(lang, 'rating_donate')} 〕━━━╮\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {esc(r['first_name'] or 'N/A')} — <b>{r['total']} ⭐</b>\n"
    else:
        text += "— Hozircha donat yo'q"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "back"), callback_data="m_rating")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()


@dp.callback_query(F.data == "rt_ref")
async def rt_ref(cb: types.CallbackQuery):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    rows = db_exec(
        "SELECT u.first_name, COUNT(r.user_id) AS cnt FROM users r "
        "JOIN users u ON r.referrer_id=u.user_id "
        "WHERE r.is_verified=1 "
        "GROUP BY u.user_id, u.first_name ORDER BY cnt DESC LIMIT 10",
        fetchall=True) or []
    text = f"╭━━━〔 {T(lang, 'rating_ref')} 〕━━━╮\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {esc(r['first_name'] or 'N/A')} — <b>{r['cnt']} ta</b>\n"
    else:
        text += "— Hozircha referal yo'q"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "back"), callback_data="m_rating")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()

# ═══════════════════════════════════════════════════════════
# DONAT — botning o'ziga
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_donate")
async def cb_donate(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="donate_cancel")
    b.adjust(1)
    txt = T(lang, "donate_title", bal=user["stars"])
    try:
        await cb.message.edit_text(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.donate_amount)
    await cb.answer()


@dp.callback_query(F.data == "donate_cancel")
async def donate_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("OK")


@dp.message(US.donate_amount)
async def donate_process(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    try:
        amount = int((message.text or "").strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer(T(lang, "enter_number"))
        return
    if amount < 1:
        await message.answer(T(lang, "enter_number"))
        return

    user = get_user(uid)
    free = user["stars"] - pending_total(uid)
    if amount > free:
        await message.answer(
            f"{T(lang, 'not_enough')}\n💰 {T(lang, 'balance')}: <b>{max(free, 0)} ⭐</b>",
            parse_mode="HTML")
        return

    if spend_stars(uid, amount) is None:
        await message.answer(T(lang, "not_enough"))
        return

    db_exec(
        "INSERT INTO donations (user_id, stars, status, created_at) VALUES (%s, %s, 'received', %s)",
        (uid, amount, now_uz().isoformat()),
    )

    await state.clear()
    await message.answer(T(lang, "donate_ok", n=amount), parse_mode="HTML")
    await message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")

    uname = f"@{user['username']}" if user["username"] else "—"
    total_don = bot_donate_balance()
    await notify_admins(
        f"💝 <b>YANGI DONAT!</b>\n\n"
        f"👤 <b>User:</b> {user['first_name'] or 'User'}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"⭐ <b>Miqdor:</b> {amount} ⭐\n"
        f"💰 <b>Bot donat balansi:</b> {total_don} ⭐\n"
        f"📅 <b>Vaqt:</b> {now_uz().strftime('%Y-%m-%d %H:%M')}"
    )

# ═══════════════════════════════════════════════════════════
# YECHIB OLISH
# ═══════════════════════════════════════════════════════════
def withdraw_menu_kb(lang):
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "stars_withdraw"), callback_data="w_stars")
    b.button(text=T(lang, "gift_withdraw"), callback_data="w_gift")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)
    return b.as_markup()


def withdraw_menu_text(lang, user):
    return (
        f"╭━━━〔 💰 <b>{T(lang, 'withdraw')}</b> 〕━━━╮\n\n"
        f"⭐ <b>{T(lang, 'balance')}:</b> {user['stars']} ⭐\n\n"
        f"{T(lang, 'choose_reward')}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )


@dp.callback_query(F.data == "m_withdraw")
async def cb_withdraw(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    try:
        await cb.message.edit_text(withdraw_menu_text(lang, user), reply_markup=withdraw_menu_kb(lang), parse_mode="HTML")
    except Exception:
        await cb.message.answer(withdraw_menu_text(lang, user), reply_markup=withdraw_menu_kb(lang), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "w_cancel")
async def w_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("OK")


@dp.callback_query(F.data == "w_back")
async def w_back(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    try:
        await cb.message.edit_text(withdraw_menu_text(lang, user), reply_markup=withdraw_menu_kb(lang), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "w_stars")
async def w_stars(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
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
        f"💬 Nechta stars yechib olmoqchisiz?\n\n"
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
    text = (message.text or "").strip().replace(" ", "").replace(",", "")
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
    free_balance = user["stars"] - pending_total(uid)
    if amount > free_balance:
        await message.answer(
            f"{T(lang, 'not_enough')}\n\n"
            f"💰 {T(lang, 'balance')}: <b>{max(free_balance, 0)} ⭐</b>\n"
            f"📊 {T(lang, 'need')}: <b>{amount} ⭐</b>", parse_mode="HTML")
        return

    row = db_exec(
        "INSERT INTO withdrawals (user_id, stars, reward_type, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (uid, amount, "stars", "pending", now_uz().isoformat()), fetch=True)
    w_id = row["id"]

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
            await bot.send_message(a["user_id"], admin_text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Adminga xabar: {e}")

# ═══════════════════════════════════════════════════════════
# GIFT YUBORISH (userbot)
# ═══════════════════════════════════════════════════════════
def _norm_emoji(e):
    return (e or "").replace("\ufe0f", "").strip()


def _tg_gift_emoji(g):
    sticker = getattr(g, "sticker", None)
    for a in getattr(sticker, "attributes", None) or []:
        if isinstance(a, tt.DocumentAttributeSticker):
            return a.alt
    return None


async def _resolve_user(user_id):
    try:
        return await tg_client.get_input_entity(user_id)
    except Exception:
        pass

    u = db_exec("SELECT username, phone FROM users WHERE user_id=%s", (user_id,), fetch=True) or {}
    if u.get("username"):
        try:
            return await tg_client.get_input_entity(u["username"])
        except Exception:
            pass
    if u.get("phone"):
        r = await tg_client(ImportContactsRequest(
            [InputPhoneContact(0, "+" + u["phone"], "User", str(user_id))]))
        if r.users:
            return await tg_client.get_input_entity(r.users[0])
    raise ValueError("Userni userbot akkauntida topib bo'lmadi")


async def userbot_send_gift(user_id, gift_row, anon=False, comment=None):
    if not tg_client:
        return False, "Userbot sozlanmagan (SESSION_STRING)"
    try:
        if not tg_client.is_connected():
            await tg_client.connect()

        res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
        want = _norm_emoji(gift_row.get("emoji"))
        cands = [
            g for g in getattr(res, "gifts", [])
            if not getattr(g, "limited", False)
            and not getattr(g, "sold_out", False)
            and _norm_emoji(_tg_gift_emoji(g)) == want
        ]
        if not cands:
            return False, "Telegram gift ro'yxatida topilmadi"
        match = next((g for g in cands if getattr(g, "stars", None) == gift_row.get("stars")), cands[0])

        peer = await _resolve_user(user_id)
        msg = tt.TextWithEntities(text=comment[:120], entities=[]) if comment else None
        invoice = tt.InputInvoiceStarGift(peer=peer, gift_id=match.id, hide_name=bool(anon), message=msg)
        form = await tg_client(functions.payments.GetPaymentFormRequest(invoice=invoice))
        await tg_client(functions.payments.SendStarsFormRequest(form_id=form.form_id, invoice=invoice))
        return True, None
    except Exception as e:
        logger.warning(f"Userbot gift xato: {e}")
        return False, str(e)


async def deliver_gift(user_id, gift_row, anon=False, comment=None):
    async with gift_lock:
        ok, err = await userbot_send_gift(user_id, gift_row, anon=anon, comment=comment)
        if ok:
            return True, None
        return False, err


async def notify_admins(text, kb=None):
    for a in list_admins():
        try:
            await bot.send_message(a["user_id"], text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
# GIFT TANLASH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "w_gift")
async def w_gift(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("❌ Giftlar yo'q!", show_alert=True)
        return

    text = (
        f"╭━━━〔 🎁 <b>Telegram Gift olish</b> 〕━━━╮\n\n"
        f"💰 <b>{T(lang, 'balance')}:</b> {user['stars']} ⭐\n\n"
        f"<i>Giftni tanlang — u avtomatik yuboriladi:</i>\n\n"
    )
    b = InlineKeyboardBuilder()
    for g in gifts:
        text += f"{esc(g['emoji'])} <b>{esc(g['name'])}</b> — {g['stars']} ⭐\n"
        b.button(text=f"{g['emoji']} {g['name']} — {g['stars']}⭐", callback_data=f"gsel_{g['key']}")
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b.button(text=T(lang, "back"), callback_data="w_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("gsel_"))
async def gift_select(cb: types.CallbackQuery, state: FSMContext):
    key = cb.data.replace("gsel_", "")
    gift = get_gift(key)
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    if not gift:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return

    free_balance = user["stars"] - pending_total(uid)
    if gift["stars"] > free_balance:
        await cb.answer(f"{T(lang, 'not_enough')}\n{T(lang, 'need')}: {gift['stars']} ⭐", show_alert=True)
        return

    await state.update_data(gift_key_sel=key)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "gift_anon_yes"), callback_data="ganon_1")
    b.button(text=T(lang, "gift_anon_no"), callback_data="ganon_0")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(2, 1)
    gift_label = f"{esc(gift['emoji'])} <b>{esc(gift['name'])}</b>"
    txt = T(lang, "gift_ask_anon", gift=gift_label, n=gift["stars"])
    try:
        await cb.message.edit_text(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.in_({"ganon_0", "ganon_1"}))
async def gift_anon(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    data = await state.get_data()
    if not data.get("gift_key_sel"):
        await cb.answer("Xato", show_alert=True)
        return
    await state.update_data(gift_anon=int(cb.data.replace("ganon_", "")))

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "gift_no_comment"), callback_data="gcomment_skip")
    b.button(text=T(lang, "cancel"), callback_data="w_cancel")
    b.adjust(1)
    try:
        await cb.message.edit_text(T(lang, "gift_ask_comment"), reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "gift_ask_comment"), reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.gift_comment)
    await cb.answer()


async def finish_gift_request(uid, state, send, comment=None):
    data = await state.get_data()
    key = data.get("gift_key_sel")
    is_anon = int(data.get("gift_anon", 0))
    gift = get_gift(key) if key else None
    user = get_user(uid)
    lang = get_user_lang(uid)
    await state.clear()

    if not gift or not user:
        await send("Xato")
        return

    free_balance = user["stars"] - pending_total(uid)
    if gift["stars"] > free_balance or spend_stars(uid, gift["stars"]) is None:
        await send(T(lang, "not_enough"), back_to_menu_kb(uid))
        return

    row = db_exec(
        "INSERT INTO withdrawals (user_id, stars, reward_type, gift_key, status, created_at, is_anon, comment) "
        "VALUES (%s, %s, 'gift', %s, 'processing', %s, %s, %s) RETURNING id",
        (uid, gift["stars"], key, now_uz().isoformat(), is_anon, comment), fetch=True)
    w_id = row["id"]
    gift_label = f"{esc(gift['emoji'])} <b>{esc(gift['name'])}</b>"

    await send(T(lang, "gift_processing", gift=gift_label, n=gift["stars"]))

    ok, err = await deliver_gift(uid, gift, anon=bool(is_anon), comment=comment)

    if ok:
        db_exec("UPDATE withdrawals SET status='approved' WHERE id=%s", (w_id,))
        await send(T(lang, "gift_done", gift=gift_label, n=gift["stars"]), back_to_menu_kb(uid))
        logger.info(f"Gift #{w_id} yuborildi -> {uid}")
    else:
        add_stars(uid, gift["stars"])
        db_exec("UPDATE withdrawals SET status='failed', error=%s WHERE id=%s", ((err or "")[:500], w_id))
        await send(T(lang, "gift_failed", gift=gift_label, n=gift["stars"]), back_to_menu_kb(uid))
        uname = f"@{user['username']}" if user["username"] else "—"
        await notify_admins(
            f"⚠️ <b>Gift avtomatik yuborilmadi</b>\n\n"
            f"🆔 So'rov: <code>#{w_id}</code>\n"
            f"👤 User: <code>{uid}</code> ({uname})\n"
            f"🎁 {gift_label} — {gift['stars']} ⭐\n"
            f"❗ {esc(err)}\n\n"
            f"Stars userga qaytarildi. Userbot'ni tekshiring.")


@dp.callback_query(F.data == "gcomment_skip")
async def gift_comment_skip(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer("⏳")

    async def send(text, kb=None):
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")

    await finish_gift_request(cb.from_user.id, state, send, comment=None)


@dp.message(US.gift_comment)
async def gift_comment_input(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Matn yuboring yoki «Izohsiz» ni bosing.")
        return
    if len(text) > 120:
        await message.answer("❌ Maksimal 120 belgi.")
        return

    async def send(t, kb=None):
        await message.answer(t, reply_markup=kb, parse_mode="HTML")

    await finish_gift_request(message.from_user.id, state, send, comment=text)

# ═══════════════════════════════════════════════════════════
# STARS SOVG'A (user-user)
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
    txt = T(lang, "gift_stars_title", bal=user["stars"])
    try:
        await cb.message.edit_text(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.gift_username)
    await cb.answer()


@dp.callback_query(F.data == "gift_cancel")
async def gift_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("OK")


@dp.message(US.gift_username)
async def gift_username_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    if not message.text:
        await message.answer(T(lang, "gift_stars_not_found"))
        return
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
    await message.answer(T(lang, "gift_stars_amount", name=target["first_name"] or "User"), parse_mode="HTML")
    await state.set_state(US.gift_amount)


@dp.message(US.gift_amount)
async def gift_amount_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer(T(lang, "enter_number"))
        return
    if amount <= 0:
        await message.answer(T(lang, "enter_number"))
        return

    user = get_user(uid)
    if amount > user["stars"] - pending_total(uid):
        await message.answer(
            f"{T(lang, 'not_enough')}\n💰 {T(lang, 'balance')}: <b>{max(user['stars'] - pending_total(uid), 0)} ⭐</b>",
            parse_mode="HTML")
        return

    data = await state.get_data()
    target = get_user(data.get("gift_target"))
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
        reply_markup=b.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "gift_confirm")
async def gift_confirm(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    data = await state.get_data()
    target_id = data.get("gift_target")
    amount = data.get("gift_amount")
    await state.clear()

    if not target_id or not amount:
        await cb.answer("Xato", show_alert=True)
        return
    user = get_user(uid)
    target = get_user(target_id)
    if not user or not target:
        await cb.answer("Xato", show_alert=True)
        return

    if amount > user["stars"] - pending_total(uid) or spend_stars(uid, amount) is None:
        await cb.answer(T(lang, "not_enough"), show_alert=True)
        return
    new_target = add_stars(target_id, amount)
    if new_target is None:
        add_stars(uid, amount)
        await cb.answer("Xato", show_alert=True)
        return
    old_target = new_target - amount

    await cb.message.edit_text(
        T(lang, "gift_stars_sent", n=amount, name=target["first_name"] or "User"), parse_mode="HTML")
    try:
        await bot.send_message(
            target_id,
            T(get_user_lang(target_id), "gift_stars_received",
              name=user["first_name"] or "User", n=amount, total=new_target),
            parse_mode="HTML")
    except Exception:
        pass
    await check_level_up(target_id, old_target, new_target)
    await cb.answer("✅")

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

    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)

    if get_chat_status(uid) == "open":
        key = "chat_active"
    else:
        open_chat(uid)
        key = "support_title"
    try:
        await cb.message.edit_text(T(lang, key), reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, key), reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.support_msg)
    await cb.answer()


def _extract_msg(message, allow_extra=True):
    if message.text:
        return "text", message.text
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    if message.document:
        return "document", message.document.file_id
    if message.voice:
        return "voice", message.voice.file_id
    if allow_extra and message.audio:
        return "audio", message.audio.file_id
    if allow_extra and message.sticker:
        return "sticker", message.sticker.file_id
    return None, None


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
        await message.answer(T(lang, "chat_closed_by_admin"), reply_markup=back_to_menu_kb(uid), parse_mode="HTML")
        return

    msg_type, content = _extract_msg(message)
    if not msg_type:
        await message.answer("❌ Bu turdagi xabar qo'llab-quvvatlanmaydi.")
        return

    save_support_msg(uid, 0, msg_type, content, 0)

    uname = f"@{user['username']}" if user["username"] else "—"
    admin_header = T("uz", "user_msg") + "\n\n" + T(
        "uz", "support_new_msg", name=user["first_name"] or "User", username=uname, uid=uid,
        time=now_uz().strftime("%Y-%m-%d %H:%M"))

    kb = InlineKeyboardBuilder()
    kb.button(text="✉️ Javob berish", callback_data=f"reply_{uid}")
    kb.button(text="🔚 Suhbatni tugatish", callback_data=f"chat_close_admin_{uid}")
    kb.adjust(1)

    sent = 0
    for a in list_admins():
        try:
            await bot.send_message(a["user_id"], admin_header, reply_markup=kb.as_markup(), parse_mode="HTML")
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
        f"Matn, rasm, video yoki fayl yuboring:", parse_mode="HTML")
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
    if not get_user(uid):
        await message.answer("❌ User topilmadi.")
        await state.clear()
        return
    if not is_chat_open(uid):
        await message.answer("⚠️ Bu suhbat yopilgan.")
        await state.clear()
        return

    msg_type, content = _extract_msg(message, allow_extra=False)
    if not msg_type:
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
    try:
        await bot.send_message(uid, T(get_user_lang(uid), "chat_closed_by_admin"), parse_mode="HTML")
    except Exception:
        pass
    try:
        await cb.message.edit_text(cb.message.html_text + "\n\n🔚 <b>SUHBAT TUGATILDI</b>", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("✅")

# ═══════════════════════════════════════════════════════════
# SHARH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_review")
async def cb_review(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    if not get_user(uid):
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="review_cancel")
    b.adjust(1)
    try:
        await cb.message.edit_text(T(lang, "review_title"), reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "review_title"), reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.review_text)
    await cb.answer()


@dp.callback_query(F.data == "review_cancel")
async def review_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("OK")


@dp.message(US.review_text)
async def review_text_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("❌ Sharh juda qisqa. Kamida 5 ta belgi.")
        return

    row = db_exec(
        "INSERT INTO reviews (user_id, text, status, created_at) VALUES (%s, %s, 'pending', %s) RETURNING id",
        (uid, text, now_uz().isoformat()), fetch=True)
    r_id = row["id"] if row else 0

    await state.clear()
    await message.answer(T(lang, "review_sent"), parse_mode="HTML")
    await message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")

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
                f"⭐ <b>Yangi sharh!</b>\n\n👤 {user['first_name'] if user else 'User'} ({uname})\n"
                f"🆔 <code>{uid}</code>\n\n💬 <i>{esc(text)}</i>",
                reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════════
ADMIN_TITLE = (
    "╭━━━〔 🛠 <b>ADMIN PANEL</b> 〕━━━╮\n\n"
    "Kerakli bo'limni tanlang:\n\n"
    "╰━━━━━━━━━━━━━━━━━╯"
)


@dp.message(Command("admin"))
async def admin_panel_cmd(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer(ADMIN_TITLE, reply_markup=admin_menu(message.from_user.id), parse_mode="HTML")


@dp.callback_query(F.data == "m_admin")
async def cb_admin(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    await state.clear()
    try:
        await cb.message.edit_text(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    except Exception:
        await cb.message.answer(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "a_back")
async def a_back(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    try:
        await cb.message.edit_text(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()

# ---------- USERBOT ----------
@dp.callback_query(F.data == "a_userbot")
async def a_userbot(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()

    if not tg_client:
        status = "❌ Ulanmagan"
        extra = "\n\n<i>API_ID, API_HASH va SESSION_STRING env'larini tekshiring.</i>"
        bal_text = "—"
    else:
        extra = ""
        try:
            me = await tg_client.get_me()
            status = f"✅ Ulangan: <b>{esc(me.first_name or '')}</b>"
        except Exception as e:
            status = f"⚠️ Xato: {esc(e)}"
        try:
            st = await tg_client(functions.payments.GetStarsStatusRequest(peer=tt.InputPeerSelf()))
            bal = getattr(st.balance, "amount", st.balance)
            bal_text = f"<b>{bal} ⭐</b>"
        except Exception as e:
            bal_text = f"<i>o'qib bo'lmadi ({esc(e)})</i>"

    text = (
        "╭━━━〔 🤖 <b>USERBOT</b> 〕━━━╮\n\n"
        f"📡 Holat: {status}\n"
        f"💰 Akkauntdagi Stars: {bal_text}\n\n"
        "Gift'lar avtomatik, shu akkauntning Stars balansidan yuboriladi.\n\n"
        "╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_userbot")
    if is_super_admin(cb.from_user.id):
        b.button(text="🔑 Session almashtirish", callback_data="a_userbot_change")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_change")
async def a_userbot_change(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await state.clear()
    await cb.message.edit_text(
        "🔑 <b>Userbot sessionni almashtirish</b>\n\n"
        "1️⃣ API_ID ni kiriting (my.telegram.org dan):",
        parse_mode="HTML")
    await state.set_state(AS.userbot_api)
    await cb.answer()


@dp.message(AS.userbot_api)
async def userbot_api_input(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    try:
        api_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting")
        return
    await state.update_data(new_api_id=api_id)
    await message.answer("2️⃣ API_HASH ni kiriting:")
    await state.set_state(AS.userbot_hash)


@dp.message(AS.userbot_hash)
async def userbot_hash_input(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    api_hash = (message.text or "").strip()
    if len(api_hash) < 10:
        await message.answer("❌ API_HASH juda qisqa")
        return
    await state.update_data(new_api_hash=api_hash)
    await message.answer(
        "3️⃣ Yangi SESSION_STRING ni yuboring\n\n"
        "<i>Ushbu session avval `session.py` yordamida olingan bo'lishi kerak.</i>",
        parse_mode="HTML")
    await state.set_state(AS.userbot_session)


@dp.message(AS.userbot_session)
async def userbot_session_input(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    session_str = (message.text or "").strip()
    if len(session_str) < 30:
        await message.answer("❌ Session juda qisqa")
        return
    data = await state.get_data()
    api_id = data.get("new_api_id")
    api_hash = data.get("new_api_hash")

    await message.answer("⏳ Sinab ko'rilmoqda...")
    try:
        test_client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await test_client.connect()
        if not await test_client.is_user_authorized():
            await test_client.disconnect()
            await message.answer("❌ Session yaroqsiz. Qaytadan oling.")
            await state.clear()
            return
        me = await test_client.get_me()
        name = me.first_name or "User"

        global tg_client, API_ID, API_HASH, SESSION_STRING
        if tg_client:
            try:
                await tg_client.disconnect()
            except Exception:
                pass
        tg_client = test_client
        API_ID = api_id
        API_HASH = api_hash
        SESSION_STRING = session_str

        set_setting("userbot_api_id", str(api_id))
        set_setting("userbot_api_hash", api_hash)
        set_setting("userbot_session", session_str)

        await state.clear()
        await message.answer(
            f"✅ <b>Userbot almashtirildi!</b>\n\n👤 Yangi akkaunt: <b>{esc(name)}</b>",
            parse_mode="HTML")
        await message.answer(ADMIN_TITLE, reply_markup=admin_menu(message.from_user.id), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")
        await state.clear()

# ---------- Kanallar ----------
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    text = "╭━━━〔 📢 <b>KANALLAR</b> 〕━━━╮\n\n"
    text += "".join(f"• {esc(ch)}\n" for ch in channels) if channels else "— Kanallar yo'q\n"
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
    await cb.message.edit_text("📢 <b>Kanal username kiriting</b>\n\nMisol: <code>@mychannel</code>", parse_mode="HTML")
    await state.set_state(AS.channel)
    await cb.answer()


@dp.message(AS.channel)
async def add_ch_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    add_channel(ch)
    await state.clear()
    await message.answer(f"✅ <b>{esc(ch)}</b> qo'shildi!", parse_mode="HTML")
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
    remove_channel(cb.data.replace("delch_", ""))
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
            text += (f"📝 {esc(q['question'])}\n  ✅ {esc(q['correct_answer'])}\n"
                     f"  ❌ {esc(q['wrong1'])} | {esc(q['wrong2'])}\n\n")
    else:
        text += "— Savollar yo'q\n"
    text += "╰━━━━━━━━━━━━━━━━━╯"
    if len(text) > 4000:
        text = text[:3990] + "…"
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
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(q_text=message.text.strip())
    await message.answer("✅ <b>To'g'ri javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_correct)


@dp.message(AS.q_correct)
async def add_q_correct(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(q_correct=message.text.strip())
    await message.answer("❌ <b>1-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong1)


@dp.message(AS.q_wrong1)
async def add_q_wrong1(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(q_wrong1=message.text.strip())
    await message.answer("❌ <b>2-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong2)


@dp.message(AS.q_wrong2)
async def add_q_wrong2(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
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
    remove_question(int(cb.data.replace("delq_", "")))
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
        text += f"{esc(g['emoji'])} <b>{esc(g['name'])}</b> — {g['stars']} ⭐\n"
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
    if not is_admin(message.from_user.id) or not message.text:
        return
    key = message.text.strip().lower().replace(" ", "_")
    if not key or not key.replace("_", "").isalnum():
        await message.answer("❌ Faqat harflar va raqamlar.")
        return
    if get_gift(key):
        await message.answer("❌ Allaqachon bor.")
        return
    await state.update_data(gift_key=key)
    await message.answer("😀 <b>Emoji</b>:", parse_mode="HTML")
    await state.set_state(AS.gift_emoji)


@dp.message(AS.gift_emoji)
async def gift_emoji_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET emoji=%s WHERE key=%s", (message.text.strip(), data["edit_gift_key"]))
        await message.answer("📝 <b>Nom (yoki /skip):</b>", parse_mode="HTML")
    else:
        await state.update_data(gift_emoji=message.text.strip())
        await message.answer("📝 <b>Nom:</b>", parse_mode="HTML")
    await state.set_state(AS.gift_name)


@dp.message(AS.gift_name)
async def gift_name_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET name=%s WHERE key=%s", (message.text.strip(), data["edit_gift_key"]))
        await message.answer("⭐ <b>Narx (yoki /skip):</b>", parse_mode="HTML")
    else:
        await state.update_data(gift_name=message.text.strip())
        await message.answer("⭐ <b>Narx:</b>", parse_mode="HTML")
    await state.set_state(AS.gift_stars)


@dp.message(AS.gift_stars)
async def gift_stars_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            try:
                db_exec("UPDATE gifts SET stars=%s WHERE key=%s", (int(message.text.strip()), data["edit_gift_key"]))
            except ValueError:
                await message.answer("❌ Raqam.")
                return
        await state.clear()
        await message.answer("✅ <b>Tahrirlandi!</b>", parse_mode="HTML")
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
    remove_gift(cb.data.replace("delgift_", ""))
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
        f"✏️ <b>{esc(gift['emoji'])} {esc(gift['name'])}</b> ({gift['stars']}⭐)\n\nYangi emoji (yoki /skip):",
        parse_mode="HTML")
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
        f"💎 Max yechish = <b>{get_setting('max_withdraw')} ⭐</b>\n"
        f"📢 Sharh kanali: <b>{esc(get_setting('review_channel') or 'yo`q')}</b>\n\n"
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
        "📢 <b>Sharh kanali username kiriting</b>\n\nMisol: <code>@my_reviews</code>\n\n"
        "Bot kanalga <b>admin</b> qilingan bo'lishi kerak!", parse_mode="HTML")
    await state.set_state(AS.review_channel)
    await cb.answer()


@dp.message(AS.review_channel)
async def set_rev_ch_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    set_setting("review_channel", ch)
    await state.clear()
    await message.answer(f"✅ Sharh kanali: <b>{esc(ch)}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.message(AS.setting_val)
async def set_val_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
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
    q = lambda sql: db_exec(sql, fetch=True)["c"]
    total = q("SELECT COUNT(*) AS c FROM users")
    ver = q("SELECT COUNT(*) AS c FROM users WHERE is_verified=1")
    ban = q("SELECT COUNT(*) AS c FROM users WHERE is_banned=1")
    pend = q("SELECT COUNT(*) AS c FROM withdrawals WHERE status='pending'")
    gifts_ok = q("SELECT COUNT(*) AS c FROM withdrawals WHERE reward_type='gift' AND status='approved'")
    gifts_fail = q("SELECT COUNT(*) AS c FROM withdrawals WHERE reward_type='gift' AND status='failed'")
    total_stars = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM users", fetch=True)["s"]
    total_don = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM donations", fetch=True)["s"]
    open_chats = q("SELECT COUNT(*) AS c FROM support_chats WHERE status='open'")
    text = (
        f"╭━━━〔 📊 <b>STATISTIKA</b> 〕━━━╮\n\n"
        f"👥 <b>Jami:</b> {total}\n"
        f"✅ <b>Tasdiqlangan:</b> {ver}\n"
        f"🚫 <b>Ban:</b> {ban}\n"
        f"💸 <b>Pending:</b> {pend}\n"
        f"🎁 <b>Yuborilgan giftlar:</b> {gifts_ok}\n"
        f"⚠️ <b>Xato giftlar:</b> {gifts_fail}\n"
        f"⭐ <b>Jami stars:</b> {total_stars}\n"
        f"💝 <b>Jami donat:</b> {total_don}\n"
        f"💬 <b>Faol suhbatlar:</b> {open_chats}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# ---------- Donatlar (admin) ----------
@dp.callback_query(F.data == "a_donations")
async def a_donations(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    total = bot_donate_balance()
    rows = db_exec(
        "SELECT d.user_id, d.stars, d.created_at, u.first_name, u.username "
        "FROM donations d LEFT JOIN users u ON d.user_id = u.user_id "
        "ORDER BY d.id DESC LIMIT 15",
        fetchall=True
    ) or []

    text = (
        f"╭━━━〔 💝 <b>BOT DONAT BALANSI</b> 〕━━━╮\n\n"
        f"💰 <b>Jami donat:</b> <b>{total} ⭐</b>\n\n"
        f"<i>Bu stars'lar botning o'ziga tegishli — Telegram akkauntingizdan ishlatishingiz mumkin.</i>\n\n"
    )
    if rows:
        text += "━━━━━━━━━━━━━━━━━━━\n"
        for r in rows:
            uname = f"@{esc(r['username'])}" if r["username"] else "—"
            date = (r["created_at"] or "")[:16].replace("T", " ")
            text += (f"• {esc(r['first_name'] or 'User')} ({uname})\n"
                     f"  ⭐ {r['stars']} — {date}\n")
    else:
        text += "— Hozircha donat yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"

    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_donations")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1, 1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# ---------- Broadcast ----------
@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📨 <b>Broadcast</b>\n\nXabar yuboring:", parse_mode="HTML")
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
    ok = fail = blocked = 0
    is_forward = (getattr(message, "forward_origin", None) is not None
                  or getattr(message, "forward_date", None) is not None)

    for i, u in enumerate(users, 1):
        try:
            if is_forward:
                await bot.forward_message(chat_id=u["user_id"], from_chat_id=message.chat.id,
                                          message_id=message.message_id)
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
        f"✅ <b>Yuborildi:</b> {ok}\n❌ <b>Xato:</b> {fail}\n"
        f"🚫 <b>Bloklagan:</b> {blocked}\n👥 <b>Jami:</b> {total}\n\n"
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
        "JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.id DESC LIMIT 10",
        fetchall=True) or []
    if not rows:
        await cb.answer("— Pending yo'q", show_alert=True)
        return
    text = "╭━━━〔 💸 <b>PENDING</b> 〕━━━╮\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        if r["reward_type"] == "gift":
            g = get_gift(r["gift_key"]) or {}
            info = f"{esc(g.get('emoji', '🎁'))} {esc(g.get('name', 'Gift'))}"
        else:
            info = f"{r['stars']} ⭐"
        uname = f"@{esc(r['username'])}" if r["username"] else "—"
        text += f"• #{r['id']} {esc(r['first_name'] or 'User')} ({uname}) — {info}\n"
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
    w = db_exec("SELECT * FROM withdrawals WHERE id=%s", (w_id,), fetch=True)
    if not w or w["status"] != "pending":
        await cb.answer("—", show_alert=True)
        return
    user = get_user(w["user_id"])
    if not user:
        await cb.answer("—", show_alert=True)
        return

    claimed = db_exec(
        "UPDATE withdrawals SET status='approved' WHERE id=%s AND status='pending' RETURNING id",
        (w_id,), fetch=True)
    if not claimed:
        await cb.answer("—", show_alert=True)
        return

    if spend_stars(w["user_id"], w["stars"]) is None:
        db_exec("UPDATE withdrawals SET status='pending' WHERE id=%s", (w_id,))
        await cb.answer(f"❌ Kerak: {w['stars']}, bor: {user['stars']}", show_alert=True)
        return

    try:
        await cb.message.edit_text(cb.message.html_text + "\n\n✅ <b>TASDIQLANGAN</b>", parse_mode="HTML")
    except Exception:
        pass

    u_lang = get_user_lang(w["user_id"])
    uname = f"@{user['username']}" if user["username"] else "—"
    is_gift = w["reward_type"] == "gift"
    g = get_gift(w["gift_key"]) if is_gift else None

    try:
        if not is_gift:
            await bot.send_message(w["user_id"], T(u_lang, "stars_will_send", n=w["stars"]), parse_mode="HTML")
            await notify_admins(
                f"⚠️ <b>Stars yuborish kerak!</b>\n\n👤 User: {user['first_name']}\n🔗 Username: {uname}\n"
                f"🆔 ID: <code>{user['user_id']}</code>\n⭐ Miqdor: <b>{w['stars']} ⭐</b>\n\n"
                f"<b>Fragment.com</b> orqali qo'lda yuboring!")
        else:
            ok, err = await deliver_gift(w["user_id"], g or {}, anon=bool(w.get("is_anon")), comment=w.get("comment"))
            label = f"{esc((g or {}).get('emoji', '🎁'))} <b>{esc((g or {}).get('name', 'Gift'))}</b>"
            if ok:
                await bot.send_message(w["user_id"], T(u_lang, "gift_done", gift=label, n=w["stars"]), parse_mode="HTML")
            else:
                add_stars(w["user_id"], w["stars"])
                db_exec("UPDATE withdrawals SET status='failed', error=%s WHERE id=%s", ((err or "")[:500], w_id))
                await bot.send_message(w["user_id"], T(u_lang, "gift_failed", gift=label, n=w["stars"]), parse_mode="HTML")
                await notify_admins(f"⚠️ <b>Gift yuborilmadi</b> #{w_id}\n❗ {esc(err)}")
    except Exception as e:
        logger.warning(f"Userga xabar ({w['user_id']}): {e}")

    await cb.answer("✅")


@dp.callback_query(F.data.startswith("rej_"))
async def reject_w(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    w_id = int(cb.data.replace("rej_", ""))
    w = db_exec("UPDATE withdrawals SET status='rejected' WHERE id=%s AND status='pending' RETURNING *",
                (w_id,), fetch=True)
    if not w:
        await cb.answer("—", show_alert=True)
        return
    try:
        await cb.message.edit_text(cb.message.html_text + "\n\n❌ <b>RAD ETILGAN</b>", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("❌")
    try:
        await bot.send_message(w["user_id"], T(get_user_lang(w["user_id"]), "rejected"), parse_mode="HTML")
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
        uname = f"@{esc(c['username'])}" if c["username"] else "—"
        icon = "🟢" if c["status"] == "open" else "🔴"
        text += f"{icon} {esc(c['first_name'] or 'User')} ({uname})\n  <code>{c['user_id']}</code>\n\n"
        b.button(text=f"💬 {c['first_name'] or 'User'}", callback_data=f"chat_open_{c['user_id']}")
        b.button(text="🗑", callback_data=f"chat_del_{c['user_id']}")
    text += "╰━━━━━━━━━━━━━━━━━╯"
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(*([2] * min(len(chats[:20]), 10)), 1)
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

    rows = db_exec("SELECT * FROM support_tickets WHERE user_id=%s ORDER BY id DESC LIMIT 10",
                   (uid,), fetchall=True) or []
    history = f"╭━━━〔 💬 <b>TARIX</b> 〕━━━╮\n\n👤 <b>{user['first_name']}</b> (<code>{uid}</code>)\n\n"
    for r in reversed(rows):
        who = "👑" if r["is_from_admin"] else "👤"
        c = r["content"]
        if r["message_type"] != "text":
            c = f"[{r['message_type']}]"
        elif len(c) > 80:
            c = c[:80] + "..."
        history += f"{who} {esc(c)}\n"
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
    delete_chat(int(cb.data.replace("chat_del_", "")))
    await cb.answer("✅")
    await a_chats(cb)

# ---------- Sharhlar ----------
@dp.callback_query(F.data == "a_reviews")
async def a_reviews(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec(
        "SELECT r.*, u.first_name, u.username FROM reviews r LEFT JOIN users u ON r.user_id=u.user_id "
        "WHERE r.status='pending' ORDER BY r.id DESC LIMIT 10", fetchall=True) or []
    if not rows:
        await cb.answer("— Pending yo'q", show_alert=True)
        return
    text = "╭━━━〔 ⭐ <b>PENDING SHARHLAR</b> 〕━━━╮\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        uname = f"@{esc(r['username'])}" if r["username"] else "—"
        text += f"👤 {esc(r['first_name'] or 'User')} ({uname})\n💬 <i>{esc(r['text'][:150])}</i>\n\n"
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
    r = db_exec("UPDATE reviews SET status='approved' WHERE id=%s AND status='pending' RETURNING *",
                (r_id,), fetch=True)
    if not r:
        await cb.answer("—", show_alert=True)
        return
    user = get_user(r["user_id"])
    review_ch = get_setting("review_channel", "")
    if review_ch and user:
        try:
            uname = f"@{user['username']}" if user["username"] else "—"
            post = (f"⭐ <b>Yangi sharh!</b>\n\n👤 <b>User:</b> {user['first_name'] or 'User'}\n"
                    f"🔗 <b>Username:</b> {uname}\n🆔 <b>ID:</b> <code>{user['user_id']}</code>\n"
                    f"📅 <b>Vaqt:</b> {now_uz().strftime('%Y-%m-%d %H:%M')}\n\n💬 <i>{esc(r['text'])}</i>")
            await bot.send_message(review_ch, post, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Sharh kanali: {e}")
    try:
        await bot.send_message(r["user_id"], T(get_user_lang(r["user_id"]), "review_approved"), parse_mode="HTML")
    except Exception:
        pass
    try:
        await cb.message.edit_text(cb.message.html_text + f"\n\n✅ <b>#{r_id} TASDIQLANDI</b>", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("revrej_"))
async def review_reject(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    r_id = int(cb.data.replace("revrej_", ""))
    r = db_exec("UPDATE reviews SET status='rejected' WHERE id=%s AND status='pending' RETURNING *",
                (r_id,), fetch=True)
    if not r:
        await cb.answer("—", show_alert=True)
        return
    try:
        await bot.send_message(r["user_id"], T(get_user_lang(r["user_id"]), "review_rejected"), parse_mode="HTML")
    except Exception:
        pass
    try:
        await cb.message.edit_text(cb.message.html_text + f"\n\n❌ <b>#{r_id} RAD ETILDI</b>", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("❌")

# ---------- Darajalar ----------
@dp.callback_query(F.data == "a_levels")
async def a_levels(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    text = "╭━━━〔 🏅 <b>DARAJALAR</b> 〕━━━╮\n\n"
    for lvl in get_levels():
        text += (f"{esc(lvl.get('emoji', ''))} <b>{esc(lvl.get('name', ''))}</b>: "
                 f"{lvl.get('min_stars', 0)}-{lvl.get('max_stars', 0)} ⭐\n")
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
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(level_name=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>", parse_mode="HTML")
    await state.set_state(AS.level_emoji)


@dp.message(AS.level_emoji)
async def level_emoji_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(level_emoji=message.text.strip())
    await message.answer("📉 <b>Min stars:</b>", parse_mode="HTML")
    await state.set_state(AS.level_min)


@dp.message(AS.level_min)
async def level_min_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
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
        val = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    db_exec("INSERT INTO levels (name, emoji, min_stars, max_stars) VALUES (%s, %s, %s, %s)",
            (data["level_name"], data["level_emoji"], data["level_min"], val))
    await state.clear()
    await message.answer("✅ <b>Daraja qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_level_list")
async def del_level_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    b = InlineKeyboardBuilder()
    for lvl in get_levels():
        if "id" not in lvl:
            continue
        b.button(text=f"❌ {lvl.get('emoji', '')} {lvl.get('name', '')}", callback_data=f"dellvl_{lvl['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_levels")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("dellvl_"))
async def del_level_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM levels WHERE id=%s", (int(cb.data.replace("dellvl_", "")),))
    await cb.answer("✅")
    await a_levels(cb)

# ---------- User boshqarish ----------
def user_manage_kb(uid, banned):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Unban" if banned else "🚫 Ban", callback_data=f"tog_{uid}")
    kb.button(text="➕ Stars", callback_data=f"adp_{uid}")
    kb.button(text="➖ Stars", callback_data=f"rem_{uid}")
    kb.button(text="✉️ Xabar", callback_data=f"msg_{uid}")
    kb.button(text="💬 Suhbat", callback_data=f"chat_open_{uid}")
    kb.button(text="⬅️", callback_data="a_back")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


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
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌")
        return
    user = get_user(uid)
    if not user:
        await message.answer("❌ Topilmadi.")
        return
    await state.clear()
    uname = f"@{user['username']}" if user["username"] else "—"
    lvl = get_user_level(user["stars"])
    phone_text = f"+{user['phone']}" if user.get("phone") else "—"
    donated = total_donated(uid)
    text = (
        f"╭━━━〔 👤 <b>USER INFO</b> 〕━━━╮\n\n"
        f"🆔 <code>{user['user_id']}</code>\n👤 {user['first_name']}\n🔗 {uname}\n📱 {phone_text}\n"
        f"⭐ {user['stars']}\n💝 Donat: {donated}\n"
        f"🏅 {esc(lvl.get('emoji', ''))} {esc(lvl.get('name', ''))}\n"
        f"🚫 Ban: {'Ha' if user['is_banned'] else 'Yo`q'}\n"
        f"✅ Ver: {'Ha' if user['is_verified'] else 'Yo`q'}\n🌐 {user.get('language', 'uz')}\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    await message.answer(text, reply_markup=user_manage_kb(uid, user["is_banned"]), parse_mode="HTML")


@dp.callback_query(F.data.startswith("tog_"))
async def toggle_ban(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("tog_", ""))
    user = get_user(uid)
    if not user:
        return
    new_val = 0 if user["is_banned"] else 1
    update_user(uid, is_banned=new_val)
    try:
        await cb.message.edit_reply_markup(reply_markup=user_manage_kb(uid, new_val))
    except Exception:
        pass
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("adp_"))
async def add_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.update_data(target_uid=int(cb.data.replace("adp_", "")), action="add")
    await cb.message.edit_text("➕ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()


@dp.callback_query(F.data.startswith("rem_"))
async def remove_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.update_data(target_uid=int(cb.data.replace("rem_", "")), action="remove")
    await cb.message.edit_text("➖ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()


@dp.message(AS.stars_amount)
async def stars_amount_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌")
        return
    if amount <= 0:
        await message.answer("❌ >0")
        return
    await state.update_data(stars_amount=amount)
    await message.answer("📝 <b>Sabab:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_reason)


@dp.message(AS.stars_reason)
async def stars_reason_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    reason = html.escape(message.text.strip())
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
        new_stars = add_stars(uid, amount)
        old_stars = new_stars - amount
    else:
        new_stars = spend_stars(uid, amount)
        if new_stars is None:
            await message.answer(f"❌ Faqat {user['stars']} ⭐")
            return
        old_stars = new_stars + amount

    await state.clear()
    u_lang = get_user_lang(uid)
    try:
        key = "stars_added" if action == "add" else "stars_removed"
        await bot.send_message(uid, T(u_lang, key, n=amount, reason=reason, total=new_stars), parse_mode="HTML")
    except Exception:
        pass
    if action == "add":
        await check_level_up(uid, old_stars, new_stars)

    sign = "➕" if action == "add" else "➖"
    await message.answer(f"✅ {sign} <b>{amount} ⭐</b>\n📝 {reason}\n💰 <b>{new_stars} ⭐</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.update_data(target_uid=int(cb.data.replace("msg_", "")))
    await cb.message.edit_text("✉️ <b>Xabar:</b>", parse_mode="HTML")
    await state.set_state(AS.user_msg)
    await cb.answer()


@dp.message(AS.user_msg)
async def user_msg_send(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    try:
        await message.copy_to(chat_id=data["target_uid"])
        await message.answer("✅")
    except Exception as e:
        await message.answer(f"❌ {esc(e)}", parse_mode="HTML")
    await state.clear()
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ---------- Adminlar ----------
@dp.callback_query(F.data == "a_admins")
async def a_admins(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    text = "╭━━━〔 👑 <b>ADMINLAR</b> 〕━━━╮\n\n"
    for a in list_admins():
        u = get_user(a["user_id"])
        tag = " 👑" if a["user_id"] in SUPER_ADMIN_IDS else ""
        text += f"• {u['first_name'] if u else 'N/A'} — <code>{a['user_id']}</code>{tag}\n"
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
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌")
        return
    user = get_user(uid)
    if not user or uid in SUPER_ADMIN_IDS:
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
    b = InlineKeyboardBuilder()
    for a in list_admins():
        if a["user_id"] in SUPER_ADMIN_IDS:
            continue
        u = get_user(a["user_id"])
        name = u["first_name"] if u else "N/A"
        b.button(text=f"❌ {html.unescape(name)}", callback_data=f"deladmin_{a['user_id']}")
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
# MINI APP API
# ═══════════════════════════════════════════════════════════
def validate_init_data(init_data, max_age=86400):
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = pairs.pop("hash", None)
        if not recv_hash:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            return None
        return json.loads(pairs["user"])
    except Exception:
        return None


def _count_refs(uid, since=None):
    if since:
        r = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s",
                    (uid, since), fetch=True)
    else:
        r = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
    return r["c"] if r else 0


def build_profile(uid):
    u = db_exec("SELECT * FROM users WHERE user_id=%s", (uid,), fetch=True)
    if not u:
        return {"error": "Foydalanuvchi topilmadi. Botda /start bosing."}
    rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0",
        (u["stars"],), fetch=True)
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    lvl = get_user_level(u["stars"])
    return {
        "user_id": u["user_id"],
        "first_name": u["first_name"] or "User",
        "username": u["username"],
        "stars": u["stars"],
        "donated": total_donated(uid),
        "level_name": lvl.get("name", "Bronza"),
        "level_emoji": lvl.get("emoji", "🥉"),
        "level_min": lvl.get("min_stars", 0),
        "level_max": lvl.get("max_stars", 10),
        "referrals": _count_refs(uid),
        "week_referrals": _count_refs(uid, week_ago),
        "rank": rank["rank"] if rank else 0,
    }


def build_rating(uid):
    # 1) Stars reytingi
    me_stars = db_exec("SELECT first_name, stars FROM users WHERE user_id=%s", (uid,), fetch=True)
    if not me_stars:
        return {"error": "Foydalanuvchi topilmadi. Botda /start bosing."}

    rows = db_exec(
        "SELECT user_id, first_name, stars FROM users "
        "WHERE is_verified=1 AND is_banned=0 ORDER BY stars DESC, user_id ASC LIMIT 10",
        fetchall=True) or []
    stars_top = [{
        "rank": i,
        "name": r["first_name"] or "User",
        "stars": r["stars"],
        "level_emoji": get_user_level(r["stars"]).get("emoji", ""),
        "is_me": r["user_id"] == uid,
    } for i, r in enumerate(rows, 1)]
    stars_rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0",
        (me_stars["stars"],), fetch=True)

    # 2) Donat reytingi
    d_rows = db_exec(
        "SELECT u.user_id, u.first_name, COALESCE(SUM(d.stars),0) AS total, COUNT(d.id) AS count "
        "FROM donations d JOIN users u ON d.user_id=u.user_id "
        "GROUP BY u.user_id, u.first_name ORDER BY total DESC LIMIT 10",
        fetchall=True) or []
    donate_top = [{
        "rank": i,
        "name": r["first_name"] or "User",
        "total": int(r["total"]),
        "count": int(r["count"]),
        "is_me": r["user_id"] == uid,
    } for i, r in enumerate(d_rows, 1)]

    me_d = db_exec(
        "SELECT COALESCE(SUM(stars),0) AS total, COUNT(id) AS count FROM donations WHERE user_id=%s",
        (uid,), fetch=True) or {"total": 0, "count": 0}
    my_don_total = int(me_d["total"])
    my_don_count = int(me_d["count"])
    don_rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM ("
        "  SELECT user_id, SUM(stars) AS total FROM donations "
        "  GROUP BY user_id HAVING SUM(stars) > %s"
        ") t",
        (my_don_total,), fetch=True)

    # 3) Referal reytingi
    r_rows = db_exec(
        "SELECT u.user_id, u.first_name, COUNT(r.user_id) AS cnt "
        "FROM users r JOIN users u ON r.referrer_id=u.user_id "
        "WHERE r.is_verified=1 "
        "GROUP BY u.user_id, u.first_name ORDER BY cnt DESC LIMIT 10",
        fetchall=True) or []
    ref_top = [{
        "rank": i,
        "name": r["first_name"] or "User",
        "count": int(r["cnt"]),
        "is_me": r["user_id"] == uid,
    } for i, r in enumerate(r_rows, 1)]

    my_ref = _count_refs(uid)
    ref_rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM ("
        "  SELECT referrer_id, COUNT(*) AS cnt FROM users "
        "  WHERE is_verified=1 AND referrer_id<>0 "
        "  GROUP BY referrer_id HAVING COUNT(*) > %s"
        ") t",
        (my_ref,), fetch=True)

    return {
        "stars": {
            "top": stars_top,
            "me": {
                "rank": stars_rank["rank"] if stars_rank else 0,
                "name": me_stars["first_name"] or "User",
                "stars": me_stars["stars"],
            },
        },
        "donate": {
            "top": donate_top,
            "me": {
                "rank": don_rank["rank"] if don_rank else 0,
                "name": me_stars["first_name"] or "User",
                "total": my_don_total,
                "count": my_don_count,
            },
        },
        "ref": {
            "top": ref_top,
            "me": {
                "rank": ref_rank["rank"] if ref_rank else 0,
                "name": me_stars["first_name"] or "User",
                "count": my_ref,
            },
        },
    }


def build_donations(uid):
    """Donat sahifasi uchun: TOP 10 + foydalanuvchining shaxsiy statistikasi."""
    me = db_exec("SELECT first_name FROM users WHERE user_id=%s", (uid,), fetch=True)
    if not me:
        return {"error": "Foydalanuvchi topilmadi. Botda /start bosing."}

    rows = db_exec(
        "SELECT u.user_id, u.first_name, "
        "       COALESCE(SUM(d.stars),0) AS total, "
        "       COUNT(d.id) AS count "
        "FROM donations d JOIN users u ON d.user_id=u.user_id "
        "GROUP BY u.user_id, u.first_name "
        "ORDER BY total DESC LIMIT 10",
        fetchall=True
    ) or []

    me_row = db_exec(
        "SELECT COALESCE(SUM(stars),0) AS total, COUNT(id) AS count "
        "FROM donations WHERE user_id=%s",
        (uid,), fetch=True
    ) or {"total": 0, "count": 0}

    my_total = int(me_row["total"])
    rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM ("
        "  SELECT user_id, SUM(stars) AS total FROM donations "
        "  GROUP BY user_id HAVING SUM(stars) > %s"
        ") t",
        (my_total,), fetch=True
    )

    top = [{
        "rank": i,
        "name": r["first_name"] or "User",
        "total": int(r["total"]),
        "count": int(r["count"]),
        "is_me": r["user_id"] == uid,
    } for i, r in enumerate(rows, 1)]

    return {
        "top": top,
        "me": {
            "rank": rank["rank"] if rank else 0,
            "name": me["first_name"] or "User",
            "total": my_total,
            "count": int(me_row["count"]),
        },
    }


def build_withdrawals(uid):
    rows = db_exec(
        "SELECT w.id, w.stars, w.reward_type, w.status, w.created_at, g.emoji, g.name "
        "FROM withdrawals w LEFT JOIN gifts g ON g.key = w.gift_key "
        "WHERE w.user_id=%s ORDER BY w.id DESC LIMIT 20",
        (uid,), fetchall=True) or []
    return {"items": [{
        "id": r["id"], "stars": r["stars"], "type": r["reward_type"], "status": r["status"],
        "created_at": r["created_at"], "gift_emoji": r["emoji"], "gift_name": r["name"],
    } for r in rows]}


def build_gifts(uid):
    u = db_exec("SELECT stars FROM users WHERE user_id=%s", (uid,), fetch=True)
    if not u:
        return {"error": "Foydalanuvchi topilmadi. Botda /start bosing."}
    free = max(u["stars"] - pending_total(uid), 0)
    return {
        "balance": u["stars"],
        "free": free,
        "gifts": [{"key": g["key"], "emoji": g["emoji"], "name": g["name"], "stars": g["stars"]}
                  for g in get_all_gifts()],
    }


def build_referrals(uid):
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    rows = db_exec(
        "SELECT first_name, joined_at FROM users "
        "WHERE referrer_id=%s AND is_verified=1 ORDER BY joined_at DESC LIMIT 50",
        (uid,), fetchall=True) or []
    return {
        "total": _count_refs(uid),
        "week": _count_refs(uid, week_ago),
        "reward": int(get_setting("stars_per_referral", "2")),
        "items": [{"name": r["first_name"] or "User", "joined_at": r["joined_at"]} for r in rows],
    }


def build_levels(uid):
    u = db_exec("SELECT stars FROM users WHERE user_id=%s", (uid,), fetch=True)
    return {
        "stars": u["stars"] if u else 0,
        "levels": [{"name": l.get("name", ""), "emoji": l.get("emoji", ""),
                    "min": l.get("min_stars", 0), "max": l.get("max_stars", 0)} for l in get_levels()],
    }


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
}


@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    resp = await handler(request)
    resp.headers.update(CORS_HEADERS)
    return resp


def make_api(builder):
    async def handler(request):
        tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
        if not tg_user or "id" not in tg_user:
            return web.json_response({"error": "Ruxsat yo'q"}, status=401)
        try:
            data = await asyncio.to_thread(builder, int(tg_user["id"]))
        except Exception as e:
            logger.error(f"API xato: {e}")
            return web.json_response({"error": "Server xatosi. Birozdan so'ng urinib ko'ring."}, status=500)
        return web.json_response(data)
    return handler


async def health(request):
    return web.Response(text="OK")


async def index(request):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(p):
        return web.FileResponse(p)
    return web.Response(text=BOT_NAME)

# ═══════════════════════════════════════════════════════════
# USERBOT ULANISH
# ═══════════════════════════════════════════════════════════
async def init_userbot():
    global tg_client, API_ID, API_HASH, SESSION_STRING

    # DB'dagi sozlamalarni tekshiramiz (admin almashtirgan bo'lishi mumkin)
    db_api_id = get_setting("userbot_api_id", "")
    db_api_hash = get_setting("userbot_api_hash", "")
    db_session = get_setting("userbot_session", "")
    if db_api_id and db_api_hash and db_session:
        try:
            API_ID = int(db_api_id)
        except ValueError:
            pass
        API_HASH = db_api_hash
        SESSION_STRING = db_session

    if not (API_ID and API_HASH and SESSION_STRING):
        logger.warning("Userbot sozlanmagan — gift yuborilmaydi")
        return
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Userbot sessiyasi yaroqsiz — SESSION_STRING ni qayta oling")
            await client.disconnect()
            return
        tg_client = client
        me = await client.get_me()
        logger.info(f"Userbot ulandi: {me.first_name} (id {me.id})")
    except Exception as e:
        logger.error(f"Userbot ulanmadi: {e}")
        tg_client = None

# ═══════════════════════════════════════════════════════════
# ISHGA TUSHIRISH
# ═══════════════════════════════════════════════════════════
async def main():
    init_db()
    await init_userbot()

    try:
        await bot.set_my_name(BOT_NAME)
    except Exception as e:
        logger.warning(f"set_my_name: {e}")

    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    for path, builder in (
        ("/api/profile", build_profile),
        ("/api/rating", build_rating),
        ("/api/donations", build_donations),
        ("/api/withdrawals", build_withdrawals),
        ("/api/gifts", build_gifts),
        ("/api/referrals", build_referrals),
        ("/api/levels", build_levels),
    ):
        app.router.add_get(path, make_api(builder))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Web server {PORT} portda ishga tushdi")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"{BOT_NAME} (@{BOT_USERNAME}) ishga tushdi")
    try:
        await dp.start_polling(bot)
    finally:
        if tg_client:
            await tg_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
