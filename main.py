import os
import asyncio
import sqlite3
import random
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
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
PORT = int(os.environ.get("PORT", 8080))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN o'rnatilmagan!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "bot_data.db"

# ==================== MA'LUMOTLAR BAZASI ====================
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
        points INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        is_suspicious INTEGER DEFAULT 0,
        joined_at TEXT,
        last_bonus TEXT
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
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    defaults = {
        "points_per_referral": "5",
        "min_withdraw": "50",
        "reward_type": "stars",
        "daily_bonus": "1",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
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
    withdraw = State()

class AS(StatesGroup):
    channel = State()
    q_text = State()
    q_ans = State()
    broadcast = State()
    setting_val = State()
    user_id = State()
    points_val = State()
    user_msg = State()

# ==================== KLAVIATURALAR ====================
def main_menu(uid):
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Profilim")
    b.button(text="🔗 Referal linkim")
    b.button(text="🏆 Reyting")
    b.button(text="🎁 Kunlik bonus")
    b.button(text="💰 Yechib olish")
    if uid in ADMIN_IDS:
        b.button(text="🛠 Admin Panel")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)

def admin_menu():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanallar", callback_data="a_channels")
    b.button(text="❓ Savollar", callback_data="a_questions")
    b.button(text="⚙️ Sozlamalar", callback_data="a_settings")
    b.button(text="📊 Statistika", callback_data="a_stats")
    b.button(text="📨 Broadcast", callback_data="a_broadcast")
    b.button(text="💸 Yechib olish", callback_data="a_withdrawals")
    b.button(text="👤 User boshqarish", callback_data="a_users")
    b.adjust(2)
    return b.as_markup()

# ==================== OBUNA TEKSHIRISH ====================
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

# ==================== JAVOB TEKSHIRISH ====================
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
            pts = int(get_setting("points_per_referral", "5"))
            update_user(ref_id, points=ref["points"] + pts)
            try:
                await bot.send_message(
                    ref_id,
                    f"🎉 Yangi referal! +{pts} ball.\nJami: {ref['points'] + pts} ball"
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
        f"🎯 Ball: {user['points']}\n"
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
    pts = int(get_setting("points_per_referral", "5"))
    user = get_user(uid)
    text = (
        f"🔗 <b>Sizning referal linkingiz:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Taklif qilganlar: {ref_count}\n"
        f"🎯 Ball: {user['points'] if user else 0}\n\n"
        f"Har bir tasdiqlangan referal uchun <b>{pts} ball</b> olasiz!"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🏆 Reyting")
async def leaderboard(message: types.Message):
    rows = db_exec(
        "SELECT first_name, points FROM users WHERE is_verified=1 AND is_banned=0 ORDER BY points DESC LIMIT 10",
        fetchall=True
    )
    text = "🏆 <b>Top 10 Referalchilar</b>\n\n"
    if rows:
        for i, r in enumerate(rows, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {r['first_name'] or 'N/A'} — {r['points']} ball\n"
    else:
        text += "Hozircha hech kim yo'q."
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🎁 Kunlik bonus")
async def daily_bonus(message: types.Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    today = datetime.now().date().isoformat()
    if user.get("last_bonus") == today:
        await message.answer("❌ Siz bugun allaqachon bonus oldingiz!")
        return
    bonus = int(get_setting("daily_bonus", "1"))
    update_user(uid, points=user["points"] + bonus, last_bonus=today)
    await message.answer(f"🎁 Siz {bonus} ball oldingiz!\nJami: {user['points'] + bonus} ball")

@dp.message(F.text == "💰 Yechib olish")
async def withdraw_start(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    min_w = int(get_setting("min_withdraw", "50"))
    if user["points"] < min_w:
        await message.answer(f"❌ Minimal: {min_w} ball. Sizda: {user['points']}")
        return
    await message.answer(f"💰 Yechib olmoqchi bo'lgan ball miqdorini kiriting (min: {min_w}):")
    await state.set_state(US.withdraw)

@dp.message(US.withdraw)
async def withdraw_process(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return
    user = get_user(message.from_user.id)
    min_w = int(get_setting("min_withdraw", "50"))
    if amount < min_w:
        await message.answer(f"❌ Minimal: {min_w}")
        return
    if amount > user["points"]:
        await message.answer(f"❌ Yetarli emas. Sizda: {user['points']}")
        return
    db_exec(
        "INSERT INTO withdrawals (user_id, amount, created_at) VALUES (?, ?, ?)",
        (user["user_id"], amount, datetime.now().isoformat())
    )
    await state.clear()
    await message.answer(f"✅ {amount} ball yechib olish so'rovi yuborildi. Admin tasdiqlashini kuting.")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 Yangi so'rov!\nUser: {user['first_name']} ({user['user_id']})\nMiqdor: {amount} ball"
            )
        except Exception:
            pass

# ==================== ADMIN PANEL ====================
@dp.message(Command("admin"))
@dp.message(F.text == "🛠 Admin Panel")
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "a_back")
async def a_back(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await cb.message.edit_text("🛠 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")
    await cb.answer()

# ---------- Kanallar ----------
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
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
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text("📢 Kanal username kiriting (masalan: @mychannel):")
    await state.set_state(AS.channel)
    await cb.answer()

@dp.message(AS.channel)
async def add_ch_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    add_channel(ch)
    await state.clear()
    await message.answer(f"✅ {ch} qo'shildi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data == "del_ch_list")
async def del_ch_list(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
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
    if cb.from_user.id not in ADMIN_IDS:
        return
    ch = cb.data.replace("delch_", "")
    remove_channel(ch)
    await cb.answer(f"✅ {ch} o'chirildi!")
    channels = get_channels()
    text = "📢 <b>Majburiy kanallar:</b>\n\n"
    text += "\n".join([f"• {c}" for c in channels]) if channels else "Hozircha kanal yo'q."
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_ch")
    b.button(text="➖ O'chirish", callback_data="del_ch_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")

# ---------- Savollar ----------
@dp.callback_query(F.data == "a_questions")
async def a_questions(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
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
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text("❓ Savolni kiriting:")
    await state.set_state(AS.q_text)
    await cb.answer()

@dp.message(AS.q_text)
async def add_q_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(q_text=message.text.strip())
    await message.answer("Endi to'g'ri javobni kiriting:")
    await state.set_state(AS.q_ans)

@dp.message(AS.q_ans)
async def add_q_ans(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    add_question(data.get("q_text"), message.text.strip())
    await state.clear()
    await message.answer("✅ Savol qo'shildi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data == "del_q_list")
async def del_q_list(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
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
    if cb.from_user.id not in ADMIN_IDS:
        return
    q_id = int(cb.data.replace("delq_", ""))
    remove_question(q_id)
    await cb.answer("✅ O'chirildi!")
    await a_questions(cb)

# ---------- Sozlamalar ----------
@dp.callback_query(F.data == "a_settings")
async def a_settings(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    text = (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🎯 Referal ball: {get_setting('points_per_referral')}\n"
        f"💰 Minimal yechish: {get_setting('min_withdraw')}\n"
        f"🎁 Mukofot turi: {get_setting('reward_type')}\n"
        f"🎁 Kunlik bonus: {get_setting('daily_bonus')}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal ball", callback_data="set_points")
    b.button(text="💰 Min yechish", callback_data="set_minw")
    b.button(text="🎁 Mukofot turi", callback_data="set_reward")
    b.button(text="🎁 Kunlik bonus", callback_data="set_daily")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.in_({"set_points", "set_minw", "set_daily"}))
async def set_val_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    mapping = {
        "set_points": ("points_per_referral", "🎯 Referal ball miqdorini kiriting:"),
        "set_minw": ("min_withdraw", "💰 Minimal yechish miqdorini kiriting:"),
        "set_daily": ("daily_bonus", "🎁 Kunlik bonus miqdorini kiriting:"),
    }
    key, prompt = mapping[cb.data]
    await state.update_data(setting_key=key)
    await cb.message.edit_text(prompt)
    await state.set_state(AS.setting_val)
    await cb.answer()

@dp.message(AS.setting_val)
async def set_val_do(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
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
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data == "set_reward")
async def set_reward(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    b = InlineKeyboardBuilder()
    for t in ["stars", "gift", "premium", "sum"]:
        b.button(text=t.capitalize(), callback_data=f"rt_{t}")
    b.button(text="⬅️ Orqaga", callback_data="a_settings")
    b.adjust(2)
    await cb.message.edit_text("🎁 Mukofot turini tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("rt_"))
async def set_reward_do(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    t = cb.data.replace("rt_", "")
    set_setting("reward_type", t)
    await cb.answer(f"✅ {t}")
    await a_settings(cb)

# ---------- Statistika ----------
@dp.callback_query(F.data == "a_stats")
async def a_stats(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    total = db_exec("SELECT COUNT(*) AS c FROM users", fetch=True)["c"]
    ver = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_verified=1", fetch=True)["c"]
    ban = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_banned=1", fetch=True)["c"]
    susp = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_suspicious=1", fetch=True)["c"]
    pend = db_exec("SELECT COUNT(*) AS c FROM withdrawals WHERE status='pending'", fetch=True)["c"]
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami: {total}\n"
        f"✅ Tasdiqlangan: {ver}\n"
        f"🚫 Ban: {ban}\n"
        f"⚠️ Shubhali: {susp}\n"
        f"💸 Kutilayotgan so'rovlar: {pend}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# ---------- Broadcast ----------
@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text("📨 Yubormoqchi bo'lgan xabaringizni yuboring (forward yoki matn):")
    await state.set_state(AS.broadcast)
    await cb.answer()

@dp.message(AS.broadcast)
async def broadcast_do(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
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
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

# ---------- Yechib olish ----------
@dp.callback_query(F.data == "a_withdrawals")
async def a_withdrawals(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    rows = db_exec(
        "SELECT w.id, w.user_id, w.amount, u.first_name FROM withdrawals w "
        "JOIN users u ON w.user_id=u.user_id WHERE w.status='pending'",
        fetchall=True
    ) or []
    if not rows:
        await cb.answer("Kutilayotgan so'rovlar yo'q!", show_alert=True)
        return
    text = "💸 <b>Kutilayotgan so'rovlar:</b>\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        text += f"• {r['first_name']} ({r['user_id']}) — {r['amount']} ball\n"
        b.button(text=f"✅ {r['id']}", callback_data=f"appr_{r['id']}")
        b.button(text=f"❌ {r['id']}", callback_data=f"rej_{r['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b)
