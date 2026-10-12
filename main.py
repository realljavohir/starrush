"""
main.py - StarRush Bot (to'liq)
"""
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
from urllib.parse import parse_qsl, quote

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
    BufferedInputFile, WebAppInfo, LabeledPrice,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web

from telethon import TelegramClient, functions, types as tt
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

import security
from security import adb as _adb

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
MIN_DONATE = 1
MAX_DONATE = 100000
UZ_PHONE_RE = re.compile(r"^998\d{9}$")
BONUS_REWARDS = [1, 1, 2, 2, 3, 3, 4]

# ═══════════════════════════════════════════════════════════
# DIZAYN
# ═══════════════════════════════════════════════════════════
DIV = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
BOX_MID = DIV
BOX_BOTTOM = ""


def box_title(title):
    return f"<b>{title}</b>\n{DIV}"


def kv(icon, label, value):
    return f"{icon} <b>{label}:</b> {value}"


def progress_bar(cur, lo, hi, width=12):
    if hi >= 999_999_999 or hi <= lo:
        return "▰" * width, 100
    pct = max(0, min(100, int((cur - lo) / (hi - lo) * 100)))
    filled = round(pct / 100 * width)
    return "▰" * filled + "▱" * (width - filled), pct


def format_number(n):
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


def esc(s):
    return html.escape(str(s)) if s is not None else ""


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


def _next_level(stars):
    for l in get_levels():
        if l["min_stars"] > stars:
            return l
    return None

# ═══════════════════════════════════════════════════════════
# TILLAR
# ═══════════════════════════════════════════════════════════
LANGS = {
    "uz": {
        "flag": "🇺🇿", "name": "O'zbekcha",
        "choose_lang": f"🌐 <b>TILNI TANLANG</b>\n{DIV}\nIltimos, o'zingizga qulay tilni tanlang 👇",
        "lang_set": "✅ <b>Til muvaffaqiyatli o'zgartirildi!</b>",
        "welcome": (
            "✨ <b>Xush kelibsiz, {name}!</b>\n" + DIV + "\n"
            "🚀 <b>StarRush</b> — Stars yig'ish platformasi\n\n"
            "👥  Do'stlarni taklif qiling\n"
            "🎁  Stars to'plab, Gift oling\n"
            "🔥  Kunlik bonus va vazifalar\n"
            "🏆  Reytingda birinchi bo'ling\n" + DIV + "\n"
            "Kerakli bo'limni tanlang 👇"
        ),
        "menu_title": f"🏠 <b>ASOSIY MENYU</b>\n{DIV}\n👇 Kerakli bo'limni tanlang:",
        "profile": "👤 Profilim", "stats": "📊 Statistika", "banner": "🎨 Banner",
        "webapp": "🚀 Mini App", "ref_link": "🔗 Referal linkim", "rating": "🏆 Reyting",
        "withdraw": "💰 Yechib olish", "donate": "💝 Donat qilish",
        "support": "💬 Admin bilan aloqa", "gift_stars": "🎁 Stars sovg'a",
        "review": "⭐ Sharh qoldirish", "admin": "🛠 Admin Panel",
        "share": "📤 Havolani ulashish", "back": "⬅️ Orqaga", "menu": "🏠 Asosiy menyu",
        "cancel": "❌ Bekor qilish", "close_chat": "🔚 Suhbatni tugatish",
        "more_btn": "⚙️ Ko'proq",
        "more_title": f"⚙️ <b>KO'PROQ</b>\n{DIV}\nQo'shimcha bo'limlar 👇",
        "history": "📜 So'rovlarim",
        "remind_on": "🔔 Eslatma: yoqilgan", "remind_off": "🔕 Eslatma: o'chiq",
        "banned": f"🚫 <b>SIZ BANLANGANSIZ!</b>\n{DIV}\nAdmin bilan bog'laning.",
        "subscribe": f"📢 <b>KANALLARGA OBUNA BO'LING</b>\n{DIV}\nBotdan foydalanish uchun kanallarga obuna bo'ling.\n\nObuna bo'lgach «✅ Tekshirish» tugmasini bosing 👇",
        "check": "✅ Tekshirish",
        "bot_check": f"🤖 <b>BOT EMASLIGINGIZNI TASDIQLANG</b>\n{DIV}\n❓ <b>Savol:</b> {{q}}\n\n👇 To'g'ri javobni tanlang:",
        "wrong_answer": "❌ Noto'g'ri javob!",
        "correct": "✅ Tasdiqlandi!",
        "wrong_ans_retry": f"❌ <b>NOTO'G'RI JAVOB!</b>\n{DIV}\nQaytadan: /start",
        "start_first": "ℹ️ Iltimos, /start buyrug'ini bosing.",
        "not_enough": "❌ <b>YETARLI EMAS!</b>",
        "min_withdraw": "❌ Minimal: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Maksimal: <b>{n} ⭐</b>",
        "enter_number": "❌ Faqat raqam kiriting.",
        "choose_reward": "🎁 <b>Mukofot turini tanlang:</b>",
        "stars_withdraw": "⭐ To'liq Stars olish", "gift_withdraw": "🎁 Telegram Gift olish",
        "sent_to_admin": f"✅ <b>SO'ROV YUBORILDI!</b>\n{DIV}\n⭐ <b>Miqdor:</b> {{n}} ⭐\n⏳ <i>Admin tasdiqlashini kuting...</i>",
        "gift_processing": f"⏳ <b>GIFT YUBORILMOQDA...</b>\n{DIV}\n{{gift}}\n⭐ <b>Narx:</b> {{n}} ⭐",
        "gift_done": f"🎉 <b>GIFT YUBORILDI!</b>\n{DIV}\n{{gift}}\n⭐ <b>Narx:</b> {{n}} ⭐\n\n🎁 Telegram profilingizni tekshiring!",
        "gift_failed": f"⚠️ <b>GIFTNI YUBORIB BO'LMADI</b>\n{DIV}\n{{gift}}\n\n💰 <b>{{n}} ⭐</b> balansingizga qaytarildi.",
        "gift_ask_anon": f"🎁 <b>GIFT TANLANDI</b>\n{DIV}\n{{gift}}\n⭐ <b>Narx:</b> {{n}} ⭐\n\n🕶 Gift <b>anonim</b> yuborilsinmi?",
        "gift_anon_yes": "🕶 Anonim", "gift_anon_no": "👤 Ismim ko'rinsin",
        "gift_ask_comment": f"💬 <b>GIFT OSTIGA IZOH</b>\n{DIV}\nMatn yuboring (maks. 120 belgi)\nyoki «Izohsiz» ni bosing 👇",
        "gift_no_comment": "➡️ Izohsiz",
        "approved": "✅ <b>So'rovingiz tasdiqlandi!</b>",
        "rejected": "❌ <b>So'rovingiz rad etildi.</b>",
        "referral_reward": f"🎉 <b>YANGI REFERAL!</b>\n{DIV}\n➕ <b>+{{n}} ⭐</b> qo'shildi",
        "total": "Jami", "balance": "Sizda", "need": "Kerak",
        "stars_added": f"🎁 <b>STARS QO'SHILDI!</b>\n{DIV}\n➕ <b>Miqdor:</b> +{{n}} ⭐\n📝 <b>Sabab:</b> <i>{{reason}}</i>\n\n💰 <b>Jami:</b> {{total}} ⭐",
        "stars_removed": f"⚠️ <b>STARS AYIRILDI!</b>\n{DIV}\n➖ <b>Miqdor:</b> {{n}} ⭐\n📝 <b>Sabab:</b> <i>{{reason}}</i>\n\n💰 <b>Jami:</b> {{total}} ⭐",
        "support_title": f"💬 <b>ADMIN BILAN ALOQA</b>\n{DIV}\nSavolingizni yozing — admin tez orada javob beradi.",
        "support_sent": "✅ <b>Savolingiz adminga yuborildi!</b>",
        "support_new_msg": "📩 <b>YANGI MUROJAAT!</b>\n\n👤 <b>User:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Vaqt:</b> {time}",
        "reply_sent": "✅ <b>Javob yuborildi!</b>",
        "chat_active": f"💬 <b>SUHBAT FAOLL</b>\n{DIV}\nXabaringizni yozing:",
        "chat_closed_by_admin": "🔚 <b>Admin suhbatni tugatdi.</b>",
        "admin_reply": "📬 <b>ADMINDAN JAVOB:</b>",
        "user_msg": "📩 <b>FOYDALANUVCHIDAN XABAR:</b>",
        "gift_stars_title": f"🎁 <b>STARS SOVG'A QILISH</b>\n{DIV}\n💰 <b>Sizda:</b> {{bal}} ⭐\n\nFoydalanuvchi <b>username</b> yoki <b>ID</b> sini kiriting:",
        "gift_stars_amount": f"👤 <b>Qabul qiluvchi:</b> {{name}}\n{DIV}\nNechta stars sovg'a qilasiz?",
        "gift_stars_confirm": f"🎁 <b>TASDIQLANG</b>\n{DIV}\n👤 <b>Kimga:</b> {{name}}\n⭐ <b>Miqdor:</b> {{n}} ⭐",
        "gift_stars_sent": "✅ <b>{n} ⭐ {name} ga yuborildi!</b>",
        "gift_stars_received": f"🎁 <b>SIZGA STARS SOVG'A QILINDI!</b>\n{DIV}\n👤 <b>Kimdan:</b> {{name}}\n⭐ <b>Miqdor:</b> +{{n}} ⭐\n\n💰 <b>Jami:</b> {{total}} ⭐",
        "gift_stars_not_found": "❌ Foydalanuvchi topilmadi.",
        "gift_stars_self": "❌ O'zingizga sovg'a qila olmaysiz.",
        "review_title": f"⭐ <b>SHARH QOLDIRISH</b>\n{DIV}\nBot haqida fikringizni yozing:",
        "review_sent": "✅ <b>Sharhingiz yuborildi!</b>",
        "review_approved": "✅ <b>Sharhingiz tasdiqlandi!</b>",
        "review_rejected": "❌ <b>Sharhingiz rad etildi.</b>",
        "level": "Daraja",
        "stars_will_send": f"✅ <b>SO'ROVINGIZ TASDIQLANDI!</b>\n{DIV}\n⭐ <b>Miqdor:</b> {{n}} ⭐",
        "level_up": f"🎉 <b>TABRIKLAYMIZ!</b>\n{DIV}\nSiz {{emoji}} <b>{{name}}</b> darajasiga chiqdingiz!\n\n⬆️ <b>Keyingi:</b> {{next_emoji}} <b>{{next_name}}</b>\n📊 <b>Kerak:</b> {{need}} ⭐",
        "banner_caption": "🎨 <b>Sizning shaxsiy baneringiz</b>",
        "ask_phone": f"📱 <b>TELEFON RAQAMNI TASDIQLANG</b>\n{DIV}\nFaqat 🇺🇿 <b>+998</b> raqamlari qabul qilinadi.\n\n👇 Quyidagi tugmani bosing:",
        "share_phone": "📱 Raqamni yuborish",
        "phone_not_own": "❌ Faqat o'zingizning raqamingizni yuboring.",
        "phone_only_uz": "❌ Faqat O'zbekiston raqamlari.",
        "phone_used": "❌ Bu raqam boshqa akkauntga bog'langan.",
        "phone_use_button": "ℹ️ «📱 Raqamni yuborish» tugmasidan foydalaning.",
        "donate_title": f"💝 <b>DONAT QILISH</b>\n{DIV}\nDonat — botni qo'llab-quvvatlash.\nSiz <b>Telegram Stars</b> yordamida stars yuborasiz.\n\n⭐ <b>Necha Stars yubormoqchisiz?</b>",
        "donate_ok": f"💝 <b>RAHMAT!</b>\n{DIV}\nSiz <b>{{n}} ⭐</b> donat qildingiz!\n\n🏆 Donat reytingida ko'rinasiz!",
        "donate_invoice_title": "Botga donat",
        "donate_invoice_desc": "Botni qo'llab-quvvatlash uchun {n} Stars",
        "donate_invoice_btn": "⭐ {n} Stars to'lash",
        "rating_choose": f"🏆 <b>REYTING</b>\n{DIV}\nQaysi reytingni ko'rmoqchisiz?",
        "rating_stars": "⭐ Eng ko'p stars egalari",
        "rating_donate": "💝 Eng ko'p donat qilganlar",
        "rating_ref": "👥 Eng ko'p referal yig'ganlar",
        "bonus_menu": "Kunlik bonus", "contest_menu": "Konkurs",
        "promo_menu": "Promokod", "tasks_menu": "Vazifalar",
        "bonus_title": "KUNLIK BONUS",
        "bonus_available": f"🔥 <b>KUNLIK BONUS</b>\n{DIV}\n🎁 <b>Bugungi mukofot:</b> {{reward}} ⭐\n🔥 <b>Seriya:</b> {{streak}} kun\n\n⏭ <b>Keyingi kun:</b> {{next}} ⭐",
        "bonus_claimed": f"✅ <b>BUGUN OLINDI!</b>\n{DIV}\n🔥 <b>Seriya:</b> {{streak}} kun\n\n⏰ Ertaga: <b>{{next}} ⭐</b>",
        "bonus_btn": "🎁 {n} ⭐ olish",
        "bonus_ok": f"🎉 <b>+{{n}} ⭐ BONUS OLINDI!</b>\n\n🔥 <b>Seriya:</b> {{streak}} kun",
        "bonus_already": "⏰ Bugun allaqachon olgansiz. Ertaga qaytib keling!",
        "promo_title": f"🎟 <b>PROMOKOD</b>\n{DIV}\nKodni kiriting va stars oling:",
        "promo_ok": "🎉 <b>+{n} ⭐</b> promokod orqali qo'shildi!",
        "promo_not_found": "❌ Promokod topilmadi.",
        "promo_used": "❌ Siz bu kodni ishlatgansiz.",
        "promo_empty": "❌ Promokod tugagan.",
        "tasks_title": "VAZIFALAR", "contest_title": "FAOL KONKURS",
        "contest_none": f"🏆 <b>FAOL KONKURS YO'Q</b>\n{DIV}\nTez orada yangi konkurs boshlanadi! 🔥",
        "hist_title": "📜 SO'ROVLARIM",
        "hist_empty": "<i>Hozircha so'rovlar yo'q</i>",
        "st_pending": "Kutilmoqda", "st_processing": "Jarayonda",
        "st_approved": "Bajarildi", "st_rejected": "Rad etildi",
        "st_failed": "Xato (qaytarildi)",
        "advertise": "📢 Reklama xizmati",
        "advertise_title": f"📢 <b>REKLAMA XIZMATLARI</b>\n{DIV}\nKanal/guruhingizni reklama qiling!\n\n👇 Tarifni tanlang:",
        "advertise_buy": "💳 Sotib olish",
        "advertise_sent": "✅ <b>So'rov yuborildi!</b>\n\nAdmin tez orada siz bilan bog'lanadi.",
        "advertise_none": f"📢 <b>REKLAMA TARIFLARI YO'Q</b>\n{DIV}\nHozircha xizmat mavjud emas.",
        "more": "⚙️ Ko'proq",
    },
    "ru": {
        "flag": "🇷🇺", "name": "Русский",
        "choose_lang": f"🌐 <b>ВЫБЕРИТЕ ЯЗЫК</b>\n{DIV}\nПожалуйста, выберите удобный язык 👇",
        "lang_set": "✅ <b>Язык успешно изменён!</b>",
        "welcome": "✨ <b>Добро пожаловать, {name}!</b>\n" + DIV + "\n🚀 <b>StarRush</b> — платформа для сбора Stars\n\n👥  Приглашайте друзей\n🎁  Копите Stars и получайте Gift\n🔥  Ежедневный бонус и задания\n🏆  Станьте первым в рейтинге\n" + DIV + "\nВыберите раздел 👇",
        "menu_title": f"🏠 <b>ГЛАВНОЕ МЕНЮ</b>\n{DIV}\n👇 Выберите раздел:",
        "profile": "👤 Профиль", "stats": "📊 Статистика", "banner": "🎨 Баннер",
        "webapp": "🚀 Mini App", "ref_link": "🔗 Реф. ссылка", "rating": "🏆 Рейтинг",
        "withdraw": "💰 Вывод", "donate": "💝 Донат",
        "support": "💬 Связь с админом", "gift_stars": "🎁 Подарить Stars",
        "review": "⭐ Отзыв", "admin": "🛠 Админ панель",
        "share": "📤 Поделиться", "back": "⬅️ Назад", "menu": "🏠 Главное меню",
        "cancel": "❌ Отмена", "close_chat": "🔚 Завершить чат",
        "more_btn": "⚙️ Ещё",
        "more_title": f"⚙️ <b>ЕЩЁ</b>\n{DIV}\nДополнительные разделы 👇",
        "history": "📜 Мои заявки",
        "remind_on": "🔔 Напоминания: вкл", "remind_off": "🔕 Напоминания: выкл",
        "banned": f"🚫 <b>ВЫ ЗАБАНЕНЫ!</b>\n{DIV}\nСвяжитесь с админом.",
        "subscribe": f"📢 <b>ПОДПИШИТЕСЬ НА КАНАЛЫ</b>\n{DIV}\nДля использования бота подпишитесь на каналы.\n\nПосле подписки «✅ Проверить» 👇",
        "check": "✅ Проверить",
        "bot_check": f"🤖 <b>ПОДТВЕРДИТЕ, ЧТО ВЫ НЕ БОТ</b>\n{DIV}\n❓ <b>Вопрос:</b> {{q}}\n\n👇 Выберите ответ:",
        "wrong_answer": "❌ Неправильный ответ!", "correct": "✅ Подтверждено!",
        "wrong_ans_retry": f"❌ <b>НЕПРАВИЛЬНЫЙ ОТВЕТ!</b>\n{DIV}\nПопробуйте: /start",
        "start_first": "ℹ️ Пожалуйста, /start",
        "not_enough": "❌ <b>НЕДОСТАТОЧНО!</b>",
        "min_withdraw": "❌ Минимум: <b>{n} ⭐</b>", "max_withdraw": "❌ Максимум: <b>{n} ⭐</b>",
        "enter_number": "❌ Введите число.", "choose_reward": "🎁 <b>Выберите награду:</b>",
        "stars_withdraw": "⭐ Получить Stars", "gift_withdraw": "🎁 Получить Gift",
        "sent_to_admin": f"✅ <b>ЗАПРОС ОТПРАВЛЕН!</b>\n{DIV}\n⭐ <b>Сумма:</b> {{n}} ⭐\n⏳ <i>Ожидайте...</i>",
        "gift_processing": f"⏳ <b>ОТПРАВЛЯЕМ GIFT...</b>\n{DIV}\n{{gift}}\n⭐ <b>Цена:</b> {{n}} ⭐",
        "gift_done": f"🎉 <b>GIFT ОТПРАВЛЕН!</b>\n{DIV}\n{{gift}}\n⭐ <b>Цена:</b> {{n}} ⭐",
        "gift_failed": f"⚠️ <b>НЕ УДАЛОСЬ ОТПРАВИТЬ</b>\n{DIV}\n{{gift}}\n\n💰 <b>{{n}} ⭐</b> возвращены.",
        "gift_ask_anon": f"🎁 <b>GIFT ВЫБРАН</b>\n{DIV}\n{{gift}}\n⭐ <b>Цена:</b> {{n}} ⭐\n\n🕶 Анонимно?",
        "gift_anon_yes": "🕶 Анонимно", "gift_anon_no": "👤 Показать имя",
        "gift_ask_comment": f"💬 <b>КОММЕНТАРИЙ</b>\n{DIV}\nТекст (макс. 120) или «Без комментария» 👇",
        "gift_no_comment": "➡️ Без комментария",
        "approved": "✅ <b>Запрос одобрен!</b>", "rejected": "❌ <b>Запрос отклонён.</b>",
        "referral_reward": f"🎉 <b>НОВЫЙ РЕФЕРАЛ!</b>\n{DIV}\n➕ <b>+{{n}} ⭐</b>",
        "total": "Всего", "balance": "У вас", "need": "Нужно",
        "stars_added": f"🎁 <b>STARS ДОБАВЛЕНЫ!</b>\n{DIV}\n➕ <b>{{n}} ⭐</b>\n📝 <i>{{reason}}</i>\n💰 <b>{{total}} ⭐</b>",
        "stars_removed": f"⚠️ <b>STARS СПИСАНЫ!</b>\n{DIV}\n➖ <b>{{n}} ⭐</b>\n📝 <i>{{reason}}</i>\n💰 <b>{{total}} ⭐</b>",
        "support_title": f"💬 <b>СВЯЗЬ С АДМИНОМ</b>\n{DIV}\nНапишите вопрос — админ ответит.",
        "support_sent": "✅ <b>Вопрос отправлен!</b>",
        "support_new_msg": "📩 <b>НОВОЕ ОБРАЩЕНИЕ!</b>\n\n👤 {name}\n🔗 {username}\n🆔 <code>{uid}</code>\n📅 {time}",
        "reply_sent": "✅ <b>Ответ отправлен!</b>",
        "chat_active": f"💬 <b>ЧАТ АКТИВЕН</b>\n{DIV}\nНапишите сообщение:",
        "chat_closed_by_admin": "🔚 <b>Админ завершил чат.</b>",
        "admin_reply": "📬 <b>ОТВЕТ ОТ АДМИНА:</b>",
        "user_msg": "📩 <b>ОТ ПОЛЬЗОВАТЕЛЯ:</b>",
        "gift_stars_title": f"🎁 <b>ПОДАРИТЬ STARS</b>\n{DIV}\n💰 <b>У вас:</b> {{bal}} ⭐\n\nВведите username или ID:",
        "gift_stars_amount": f"👤 <b>Получатель:</b> {{name}}\n{DIV}\nСколько stars?",
        "gift_stars_confirm": f"🎁 <b>ПОДТВЕРДИТЕ</b>\n{DIV}\n👤 {{name}}\n⭐ {{n}} ⭐",
        "gift_stars_sent": "✅ <b>{n} ⭐ → {name}!</b>",
        "gift_stars_received": f"🎁 <b>ВАМ ПОДАРИЛИ STARS!</b>\n{DIV}\n👤 {{name}}\n⭐ +{{n}} ⭐\n💰 {{total}} ⭐",
        "gift_stars_not_found": "❌ Пользователь не найден.",
        "gift_stars_self": "❌ Нельзя себе.",
        "review_title": f"⭐ <b>ОСТАВИТЬ ОТЗЫВ</b>\n{DIV}\nНапишите отзыв о боте:",
        "review_sent": "✅ <b>Отзыв отправлен!</b>",
        "review_approved": "✅ <b>Отзыв одобрен!</b>",
        "review_rejected": "❌ <b>Отзыв отклонён.</b>",
        "level": "Уровень",
        "stars_will_send": f"✅ <b>ОДОБРЕНО!</b>\n{DIV}\n⭐ <b>{{n}} ⭐</b>",
        "level_up": f"🎉 <b>ПОЗДРАВЛЯЕМ!</b>\n{DIV}\nВы достигли {{emoji}} <b>{{name}}</b>!\n⬆️ {{next_emoji}} <b>{{next_name}}</b> — {{need}} ⭐",
        "banner_caption": "🎨 <b>Ваш баннер</b>",
        "ask_phone": f"📱 <b>ПОДТВЕРДИТЕ НОМЕР</b>\n{DIV}\nТолько 🇺🇿 <b>+998</b>.\n👇 Кнопка ниже:",
        "share_phone": "📱 Отправить номер",
        "phone_not_own": "❌ Только свой номер.",
        "phone_only_uz": "❌ Только Узбекистан.",
        "phone_used": "❌ Номер привязан.",
        "phone_use_button": "ℹ️ Используйте кнопку.",
        "donate_title": f"💝 <b>ДОНАТ</b>\n{DIV}\nПоддержка бота через <b>Telegram Stars</b>.\n\n⭐ <b>Сколько Stars?</b>",
        "donate_ok": f"💝 <b>СПАСИБО!</b>\n{DIV}\nВы отправили <b>{{n}} ⭐</b>!",
        "donate_invoice_title": "Донат", "donate_invoice_desc": "Донат {n} Stars", "donate_invoice_btn": "⭐ {n} Stars",
        "rating_choose": f"🏆 <b>РЕЙТИНГ</b>\n{DIV}\nКакой?",
        "rating_stars": "⭐ Больше Stars", "rating_donate": "💝 Больше донатов", "rating_ref": "👥 Больше рефералов",
        "bonus_menu": "Ежедневный бонус", "contest_menu": "Конкурс", "promo_menu": "Промокод", "tasks_menu": "Задания",
        "bonus_title": "БОНУС",
        "bonus_available": f"🔥 <b>БОНУС</b>\n{DIV}\n🎁 {{reward}} ⭐\n🔥 {{streak}} дн.\n⏭ {{next}} ⭐",
        "bonus_claimed": f"✅ <b>ПОЛУЧЕН!</b>\n{DIV}\n🔥 {{streak}} дн.\n⏰ Завтра: {{next}} ⭐",
        "bonus_btn": "🎁 {n} ⭐", "bonus_ok": f"🎉 <b>+{{n}} ⭐!</b>\n🔥 {{streak}} дн.",
        "bonus_already": "⏰ Уже получен. Завтра!",
        "promo_title": f"🎟 <b>ПРОМОКОД</b>\n{DIV}\nВведите код:",
        "promo_ok": "🎉 <b>+{n} ⭐</b>!",
        "promo_not_found": "❌ Не найден.", "promo_used": "❌ Уже использован.", "promo_empty": "❌ Закончился.",
        "tasks_title": "ЗАДАНИЯ", "contest_title": "КОНКУРС",
        "contest_none": f"🏆 <b>НЕТ КОНКУРСА</b>\n{DIV}\nСкоро! 🔥",
        "hist_title": "📜 МОИ ЗАЯВКИ", "hist_empty": "<i>Пусто</i>",
        "st_pending": "Ожидает", "st_processing": "В процессе", "st_approved": "Выполнено",
        "st_rejected": "Отклонено", "st_failed": "Ошибка",
        "advertise": "📢 Реклама",
        "advertise_title": f"📢 <b>РЕКЛАМА</b>\n{DIV}\nРекламируйте канал/группу!\n👇 Выберите тариф:",
        "advertise_buy": "💳 Купить",
        "advertise_sent": "✅ <b>Заявка отправлена!</b>",
        "advertise_none": f"📢 <b>ТАРИФОВ НЕТ</b>\n{DIV}\nПока недоступно.",
        "more": "⚙️ Ещё",
    },
    "en": {
        "flag": "🇬🇧", "name": "English",
        "choose_lang": f"🌐 <b>CHOOSE LANGUAGE</b>\n{DIV}\nPlease choose 👇",
        "lang_set": "✅ <b>Language changed!</b>",
        "welcome": "✨ <b>Welcome, {name}!</b>\n" + DIV + "\n🚀 <b>StarRush</b> — Stars collecting platform\n\n👥  Invite friends\n🎁  Collect Stars and get Gifts\n🔥  Daily bonus and tasks\n🏆  Be #1 on the leaderboard\n" + DIV + "\nChoose a section 👇",
        "menu_title": f"🏠 <b>MAIN MENU</b>\n{DIV}\n👇 Choose a section:",
        "profile": "👤 Profile", "stats": "📊 Statistics", "banner": "🎨 Banner",
        "webapp": "🚀 Mini App", "ref_link": "🔗 Referral link", "rating": "🏆 Rating",
        "withdraw": "💰 Withdraw", "donate": "💝 Donate",
        "support": "💬 Contact admin", "gift_stars": "🎁 Gift Stars",
        "review": "⭐ Leave review", "admin": "🛠 Admin Panel",
        "share": "📤 Share", "back": "⬅️ Back", "menu": "🏠 Main menu",
        "cancel": "❌ Cancel", "close_chat": "🔚 Close chat",
        "more_btn": "⚙️ More", "more_title": f"⚙️ <b>MORE</b>\n{DIV}\nExtra sections 👇",
        "history": "📜 My requests",
        "remind_on": "🔔 Reminders: on", "remind_off": "🔕 Reminders: off",
        "banned": f"🚫 <b>YOU ARE BANNED!</b>\n{DIV}\nContact admin.",
        "subscribe": f"📢 <b>SUBSCRIBE TO CHANNELS</b>\n{DIV}\nSubscribe to use the bot.\n\nPress «✅ Check» 👇",
        "check": "✅ Check",
        "bot_check": f"🤖 <b>CONFIRM YOU'RE NOT A BOT</b>\n{DIV}\n❓ {{q}}\n👇 Choose:",
        "wrong_answer": "❌ Wrong!", "correct": "✅ Confirmed!",
        "wrong_ans_retry": f"❌ <b>WRONG!</b>\n{DIV}\nTry: /start",
        "start_first": "ℹ️ Please send /start",
        "not_enough": "❌ <b>NOT ENOUGH!</b>",
        "min_withdraw": "❌ Min: <b>{n} ⭐</b>", "max_withdraw": "❌ Max: <b>{n} ⭐</b>",
        "enter_number": "❌ Numbers only.", "choose_reward": "🎁 <b>Choose reward:</b>",
        "stars_withdraw": "⭐ Get Stars", "gift_withdraw": "🎁 Get Gift",
        "sent_to_admin": f"✅ <b>SENT!</b>\n{DIV}\n⭐ <b>{{n}} ⭐</b>\n⏳ <i>Wait...</i>",
        "gift_processing": f"⏳ <b>SENDING GIFT...</b>\n{DIV}\n{{gift}}\n⭐ {{n}} ⭐",
        "gift_done": f"🎉 <b>GIFT SENT!</b>\n{DIV}\n{{gift}}\n⭐ {{n}} ⭐",
        "gift_failed": f"⚠️ <b>FAILED</b>\n{DIV}\n{{gift}}\n💰 <b>{{n}} ⭐</b> refunded.",
        "gift_ask_anon": f"🎁 <b>GIFT SELECTED</b>\n{DIV}\n{{gift}}\n⭐ {{n}} ⭐\n🕶 Anonymous?",
        "gift_anon_yes": "🕶 Anonymous", "gift_anon_no": "👤 Show name",
        "gift_ask_comment": f"💬 <b>COMMENT</b>\n{DIV}\nText (max 120) or «No comment» 👇",
        "gift_no_comment": "➡️ No comment",
        "approved": "✅ <b>Approved!</b>", "rejected": "❌ <b>Rejected.</b>",
        "referral_reward": f"🎉 <b>NEW REFERRAL!</b>\n{DIV}\n➕ <b>+{{n}} ⭐</b>",
        "total": "Total", "balance": "You have", "need": "Need",
        "stars_added": f"🎁 <b>STARS ADDED!</b>\n{DIV}\n➕ {{n}} ⭐\n📝 <i>{{reason}}</i>\n💰 {{total}} ⭐",
        "stars_removed": f"⚠️ <b>STARS REMOVED!</b>\n{DIV}\n➖ {{n}} ⭐\n📝 <i>{{reason}}</i>\n💰 {{total}} ⭐",
        "support_title": f"💬 <b>CONTACT ADMIN</b>\n{DIV}\nWrite your question:",
        "support_sent": "✅ <b>Sent!</b>",
        "support_new_msg": "📩 <b>NEW!</b>\n\n👤 {name}\n🔗 {username}\n🆔 <code>{uid}</code>\n📅 {time}",
        "reply_sent": "✅ <b>Reply sent!</b>",
        "chat_active": f"💬 <b>CHAT ACTIVE</b>\n{DIV}\nSend your message:",
        "chat_closed_by_admin": "🔚 <b>Admin closed chat.</b>",
        "admin_reply": "📬 <b>REPLY:</b>", "user_msg": "📩 <b>FROM USER:</b>",
        "gift_stars_title": f"🎁 <b>GIFT STARS</b>\n{DIV}\n💰 <b>You:</b> {{bal}} ⭐\n\nEnter username or ID:",
        "gift_stars_amount": f"👤 {{name}}\n{DIV}\nHow many stars?",
        "gift_stars_confirm": f"🎁 <b>CONFIRM</b>\n{DIV}\n👤 {{name}}\n⭐ {{n}} ⭐",
        "gift_stars_sent": "✅ <b>{n} ⭐ → {name}!</b>",
        "gift_stars_received": f"🎁 <b>YOU GOT STARS!</b>\n{DIV}\n👤 {{name}}\n⭐ +{{n}} ⭐\n💰 {{total}} ⭐",
        "gift_stars_not_found": "❌ Not found.", "gift_stars_self": "❌ Can't gift yourself.",
        "review_title": f"⭐ <b>LEAVE REVIEW</b>\n{DIV}\nWrite:",
        "review_sent": "✅ <b>Sent!</b>",
        "review_approved": "✅ <b>Approved!</b>", "review_rejected": "❌ <b>Rejected.</b>",
        "level": "Level",
        "stars_will_send": f"✅ <b>APPROVED!</b>\n{DIV}\n⭐ {{n}} ⭐",
        "level_up": f"🎉 <b>CONGRATS!</b>\n{DIV}\n{{emoji}} <b>{{name}}</b>!\n⬆️ {{next_emoji}} <b>{{next_name}}</b> — {{need}} ⭐",
        "banner_caption": "🎨 <b>Your banner</b>",
        "ask_phone": f"📱 <b>CONFIRM PHONE</b>\n{DIV}\nOnly 🇺🇿 <b>+998</b>.\n👇",
        "share_phone": "📱 Share number",
        "phone_not_own": "❌ Only your own.",
        "phone_only_uz": "❌ Uzbekistan only.",
        "phone_used": "❌ Number linked.",
        "phone_use_button": "ℹ️ Use the button.",
        "donate_title": f"💝 <b>DONATE</b>\n{DIV}\nSupport via <b>Telegram Stars</b>.\n⭐ <b>How many?</b>",
        "donate_ok": f"💝 <b>THANKS!</b>\n{DIV}\n{{n}} ⭐!",
        "donate_invoice_title": "Donate", "donate_invoice_desc": "{n} Stars", "donate_invoice_btn": "⭐ {n} Stars",
        "rating_choose": f"🏆 <b>RATING</b>\n{DIV}\nWhich?",
        "rating_stars": "⭐ Most Stars", "rating_donate": "💝 Most Donations", "rating_ref": "👥 Most Referrals",
        "bonus_menu": "Daily bonus", "contest_menu": "Contest", "promo_menu": "Promocode", "tasks_menu": "Tasks",
        "bonus_title": "BONUS",
        "bonus_available": f"🔥 <b>BONUS</b>\n{DIV}\n🎁 {{reward}} ⭐\n🔥 {{streak}} days\n⏭ {{next}} ⭐",
        "bonus_claimed": f"✅ <b>CLAIMED!</b>\n{DIV}\n🔥 {{streak}} days\n⏰ Tomorrow: {{next}} ⭐",
        "bonus_btn": "🎁 {n} ⭐", "bonus_ok": f"🎉 <b>+{{n}} ⭐!</b>\n🔥 {{streak}} days",
        "bonus_already": "⏰ Already claimed today!",
        "promo_title": f"🎟 <b>PROMOCODE</b>\n{DIV}\nEnter code:",
        "promo_ok": "🎉 <b>+{n} ⭐</b>!",
        "promo_not_found": "❌ Not found.", "promo_used": "❌ Used.", "promo_empty": "❌ Expired.",
        "tasks_title": "TASKS", "contest_title": "CONTEST",
        "contest_none": f"🏆 <b>NO CONTEST</b>\n{DIV}\nSoon! 🔥",
        "hist_title": "📜 MY REQUESTS", "hist_empty": "<i>Empty</i>",
        "st_pending": "Pending", "st_processing": "Processing", "st_approved": "Done",
        "st_rejected": "Rejected", "st_failed": "Failed",
        "advertise": "📢 Advertising",
        "advertise_title": f"📢 <b>ADVERTISING</b>\n{DIV}\nAdvertise your channel!\n👇 Choose:",
        "advertise_buy": "💳 Buy",
        "advertise_sent": "✅ <b>Sent!</b>",
        "advertise_none": f"📢 <b>NO TARIFFS</b>\n{DIV}\nComing soon.",
        "more": "⚙️ More",
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
        _pool = ThreadedConnectionPool(2, 20, DATABASE_URL)
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
        user_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
        language TEXT DEFAULT 'uz', stars INTEGER DEFAULT 0, referrer_id BIGINT DEFAULT 0,
        is_verified INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, is_suspicious INTEGER DEFAULT 0,
        joined_at TEXT)""")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_ok INTEGER DEFAULT 1")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS remind INTEGER DEFAULT 1")

    c.execute("CREATE TABLE IF NOT EXISTS channels (id SERIAL PRIMARY KEY, channel_username TEXT UNIQUE)")
    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id SERIAL PRIMARY KEY, question TEXT, correct_answer TEXT, wrong1 TEXT, wrong2 TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS gifts (
        key TEXT PRIMARY KEY, emoji TEXT, name TEXT, stars INTEGER)""")
    c.execute("ALTER TABLE gifts ADD COLUMN IF NOT EXISTS gift_id BIGINT")
    c.execute("ALTER TABLE gifts ADD COLUMN IF NOT EXISTS premium_emoji_id TEXT")

    c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id SERIAL PRIMARY KEY, user_id BIGINT, stars INTEGER, reward_type TEXT, gift_key TEXT,
        status TEXT DEFAULT 'pending', created_at TEXT)""")
    c.execute("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS is_anon INTEGER DEFAULT 0")
    c.execute("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS comment TEXT")
    c.execute("ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS error TEXT")

    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS admins (user_id BIGINT PRIMARY KEY, added_by BIGINT, added_at TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
        id SERIAL PRIMARY KEY, user_id BIGINT, admin_id BIGINT, message_type TEXT,
        content TEXT, is_from_admin INTEGER DEFAULT 0, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS support_chats (
        user_id BIGINT PRIMARY KEY, status TEXT DEFAULT 'open', admin_id BIGINT DEFAULT 0, updated_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY, user_id BIGINT, text TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS levels (
        id SERIAL PRIMARY KEY, name TEXT, emoji TEXT, min_stars INTEGER, max_stars INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS donations (
        id SERIAL PRIMARY KEY, user_id BIGINT, stars INTEGER, charge_id TEXT UNIQUE,
        payload TEXT, status TEXT DEFAULT 'received', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS contests (
        id SERIAL PRIMARY KEY, title TEXT, description TEXT, reward_emoji TEXT DEFAULT '🎁',
        reward_name TEXT DEFAULT 'Gift', target INTEGER DEFAULT 0, start_at TEXT, end_at TEXT,
        status TEXT DEFAULT 'active', winner_id BIGINT DEFAULT 0, winner_referrals INTEGER DEFAULT 0,
        created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_bonus (
        user_id BIGINT PRIMARY KEY, last_claim TEXT, streak INTEGER DEFAULT 0, total_claimed INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY, title TEXT, emoji TEXT DEFAULT '📌', reward INTEGER DEFAULT 5,
        link TEXT, action TEXT DEFAULT 'manual', is_active INTEGER DEFAULT 1, once INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_tasks (
        user_id BIGINT, task_id INTEGER, done INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0,
        updated_at TEXT, PRIMARY KEY (user_id, task_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY, reward INTEGER, uses_left INTEGER DEFAULT 100, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS promo_uses (
        user_id BIGINT, code TEXT, used_at TEXT, PRIMARY KEY (user_id, code))""")
    c.execute("""CREATE TABLE IF NOT EXISTS ad_services (
        id SERIAL PRIMARY KEY, title TEXT, description TEXT, hours INTEGER DEFAULT 12,
        price_uzs INTEGER DEFAULT 0, bonus_subs INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
        position INTEGER DEFAULT 0, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS ad_requests (
        id SERIAL PRIMARY KEY, user_id BIGINT, service_id INTEGER, service_title TEXT,
        price_uzs INTEGER, hours INTEGER, status TEXT DEFAULT 'pending', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bonus_config (
        id SERIAL PRIMARY KEY, day_num INTEGER UNIQUE, reward INTEGER, is_active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS premium_emojis (
        key TEXT PRIMARY KEY, emoji_id TEXT, fallback TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS referral_rewards (
        id SERIAL PRIMARY KEY, referrer_id BIGINT, referred_id BIGINT UNIQUE,
        amount INTEGER, status TEXT DEFAULT 'pending', created_at TEXT, release_at TEXT, paid_at TEXT)""")

    defaults = {
        "stars_per_referral": "2", "min_withdraw": "50", "max_withdraw": "1000000",
        "review_channel": "", "gift_channel": "", "min_donate": "1",
        "ref_hold_hours": "0", "ref_clawback_days": "7",
        "daily_withdraw_limit": "5000", "min_account_age_days": "0",
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
            ("heart", "💝", "Heart", 15, 5170145012310081615),
            ("teddy", "🧸", "Teddy Bear", 15, 5170233102089325572),
            ("giftbox", "🎁", "Gift Box", 25, 5170250435875467955),
            ("rose", "🌹", "Rose", 25, 5168103777161739235),
            ("cake", "🎂", "Cake", 50, 5170145012310081620),
            ("bouquet", "💐", "Bouquet", 50, 5170250435875467960),
            ("rocket", "🚀", "Rocket", 50, 5170233102089325580),
            ("trophy", "🏆", "Trophy", 100, 5170250435875467970),
            ("ring", "💍", "Ring", 100, 5168103777161739245),
            ("diamond", "💎", "Diamond", 100, 5170233102089325590),
        ]
        for key, emoji, name, stars, gid in default_gifts:
            c.execute("""INSERT INTO gifts (key, emoji, name, stars, gift_id)
                         VALUES (%s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING""",
                      (key, emoji, name, stars, gid))

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

    c.execute("SELECT COUNT(*) FROM tasks")
    if c.fetchone()[0] == 0:
        defaults_tasks = [
            ("Do'stni taklif qilish", "👥", 5, None, "ref", 1, 0),
            ("Kanalga obuna bo'lish", "📢", 10, "@StarRushUZ", "sub", 1, 1),
            ("Mini App'ga kirish", "🚀", 3, None, "webapp", 1, 0),
            ("Profilni to'ldirish", "✅", 5, None, "profile", 1, 0),
        ]
        for t in defaults_tasks:
            c.execute("""INSERT INTO tasks (title, emoji, reward, link, action, is_active, once)
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""", t)

    c.execute("SELECT COUNT(*) FROM bonus_config")
    if c.fetchone()[0] == 0:
        for i, r in enumerate(BONUS_REWARDS, 1):
            c.execute("INSERT INTO bonus_config (day_num, reward, is_active) VALUES (%s, %s, 1)", (i, r))

    c.execute("SELECT COUNT(*) FROM ad_services")
    if c.fetchone()[0] == 0:
        defaults_ads = [
            ("12 soat reklama", "Kanal/guruhingiz 12 soat davomida kanalimizda", 12, 9999, 0),
            ("24 soat reklama", "Kanal/guruhingiz 24 soat davomida kanalimizda", 24, 14999, 0),
            ("50 garant obunachi", "50 ta garant obunachi", 0, 6999, 50),
            ("100 garant obunachi", "100 ta garant obunachi", 0, 12999, 100),
        ]
        for t in defaults_ads:
            c.execute("""INSERT INTO ad_services (title, description, hours, price_uzs, bonus_subs, is_active)
                         VALUES (%s,%s,%s,%s,%s,1)""", t)

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
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""", (key, str(value)))


def _clean_user(row):
    if not row:
        return None
    d = dict(row)
    for k in ("first_name", "last_name", "username"):
        if d.get(k):
            d[k] = html.escape(d[k])
    return d


def get_user(user_id):
    return _clean_user(db_exec("SELECT * FROM users WHERE user_id=%s", (user_id,), fetch=True))


def get_user_by_username(username):
    return _clean_user(db_exec("SELECT * FROM users WHERE LOWER(username)=%s",
                              (username.lstrip("@").lower(),), fetch=True))


def get_user_lang(user_id):
    row = db_exec("SELECT language FROM users WHERE user_id=%s", (user_id,), fetch=True)
    return row["language"] if row and row.get("language") in LANGS else "uz"


def update_user(user_id, **kwargs):
    if not kwargs:
        return
    fields = ", ".join([f"{k}=%s" for k in kwargs.keys()])
    db_exec(f"UPDATE users SET {fields} WHERE user_id=%s", list(kwargs.values()) + [user_id])


def create_user(user_id, username, first_name, last_name, referrer_id=0):
    db_exec("""INSERT INTO users (user_id, username, first_name, last_name, referrer_id, joined_at)
        VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING""",
            (user_id, username, first_name, last_name, referrer_id, now_uz().isoformat()))


def spend_stars(user_id, n):
    row = db_exec("UPDATE users SET stars = stars - %s WHERE user_id=%s AND stars >= %s RETURNING stars",
                  (n, user_id, n), fetch=True)
    return row["stars"] if row else None


def add_stars(user_id, n):
    row = db_exec("UPDATE users SET stars = stars + %s WHERE user_id=%s RETURNING stars",
                  (n, user_id), fetch=True)
    return row["stars"] if row else None


def pending_total(user_id):
    row = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM withdrawals WHERE user_id=%s AND status='pending'",
                  (user_id,), fetch=True)
    return int(row["s"]) if row else 0


def total_donated(user_id):
    row = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM donations WHERE user_id=%s", (user_id,), fetch=True)
    return int(row["s"]) if row else 0


def bot_donate_balance():
    row = db_exec("SELECT COALESCE(SUM(stars), 0) AS s FROM donations", fetch=True)
    return int(row["s"]) if row else 0


def is_admin(user_id):
    if user_id in SUPER_ADMIN_IDS:
        return True
    return db_exec("SELECT 1 FROM admins WHERE user_id=%s", (user_id,), fetch=True) is not None


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


def add_question(q, correct, w1, w2):
    db_exec("INSERT INTO questions (question, correct_answer, wrong1, wrong2) VALUES (%s, %s, %s, %s)",
            (q, correct, w1, w2))


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


def add_gift(key, emoji, name, stars, gift_id=None, premium_emoji_id=None):
    db_exec("""INSERT INTO gifts (key, emoji, name, stars, gift_id, premium_emoji_id)
               VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (key) DO UPDATE SET
                 emoji=EXCLUDED.emoji, name=EXCLUDED.name, stars=EXCLUDED.stars,
                 gift_id=EXCLUDED.gift_id, premium_emoji_id=EXCLUDED.premium_emoji_id""",
            (key, emoji, name, stars, gift_id, premium_emoji_id))


def remove_gift(key):
    db_exec("DELETE FROM gifts WHERE key=%s", (key,))


def get_chat_status(user_id):
    row = db_exec("SELECT status FROM support_chats WHERE user_id=%s", (user_id,), fetch=True)
    return row["status"] if row else None


def open_chat(user_id):
    db_exec("""INSERT INTO support_chats (user_id, status, admin_id, updated_at)
               VALUES (%s, 'open', 0, %s) ON CONFLICT (user_id) DO UPDATE SET
                 status='open', updated_at=EXCLUDED.updated_at""",
            (user_id, now_uz().isoformat()))


def close_chat(user_id, closed_by="user"):
    db_exec("UPDATE support_chats SET status=%s, updated_at=%s WHERE user_id=%s",
            (f"closed_by_{closed_by}", now_uz().isoformat(), user_id))


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
    rows = db_exec("""SELECT sc.user_id, sc.status, sc.updated_at, u.first_name, u.username
        FROM support_chats sc LEFT JOIN users u ON sc.user_id=u.user_id ORDER BY sc.updated_at DESC""",
        fetchall=True)
    return [dict(r) for r in rows] if rows else []


def get_bonus_rewards():
    rows = db_exec("SELECT day_num, reward FROM bonus_config WHERE is_active=1 ORDER BY day_num", fetchall=True)
    if rows:
        return [r["reward"] for r in rows]
    return BONUS_REWARDS


def get_bonus_reward(streak):
    rewards = get_bonus_rewards()
    return rewards[min(streak, len(rewards) - 1)]


def check_daily_bonus(user_id):
    today = now_uz().strftime("%Y-%m-%d")
    row = db_exec("SELECT * FROM daily_bonus WHERE user_id=%s", (user_id,), fetch=True)
    if not row:
        return {"can_claim": True, "streak": 0, "reward": get_bonus_reward(0), "next_reward": get_bonus_reward(1)}
    last = (row.get("last_claim") or "")[:10]
    streak = int(row.get("streak") or 0)
    can_claim = last != today
    if last and last != today:
        yest = (now_uz() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last != yest:
            streak = 0
    return {"can_claim": can_claim, "streak": streak,
            "reward": get_bonus_reward(streak), "next_reward": get_bonus_reward(streak + 1)}


def claim_daily_bonus(user_id):
    info = check_daily_bonus(user_id)
    if not info["can_claim"]:
        return None
    reward = info["reward"]
    new_streak = info["streak"] + 1
    db_exec("""INSERT INTO daily_bonus (user_id, last_claim, streak, total_claimed) VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                 last_claim=EXCLUDED.last_claim, streak=EXCLUDED.streak,
                 total_claimed=daily_bonus.total_claimed + %s""",
            (user_id, now_uz().isoformat(), new_streak, reward, reward))
    add_stars(user_id, reward)
    return {"reward": reward, "streak": new_streak}


def get_user_tasks(user_id):
    tasks_db = db_exec("SELECT * FROM tasks WHERE is_active=1 ORDER BY id", fetchall=True) or []
    result = []
    for t in tasks_db:
        ut = db_exec("SELECT done, claimed FROM user_tasks WHERE user_id=%s AND task_id=%s",
                     (user_id, t["id"]), fetch=True) or {"done": 0, "claimed": 0}
        done = bool(ut["done"])
        claimed = bool(ut["claimed"])
        result.append({
            "id": t["id"], "title": t["title"], "emoji": t["emoji"],
            "reward": t["reward"], "link": t["link"], "action": t["action"],
            "done": done, "claimed": claimed, "claimable": done and not claimed,
        })
    return result


def mark_task_done(user_id, task_id, done=True):
    db_exec("""INSERT INTO user_tasks (user_id, task_id, done, updated_at) VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id, task_id) DO UPDATE SET
                 done=EXCLUDED.done, updated_at=EXCLUDED.updated_at""",
            (user_id, task_id, 1 if done else 0, now_uz().isoformat()))


def claim_task_reward(user_id, task_id):
    t = db_exec("SELECT * FROM tasks WHERE id=%s AND is_active=1", (task_id,), fetch=True)
    if not t:
        return None
    ut = db_exec("SELECT done, claimed FROM user_tasks WHERE user_id=%s AND task_id=%s",
                 (user_id, task_id), fetch=True) or {"done": 0, "claimed": 0}
    if not ut["done"] or ut["claimed"]:
        return None
    db_exec("UPDATE user_tasks SET claimed=1, updated_at=%s WHERE user_id=%s AND task_id=%s",
            (now_uz().isoformat(), user_id, task_id))
    add_stars(user_id, t["reward"])
    return t["reward"]


def use_promocode(user_id, code):
    code = code.strip().upper()
    if not code:
        return None, "promo_not_found"
    p = db_exec("SELECT * FROM promocodes WHERE code=%s", (code,), fetch=True)
    if not p:
        return None, "promo_not_found"
    if int(p["uses_left"]) <= 0:
        return None, "promo_empty"
    if db_exec("SELECT 1 FROM promo_uses WHERE user_id=%s AND code=%s", (user_id, code), fetch=True):
        return None, "promo_used"
    db_exec("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code=%s", (code,))
    db_exec("INSERT INTO promo_uses (user_id, code, used_at) VALUES (%s, %s, %s)",
            (user_id, code, now_uz().isoformat()))
    add_stars(user_id, p["reward"])
    return p["reward"], None


def get_active_contest():
    row = db_exec("SELECT * FROM contests WHERE status='active' ORDER BY id DESC LIMIT 1", fetch=True)
    return dict(row) if row else None


def get_contest_leaderboard(contest, uid, limit=20):
    leaders = db_exec(
        "SELECT u.user_id, u.first_name AS name, COUNT(r.user_id) AS count "
        "FROM users r JOIN users u ON r.referrer_id = u.user_id "
        "WHERE r.is_verified=1 AND r.joined_at >= %s "
        "GROUP BY u.user_id, u.first_name ORDER BY count DESC LIMIT %s",
        (contest["start_at"], limit), fetchall=True) or []
    my = db_exec("SELECT COUNT(*) AS count FROM users WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s",
                 (uid, contest["start_at"]), fetch=True) or {"count": 0}
    my_rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM (SELECT referrer_id, COUNT(*) AS cnt FROM users "
        "WHERE is_verified=1 AND joined_at >= %s AND referrer_id <> 0 "
        "GROUP BY referrer_id HAVING COUNT(*) > %s) t",
        (contest["start_at"], my["count"]), fetch=True)
    u = get_user(uid) or {}
    return {
        "leaders": [{"name": r["name"] or "User", "count": int(r["count"]), "is_me": r["user_id"] == uid} for r in leaders],
        "me": {"rank": my_rank["rank"] if my_rank else 0, "name": u.get("first_name", "User"), "count": int(my["count"])},
    }


def get_ad_services(active_only=True):
    q = "SELECT * FROM ad_services"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY position, id"
    rows = db_exec(q, fetchall=True)
    return [dict(r) for r in rows] if rows else []


def get_ad_service(sid):
    row = db_exec("SELECT * FROM ad_services WHERE id=%s", (sid,), fetch=True)
    return dict(row) if row else None


def add_ad_request(user_id, service):
    db_exec("""INSERT INTO ad_requests (user_id, service_id, service_title, price_uzs, hours, status, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
            (user_id, service["id"], service["title"], service["price_uzs"],
             service["hours"], now_uz().isoformat()))


def get_premium_emoji(key, fallback=""):
    row = db_exec("SELECT emoji_id, fallback FROM premium_emojis WHERE key=%s", (key,), fetch=True)
    if row and row["emoji_id"]:
        return row["emoji_id"]
    return fallback


def set_premium_emoji(key, emoji_id, fallback=""):
    db_exec("""INSERT INTO premium_emojis (key, emoji_id, fallback) VALUES (%s, %s, %s)
               ON CONFLICT (key) DO UPDATE SET emoji_id=EXCLUDED.emoji_id, fallback=EXCLUDED.fallback""",
            (key, emoji_id, fallback))


def pe(key, fallback):
    eid = get_premium_emoji(key)
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'
    return fallback

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
    promo_code = State()


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
    gift_id_input = State()
    gift_stars = State()
    gift_premium_id = State()
    reply_to_user = State()
    review_channel = State()
    gift_channel = State()
    level_name = State()
    level_emoji = State()
    level_min = State()
    level_max = State()
    userbot_api = State()
    userbot_hash = State()
    userbot_session = State()
    contest_title = State()
    contest_desc = State()
    contest_reward_name = State()
    contest_reward_emoji = State()
    contest_days = State()
    task_title = State()
    task_emoji = State()
    task_reward = State()
    task_link = State()
    task_action = State()
    promo_code_admin = State()
    promo_reward = State()
    promo_uses = State()
    ad_title = State()
    ad_desc = State()
    ad_hours = State()
    ad_price = State()
    ad_subs = State()
    bonus_reward = State()
    pe_key = State()
    pe_id = State()
    pe_fallback = State()

# ═══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════════════
def main_menu(uid):
    lang = get_user_lang(uid)
    cb = lambda text, data: InlineKeyboardButton(text=text, callback_data=data)
    rows = []
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton(text="🚀 Mini App", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows += [
        [cb(T(lang, "ref_link"), "m_reflink")],
        [cb("🔥 " + T(lang, "bonus_menu"), "m_bonus"), cb("📌 " + T(lang, "tasks_menu"), "m_tasks")],
        [cb("🏆 " + T(lang, "contest_menu"), "m_contest"), cb("🎟 " + T(lang, "promo_menu"), "m_promo")],
        [cb(T(lang, "withdraw"), "m_withdraw"), cb(T(lang, "profile"), "m_profile")],
        [cb(T(lang, "advertise"), "m_advertise")],
        [cb(T(lang, "more_btn"), "m_more")],
    ]
    if is_admin(uid):
        rows.append([cb(T(lang, "admin"), "m_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def more_menu(uid):
    lang = get_user_lang(uid)
    u = get_user(uid) or {}
    cb = lambda text, data: InlineKeyboardButton(text=text, callback_data=data)
    remind = T(lang, "remind_on") if u.get("remind", 1) else T(lang, "remind_off")
    return InlineKeyboardMarkup(inline_keyboard=[
        [cb(T(lang, "stats"), "m_stats"), cb(T(lang, "history"), "m_history")],
        [cb(T(lang, "gift_stars"), "m_gift"), cb(T(lang, "donate"), "m_donate")],
        [cb(T(lang, "banner"), "m_banner"), cb(T(lang, "rating"), "m_rating")],
        [cb(T(lang, "review"), "m_review"), cb(T(lang, "support"), "m_support")],
        [cb(remind, "m_remind"), cb("🌐 Til", "m_lang")],
        [cb(T(lang, "back"), "m_menu")],
    ])


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
    b.button(text="🏆 Konkurslar", callback_data="a_contests")
    b.button(text="📌 Vazifalar", callback_data="a_tasks")
    b.button(text="🎟 Promokodlar", callback_data="a_promocodes")
    b.button(text="📢 Reklama tarif", callback_data="a_ads")
    b.button(text="🎁 Bonus config", callback_data="a_bonus")
    b.button(text="✨ Premium emoji", callback_data="a_pe")
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
        except TelegramBadRequest:
            continue
        except Exception:
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
async def send_human_check(target, state, uid, lang, user):
    if not user.get("phone"):
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=T(lang, "share_phone"), request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True)
        await state.set_state(US.phone)
        await target.answer(T(lang, "ask_phone"), reply_markup=kb, parse_mode="HTML")
        return

    q = get_random_question()
    if not q:
        update_user(uid, is_verified=1)
        await target.answer(T(lang, "welcome", name=user["first_name"] or "User"),
                            reply_markup=main_menu(uid), parse_mode="HTML")
        return

    answers = [(q["correct_answer"], True), (q["wrong1"], False), (q["wrong2"], False)]
    random.shuffle(answers)
    correct_idx = next(i for i, (_, okk) in enumerate(answers) if okk)
    b = InlineKeyboardBuilder()
    for i, (ans, _) in enumerate(answers):
        b.button(text=ans, callback_data=f"ans_{i}")
    b.adjust(1)
    await state.update_data(q_id=q["id"], ref_id=user["referrer_id"] or 0, ans_correct=correct_idx)
    await state.set_state(US.answer)
    await target.answer(T(lang, "bot_check", q=esc(q["question"])),
                        reply_markup=b.as_markup(), parse_mode="HTML")


@dp.message(US.phone, F.contact)
async def phone_received(message, state):
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
    await send_human_check(message, state, uid, lang, get_user(uid))


@dp.message(US.phone)
async def phone_other(message, state):
    await message.answer(T(get_user_lang(message.from_user.id), "phone_use_button"))

# ═══════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(message, state):
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
        await message.answer(T("uz", "choose_lang"), reply_markup=lang_keyboard(), parse_mode="HTML")
        return

    if not user["is_verified"] and not user["referrer_id"] and ref_id:
        update_user(uid, referrer_id=ref_id)
        user["referrer_id"] = ref_id

    lang = get_user_lang(uid)

    if user["is_banned"]:
        await message.answer(T(lang, "banned"), parse_mode="HTML")
        return

    if not await check_subs(uid):
        await message.answer(T(lang, "subscribe"), reply_markup=await subs_kb(uid), parse_mode="HTML")
        return

    update_user(uid, sub_ok=1)

    if user["is_verified"]:
        await message.answer(T(lang, "welcome", name=user["first_name"] or esc(fname)),
                            reply_markup=main_menu(uid), parse_mode="HTML")
        return

    await send_human_check(message, state, uid, lang, user)

# ═══════════════════════════════════════════════════════════
# ASOSIY MENYU HANDLERLARI
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_menu")
async def cb_menu(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "m_more")
async def cb_more(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(T(lang, "more_title"), reply_markup=more_menu(uid), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "more_title"), reply_markup=more_menu(uid), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "m_remind")
async def cb_remind(cb):
    uid = cb.from_user.id
    db_exec("UPDATE users SET remind = 1 - COALESCE(remind, 1) WHERE user_id=%s", (uid,))
    try:
        await cb.message.edit_reply_markup(reply_markup=more_menu(uid))
    except Exception:
        pass
    await cb.answer("✅")


@dp.callback_query(F.data == "m_lang")
async def cb_lang(cb, state):
    await state.clear()
    txt = "🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>"
    try:
        await cb.message.edit_text(txt, reply_markup=lang_keyboard(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=lang_keyboard(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb, state):
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
        await cb.message.answer(T(lang, "subscribe"), reply_markup=await subs_kb(uid), parse_mode="HTML")
        return
    if user["is_verified"]:
        await cb.message.answer(T(lang, "welcome", name=user["first_name"] or "User"),
                                reply_markup=main_menu(uid), parse_mode="HTML")
        return
    await send_human_check(cb.message, state, uid, lang, user)


@dp.message(US.answer)
async def ans_msg(message, state):
    await message.answer("👇 Iltimos, tugmadan tanlang")


@dp.callback_query(F.data.startswith("ans_"))
async def check_ans(cb, state):
    parts = cb.data.split("_")
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    st = await state.get_data()
    if len(parts) != 2 or "ans_correct" not in st:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    is_correct = parts[1] == str(st["ans_correct"])
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
                if not await security.referral_velocity_ok(ref_id):
                    await notify_admins(f"⚠️ Shubhali referal\nReferer: <code>{ref_id}</code>\nYangi: <code>{uid}</code>")
                else:
                    reward = int(get_setting("stars_per_referral", "2"))
                    new_stars = add_stars(ref_id, reward)
                    if new_stars is not None:
                        ref_lang = get_user_lang(ref_id)
                        try:
                            await bot.send_message(ref_id,
                                T(ref_lang, "referral_reward", n=reward) + f"\n💰 {T(ref_lang, 'total')}: <b>{new_stars} ⭐</b>",
                                parse_mode="HTML")
                        except Exception:
                            pass
                        await check_level_up(ref_id, new_stars - reward, new_stars)
                        for rt in (db_exec("SELECT id FROM tasks WHERE action='ref' AND is_active=1", fetchall=True) or []):
                            mark_task_done(ref_id, rt["id"])
    await state.clear()
    await cb.answer(T(lang, "correct"))
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(T(lang, "welcome", name=user["first_name"] or "User"),
                            reply_markup=main_menu(uid), parse_mode="HTML")


@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(cb, state):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    if not await check_subs(uid):
        await cb.answer(T(lang, "not_enough"), show_alert=True)
        return
    update_user(uid, sub_ok=1)
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
        await cb.message.answer(T(lang, "welcome", name=user["first_name"] or "User"),
                                reply_markup=main_menu(uid), parse_mode="HTML")
        return
    await send_human_check(cb.message, state, uid, lang, user)


async def check_level_up(user_id, old_stars, new_stars):
    old_lvl = get_user_level(old_stars)
    new_lvl = get_user_level(new_stars)
    if old_lvl.get("name") == new_lvl.get("name"):
        return
    lang = get_user_lang(user_id)
    nxt = None
    for l in get_levels():
        if l["min_stars"] > new_stars:
            nxt = l
            break
    if nxt:
        next_emoji = nxt.get("emoji", "")
        next_name = nxt.get("name", "")
        need = nxt["min_stars"] - new_stars
    else:
        next_emoji, next_name, need = "👑", "MAX", 0
    try:
        await bot.send_message(user_id,
            T(lang, "level_up", emoji=new_lvl.get("emoji", ""), name=new_lvl.get("name", ""),
              next_emoji=next_emoji, next_name=next_name, need=need), parse_mode="HTML")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# PROFIL / STATISTIKA (bir xil format)
# ═══════════════════════════════════════════════════════════
def _profile_text(uid, lang, user):
    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
    ref_count = refs["c"] if refs else 0
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    week_refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s",
                       (uid, week_ago), fetch=True)
    week_ref_count = week_refs["c"] if week_refs else 0
    rank_row = db_exec("SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0",
                      (user["stars"],), fetch=True)
    rank = rank_row["rank"] if rank_row else "—"
    donated = total_donated(uid)
    lvl = get_user_level(user["stars"])
    nxt = _next_level(user["stars"])
    bar, pct = progress_bar(user["stars"], lvl.get("min_stars", 0), lvl.get("max_stars", 10))
    next_text = (f"{nxt.get('emoji', '')} {nxt.get('name', '')} — {nxt['min_stars']} ⭐"
                 if nxt else "👑 <b>Eng yuqori daraja!</b>")
    uname = f"@{user['username']}" if user["username"] else "—"
    return (
        f"{box_title('👤 PROFIL')}\n"
        f"<b>{user['first_name'] or 'N/A'}</b> · {uname}\n<code>{uid}</code>\n\n"
        f"{lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n"
        f"{bar}  {pct}%\n"
        f"⭐ <b>{format_number(user['stars'])}</b> Stars\n"
        f"⬆️ Keyingi: {next_text}\n\n"
        f"{DIV}\n"
        f"{kv('👥', 'Takliflar', format_number(ref_count) + ' ta')}\n"
        f"{kv('📈', 'Bu hafta', '+' + format_number(week_ref_count))}\n"
        f"{kv('🏆', \"O'rin\", '#' + format_number(rank))}\n"
        f"{kv('💝', 'Donat', format_number(donated) + ' ⭐')}\n\n"
        f"{DIV}\n"
        f"{'✅' if user['is_verified'] else '❌'} Tasdiqlangan   "
        f"{'🚫' if user['is_banned'] else '✅'} Holat\n"
        f"📅 Qo'shilgan: {(user['joined_at'] or '—')[:10]}"
    )


@dp.callback_query(F.data == "m_profile")
async def cb_profile(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    text = _profile_text(uid, lang, user)
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="m_profile")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
    await cb.answer()


@dp.callback_query(F.data == "m_stats")
async def cb_stats(cb, state):
    await cb_profile(cb, state)


# ═══════════════════════════════════════════════════════════
# BONUS
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_bonus")
async def cb_bonus(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    info = check_daily_bonus(uid)
    if info["can_claim"]:
        text = T(lang, "bonus_available", reward=info["reward"], streak=info["streak"], next=info["next_reward"])
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "bonus_btn", n=info["reward"]), callback_data="claim_daily")
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
    else:
        text = T(lang, "bonus_claimed", streak=info["streak"], next=info["next_reward"])
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "claim_daily")
async def claim_daily_cb(cb):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    res = claim_daily_bonus(uid)
    if res is None:
        await cb.answer(T(lang, "bonus_already"), show_alert=True)
        return
    try:
        await bot.send_message(uid, T(lang, "stars_added", n=res["reward"], reason="Kunlik bonus",
                                      total=(get_user(uid) or {}).get("stars", 0)), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer(T(lang, "bonus_ok", n=res["reward"], streak=res["streak"]), show_alert=True)
    info = check_daily_bonus(uid)
    text = T(lang, "bonus_claimed", streak=info["streak"], next=info["next_reward"])
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# KONKURS
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_contest")
async def cb_contest(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    contest = get_active_contest()
    if not contest:
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
        try:
            await cb.message.edit_text(T(lang, "contest_none"), reply_markup=b.as_markup(), parse_mode="HTML")
        except Exception:
            await cb.message.answer(T(lang, "contest_none"), reply_markup=b.as_markup(), parse_mode="HTML")
        await cb.answer()
        return
    lb = get_contest_leaderboard(contest, uid, limit=10)
    try:
        end = datetime.fromisoformat(contest["end_at"])
    except Exception:
        end = now_uz()
    diff = (end - now_uz()).total_seconds()
    days, hours = int(diff // 86400), int((diff % 86400) // 3600)
    title_pe = pe("contest", "🏆") + " <b>" + esc(contest["title"]) + "</b>"
    text = (f"{box_title(T(lang, 'contest_title'))}\n"
            f"{title_pe}\n\n"
            f"<i>{esc(contest['description'])}</i>\n\n"
            f"{DIV}\n"
            f"🎁 <b>Sovrin:</b> {esc(contest['reward_emoji'])} <b>{esc(contest['reward_name'])}</b>\n"
            f"⏰ <b>Qoldi:</b> {days} kun {hours} soat\n\n{DIV}\n"
            f"📊 <b>LEADERBOARD:</b>\n\n")
    if lb["leaders"]:
        for i, l in enumerate(lb["leaders"], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"<b>{i}.</b>"
            me_tag = " ⬅️ <b>SIZ</b>" if l["is_me"] else ""
            text += f"{medal} {esc(l['name'])} — <b>{format_number(l['count'])}</b> ta{me_tag}\n"
    else:
        text += "<i>Hozircha qatnashuvchi yo'q</i>\n"
    text += (f"\n{DIV}\n👤 <b>SIZ:</b> #{format_number(lb['me']['rank'])} — "
             f"<b>{format_number(lb['me']['count'])}</b> ta referal")
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "share"), callback_data="m_reflink")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


# ═══════════════════════════════════════════════════════════
# VAZIFALAR
# ═══════════════════════════════════════════════════════════
async def refresh_task_status(uid):
    for t in get_user_tasks(uid):
        if t["action"] == "ref" and not t["done"]:
            refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
            if refs and refs["c"] > 0:
                mark_task_done(uid, t["id"])
        elif t["action"] == "profile" and not t["done"]:
            u = get_user(uid)
            if u and u.get("phone"):
                mark_task_done(uid, t["id"])
        elif t["action"] == "sub" and not t["done"]:
            if await check_subs(uid):
                mark_task_done(uid, t["id"])


@dp.callback_query(F.data == "m_tasks")
async def cb_tasks(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    await refresh_task_status(uid)
    tasks = get_user_tasks(uid)
    text = f"{box_title('📌 ' + T(lang, 'tasks_title'))}\n\n"
    b = InlineKeyboardBuilder()
    if tasks:
        for t in tasks:
            if t["claimed"]:
                status = f"✅ <b>{t['reward']} ⭐ olindi</b>"
            elif t["claimable"]:
                status = "🎁 <b>Mukofot tayyor!</b>"
                b.button(text=f"🎁 {t['title'][:25]} → +{t['reward']}", callback_data=f"claimtask_{t['id']}")
            elif t["done"]:
                status = "✅ <b>Bajarildi</b>"
            else:
                status = "⏳ <i>Bajarilmagan</i>"
            text += f"{esc(t['emoji'])} <b>{esc(t['title'])}</b>\n   +{t['reward']} ⭐ — {status}\n\n"
    else:
        text += "<i>Vazifalar yo'q</i>\n\n"
    text += BOX_BOTTOM
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("claimtask_"))
async def claim_task_cb(cb, state):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    task_id = int(cb.data.replace("claimtask_", ""))
    reward = claim_task_reward(uid, task_id)
    if reward is None:
        await cb.answer("❌ Mukofot olish mumkin emas", show_alert=True)
        return
    try:
        await bot.send_message(uid, T(lang, "stars_added", n=reward, reason="Vazifa mukofoti",
                                      total=(get_user(uid) or {}).get("stars", 0)), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer(T(lang, "bonus_ok", n=reward, streak=0), show_alert=False)
    await cb_tasks(cb, state)


# ═══════════════════════════════════════════════════════════
# PROMOKOD
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_promo")
async def cb_promo(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(T(lang, "promo_title"), reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "promo_title"), reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.promo_code)
    await cb.answer()


@dp.message(US.promo_code)
async def promo_code_input(message, state):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    code = (message.text or "").strip().upper()
    if not code:
        await message.answer(T(lang, "promo_not_found"))
        return
    reward, err2 = use_promocode(uid, code)
    await state.clear()
    if err2:
        await message.answer(T(lang, err2), parse_mode="HTML")
        return
    await message.answer(T(lang, "promo_ok", n=reward), parse_mode="HTML")
    try:
        await bot.send_message(uid, T(lang, "stars_added", n=reward, reason=f"Promokod: {code}",
                                      total=(get_user(uid) or {}).get("stars", 0)), parse_mode="HTML")
    except Exception:
        pass
    await message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
