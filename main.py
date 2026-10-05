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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web

# ----------------- SOZLAMALAR -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8811849720:AAFK1yAFlJk3hKi9brRi1AFM5ZrzuSV3oKc")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "6713905538").split(",") if x.strip().isdigit()]
PORT = int(os.environ.get("PORT", 8080))
USE_WEBHOOK = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ----------------- MA'LUMOTLAR BAZASI -----------------
DB_PATH = "bot_data.db"

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
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language TEXT DEFAULT 'uz',
        points INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        is_suspicious INTEGER DEFAULT 0,
        joined_at TEXT,
        last_bonus TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_username TEXT UNIQUE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    # Standart sozlamalar
    defaults = {
        'points_per_referral': '5',
        'min_withdraw': '50',
        'reward_type': 'stars',
        'daily_bonus': '1',
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    # Standart savol
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)",
                  ("2 + 2 nechaga teng? (raqamda yozing)", "4"))
        c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)",
                  ("O'zbekiston poytaxti? (kichik harfda)", "toshkent"))
    conn.commit()
    conn.close()
    logger.info("Ma'lumotlar bazasi tayyor.")

def get_setting(key, default=None):
    row = db_exec("SELECT value FROM settings WHERE key=?", (key,), fetch=True)
    return row['value'] if row else default

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

def get_all_channels():
    rows = db_exec("SELECT channel_username FROM channels", fetchall=True)
    return [r['channel_username'] for r in rows] if rows else []

def add_channel(channel):
    db_exec("INSERT OR IGNORE INTO channels (channel_username) VALUES (?)", (channel,))

def remove_channel(channel):
    db_exec("DELETE FROM channels WHERE channel_username=?", (channel,))

def get_random_question():
    row = db_exec("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1", fetch=True)
    return dict(row) if row else None

def get_question_by_id(q_id):
    row = db_exec("SELECT * FROM questions WHERE id=?", (q_id,), fetch=True)
    return dict(row) if row else None

def add_question(question, answer):
    db_exec("INSERT INTO questions (question, answer) VALUES (?, ?)", (question, answer))

def remove_question(q_id):
    db_exec("DELETE FROM questions WHERE id=?", (q_id,))

def get_questions():
    rows = db_exec("SELECT * FROM questions", fetchall=True)
    return [dict(r) for r in rows] if rows else []

# ----------------- BOT VA DISPATCHER -----------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ----------------- HOLATLAR -----------------
class UserStates(StatesGroup):
    waiting_answer = State()
    waiting_withdraw = State()

class AdminStates(StatesGroup):
    waiting_channel = State()
    waiting_question = State()
    waiting_question_answer = State()
    waiting_broadcast = State()
    waiting_setting_value = State()
    waiting_user_id = State()
    waiting_points_amount = State()
    waiting_user_message = State()

# ----------------- KLAVIATURALAR -----------------
def main_menu(user_id):
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Profilim")
    b.button(text="🔗 Referal linkim")
    b.button(text="🏆 Reyting")
    b.button(text="🎁 Kunlik bonus")
    b.button(text="💰 Yechib olish")
    if user_id in ADMIN_IDS:
        b.button(text="🛠 Admin Panel")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)

def admin_menu():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanallar", callback_data="admin_channels")
    b.button(text="❓ Savollar", callback_data="admin_questions")
    b.button(text="⚙️ Sozlamalar", callback_data="admin_settings")
    b.button(text="📊 Statistika", callback_data="admin_stats")
    b.button(text="📨 Broadcast", callback_data="admin_broadcast")
    b.button(text="💸 Yechib olish", callback_data="admin_withdrawals")
    b.button(text="👤 User boshqarish", callback_data="admin_users")
    b.adjust(2)
    return b.as_markup()

# ----------------- OBUNA TEKSHIRUVI -----------------
async def check_subscriptions(user_id):
    channels = get_all_channels()
    if not channels:
        return True
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except TelegramBadRequest as e:
            logger.warning(f"Kanal tekshirishda xato ({channel}): {e}")
            continue
        except Exception as e:
            logger.warning(f"Kanal tekshirishda kutilmagan xato ({channel}): {e}")
            continue
    return True

async def subscription_keyboard():
    channels = get_all_channels()
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

# ----------------- /start -----------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name or "Foydalanuvchi"
    last_name = message.from_user.last_name

    # Referal ID
    args = message.text.split(maxsplit=1)
    referrer_id = 0
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != user_id:
                referrer_id = ref_id
        except ValueError:
            pass

    user = get_user(user_id)
    if user is None:
        is_suspicious = 0 if username else 1
        create_user(user_id, username, first_name, last_name, referrer_id)
        if is_suspicious:
            update_user(user_id, is_suspicious=1)
        user = get_user(user_id)

    if user['is_banned']:
        await message.answer("❌ Siz banlangansiz.")
        return

    # Obuna tekshirish
    if not await check_subscriptions(user_id):
        kb = await subscription_keyboard()
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=kb
        )
        return

    # Verifikatsiya tekshiruvi
    if user['is_verified']:
        await message.answer(
            f"Salom, {first_name}! 👋\n\nAsosiy menyu:",
            reply_markup=main_menu(user_id)
        )
        return

    # Savol berish
    q = get_random_question()
    if not q:
        update_user(user_id, is_verified=1)
        await message.answer(
            f"✅ Tasdiqlandi! Salom, {first_name}!",
            reply_markup=main_menu(user_id)
        )
        return

    await state.update_data(question_id=q['id'], referrer_id=referrer_id)
    await state.set_state(UserStates.waiting_answer)
    await message.answer(
        f"🤖 Iltimos, bot emasligingizni tasdiqlang:\n\n❓ {q['question']}"
    )

# ----------------- JAVOBNI TEKSHIRISH -----------------
@dp.message(UserStates.waiting_answer)
async def check_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get('question_id')
    referrer_id = data.get('referrer_id', 0)

    q = get_question_by_id(q_id) if q_id else None
    if not q:
        await state.clear()
        await message.answer("Xatolik. /start ni qaytadan bosing.")
        return

    if message.text.strip().lower() != q['answer'].strip().lower():
        await message.answer("❌ Noto'g'ri javob. Qaytadan: /start")
        await state.clear()
        return

    user_id = message.from_user.id
    update_user(user_id, is_verified=1)

    # Referal hisoblash
    if referrer_id and referrer_id != user_id:
        referrer = get_user(referrer_id)
        if referrer and not referrer['is_banned']:
            # Anti-fraud: faqat bir marta hisoblash
            already = db_exec(
                "SELECT 1 FROM users WHERE user_id=? AND referrer_id=?",
                (user_id, referrer_id), fetch=True
            )
            points = int(get_setting('points_per_referral', '5'))
            update_user(referrer_id, points=referrer['points'] + points)
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Yangi referal! +{points} ball.\nJami: {referrer['points'] + points} ball"
                )
            except Exception:
                pass

    await state.clear()
    await message.answer(
        "✅ Tasdiqlandi! Endi botdan foydalanishingiz mumkin.",
        reply_markup=main_menu(user_id)
    )

# ----------------- OBUNA TEKSHIRISH CALLBACK -----------------
@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Hali barcha kanallarga obuna emassiz!", show_alert=True)
        return

    await callback.answer("✅ Obuna tasdiqlandi!")
    try:
        await callback.message.delete()
    except Exception:
        pass

    user = get_user(user_id)
    if user and user['is_verified']:
        await callback.message.answer("Asosiy menyu:", reply_markup=main_menu(user_id))
        return

    q = get_random_question()
    if not q:
        update_user(user_id, is_verified=1)
        await callback.message.answer("✅ Tasdiqlandi!", reply_markup=main_menu(user_id))
        return

    await state.update_data(question_id=q['id'], referrer_id=user['referrer_id'] if user else 0)
    await state.set_state(UserStates.waiting_answer)
    await callback.message.answer(f"🤖 Bot emasligingizni tasdiqlang:\n\n❓ {q['question']}")

# ----------------- MENYU HANDLERLARI -----------------
@dp.message(F.text == "👤 Profilim")
async def profile(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    # Referal soni
    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND is_verified=1",
                   (user['user_id'],), fetch=True)
    ref_count = refs['c'] if refs else 0
    text = (
        f"👤 <b>Profilingiz</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Ism: {user['first_name'] or 'N/A'}\n"
        f"🔗 Username: @{user['username'] if user['username'] else 'yo\'q'}\n"
        f"🎯 Ball: {user['points']}\n"
        f"👥 Referallar: {ref_count}\n"
        f"✅ Tasdiqlangan: {'Ha' if user['is_verified'] else 'Yo\'q'}\n"
        f"📅 Qo'shilgan: {user['joined_at'][:10] if user['joined_at'] else 'N/A'}"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🔗 Referal linkim")
async def ref_link(message: types.Message):
    user_id = message.from_user.id
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user_id}"
    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND is_verified=1",
                   (user_id,), fetch=True)
    ref_count = refs['c'] if refs else 0
    points = int(get_setting('points_per_referral', '5'))
    user = get_user(user_id)
    text = (
        f"🔗 <b>Sizning referal linkingiz:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Taklif qilganlar: {ref_count}\n"
        f"🎯 Ball: {user['points'] if user else 0}\n\n"
        f"Har bir tasdiqlangan referal uchun <b>{points} ball</b> olasiz!"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🏆 Reyting")
async def leaderboard(message: types.Message):
    rows = db_exec("""SELECT first_name, points FROM users 
                      WHERE is_verified=1 AND is_banned=0 
                      ORDER BY points DESC LIMIT 10""", fetchall=True)
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
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    today = datetime.now().date().isoformat()
    if user.get('last_bonus') == today:
        await message.answer("❌ Siz bugun allaqachon bonus oldingiz!")
        return
    bonus = int(get_setting('daily_bonus', '1'))
    update_user(user_id, points=user['points'] + bonus, last_bonus=today)
    await message.answer(f"🎁 Siz {bonus} ball oldingiz!\nJami: {user['points'] + bonus} ball")

@dp.message(F.text == "💰 Yechib olish")
async def withdraw_start(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    min_w = int(get_setting('min_withdraw', '50'))
    if user['points'] < min_w:
        await message.answer(f"❌ Minimal: {min_w} ball. Sizda: {user['points']}")
        return
    await message.answer(f"💰 Yechib olmoqchi bo'lgan ball miqdorini kiriting (min: {min_w}):")
    await state.set_state(UserStates.waiting_withdraw)

@dp.message(UserStates.waiting_withdraw)
async def withdraw_process(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return
    user = get_user(message.from_user.id)
    min_w = int(get_setting('min_withdraw', '50'))
    if amount < min_w:
        await message.answer(f"❌ Minimal: {min_w}")
        return
    if amount > user['points']:
        await message.answer(f"❌ Yetarli emas. Sizda: {user['points']}")
        return
    db_exec("INSERT INTO withdrawals (user_id, amount, created_at) VALUES (?, ?, ?)",
            (user['user_id'], amount, datetime.now().isoformat()))
    await state.clear()
    await message.answer(f"✅ {amount} ball yechib olish so'rovi yuborildi. Admin tasdiqlashini kuting.")
    # Adminga xabar
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"💸 Yangi so'rov!\nUser: {user['first_name']} ({user['user_id']})\nMiqdor: {amount} ball")
        except Exception:
            pass

# ----------------- ADMIN PANEL -----------------
@dp.message(Command("admin"))
@dp.message(F.text == "🛠 Admin Panel")
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer("🛠 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_back")
async def admin_back(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await cb.message.edit_text("🛠 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "admin_channels")
async def admin_channels(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    channels = get_all_channels()
    text = "📢 <b>Majburiy kanallar:</b>\n\n"
    text += "\n".join([f"• {ch}" for ch in channels]) if channels else "Hozircha kanal yo'q."
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_channel")
    b.button(text="➖ O'chirish", callback_data="del_channel_list")
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text("📢 Kanal username kiriting (masalan: @mychannel):")
    await state.set_state(AdminStates.waiting_channel)
    await cb.answer()

@dp.message(AdminStates.waiting_channel)
async def add_channel_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    add_channel(ch)
    await state.clear()
    await message.answer(f"✅ {ch} qo'shildi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data == "del_channel_list")
async def del_channel_list(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    channels = get_all_channels()
    if not channels:
        await cb.answer("Kanallar yo'q!", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.button(text=f"❌ {ch}", callback_data=f"delch_{ch}")
    b.button(text="⬅️ Orqaga", callback_data="admin_channels")
    b.adjust(1)
    await cb.message.edit_text("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("delch_"))
async def del_channel_do(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    ch = cb.data.replace("delch_", "")
    remove_channel(ch)
    await cb.answer(f"✅ {ch} o'chirildi!")
    channels = get_all_channels()
    text = "📢 <b>Majburiy kanallar:</b>\n\n"
    text += "\n".join([f"• {c}" for c in channels]) if channels else "Hozircha kanal yo'q."
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_channel")
    b.button(text="➖ O'chirish", callback_data="del_channel_list")
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_questions")
async def admin_questions(cb: types.CallbackQuery):
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
    b.button(text="➕ Qo'shish", callback_data="add_question")
    b.button(text="➖ O'chirish", callback_data="del_question_list")
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "add_question")
async def add_question_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text("❓ Savolni kiriting:")
    await state.set_state(AdminStates.waiting_question)
    await cb.answer()

@dp.message(AdminStates.waiting_question)
async def add_question_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(q_text=message.text.strip())
    await message.answer("Endi to'g'ri javobni kiriting:")
    await state.set_state(AdminStates.waiting_question_answer)

@dp.message(AdminStates.waiting_question_answer)
async def add_question_answer(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    add_question(data.get('q_text'), message.text.strip())
    await state.clear()
    await message.answer("✅ Savol qo'shildi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data == "del_question_list")
async def del_question_list(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    qs = get_questions()
    if not qs:
        await cb.answer("Savollar yo'q!", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for q in qs:
        b.button(text=f"❌ {q['question'][:40]}", callback_data=f"delq_{q['id']}")
    b.button(text="⬅️ Orqaga", callback_data="admin_questions")
    b.adjust(1)
    await cb.message.edit_text("O'chirmoqchi bo'lgan savolni tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("delq_"))
async def del_question_do(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    q_id = int(cb.data.replace("delq_", ""))
    remove_question(q_id)
    await cb.answer("✅ O'chirildi!")
    await admin_questions(cb)

@dp.callback_query(F.data == "admin_settings")
async def admin_settings(cb: types.CallbackQuery):
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
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.in_({"set_points", "set_minw", "set_daily"}))
async def set_setting_start(cb: types.CallbackQuery, state: FSMContext):
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
    await state.set_state(AdminStates.waiting_setting_value)
    await cb.answer()

@dp.message(AdminStates.waiting_setting_value)
async def set_setting_value(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return
    data = await state.get_data()
    set_setting(data['setting_key'], val)
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
    b.button(text="⬅️ Orqaga", callback_data="admin_settings")
    b.adjust(2)
    await cb.message.edit_text("🎁 Mukofot turini tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("rt_"))
async def set_reward_do(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    t = cb.data.replace("rt_", "")
    set_setting('reward_type', t)
    await cb.answer(f"✅ {t}")
    await admin_settings(cb)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    total = db_exec("SELECT COUNT(*) AS c FROM users", fetch=True)['c']
    verified = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_verified=1", fetch=True)['c']
    banned = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_banned=1", fetch=True)['c']
    susp = db_exec("SELECT COUNT(*) AS c FROM users WHERE is_suspicious=1", fetch=True)['c']
    pending = db_exec("SELECT COUNT(*) AS c FROM withdrawals WHERE status='pending'", fetch=True)['c']
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami: {total}\n"
        f"✅ Tasdiqlangan: {verified}\n"
        f"🚫 Ban: {banned}\n"
        f"⚠️ Shubhali: {susp}\n"
        f"💸 Kutilayotgan so'rovlar: {pending}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text(
        "📨 Yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "(Forward ham, oddiy matn ham bo'ladi)"
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await cb.answer()

@dp.message(AdminStates.waiting_broadcast)
async def broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    users = db_exec("SELECT user_id FROM users WHERE is_banned=0", fetchall=True) or []
    success = 0
    failed = 0
    for u in users:
        try:
            await message.copy_to(chat_id=u['user_id'])
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await message.answer(f"📨 Yuborildi!\n✅ {success}\n❌ {failed}")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    rows = db_exec("""SELECT w.id, w.user_id, w.amount, u.first_name 
                      FROM withdrawals w JOIN users u ON w.user_id=u.user_id 
                      WHERE w.status='pending'""", fetchall=True) or []
    if not rows:
        await cb.answer("Kutilayotgan so'rovlar yo'q!", show_alert=True)
        return
    text = "💸 <b>Kutilayotgan so'rovlar:</b>\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        text += f"• {r['first_name']} ({r['user_id']}) — {r['amount']} ball\n"
        b.button(text=f"✅ {r['id']} tasdiq", callback_data=f"appr_{r['id']}")
        b.button(text=f"❌ {r['id']} rad", callback_data=f"rej_{r['id']}")
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    b.adjust(2)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("appr_"))
async def approve_w(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    w_id = int(cb.data.replace("appr_", ""))
    w = db_exec("SELECT * FROM withdrawals WHERE id=?", (w_id,), fetch=True)
    if not w:
        await cb.answer("Topilmadi!", show_alert=True)
        return
    user = get_user(w['user_id'])
    if not user or user['points'] < w['amount']:
        await cb.answer("❌ Foydalanuvchida yetarli ball yo'q!", show_alert=True)
        return
    update_user(w['user_id'], points=user['points'] - w['amount'])
    db_exec("UPDATE withdrawals SET status='approved' WHERE id=?", (w_id,))
    await cb.answer("✅ Tasdiqlandi!")
    try:
        await bot.send_message(w['user_id'], f"✅ {w['amount']} ball yechib olish tasdiqlandi!")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("rej_"))
async def reject_w(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    w_id = int(cb.data.replace("rej_", ""))
    db_exec("UPDATE withdrawals SET status='rejected' WHERE id=?", (w_id,))
    await cb.answer("❌ Rad etildi!")

@dp.callback_query(F.data == "admin_users")
async def admin_users(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await cb.message.edit_text("👤 Foydalanuvchi ID sini kiriting:")
    await state.set_state(AdminStates.waiting_user_id)
    await cb.answer()

@dp.message(AdminStates.waiting_user_id)
async def admin_user_info(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
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
    b.button(text="🚫 Ban" if not user['is_banned'] else "✅ Unban",
             callback_data=f"tog_{uid}")
    b.button(text="➕ Ball qo'shish", callback_data=f"adp_{uid}")
    b.button(text="✉️ Xabar yuborish", callback_data=f"msg_{uid}")
    b.button(text="⬅️ Orqaga", callback_data="admin_back")
    b.adjust(2)
    text = (
        f"👤 <b>Foydalanuvchi:</b>\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Ism: {user['first_name']}\n"
        f"Username: @{user['username'] or 'yoq'}\n"
        f"Ball: {user['points']}\n"
        f"Ban: {'Ha' if user['is_banned'] else 'Yo\\'q'}\n"
        f"Tasdiqlangan: {'Ha' if user['is_verified'] else 'Yo\\'q'}"
    )
    await message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tog_"))
async def toggle_ban(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    uid = int(cb.data.replace("tog_", ""))
    user = get_user(uid)
    if not user:
        return
    update_user(uid, is_banned=0 if user['is_banned'] else 1)
    await cb.answer("✅ O'zgartirildi!")
    await admin_users(cb, None)

@dp.callback_query(F.data.startswith("adp_"))
async def add_points_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    uid = int(cb.data.replace("adp_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("➕ Qancha ball qo'shilsin? (manfiy ham mumkin)")
    await state.set_state(AdminStates.waiting_points_amount)
    await cb.answer()

@dp.message(AdminStates.waiting_points_amount)
async def add_points_do(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return
    data = await state.get_data()
    uid = data['target_uid']
    user = get_user(uid)
    if not user:
        await message.answer("❌ Topilmadi.")
        return
    new_points = max(0, user['points'] + amount)
    update_user(uid, points=new_points)
    await state.clear()
    await message.answer(f"✅ Yangi ball: {new_points}")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    uid = int(cb.data.replace("msg_", ""))
    await state.update_data(target_uid=uid)
    await cb.message.edit_text("✉️ Yubormoqchi bo'lgan xabaringizni yozing:")
    await state.set_state(AdminStates.waiting_user_message)
    await cb.answer()

@dp.message(AdminStates.waiting_user_message)
async def user_msg_send(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    uid = data['target_uid']
    try:
        await message.copy_to(chat_id=uid)
        await message.answer("✅ Yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
    await state.clear()
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu())

# ----------------- HEALTH CHECK + POLLING/WEBHOOK -----------------
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
    await bot.delete_webhook(drop_pending_updates=True)  # Konfliktni oldini oladi

    if USE_WEBHOOK and WEBHOOK_URL:
        # Webhook rejimi (ixtiyoriy)
        from aiohttp import web as aio_web
        app = aio_web.Application()

        async def webhook_handler(request):
            try:
                data = await request.json()
                update = types.Update.model_validate(data, context={"bot": bot})
                await dp.feed_update(bot, update)
            except Exception as e:
                logger.exception(f"Webhook xato: {e}")
            return aio_web.Response(text="OK")

        app.router.add_post("/webhook", webhook_handler)
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        runner = aio_web.AppRunner(app)
        await runner.setup()
        site = aio_web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")
        await asyncio.Event().wait()
    else:
        # Polling rejimi (tavsiya etiladi)
        logger.info("Polling rejimida ishga tushmoqda...")
        asyncio.create_task(start_web())  # Render health check uchun
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
