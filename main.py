import os
import asyncio
import sqlite3
import logging
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

# ==================== GIFTLAR (rasmdan) ====================
GIFTS = {
    "heart":     {"emoji": "💝", "name": "Heart",      "stars": 15},
    "teddy":     {"emoji": "🧸", "name": "Teddy Bear", "stars": 15},
    "giftbox":   {"emoji": "🎁", "name": "Gift Box",   "stars": 25},
    "rose":      {"emoji": "🌹", "name": "Rose",       "stars": 25},
    "cake":      {"emoji": "🎂", "name": "Cake",       "stars": 50},
    "bouquet":   {"emoji": "💐", "name": "Bouquet",    "stars": 50},
    "rocket":    {"emoji": "🚀", "name": "Rocket",     "stars": 50},
    "champagne": {"emoji": "🍾", "name": "Champagne",  "stars": 50},
    "trophy":    {"emoji": "🏆", "name": "Trophy",     "stars": 100},
    "ring":      {"emoji": "💍", "name": "Ring",       "stars": 100},
    "diamond":   {"emoji": "💎", "name": "Diamond",    "stars": 100},
}

MIN_STARS = 50
MAX_STARS = 1_000_000

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
    # Endi "points" o'rniga "stars" ishlatiladi
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
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
        answer TEXT
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
        "stars_per_referral": "5",   # har bir referal uchun nechta stars
        "min_withdraw": "50",         # minimal stars yechish
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    for a in SUPER_ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                  (a, a, datetime.now().isoformat()))

    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)",
                  ("2 + 2 nechaga teng? (raqamda)", "4"))
        c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)",
                  ("O'zbekiston poytaxti? (lotin, kichik harf)", "toshkent"))
        c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)",
                  ("10 - 3 nechaga teng? (raqamda)", "7"))
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

def add_question(q, a):
    db_exec("INSERT INTO questions (question, answer) VALUES (?, ?)", (q, a))

def remove_question(q_id):
    db_exec("DELETE FROM questions WHERE id=?", (q_id,))

def get_questions():
    rows = db_exec("SELECT * FROM questions", fetchall=True)
    return [dict(r) for r in rows] if rows else []

# ==================== BOT ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class US(StatesGroup):
    answer = State()
    withdraw_stars = State()

class AS(StatesGroup):
    channel = State()
    q_text = State()
    q_ans = State()
    broadcast = State()
    setting_val = State()
    user_id = State()
    stars_val = State()
    user_msg = State()
    add_admin_id = State()

# ==================== KLAVIATURALAR ====================
def main_menu(uid):
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Profilim")
    b.button(text="🔗 Referal linkim")
    b.button(text="🏆 Reyting")
    b.button(text="💰 Yechib olish")
    if is_admin(uid):
        b.button(text="🛠 Admin Panel")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)

def admin_menu(uid):
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanallar", callback_data="a_channels")
    b.button(text="❓ Savollar", callback_data="a_questions")
    b.button(text="⚙️ Sozlamalar", callback_data="a_settings")
    b.button(text="📊 Statistika", callback_data="a_stats")
    b.button(text="📨 Broadcast", callback_data="a_broadcast")
    b.button(text="💸 Yechib olish", callback_data="a_withdrawals")
    b.button(text="👤 User boshqarish", callback_data="a_users")
    b.button(text="🎁 Giftlar", callback_data="a_gifts")
    if is_super_admin(uid):
        b.button(text="👑 Adminlar", callback_data="a_admins")
    b.adjust(2)
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

async def subs_kb():
    channels = get_channels()
    b = InlineKeyboardBuilder()
    for ch in channels:
        try:
            chat = await bot.get_chat(ch)
            link = chat.invite_link or f"https://t.me/{ch.replace('@', '')}"
        except Exception:
            link = f"https://t.me/{ch.replace('@', '')}"
        b.button(text=f"📢 {ch}", url=link)
    b.button(text="✅ Tekshirish", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()

# ==================== /start ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    uname = message.from_user.username
    fname = message.from_user.first_name or "Foydalanuvchi"
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
        user = get_user(uid)

    if user["is_banned"]:
        await message.answer("❌ Siz banlangansiz.")
        return

    if not await check_subs(uid):
        kb = await subs_kb()
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=kb
        )
        return

    if user["is_verified"]:
        await message.answer(
            f"Salom, {fname}! 👋\n\nAsosiy menyu:",
            reply_markup=main_menu(uid)
        )
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await message.answer(
            f"✅ Tasdiqlandi! Salom, {fname}!",
            reply_markup=main_menu(uid)
        )
        return

    await state.update_data(q_id=q["id"], ref_id=ref_id)
    await state.set_state(US.answer)
    await message.answer(f"🤖 Iltimos, bot emasligingizni tasdiqlang:\n\n❓ {q['question']}")

# ==================== JAVOB ====================
@dp.message(US.answer)
async def check_ans(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("q_id")
    ref_id = data.get("ref_id", 0)

    q = get_question(q_id) if q_id else None
    if not q:
        await state.clear()
        await message.answer("Xatolik. /start ni qaytadan bosing.")
        return

    if message.text.strip().lower() != q["answer"].strip().lower():
        await message.answer("❌ Noto'g'ri javob. Qaytadan: /start")
        await state.clear()
        return

    uid = message.from_user.id
    update_user(uid, is_verified=1)

    if ref_id and ref_id != uid:
        ref = get_user(ref_id)
        if ref and not ref["is_banned"]:
            reward = int(get_setting("stars_per_referral", "5"))
            update_user(ref_id, stars=ref["stars"] + reward)
            try:
                await bot.send_message(
                    ref_id,
                    f"🎉 Yangi referal! +{reward} ⭐\nJami: {ref['stars'] + reward} ⭐"
                )
            except Exception:
                pass

    await state.clear()
    await message.answer(
        "✅ Tasdiqlandi! Endi botdan foydalanishingiz mumkin.",
        reply_markup=main_menu(uid)
    )

# ==================== OBUNA CALLBACK ====================
@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not await check_subs(uid):
        await cb.answer("❌ Hali obuna emassiz!", show_alert=True)
        return

    await cb.answer("✅ Tasdiqlandi!")
    try:
        await cb.message.delete()
    except Exception:
        pass

    user = get_user(uid)
    if user and user["is_verified"]:
        await cb.message.answer("Asosiy menyu:", reply_markup=main_menu(uid))
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await cb.message.answer("✅ Tasdiqlandi!", reply_markup=main_menu(uid))
        return

    await state.update_data(q_id=q["id"], ref_id=user["referrer_id"] if user else 0)
    await state.set_state(US.answer)
    await cb.message.answer(f"🤖 Bot emasligingizni tasdiqlang:\n\n❓ {q['question']}")

# ==================== MENYU ====================
@dp.message(F.text == "👤 Profilim")
async def profile(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    refs = db_exec(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND is_verified=1",
        (user["user_id"],), fetch=True
    )
    ref_count = refs["c"] if refs else 0
    uname = f"@{user['username']}" if user["username"] else "yo'q"
    ver = "Ha" if user["is_verified"] else "Yo'q"
    joined = user["joined_at"][:10] if user["joined_at"] else "N/A"
    text = (
        f"👤 <b>Profilingiz</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Ism: {user['first_name'] or 'N/A'}\n"
        f"🔗 Username: {uname}\n"
        f"⭐ Stars: <b>{user['stars']}</b>\n"
        f"👥 Referallar: {ref_count}\n"
        f"✅ Tasdiqlangan: {ver}\n"
        f"📅 Qo'shilgan: {joined}"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🔗 Referal linkim")
async def ref_link(message: types.Message):
    uid = message.from_user.id
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    refs = db_exec(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND is_verified=1",
        (uid,), fetch=True
    )
    ref_count = refs["c"] if refs else 0
    reward = int(get_setting("stars_per_referral", "5"))
    user = get_user(uid)
    text = (
        f"🔗 <b>Sizning referal linkingiz:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Taklif qilganlar: {ref_count}\n"
        f"⭐ Stars: {user['stars'] if user else 0}\n\n"
        f"Har bir tasdiqlangan referal uchun <b>{reward} ⭐</b> olasiz!"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🏆 Reyting")
async def leaderboard(message: types.Message):
    rows = db_exec(
        "SELECT first_name, stars FROM users WHERE is_verified=1 AND is_banned=0 ORDER BY stars DESC LIMIT 10",
        fetchall=True
    )
    text = "🏆 <b>Top 10 Referalchilar</b>\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {r['first_name'] or 'N/A'} — {r['stars']} ⭐\n"
    else:
        text += "Hozircha hech kim yo'q."
    await message.answer(text, parse_mode="HTML")

# ==================== YECHIB OLISH ====================
@dp.message(F.text == "💰 Yechib olish")
async def withdraw_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return

    min_w = int(get_setting("min_withdraw", "50"))
    if user["stars"] < min_w:
        await message.answer(
            f"❌ Yechib olish uchun kamida {min_w} ⭐ kerak.\n"
            f"Sizda: {user['stars']} ⭐"
        )
        return

    b = InlineKeyboardBuilder()
    b.button(text="⭐ To'liq Stars olish", callback_data="w_stars")
    b.button(text="🎁 Telegram Gift olish", callback_data="w_gift")
    b.button(text="❌ Bekor qilish", callback_data="w_cancel")
    b.adjust(1)

    await message.answer(
        f"💰 <b>Yechib olish</b>\n\n"
        f"Sizda: <b>{user['stars']} ⭐</b>\n"
        f"Min: {min_w} ⭐\n\n"
        f"Mukofot turini tanlang:",
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
    await cb.answer("Bekor qilindi")

# ========== STARS ==========
@dp.callback_query(F.data == "w_stars")
async def w_stars(cb: types.CallbackQuery, state: FSMContext):
    user = get_user(cb.from_user.id)
    await cb.message.edit_text(
        f"⭐ <b>Stars yechib olish</b>\n\n"
        f"Sizda: <b>{user['stars']} ⭐</b>\n"
        f"Min: {MIN_STARS} ⭐\n"
        f"Max: {MAX_STARS:,} ⭐\n\n"
        f"Nechta stars yechib olmoqchisiz?\n"
        f"Raqamni kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(US.withdraw_stars)
    await cb.answer()

@dp.message(US.withdraw_stars)
async def w_stars_process(message: types.Message, state: FSMContext):
    text = message.text.strip().replace(" ", "").replace(",", "")
    try:
        amount = int(text)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return

    if amount < MIN_STARS:
        await message.answer(f"❌ Minimal: {MIN_STARS} ⭐")
        return
    if amount > MAX_STARS:
        await message.answer(f"❌ Maksimal: {MAX_STARS:,} ⭐")
        return

    user = get_user(message.from_user.id)
    if amount > user["stars"]:
        await message.answer(
            f"❌ Yetarli emas!\n"
            f"Sizda: {user['stars']} ⭐\n"
            f"Kerak: {amount} ⭐"
        )
        return

    db_exec(
        "INSERT INTO withdrawals (user_id, stars, reward_type, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (user["user_id"], amount, "stars", "pending", datetime.now().isoformat())
    )
    last = db_exec("SELECT MAX(id) AS id FROM withdrawals", fetch=True)
    w_id = last["id"] if last else 0

    await state.clear()
    await message.answer(
        f"✅ <b>{amount} ⭐</b> yechib olish so'rovi yuborildi.\n"
        f"Admin tasdiqlashini kuting.",
        parse_mode="HTML"
    )

    # Adminga xabar
    uname = f"@{user['username']}" if user["username"] else "yo'q"
    admin_text = (
        f"💸 <b>Yangi STARS so'rovi!</b>\n\n"
        f"🆔 So'rov: <code>#{w_id}</code>\n"
        f"👤 User: {user['first_name']} (<code>{user['user_id']}</code>)\n"
        f"🔗 Username: {uname}\n"
        f"⭐ Miqdor: <b>{amount} stars</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"appr_{w_id}")
    kb.button(text="❌ Rad etish", callback_data=f"rej_{w_id}")
    kb.adjust(2)

    for a in list_admins():
        try:
            await bot.send_message(
                a["user_id"],
                admin_text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Adminga xabar yuborishda xato ({a['user_id']}): {e}")

# ========== GIFT ==========
@dp.callback_query(F.data == "w_gift")
async def w_gift(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(cb.from_user.id)

    text = (
        f"🎁 <b>Telegram Gift olish</b>\n\n"
        f"Sizda: <b>{user['stars']} ⭐</b>\n\n"
        f"Giftni tanlang:\n\n"
    )

    b = InlineKeyboardBuilder()
    for key, g in GIFTS.items():
        text += f"{g['emoji']} {g['name']} — {g['stars']} ⭐\n"
        b.button(
            text=f"{g['emoji']} {g['name']} — {g['stars']}⭐",
            callback_data=f"gift_{key}"
        )
    b.button(text="⬅️ Orqaga", callback_data="w_back")
    b.adjust(1)

    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "w_back")
async def w_back(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(cb.from_user.id)
    min_w = int(get_setting("min_withdraw", "50"))

    b = InlineKeyboardBuilder()
    b.button(text="⭐ To'liq Stars olish", callback_data="w_stars")
    b.button(text="🎁 Telegram Gift olish", callback_data="w_gift")
    b.button(text="❌ Bekor qilish", callback_data="w_cancel")
    b.adjust(1)

    await cb.message.edit_text(
        f"💰 <b>Yechib olish</b>\n\n"
        f"Sizda: <b>{user['stars']} ⭐</b>\n"
        f"Min: {min_w} ⭐\n\n"
        f"Mukofot turini tanlang:",
        reply_markup=b.as_markup(),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("gift_"))
async def gift_select(cb: types.CallbackQuery, state: FSMContext):
    key = cb.data.replace("gift_", "")
    gift = GIFTS.get(key)
    if not gift:
        await cb.answer("Topilmadi!", show_alert=True)
        return

    user = get_user(cb.from_user.id)
    if gift["stars"] > user["stars"]:
        await cb.answer(
            f"❌ Yetarli emas!\nKerak: {gift['stars']} ⭐\nSizda: {user['stars']} ⭐",
            show_alert=True
        )
        return

    db_exec(
        "INSERT INTO withdrawals (user_id, stars, reward_type, gift_key, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user["user_id"], gift["stars"], "gift", key, "pending", datetime.now().isoformat())
    )
    last = db_exec("SELECT MAX(id) AS id FROM withdrawals", fetch=True)
    w_id = last["id"] if last else 0

    await state.clear()

    await cb.message.edit_text(
        f"✅ <b>{gift['emoji']} {gift['name']}</b> ({gift['stars']}⭐) so'rovingiz yuborildi.\n"
        f"So'rov raqami: <code>#{w_id}</code>\n\n"
        f"Admin tasdiqlashini kuting.",
        parse_mode="HTML"
    )
    await cb.answer("✅ So'rov yuborildi!")

    uname = f"@{user['username']}" if user["username"] else "yo'q"
    admin_text = (
        f"🎁 <b>Yangi GIFT so'rovi!</b>\n\n"
        f"🆔 So'rov: <code>#{w_id}</code>\n"
        f"👤 User: {user['first_name']} (<code>{user['user_id']}</code>)\n"
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
            await bot.send_message(
                a["user_id"],
                admin_text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Adminga xabar yuborishda xato ({a['user_id']}): {e}")

# ==================== ADMIN PANEL ====================
@dp.message(Command("admin"))
@dp.message(F.text == "🛠 Admin Panel")
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer(
        "🛠 <b>Admin Panel</b>",
        reply_markup=admin_menu(message.from_user.id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "a_back")
async def a_back(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text(
        "🛠 <b>Admin Panel</b>",
        reply_markup=admin_menu(cb.from_user.id),
        parse_mode="HTML"
    )
    await cb.answer()

# ---------- Kanallar ----------
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    text = "📢 <b>Majburiy kanallar:</b>\n\n"
    text += "\n".join([f"• {ch}" for ch in channels]) if channels else "Hozircha kanal yo'q."
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_ch")
    b.button(text="➖ O'chirish", callback_data="del_ch_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_ch")
async def add_ch_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📢 Kanal username kiriting (masalan: @mychannel):")
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
    await message.answer(f"✅ {ch} qo'shildi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_ch_list")
async def del_ch_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    if not channels:
        await cb.answer("Kanallar yo'q!", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.button(text=f"❌ {ch}", callback_data=f"delch_{ch}")
    b.button(text="⬅️ Orqaga", callback_data="a_channels")
    b.adjust(1)
    await cb.message.edit_text("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("delch_"))
async def del_ch_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    ch = cb.data.replace("delch_", "")
    remove_channel(ch)
    await cb.answer(f"✅ {ch} o'chirildi!")
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
            text += f"• {q['question']} → <code>{q['answer']}</code>\n"
    else:
        text += "Hozircha savol yo'q."
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_q")
    b.button(text="➖ O'chirish", callback_data="del_q_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
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
    await message.answer("Endi to'g'ri javobni kiriting:")
    await state.set_state(AS.q_ans)

@dp.message(AS.q_ans)
async def add_q_ans(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    add_question(data.get("q_text"), message.text.strip())
    await state.clear()
    await message.answer("✅ Savol qo'shildi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data == "del_q_list")
async def del_q_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    qs = get_questions()
    if not qs:
        await cb.answer("Savollar yo'q!", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for q in qs:
        b.button(text=f"❌ {q['question'][:40]}", callback_data=f"delq_{q['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_questions")
    b.adjust(1)
    await cb.message.edit_text("O'chirmoqchi bo'lgan savolni tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("delq_"))
async def del_q_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    q_id = int(cb.data.replace("delq_", ""))
    remove_question(q_id)
    await cb.answer("✅ O'chirildi!")
    await a_questions(cb)

# ---------- Sozlamalar ----------
@dp.callback_query(F.data == "a_settings")
async def a_settings(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    text = (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🎯 1 referal = {get_setting('stars_per_referral')} ⭐\n"
        f"💰 Min yechish = {get_setting('min_withdraw')} ⭐"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal stars", callback_data="set_ref")
    b.button(text="💰 Min yechish", callback_data="set_minw")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.in_({"set_ref", "set_minw"}))
async def set_val_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    mapping = {
        "set_ref": ("stars_per_referral", "🎯 1 referal uchun nechta stars berilsin?"),
        "set_minw": ("min_withdraw", "💰 Minimal yechish (stars) kiriting:"),
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
    await message.answer(f"✅ Yangilandi: {data['setting_key']} = {val}")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ---------- Giftlar ----------
@dp.callback_query(F.data == "a_gifts")
async def a_gifts(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    text = "🎁 <b>Mavjud giftlar va narxlari:</b>\n\n"
    for key, g in GIFTS.items():
        text += f"{g['emoji']} <b>{g['name']}</b> — {g['stars']} ⭐\n"
    text += "\n<i>Narxlar Telegram tomonidan belgilangan.</i>"
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# ---------- Adminlar ----------
@dp.callback_query(F.data == "a_admins")
async def a_admins(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat super admin!", show_alert=True)
        return
    admins = list_admins()
    text = "👑 <b>Adminlar ro'yxati:</b>\n\n"
    for a in admins:
        u = get_user(a["user_id"])
        name = u["first_name"] if u else "N/A"
        tag = " (SUPER)" if a["user_id"] in SUPER_ADMIN_IDS else ""
        text += f"• {name} — <code>{a['user_id']}</code>{tag}\n"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Admin qo'shish", callback_data="add_admin")
    b.button(text="➖ Admin o'chirish", callback_data="del_admin_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "👑 Yangi admin ID sini kiriting:\n\n"
        "(Foydalanuvchi botga /start bosgan bo'lishi kerak)"
    )
    await state.set_state(AS.add_admin_id)
    await cb.answer()

@dp.message(AS.add_admin_id)
async def add_admin_do(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return
    user = get_user(uid)
    if not user:
        await message.answer("❌ Bu foydalanuvchi topilmadi. U avval /start bosishi kerak.")
        return
    if uid in SUPER_ADMIN_IDS:
        await message.answer("❌ Bu allaqachon super admin.")
        return
    add_admin(uid, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ {user['first_name']} (<code>{uid}</code>) admin qilindi!", parse_mode="HTML")
    try:
        await bot.send_message(uid, "🎉 Siz admin etib tayinlandingiz!\n\n/admin buyrug'ini yuboring.")
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
    await cb.message.edit_text("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("deladmin_"))
async def del_admin_do(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("deladmin_", ""))
    if uid in SUPER_ADMIN_IDS:
        await cb.answer("❌ Super adminni o'chirib bo'lmaydi!", show_alert=True)
        return
    remove_admin(uid)
    await cb.answer("✅ O'chirildi!")
    await a_admins(cb)

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
        f"💸 Kutilayotgan so'rovlar: {pend}\n"
        f"⭐ Jami stars: {total_stars}"
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
    await cb.message.edit_text("📨 Yubormoqchi bo'lgan xabaringizni yuboring (forward yoki matn):")
    await state.set_state(AS.broadcast)
    await cb.answer()

@dp.message(AS.broadcast)
async def broadcast_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users = db_exec("SELECT user_id FROM users WHERE is_banned=0", fetchall=True) or []
    ok = 0
    fail = 0
    for u in users:
        try:
            await message.copy_to(chat_id=u["user_id"])
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await message.answer(f"📨 Yuborildi!\n✅ {ok}\n❌ {fail}")
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
        await cb.answer("Kutilayotgan so'rovlar yo'q!", show_alert=True)
        return
    text = "💸 <b>Kutilayotgan so'rovlar:</b>\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        if r["reward_type"] == "gift":
            g = GIFTS.get(r["gift_key"], {})
            info = f"{g.get('emoji', '🎁')} {g.get('name', 'Gift')} ({r['stars']}⭐)"
        else:
            info = f"{r['stars']} ⭐"
        uname = f"@{r['username']}" if r["username"] else "yo'q"
        text += f"• #{r['id']} {r['first_name']} ({uname}) — {info}\n"
        b.button(text=f"✅ #{r['id']}", callback_data=f"appr_{r['id']}")
        b.button(text=f"❌ #{r['id']}", callback_data=f"rej_{r['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("appr_"))
async def approve_w(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    w_id = int(cb.data.replace("appr_", ""))
    w = db_exec("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetch=True)
    if not w:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    if w["status"] != "pending":
        await cb.answer("Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)
        return
    user = get_user(w["user_id"])
    if not user:
        await cb.answer("User topilmadi!", show_alert=True)
        return

    if user["stars"] < w["stars"]:
        await cb.answer(
            f"❌ User'da yetarli stars yo'q!\nKerak: {w['stars']}, bor: {user['stars']}",
            show_alert=True
        )
        return

    # Stars ni ayirish
    update_user(w["user_id"], stars=user["stars"] - w["stars"])
    db_exec("UPDATE withdrawals SET status='approved' WHERE id=?", (w_id,))

    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n✅ <b>TASDIQLANGAN</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

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
                f"✅ <b>{w['stars']} ⭐</b> yechib olish tasdiqlandi!\n\n"
                f"To'lovni qabul qilish uchun yuqoridagi xabarni bosing.",
                parse_mode="HTML"
            )
            await cb.answer("✅ Tasdiqlandi va Stars yuborildi!")
        except Exception as e:
            logger.error(f"Stars yuborishda xato: {e}")
            update_user(w["user_id"], stars=user["stars"])
            db_exec("UPDATE withdrawals SET status='pending' WHERE id=?", (w_id,))
            await cb.answer(f"❌ Xato: {e}", show_alert=True)
            return
    else:
        g = GIFTS.get(w["gift_key"], {})
        await bot.send_message(
            w["user_id"],
            f"✅ <b>{g.get('emoji', '🎁')} {g.get('name', 'Gift')}</b> so'rovingiz tasdiqlandi!\n\n"
            f"Admin tez orada giftni yuboradi.",
            parse_mode="HTML"
        )
        await cb.answer("✅ Tasdiqlandi! Gift qo'lda yuboriladi.")

@dp.callback_query(F.data.startswith("rej_"))
async def reject_w(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    w_id = int(cb.data.replace("rej_", ""))
    w = db_exec("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetch=True)
    if not w:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    if w["status"] != "pending":
        await cb.answer("Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    db_exec("UPDATE withdrawals SET status='rejected' WHERE id=?", (w_id,))

    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n❌ <b>RAD ETILGAN</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await cb.answer("❌ Rad etildi!")
    if w:
        try:
            if w["reward_type"] == "gift":
                g = GIFTS.get(w["gift_key"], {})
                info = f"{g.get('emoji', '🎁')} {g.get('name', 'Gift')}"
            else:
                info = f"{w['stars']} ⭐"
            await bot.send_message(
                w["user_id"],
                f"❌ {info} yechib olish so'rovingiz rad etildi."
            )
        except Exception:
            pass

# ---------- User boshqarish ----------
@dp.callback_query(F.data == "a_users")
async def a_users(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👤 Foydalanuvchi ID sini kiriting:")
    await state.set_state(AS.user_id)
    await cb.answer()

@dp.message(AS.user_id)
async def user_info(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
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
    b.button(text="✉️ Xabar yuborish", callback_data=f"msg_{uid}")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2)
    uname = f"@{user['username']}" if user["username"] else "yo'q"
    ban = "Ha" if user["is_banned"] else "Yo'q"
    ver = "Ha" if user["is_verified"] else "Yo'q"
    text = (
        f"👤 <b>Foydalanuvchi:</b>\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Ism: {user['first_name']}\n"
        f"Username: {uname}\n"
        f"⭐ Stars: {user['stars']}\n"
        f"Ban: {ban}\n"
        f"Tasdiqlangan: {ver}"
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
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data.startswith("adp_"))
async def add_stars_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("adp_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("➕ Qancha stars qo'shilsin? (manfiy ham mumkin)")
    await state.set_state(AS.stars_val)
    await cb.answer()

@dp.message(AS.stars_val)
async def add_stars_do(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return
    data = await state.get_data()
    uid = data["target_uid"]
    user = get_user(uid)
    if not user:
        await message.answer("❌ Topilmadi.")
        return
    new_stars = max(0, user["stars"] + amount)
    update_user(uid, stars=new_stars)
    await state.clear()
    await message.answer(f"✅ Yangi stars: {new_stars}")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("msg_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("✉️ Yubormoqchi bo'lgan xabaringizni yozing:")
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
        await message.answer("✅ Yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
    await state.clear()
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

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
    logger.info(f"Health server portda: {PORT}")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling rejimida ishga tushmoqda...")
    asyncio.create_task(start_web())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
