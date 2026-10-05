import os
import asyncio
import sqlite3
import random
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web
import logging

# ----------------- SOZLAMALAR -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8811849720:AAFK1yAFlJk3hKi9brRi1AFM5ZrzuSV3oKc")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "6713905538").split(",")]  # Admin ID lar
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-app.onrender.com/webhook") # Render URL
PORT = int(os.environ.get("PORT", 8080))

# ----------------- MA'LUMOTLAR BAZASI -----------------
def init_db():
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    # Foydalanuvchilar jadvali
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
    # Majburiy kanallar
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_username TEXT UNIQUE
    )''')
    # Tekshiruv savollari
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT
    )''')
    # Yechib olish so'rovlari
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    # Sozlamalar
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    # Standart sozlamalar
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('points_per_referral', '1')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_withdraw', '50')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('reward_type', 'stars')") # stars, gift, premium, sum
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- YORDAMCHI FUNKSIYALAR -----------------
def get_setting(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user(user_id, **kwargs):
    conn = get_db()
    c = conn.cursor()
    fields = ", ".join([f"{k}=?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    c.execute(f"UPDATE users SET {fields} WHERE user_id=?", values)
    conn.commit()
    conn.close()

def create_user(user_id, username, first_name, last_name, referrer_id=0):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, referrer_id, joined_at) 
        VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, username, first_name, last_name, referrer_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_all_channels():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT channel_username FROM channels")
    rows = c.fetchall()
    conn.close()
    return [row['channel_username'] for row in rows]

def add_channel(channel):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO channels (channel_username) VALUES (?)", (channel,))
    conn.commit()
    conn.close()

def remove_channel(channel):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE channel_username=?", (channel,))
    conn.commit()
    conn.close()

def get_random_question():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def add_question(question, answer):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()

def remove_question(q_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM questions WHERE id=?", (q_id,))
    conn.commit()
    conn.close()

def get_questions():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM questions")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ----------------- BOT VA DISPATCHER -----------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ----------------- HOLATLAR -----------------
class UserStates(StatesGroup):
    waiting_question_answer = State()
    waiting_withdraw_amount = State()

class AdminStates(StatesGroup):
    waiting_channel = State()
    waiting_question = State()
    waiting_question_answer = State()
    waiting_broadcast = State()
    waiting_points_user = State()
    waiting_points_amount = State()
    waiting_reward_type = State()

# ----------------- KLAVIATURALAR -----------------
def main_menu_keyboard(user_id):
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Profilim")
    builder.button(text="🔗 Referal linkim")
    builder.button(text="🏆 Reyting")
    builder.button(text="🎁 Kunlik bonus")
    builder.button(text="💰 Yechib olish")
    if user_id in ADMIN_IDS:
        builder.button(text="🛠 Admin Panel")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Kanallar", callback_data="admin_channels")
    builder.button(text="❓ Savollar", callback_data="admin_questions")
    builder.button(text="⚙️ Sozlamalar", callback_data="admin_settings")
    builder.button(text="📊 Statistika", callback_data="admin_stats")
    builder.button(text="📨 Xabar yuborish", callback_data="admin_broadcast")
    builder.button(text="💸 Yechib olish so'rovlari", callback_data="admin_withdrawals")
    builder.button(text="👤 Userni boshqarish", callback_data="admin_user_manage")
    builder.adjust(2)
    return builder.as_markup()

def channels_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Kanal qo'shish", callback_data="add_channel")
    builder.button(text="➖ Kanal o'chirish", callback_data="remove_channel_list")
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    return builder.as_markup()

def questions_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Savol qo'shish", callback_data="add_question")
    builder.button(text="➖ Savol o'chirish", callback_data="remove_question_list")
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    return builder.as_markup()

def settings_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 Referal ball miqdori", callback_data="set_points")
    builder.button(text="💰 Minimal yechib olish", callback_data="set_min_withdraw")
    builder.button(text="🎁 Mukofot turi", callback_data="set_reward_type")
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    return builder.as_markup()

# ----------------- MAJBURIY OBUNA TEKSHIRUVI -----------------
async def check_subscriptions(user_id):
    channels = get_all_channels()
    if not channels:
        return True
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except TelegramBadRequest:
            continue
        except Exception:
            continue
    return True

async def get_subscription_keyboard():
    channels = get_all_channels()
    builder = InlineKeyboardBuilder()
    for channel in channels:
        # Kanal username yoki linkini olish
        try:
            chat = await bot.get_chat(channel)
            link = chat.invite_link if chat.invite_link else f"https://t.me/{channel.replace('@', '')}"
        except:
            link = f"https://t.me/{channel.replace('@', '')}"
        builder.button(text=f"📢 {channel}", url=link)
    builder.button(text="✅ Tekshirish", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()

# ----------------- /start BUYRUG'I -----------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Referal ID ni aniqlash
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != user_id:  # O'zini o'zi taklif qilmasin
                referrer_id = ref_id
        except ValueError:
            pass
    
    # Foydalanuvchi bazada borligini tekshirish
    user = get_user(user_id)
    is_new = user is None
    
    if is_new:
        # Shubhali akkaunt tekshiruvi (username yo'q)
        is_suspicious = 1 if not username else 0
        create_user(user_id, username, first_name, last_name, referrer_id)
        if is_suspicious:
            update_user(user_id, is_suspicious=1)
    
    user = get_user(user_id)
    
    # Ban tekshiruvi
    if user['is_banned']:
        await message.answer("❌ Siz banlangansiz. Admin bilan bog'laning.")
        return
    
    # Majburiy obuna tekshiruvi
    if not await check_subscriptions(user_id):
        keyboard = await get_subscription_keyboard()
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=keyboard
        )
        return
    
    # Agar allaqachon verifikatsiya qilingan bo'lsa
    if user['is_verified']:
        await message.answer(
            f"Salom, {first_name}! 👋\n\nAsosiy menyu:",
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # Tekshiruv savolini yuborish
    question = get_random_question()
    if question:
        await message.answer(f"🤖 Iltimos, bot emasligingizni tasdiqlang:\n\n{question['question']}")
        await state.update_data(question_id=question['id'], referrer_id=referrer_id)
        await state.set_state(UserStates.waiting_question_answer)
    else:
        # Agar savol bo'lmasa, to'g'ridan-to'g'ri tasdiqlash
        update_user(user_id, is_verified=1)
        await message.answer(
            f"✅ Tasdiqlandi! Salom, {first_name}!",
            reply_markup=main_menu_keyboard(user_id)
        )

# ----------------- SAVOLGA JAVOB -----------------
@dp.message(StateFilter(UserStates.waiting_question_answer))
async def check_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get('question_id')
    referrer_id = data.get('referrer_id', 0)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT answer FROM questions WHERE id=?", (q_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        await message.answer("Xatolik yuz berdi. Qaytadan /start bosing.")
        await state.clear()
        return
    
    correct_answer = row['answer'].strip().lower()
    user_answer = message.text.strip().lower()
    
    if user_answer != correct_answer:
        await message.answer("❌ Noto'g'ri javob. Qaytadan urinib ko'ring: /start")
        await state.clear()
        return
    
    user_id = message.from_user.id
    update_user(user_id, is_verified=1)
    
    # Referal hisoblash (agar referrer_id mavjud bo'lsa)
    if referrer_id and referrer_id != user_id:
        referrer = get_user(referrer_id)
        if referrer and not referrer['is_banned']:
            points_per_ref = int(get_setting('points_per_referral', '1'))
            update_user(referrer_id, points=referrer['points'] + points_per_ref)
            # Log
            logging.info(f"Referal: {user_id} -> {referrer_id}, ball: {points_per_ref}")
    
    await state.clear()
    await message.answer(
        "✅ Tasdiqlandi! Endi botdan to'liq foydalanishingiz mumkin.",
        reply_markup=main_menu_keyboard(user_id)
    )

# ----------------- OBUNANI TEKSHIRISH -----------------
@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscriptions(user_id):
        await callback.message.delete()
        user = get_user(user_id)
        if not user['is_verified']:
            # Savolga o'tish
            question = get_random_question()
            if question:
                await callback.message.answer(f"🤖 Iltimos, bot emasligingizni tasdiqlang:\n\n{question['question']}")
                # State ni bu yerda boshqarish qiyin, shuning uchun oddiy yo'l
                # Aslida state ni callback da ishlatish uchun dp.message ishlatiladi
                # Bu yerda soddaroq yo'l tutamiz
                await callback.message.answer("Iltimos, /start buyrug'ini qaytadan bosing va savolga javob bering.")
            else:
                update_user(user_id, is_verified=1)
                await callback.message.answer("✅ Tasdiqlandi!", reply_markup=main_menu_keyboard(user_id))
        else:
            await callback.message.answer("✅ Obuna tasdiqlandi!", reply_markup=main_menu_keyboard(user_id))
    else:
        await callback.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

# ----------------- ASOSIY MENYU HANDLERLARI -----------------
@dp.message(F.text == "👤 Profilim")
async def profile(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    
    text = f"""👤 **Profilingiz**
    
🆔 ID: `{user['user_id']}`
👤 Ism: {user['first_name'] or 'N/A'}
🔗 Username: @{user['username'] if user['username'] else 'N/A'}
🎯 Ball: {user['points']}
📅 Qo'shilgan: {user['joined_at'][:10] if user['joined_at'] else 'N/A'}
✅ Tasdiqlangan: {'Ha' if user['is_verified'] else 'Yo\'q'}
⚠️ Shubhali: {'Ha' if user['is_suspicious'] else 'Yo\'q'}
"""
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🔗 Referal linkim")
async def referral_link(message: types.Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    # Taklif qilganlar soni
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM users WHERE referrer_id=? AND is_verified=1", (user_id,))
    ref_count = c.fetchone()['count']
    conn.close()
    
    text = f"""🔗 **Sizning referal linkingiz:**
    
`{link}`
    
👥 Taklif qilganlar: {ref_count}
🎯 Ball: {get_user(user_id)['points']}
    
Har bir tasdiqlangan referal uchun {get_setting('points_per_referral', '1')} ball olasiz!"""
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🏆 Reyting")
async def leaderboard(message: types.Message):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT user_id, first_name, points FROM users 
                 WHERE is_verified=1 AND is_banned=0 
                 ORDER BY points DESC LIMIT 10""")
    rows = c.fetchall()
    conn.close()
    
    text = "🏆 **Top 10 Referalchilar**\n\n"
    for i, row in enumerate(rows, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {row['first_name'] or 'N/A'} — {row['points']} ball\n"
    
    if not rows:
        text += "Hozircha hech kim yo'q."
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🎁 Kunlik bonus")
async def daily_bonus(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    
    # Oxirgi bonus sanasini tekshirish
    last_bonus = user.get('last_bonus')
    today = datetime.now().date().isoformat()
    
    if last_bonus == today:
        await message.answer("❌ Siz bugun allaqachon bonus oldingiz. Ertaga qaytadan urinib ko'ring!")
        return
    
    # Bonus berish (1 ball)
    bonus_amount = 1
    update_user(user_id, points=user['points'] + bonus_amount, last_bonus=today)
    await message.answer(f"🎁 Siz {bonus_amount} ball oldingiz! Jami: {user['points'] + bonus_amount} ball")

@dp.message(F.text == "💰 Yechib olish")
async def withdraw(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start buyrug'ini bosing.")
        return
    
    min_withdraw = int(get_setting('min_withdraw', '50'))
    if user['points'] < min_withdraw:
        await message.answer(f"❌ Yechib olish uchun kamida {min_withdraw} ball kerak. Sizda: {user['points']} ball")
        return
    
    await message.answer(f"💰 Yechib olmoqchi bo'lgan ball miqdorini kiriting (min: {min_withdraw}):")
    await state.set_state(UserStates.waiting_withdraw_amount)

@dp.message(StateFilter(UserStates.waiting_withdraw_amount))
async def process_withdraw(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Iltimos, faqat raqam kiriting.")
        return
    
    user = get_user(message.from_user.id)
    min_withdraw = int(get_setting('min_withdraw', '50'))
    
    if amount < min_withdraw:
        await message.answer(f"❌ Minimal miqdor: {min_withdraw}")
        return
    
    if amount > user['points']:
        await message.answer(f"❌ Sizda yetarli ball yo'q. Mavjud: {user['points']}")
        return
    
    # So'rov yaratish
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO withdrawals (user_id, amount, created_at) VALUES (?, ?, ?)",
              (user['user_id'], amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ {amount} ball yechib olish so'rovi yuborildi. Admin tasdiqlashini kuting.")

# ----------------- ADMIN PANEL -----------------
@dp.message(F.text == "🛠 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("🛠 **Admin Panel**\n\nKerakli bo'limni tanlang:", 
                         reply_markup=admin_menu_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    data = callback.data
    
    if data == "admin_back":
        await callback.message.edit_text("🛠 **Admin Panel**", reply_markup=admin_menu_keyboard(), parse_mode="Markdown")
        await callback.answer()
    
    elif data == "admin_channels":
        channels = get_all_channels()
        text = "📢 **Majburiy kanallar:**\n\n"
        text += "\n".join([f"• {ch}" for ch in channels]) if channels else "Hozircha kanal yo'q."
        await callback.message.edit_text(text, reply_markup=channels_menu_keyboard(), parse_mode="Markdown")
        await callback.answer()
    
    elif data == "add_channel":
        await callback.message.edit_text("📢 Kanal username ini kiriting (masalan: @mychannel):")
        await state.set_state(AdminStates.waiting_channel)
        await callback.answer()
    
    elif data == "remove_channel_list":
        channels = get_all_channels()
        if not channels:
            await callback.answer("❌ Kanallar yo'q!", show_alert=True)
            return
        builder = InlineKeyboardBuilder()
        for ch in channels:
            builder.button(text=f"❌ {ch}", callback_data=f"del_ch_{ch}")
        builder.button(text="⬅️ Orqaga", callback_data="admin_channels")
        builder.adjust(1)
        await callback.message.edit_text("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=builder.as_markup())
        await callback.answer()
    
    elif data.startswith("del_ch_"):
        ch = data.replace("del_ch_", "")
        remove_channel(ch)
        await callback.answer(f"✅ {ch} o'chirildi!")
        # Yangilash
        channels = get_all_channels()
        text = "📢 **Majburiy kanallar:**\n\n"
        text += "\n".join([f"• {ch}" for ch in channels]) if channels else "Hozircha kanal yo'q."
        await callback.message.edit_text(text, reply_markup=channels_menu_keyboard(), parse_mode="Markdown")
    
    elif data == "admin_questions":
        questions = get_questions()
        text = "❓ **Tekshiruv savollari:**\n\n"
        if questions:
            for q in questions:
                text += f"• {q['question']} → {q['answer']}\n"
        else:
            text += "Hozircha savol yo'q."
        await callback.message.edit_text(text, reply_markup=questions_menu_keyboard(), parse_mode="Markdown")
        await callback.answer()
    
    elif data == "add_question":
        await callback.message.edit_text("❓ Savolni kiriting:")
        await state.set_state(AdminStates.waiting_question)
        await callback.answer()
    
    elif data == "remove_question_list":
        questions = get_questions()
        if not questions:
            await callback.answer("❌ Savollar yo'q!", show_alert=True)
            return
        builder = InlineKeyboardBuilder()
        for q in questions:
            builder.button(text=f"❌ {q['question'][:30]}...", callback_data=f"del_q_{q['id']}")
        builder.button(text="⬅️ Orqaga", callback_data="admin_questions")
        builder.adjust(1)
        await callback.message.edit_text("O'chirmoqchi bo'lgan savolni tanlang:", reply_markup=builder.as_markup())
        await callback.answer()
    
    elif data.startswith("del_q_"):
        q_id = int(data.replace("del_q_", ""))
        remove_question(q_id)
        await callback.answer("✅ Savol o'chirildi!")
        questions = get_questions()
        text = "❓ **Tekshiruv savollari:**\n\n"
        if questions:
            for q in questions:
                text += f"• {q['question']} → {q['answer']}\n"
        else:
            text += "Hozircha savol yo'q."
        await callback.message.edit_text(text, reply_markup=questions_menu_keyboard(), parse_mode="Markdown")
    
    elif data == "admin_settings":
        points_per_ref = get_setting('points_per_referral', '1')
        min_withdraw = get_setting('min_withdraw', '50')
        reward_type = get_setting('reward_type', 'stars')
        text = f"""⚙️ **Sozlamalar**
        
🎯 Referal ball: {points_per_ref}
💰 Minimal yechib olish: {min_withdraw}
🎁 Mukofot turi: {reward_type}"""
        await callback.message.edit_text(text, reply_markup=settings_menu_keyboard(), parse_mode="Markdown")
        await callback.answer()
    
    elif data == "set_points":
        await callback.message.edit_text("🎯 Referal uchun ball miqdorini kiriting:")
        await state.set_state(AdminStates.waiting_points_amount)
        await state.update_data(setting_type="points_per_referral")
        await callback.answer()
    
    elif data == "set_min_withdraw":
        await callback.message.edit_text("💰 Minimal yechib olish miqdorini kiriting:")
        await state.set_state(AdminStates.waiting_points_amount)
        await state.update_data(setting_type="min_withdraw")
        await callback.answer()
    
    elif data == "set_reward_type":
        builder = InlineKeyboardBuilder()
        builder.button(text="⭐ Stars", callback_data="reward_stars")
        builder.button(text="🎁 Gift", callback_data="reward_gift")
        builder.button(text="💎 Premium", callback_data="reward_premium")
        builder.button(text="💰 Sum", callback_data="reward_sum")
        builder.button(text="⬅️ Orqaga", callback_data="admin_settings")
        builder.adjust(2)
        await callback.message.edit_text("🎁 Mukofot turini tanlang:", reply_markup=builder.as_markup())
        await callback.answer()
    
    elif data.startswith("reward_"):
        reward_type = data.replace("reward_", "")
        set_setting('reward_type', reward_type)
        await callback.answer(f"✅ Mukofot turi: {reward_type}")
        await callback.message.edit_text("✅ Sozlamalar yangilandi!", reply_markup=settings_menu_keyboard())
    
    elif data == "admin_stats":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as total FROM users")
        total = c.fetchone()['total']
        c.execute("SELECT COUNT(*) as verified FROM users WHERE is_verified=1")
        verified = c.fetchone()['verified']
        c.execute("SELECT COUNT(*) as banned FROM users WHERE is_banned=1")
        banned = c.fetchone()['banned']
        c.execute("SELECT COUNT(*) as suspicious FROM users WHERE is_suspicious=1")
        suspicious = c.fetchone()['suspicious']
        conn.close()
        
        text = f"""📊 **Statistika**
        
👥 Jami foydalanuvchilar: {total}
✅ Tasdiqlangan: {verified}
🚫 Banlangan: {banned}
⚠️ Shubhali: {suspicious}"""
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Orqaga", callback_data="admin_back")
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()
    
    elif data == "admin_broadcast":
        await callback.message.edit_text("📨 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni kiriting:")
        await state.set_state(AdminStates.waiting_broadcast)
        await callback.answer()
    
    elif data == "admin_withdrawals":
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT w.id, w.user_id, w.amount, u.first_name 
                     FROM withdrawals w 
                     JOIN users u ON w.user_id = u.user_id 
                     WHERE w.status='pending'""")
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            await callback.answer("❌ Kutilayotgan so'rovlar yo'q!", show_alert=True)
            return
        
        builder = InlineKeyboardBuilder()
        for row in rows:
            builder.button(
                text=f"✅ {row['first_name']} - {row['amount']} ball",
                callback_data=f"approve_w_{row['id']}"
            )
            builder.button(
                text=f"❌ Rad etish",
                callback_data=f"reject_w_{row['id']}"
            )
        builder.button(text="⬅️ Orqaga", callback_data="admin_back")
        builder.adjust(1)
        await callback.message.edit_text("💸 **Kutilayotgan yechib olish so'rovlari:**", 
                                         reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()
    
    elif data.startswith("approve_w_"):
        w_id = int(data.replace("approve_w_", ""))
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM withdrawals WHERE id=?", (w_id,))
        w = c.fetchone()
        if w:
            # Ballarni ayirish
            user = get_user(w['user_id'])
            if user and user['points'] >= w['amount']:
                update_user(w['user_id'], points=user['points'] - w['amount'])
                c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (w_id,))
                conn.commit()
                await callback.answer("✅ Tasdiqlandi!")
                # Foydalanuvchiga xabar
                try:
                    await bot.send_message(w['user_id'], f"✅ Sizning {w['amount']} ball yechib olish so'rovingiz tasdiqlandi!")
                except:
                    pass
            else:
                await callback.answer("❌ Foydalanuvchida yetarli ball yo'q!", show_alert=True)
        conn.close()
        # Ro'yxatni yangilash
        await callback.message.edit_text("✅ So'rov tasdiqlandi. /admin buyrug'i orqali qayta kiriting.")
    
    elif data.startswith("reject_w_"):
        w_id = int(data.replace("reject_w_", ""))
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (w_id,))
        conn.commit()
        conn.close()
        await callback.answer("❌ Rad etildi!")
        await callback.message.edit_text("❌ So'rov rad etildi.")
    
    elif data == "admin_user_manage":
        await callback.message.edit_text("👤 Foydalanuvchi ID sini kiriting:")
        await state.set_state(AdminStates.waiting_points_user)
        await callback.answer()

# ----------------- ADMIN STATE HANDLERLARI -----------------
@dp.message(StateFilter(AdminStates.waiting_channel))
async def process_channel(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    channel = message.text.strip()
    if not channel.startswith("@"):
        channel = "@" + channel
    add_channel(channel)
    await state.clear()
    await message.answer(f"✅ {channel} qo'shildi!")
    await admin_panel(message)

@dp.message(StateFilter(AdminStates.waiting_question))
async def process_question(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(question_text=message.text)
    await message.answer("Endi bu savolning to'g'ri javobini kiriting:")
    await state.set_state(AdminStates.waiting_question_answer)

@dp.message(StateFilter(AdminStates.waiting_question_answer))
async def process_question_answer(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    question = data.get('question_text')
    answer = message.text.strip()
    add_question(question, answer)
    await state.clear()
    await message.answer("✅ Savol qo'shildi!")
    await admin_panel(message)

@dp.message(StateFilter(AdminStates.waiting_points_amount))
async def process_points_setting(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    setting_type = data.get('setting_type')
    try:
        value = int(message.text)
    except ValueError:
        await message.answer("❌ Iltimos, raqam kiriting.")
        return
    set_setting(setting_type, value)
    await state.clear()
    await message.answer(f"✅ Sozlama yangilandi: {setting_type} = {value}")
    await admin_panel(message)

@dp.message(StateFilter(AdminStates.waiting_broadcast))
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user['user_id'])
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    
    await message.answer(f"📨 Xabar yuborildi!\n✅ Muvaffaqiyatli: {success}\n❌ Xato: {failed}")
    await admin_panel(message)

@dp.message(StateFilter(AdminStates.waiting_points_user))
async def process_user_manage(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri ID kiriting.")
        return
    
    user = get_user(user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Ban", callback_data=f"ban_{user_id}")
    builder.button(text="✅ Unban", callback_data=f"unban_{user_id}")
    builder.button(text="➕ Ball qo'shish", callback_data=f"addpoints_{user_id}")
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    builder.adjust(2)
    
    text = f"""👤 **Foydalanuvchi ma'lumotlari:**
    
ID: `{user['user_id']}`
Ism: {user['first_name']}
Ball: {user['points']}
Ban: {'Ha' if user['is_banned'] else 'Yo\'q'}"""
    
    await state.clear()
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ban_"))
async def ban_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    user_id = int(callback.data.replace("ban_", ""))
    update_user(user_id, is_banned=1)
    await callback.answer("✅ Banlandi!")
    await callback.message.edit_text(f"✅ Foydalanuvchi {user_id} banlandi.")

@dp.callback_query(F.data.startswith("unban_"))
async def unban_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    user_id = int(callback.data.replace("unban_", ""))
    update_user(user_id, is_banned=0)
    await callback.answer("✅ Unbanlandi!")
    await callback.message.edit_text(f"✅ Foydalanuvchi {user_id} unbanlandi.")

# ----------------- WEBHOOK VA RENDER SOZLAMALARI -----------------
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

async def handle_webhook(request):
    try:
        update = types.Update.model_validate(await request.json())
        await dp.feed_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return web.Response(status=500)

async def health_check(request):
    return web.Response(text="OK", status=200)

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_get("/health", health_check)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    logging.info(f"Bot started on port {PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
