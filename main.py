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
    BufferedInputFile, WebAppInfo, LabeledPrice,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web

from telethon import TelegramClient, functions, types as tt
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

import security
from security import adb, aio

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

# Bonus streak mukofotlari (0-kun, 1-kun, 2-kun, ..., 6+ kun)
BONUS_REWARDS = [3, 5, 8, 12, 18, 25, 50]

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
        "gift_failed": "⚠️ <b>Giftni yuborib bo'lmadi.</b>\n\n{gift}\n\n💰 <b>{n} ⭐</b> balansingizga qaytarildi.",
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
        "admin_reply": "📬 <b>Admindan javob:</b>",
        "user_msg": "📩 <b>Foydalanuvchidan xabar:</b>",
        "gift_stars_title": "🎁 <b>Stars sovg'a qilish</b>\n\n💰 Sizda: <b>{bal} ⭐</b>\n\nFoydalanuvchi <b>username</b> yoki <b>ID</b> sini kiriting:",
        "gift_stars_amount": "👤 Qabul qiluvchi: <b>{name}</b>\n\nNechta stars sovg'a qilasiz?",
        "gift_stars_confirm": "🎁 <b>Tasdiqlang</b>\n\n👤 Kimga: <b>{name}</b>\n⭐ Miqdor: <b>{n} ⭐</b>",
        "gift_stars_sent": "✅ <b>{n} ⭐ {name} ga yuborildi!</b>",
        "gift_stars_received": "🎁 <b>Sizga stars sovg'a qilindi!</b>\n\n👤 Kimdan: <b>{name}</b>\n⭐ Miqdor: <b>+{n} ⭐</b>\n\n💰 Jami: <b>{total} ⭐</b>",
        "gift_stars_not_found": "❌ Foydalanuvchi topilmadi.",
        "gift_stars_self": "❌ O'zingizga sovg'a qila olmaysiz.",
        "review_title": "⭐ <b>Sharh qoldirish</b>\n\nBot haqida fikringizni yozing:",
        "review_sent": "✅ <b>Sharhingiz yuborildi!</b>",
        "review_approved": "✅ <b>Sharhingiz tasdiqlandi!</b>",
        "review_rejected": "❌ <b>Sharhingiz rad etildi.</b>",
        "level": "Daraja",
        "stars_will_send": "✅ <b>So'rovingiz tasdiqlandi!</b>\n\n⭐ Miqdor: <b>{n} ⭐</b>",
        "level_up": "🎉 <b>TABRIKLAYMIZ!</b>\n\nSiz {emoji} <b>{name}</b> darajasiga chiqdingiz!\n\n⬆️ Keyingi: {next_emoji} <b>{next_name}</b>\n📊 Kerak: <b>{need} ⭐</b>",
        "banner_caption": "🎨 <b>Sizning shaxsiy baneringiz</b>",
        "ask_phone": "📱 <b>Telefon raqamingizni tasdiqlang</b>\n\nFaqat 🇺🇿 <b>+998</b> raqamlari qabul qilinadi.",
        "share_phone": "📱 Raqamni yuborish",
        "phone_not_own": "❌ Faqat o'zingizning raqamingizni yuboring.",
        "phone_only_uz": "❌ Faqat O'zbekiston raqamlari (+998 XX XXX XX XX).",
        "phone_used": "❌ Bu raqam boshqa akkauntga bog'langan.",
        "phone_use_button": "ℹ️ Iltimos, pastdagi «📱 Raqamni yuborish» tugmasidan foydalaning.",
        "donate_title": (
            "💝 <b>Donat qilish</b>\n\n"
            "Donat — botni qo'llab-quvvatlash. Siz <b>Telegram Stars</b> "
            "yordamida botga stars yuborasiz.\n\n"
            "💡 <i>Telegram Stars — Telegram'ning ichki valyutasi. "
            "Uni @xorazmll orqali sotib olishingiz mumkin.</i>\n\n"
            "⭐ <b>Necha Stars yubormoqchisiz?</b>"
        ),
        "donate_ok": "💝 <b>Rahmat!</b>\n\nSiz <b>{n} ⭐</b> donat qildingiz!\n\n🏆 Donat reytingida ko'rinasiz!",
        "donate_invoice_title": "Botga donat",
        "donate_invoice_desc": "Botni qo'llab-quvvatlash uchun {n} Stars",
        "donate_invoice_btn": "⭐ {n} Stars to'lash",
        "rating_choose": "🏆 <b>Reyting</b>\n\nQaysi reytingni ko'rmoqchisiz?",
        "rating_stars": "⭐ Eng ko'p stars egalari",
        "rating_donate": "💝 Eng ko'p donat qilganlar",
        "rating_ref": "👥 Eng ko'p referal yig'ganlar",
        # YANGI
        "bonus_menu": "🔥 Kunlik bonus",
        "contest_menu": "🏆 Konkurs",
        "promo_menu": "🎟 Promokod",
        "tasks_menu": "📌 Vazifalar",
        "bonus_title": "🔥 <b>Kunlik bonus</b>",
        "bonus_available": "🎁 Bugungi mukofot: <b>{reward} ⭐</b>\n🔥 Seriya: <b>{streak} kun</b>\n\nKeyingi kun: <b>{next} ⭐</b>",
        "bonus_claimed": "✅ Bugun olindi!\n🔥 Seriya: <b>{streak} kun</b>\n\n⏰ Ertaga yana keling — <b>{next} ⭐</b>",
        "bonus_btn": "🎁 {n} ⭐ olish",
        "bonus_ok": "🎉 <b>+{n} ⭐</b> bonus olindi!\n🔥 Seriya: <b>{streak} kun</b>",
        "bonus_already": "⏰ Bugun allaqachon olgansiz. Ertaga qaytib keling!",
        "promo_title": "🎟 <b>Promokod</b>\n\nKodni kiriting va stars oling:",
        "promo_ok": "🎉 <b>+{n} ⭐</b> promokod orqali qo'shildi!",
        "promo_not_found": "❌ Promokod topilmadi.",
        "promo_used": "❌ Siz bu kodni ishlatgansiz.",
        "promo_empty": "❌ Promokod tugagan.",
        "tasks_title": "📌 <b>Vazifalar</b>\n\nVazifalarni bajaring va stars oling:",
        "task_done": "✅ Bajarildi",
        "task_claim": "🎁 +{n} ⭐ olish",
        "task_claimed": "✅ Mukofot olindi",
        "task_not_done": "⏳ Bajarilmagan",
        "task_ok": "🎉 <b>+{n} ⭐</b> vazifa mukofoti!",
        "contest_title": "🏆 <b>Faol konkurs</b>",
        "contest_none": "🏆 Hozircha faol konkurs yo'q.\n\nTez orada yangi konkurs boshlanadi!",
    },

    "ru": {
        "flag": "🇷🇺", "name": "Русский",
        "choose_lang": "🌐 <b>Выберите язык</b>\n\nПожалуйста, выберите удобный для вас язык:",
        "lang_set": "✅ Язык успешно изменён!",
        "welcome": "👋 <b>Привет, {name}!</b>\n\n🎯 <i>Добро пожаловать в реферальный бот!</i>\n\nВыберите нужный раздел из меню ниже 👇",
        "menu_title": "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        "profile": "👤 Профиль",
        "stats": "📊 Статистика",
        "banner": "🎨 Баннер",
        "webapp": "🚀 Мини App",
        "ref_link": "🔗 Реферальная ссылка",
        "rating": "🏆 Рейтинг",
        "withdraw": "💰 Вывод",
        "donate": "💝 Донат",
        "support": "💬 Связь с админом",
        "gift_stars": "🎁 Подарить Stars",
        "review": "⭐ Оставить отзыв",
        "admin": "🛠 Админ панель",
        "share": "📤 Поделиться",
        "back": "⬅️ Назад",
        "menu": "🏠 Главное меню",
        "cancel": "❌ Отмена",
        "close_chat": "🔚 Завершить чат",
        "banned": "🚫 <b>Вы забанены!</b>\n\nСвяжитесь с админом.",
        "subscribe": "📢 <b>Подпишитесь на каналы для использования бота:</b>\n\nПосле подписки нажмите «✅ Проверить».",
        "check": "✅ Проверить",
        "bot_check": "🤖 <b>Подтвердите, что вы не бот</b>\n\n❓ <b>Вопрос:</b> {q}\n\nВыберите правильный ответ 👇",
        "wrong_answer": "❌ Неправильный ответ!",
        "correct": "✅ Подтверждено!",
        "wrong_ans_retry": "❌ <b>Неправильный ответ!</b>\n\nПопробуйте снова: /start",
        "start_first": "ℹ️ Пожалуйста, отправьте /start",
        "not_enough": "❌ <b>Недостаточно!</b>",
        "min_withdraw": "❌ Минимум: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Максимум: <b>{n} ⭐</b>",
        "enter_number": "❌ Введите только число.",
        "choose_reward": "🎁 Выберите тип награды:",
        "stars_withdraw": "⭐ Получить Stars",
        "gift_withdraw": "🎁 Получить Telegram Gift",
        "sent_to_admin": "✅ <b>Запрос отправлен!</b>\n\n⭐ Сумма: <b>{n} ⭐</b>\n⏳ Ожидайте подтверждения админа...",
        "gift_processing": "⏳ <b>Отправляем gift...</b>\n\n{gift} — <b>{n} ⭐</b>",
        "gift_done": "🎉 <b>Gift отправлен!</b>\n\n{gift}\n⭐ Цена: <b>{n} ⭐</b>\n\n🎁 Проверьте свой профиль Telegram!",
        "gift_failed": "⚠️ <b>Не удалось отправить gift.</b>\n\n{gift}\n\n💰 <b>{n} ⭐</b> возвращены на ваш баланс.",
        "gift_ask_anon": "{gift} — <b>{n} ⭐</b>\n\n🕶 Отправить gift <b>анонимно</b>?",
        "gift_anon_yes": "🕶 Анонимно",
        "gift_anon_no": "👤 Показать моё имя",
        "gift_ask_comment": "💬 <b>Какой комментарий добавить к gift?</b>\n\nОтправьте текст (макс. 120 символов) или нажмите «Без комментария».",
        "gift_no_comment": "➡️ Без комментария",
        "approved": "✅ <b>Ваш запрос одобрен!</b>",
        "rejected": "❌ <b>Ваш запрос отклонён.</b>",
        "referral_reward": "🎉 <b>Новый реферал!</b>\n\n➕ +{n} ⭐ добавлено",
        "total": "Всего",
        "balance": "У вас",
        "need": "Нужно",
        "stars_added": "🎁 <b>Вам добавлены stars!</b>\n\n➕ Сумма: <b>+{n} ⭐</b>\n📝 Причина: <i>{reason}</i>\n\n💰 Всего: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Списаны stars!</b>\n\n➖ Сумма: <b>{n} ⭐</b>\n📝 Причина: <i>{reason}</i>\n\n💰 Всего: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Связь с админом</b>\n\nНапишите свой вопрос — админ скоро ответит.",
        "support_sent": "✅ <b>Ваш вопрос отправлен админу!</b>",
        "support_new_msg": "📩 <b>Новое обращение!</b>\n\n👤 <b>User:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Время:</b> {time}",
        "reply_sent": "✅ <b>Ответ отправлен!</b>",
        "chat_active": "💬 <b>Чат активен</b>\n\nНапишите ваше сообщение.",
        "chat_closed_by_admin": "🔚 <b>Админ завершил чат.</b>",
        "admin_reply": "📬 <b>Ответ от админа:</b>",
        "user_msg": "📩 <b>От пользователя:</b>",
        "gift_stars_title": "🎁 <b>Подарить Stars</b>\n\n💰 У вас: <b>{bal} ⭐</b>\n\nВведите <b>username</b> или <b>ID</b> получателя:",
        "gift_stars_amount": "👤 Получатель: <b>{name}</b>\n\nСколько stars подарить?",
        "gift_stars_confirm": "🎁 <b>Подтвердите</b>\n\n👤 Кому: <b>{name}</b>\n⭐ Сумма: <b>{n} ⭐</b>",
        "gift_stars_sent": "✅ <b>{n} ⭐ отправлено {name}!</b>",
        "gift_stars_received": "🎁 <b>Вам подарили stars!</b>\n\n👤 От: <b>{name}</b>\n⭐ Сумма: <b>+{n} ⭐</b>\n\n💰 Всего: <b>{total} ⭐</b>",
        "gift_stars_not_found": "❌ Пользователь не найден.",
        "gift_stars_self": "❌ Нельзя подарить самому себе.",
        "review_title": "⭐ <b>Оставить отзыв</b>\n\nНапишите ваш отзыв о боте:",
        "review_sent": "✅ <b>Ваш отзыв отправлен!</b>",
        "review_approved": "✅ <b>Ваш отзыв одобрен!</b>",
        "review_rejected": "❌ <b>Ваш отзыв отклонён.</b>",
        "level": "Уровень",
        "stars_will_send": "✅ <b>Ваш запрос одобрен!</b>\n\n⭐ Сумма: <b>{n} ⭐</b>",
        "level_up": "🎉 <b>ПОЗДРАВЛЯЕМ!</b>\n\nВы достигли уровня {emoji} <b>{name}</b>!\n\n⬆️ Следующий: {next_emoji} <b>{next_name}</b>\n📊 Нужно: <b>{need} ⭐</b>",
        "banner_caption": "🎨 <b>Ваш персональный баннер</b>",
        "ask_phone": "📱 <b>Подтвердите номер телефона</b>\n\nПринимаются только 🇺🇿 номера <b>+998</b>.",
        "share_phone": "📱 Отправить номер",
        "phone_not_own": "❌ Отправьте только свой номер.",
        "phone_only_uz": "❌ Только номера Узбекистана (+998 XX XXX XX XX).",
        "phone_used": "❌ Этот номер уже привязан к другому аккаунту.",
        "phone_use_button": "ℹ️ Пожалуйста, используйте кнопку «📱 Отправить номер».",
        "donate_title": (
            "💝 <b>Донат</b>\n\n"
            "Донат — поддержка бота. Вы отправляете stars через "
            "<b>Telegram Stars</b>.\n\n"
            "💡 <i>Telegram Stars — внутренняя валюта Telegram. "
            "Купить можно через @xorazmll.</i>\n\n"
            "⭐ <b>Сколько Stars отправить?</b>"
        ),
        "donate_ok": "💝 <b>Спасибо!</b>\n\nВы отправили <b>{n} ⭐</b>!\n\n🏆 Вы в рейтинге донатов!",
        "donate_invoice_title": "Донат боту",
        "donate_invoice_desc": "Поддержка бота на {n} Stars",
        "donate_invoice_btn": "⭐ Оплатить {n} Stars",
        "rating_choose": "🏆 <b>Рейтинг</b>\n\nКакой рейтинг посмотреть?",
        "rating_stars": "⭐ Больше всего Stars",
        "rating_donate": "💝 Больше всего донатов",
        "rating_ref": "👥 Больше всего рефералов",
        "bonus_menu": "🔥 Ежедневный бонус",
        "contest_menu": "🏆 Конкурс",
        "promo_menu": "🎟 Промокод",
        "tasks_menu": "📌 Задания",
        "bonus_title": "🔥 <b>Ежедневный бонус</b>",
        "bonus_available": "🎁 Сегодняшний бонус: <b>{reward} ⭐</b>\n🔥 Серия: <b>{streak} дн.</b>\n\nСледующий день: <b>{next} ⭐</b>",
        "bonus_claimed": "✅ Сегодня получен!\n🔥 Серия: <b>{streak} дн.</b>\n\n⏰ Возвращайтесь завтра — <b>{next} ⭐</b>",
        "bonus_btn": "🎁 Получить {n} ⭐",
        "bonus_ok": "🎉 <b>+{n} ⭐</b> бонус получен!\n🔥 Серия: <b>{streak} дн.</b>",
        "bonus_already": "⏰ Сегодня уже получен. Возвращайтесь завтра!",
        "promo_title": "🎟 <b>Промокод</b>\n\nВведите код и получите stars:",
        "promo_ok": "🎉 <b>+{n} ⭐</b> добавлено через промокод!",
        "promo_not_found": "❌ Промокод не найден.",
        "promo_used": "❌ Вы уже использовали этот код.",
        "promo_empty": "❌ Промокод закончился.",
        "tasks_title": "📌 <b>Задания</b>\n\nВыполняйте задания и получайте stars:",
        "task_done": "✅ Выполнено",
        "task_claim": "🎁 Получить +{n} ⭐",
        "task_claimed": "✅ Получено",
        "task_not_done": "⏳ Не выполнено",
        "task_ok": "🎉 <b>+{n} ⭐</b> за задание!",
        "contest_title": "🏆 <b>Активный конкурс</b>",
        "contest_none": "🏆 Пока нет активного конкурса.\n\nСкоро начнётся новый!",
    },

    "en": {
        "flag": "🇬🇧", "name": "English",
        "choose_lang": "🌐 <b>Choose language</b>\n\nPlease choose your preferred language:",
        "lang_set": "✅ Language changed successfully!",
        "welcome": "👋 <b>Hi, {name}!</b>\n\n🎯 <i>Welcome to the referral bot!</i>\n\nChoose a section from the menu below 👇",
        "menu_title": "🏠 <b>Main menu</b>\n\nChoose a section:",
        "profile": "👤 Profile",
        "stats": "📊 Statistics",
        "banner": "🎨 Banner",
        "webapp": "🚀 Mini App",
        "ref_link": "🔗 Referral link",
        "rating": "🏆 Rating",
        "withdraw": "💰 Withdraw",
        "donate": "💝 Donate",
        "support": "💬 Contact admin",
        "gift_stars": "🎁 Gift Stars",
        "review": "⭐ Leave review",
        "admin": "🛠 Admin Panel",
        "share": "📤 Share",
        "back": "⬅️ Back",
        "menu": "🏠 Main menu",
        "cancel": "❌ Cancel",
        "close_chat": "🔚 Close chat",
        "banned": "🚫 <b>You are banned!</b>\n\nContact admin.",
        "subscribe": "📢 <b>Subscribe to channels to use the bot:</b>\n\nAfter subscribing, press «✅ Check».",
        "check": "✅ Check",
        "bot_check": "🤖 <b>Confirm you're not a bot</b>\n\n❓ <b>Question:</b> {q}\n\nChoose the correct answer 👇",
        "wrong_answer": "❌ Wrong answer!",
        "correct": "✅ Confirmed!",
        "wrong_ans_retry": "❌ <b>Wrong answer!</b>\n\nTry again: /start",
        "start_first": "ℹ️ Please send /start",
        "not_enough": "❌ <b>Not enough!</b>",
        "min_withdraw": "❌ Minimum: <b>{n} ⭐</b>",
        "max_withdraw": "❌ Maximum: <b>{n} ⭐</b>",
        "enter_number": "❌ Numbers only.",
        "choose_reward": "🎁 Choose reward type:",
        "stars_withdraw": "⭐ Get Stars",
        "gift_withdraw": "🎁 Get Telegram Gift",
        "sent_to_admin": "✅ <b>Request sent!</b>\n\n⭐ Amount: <b>{n} ⭐</b>\n⏳ Wait for admin approval...",
        "gift_processing": "⏳ <b>Sending your gift...</b>\n\n{gift} — <b>{n} ⭐</b>",
        "gift_done": "🎉 <b>Gift sent!</b>\n\n{gift}\n⭐ Price: <b>{n} ⭐</b>\n\n🎁 Check your Telegram profile!",
        "gift_failed": "⚠️ <b>Couldn't send the gift.</b>\n\n{gift}\n\n💰 <b>{n} ⭐</b> was returned to your balance.",
        "gift_ask_anon": "{gift} — <b>{n} ⭐</b>\n\n🕶 Send the gift <b>anonymously</b>?",
        "gift_anon_yes": "🕶 Anonymous",
        "gift_anon_no": "👤 Show my name",
        "gift_ask_comment": "💬 <b>What comment should be added to the gift?</b>\n\nSend text (max 120 chars) or press «No comment».",
        "gift_no_comment": "➡️ No comment",
        "approved": "✅ <b>Your request approved!</b>",
        "rejected": "❌ <b>Your request rejected.</b>",
        "referral_reward": "🎉 <b>New referral!</b>\n\n➕ +{n} ⭐ added",
        "total": "Total",
        "balance": "You have",
        "need": "Need",
        "stars_added": "🎁 <b>Stars added!</b>\n\n➕ Amount: <b>+{n} ⭐</b>\n📝 Reason: <i>{reason}</i>\n\n💰 Total: <b>{total} ⭐</b>",
        "stars_removed": "⚠️ <b>Stars removed!</b>\n\n➖ Amount: <b>{n} ⭐</b>\n📝 Reason: <i>{reason}</i>\n\n💰 Total: <b>{total} ⭐</b>",
        "support_title": "💬 <b>Contact admin</b>\n\nWrite your question — admin will reply soon.",
        "support_sent": "✅ <b>Your question sent to admin!</b>",
        "support_new_msg": "📩 <b>New message!</b>\n\n👤 <b>User:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>ID:</b> <code>{uid}</code>\n📅 <b>Time:</b> {time}",
        "reply_sent": "✅ <b>Reply sent!</b>",
        "chat_active": "💬 <b>Chat active</b>\n\nSend your message.",
        "chat_closed_by_admin": "🔚 <b>Admin closed the chat.</b>",
        "admin_reply": "📬 <b>Reply from admin:</b>",
        "user_msg": "📩 <b>From user:</b>",
        "gift_stars_title": "🎁 <b>Gift Stars</b>\n\n💰 You have: <b>{bal} ⭐</b>\n\nEnter recipient's <b>username</b> or <b>ID</b>:",
        "gift_stars_amount": "👤 Recipient: <b>{name}</b>\n\nHow many stars to gift?",
        "gift_stars_confirm": "🎁 <b>Confirm</b>\n\n👤 To: <b>{name}</b>\n⭐ Amount: <b>{n} ⭐</b>",
        "gift_stars_sent": "✅ <b>{n} ⭐ sent to {name}!</b>",
        "gift_stars_received": "🎁 <b>You received stars!</b>\n\n👤 From: <b>{name}</b>\n⭐ Amount: <b>+{n} ⭐</b>\n\n💰 Total: <b>{total} ⭐</b>",
        "gift_stars_not_found": "❌ User not found.",
        "gift_stars_self": "❌ Can't gift yourself.",
        "review_title": "⭐ <b>Leave review</b>\n\nWrite your review about the bot:",
        "review_sent": "✅ <b>Your review sent!</b>",
        "review_approved": "✅ <b>Your review approved!</b>",
        "review_rejected": "❌ <b>Your review rejected.</b>",
        "level": "Level",
        "stars_will_send": "✅ <b>Your request approved!</b>\n\n⭐ Amount: <b>{n} ⭐</b>",
        "level_up": "🎉 <b>CONGRATULATIONS!</b>\n\nYou reached {emoji} <b>{name}</b> level!\n\n⬆️ Next: {next_emoji} <b>{next_name}</b>\n📊 Need: <b>{need} ⭐</b>",
        "banner_caption": "🎨 <b>Your personal banner</b>",
        "ask_phone": "📱 <b>Confirm your phone number</b>\n\nOnly 🇺🇿 <b>+998</b> numbers are accepted.",
        "share_phone": "📱 Share number",
        "phone_not_own": "❌ Send only your own number.",
        "phone_only_uz": "❌ Only Uzbekistan numbers (+998 XX XXX XX XX).",
        "phone_used": "❌ This number is linked to another account.",
        "phone_use_button": "ℹ️ Please use the «📱 Share number» button below.",
        "donate_title": (
            "💝 <b>Donate</b>\n\n"
            "Donate — support the bot. You send stars via "
            "<b>Telegram Stars</b>.\n\n"
            "💡 <i>Telegram Stars — internal Telegram currency. "
            "Buy it via @xorazmll.</i>\n\n"
            "⭐ <b>How many Stars to send?</b>"
        ),
        "donate_ok": "💝 <b>Thank you!</b>\n\nYou sent <b>{n} ⭐</b>!\n\n🏆 You're in the donate rating!",
        "donate_invoice_title": "Donate to bot",
        "donate_invoice_desc": "Support bot with {n} Stars",
        "donate_invoice_btn": "⭐ Pay {n} Stars",
        "rating_choose": "🏆 <b>Rating</b>\n\nWhich rating to view?",
        "rating_stars": "⭐ Most Stars",
        "rating_donate": "💝 Most Donations",
        "rating_ref": "👥 Most Referrals",
        "bonus_menu": "🔥 Daily bonus",
        "contest_menu": "🏆 Contest",
        "promo_menu": "🎟 Promocode",
        "tasks_menu": "📌 Tasks",
        "bonus_title": "🔥 <b>Daily bonus</b>",
        "bonus_available": "🎁 Today's reward: <b>{reward} ⭐</b>\n🔥 Streak: <b>{streak} days</b>\n\nNext day: <b>{next} ⭐</b>",
        "bonus_claimed": "✅ Claimed today!\n🔥 Streak: <b>{streak} days</b>\n\n⏰ Come back tomorrow — <b>{next} ⭐</b>",
        "bonus_btn": "🎁 Claim {n} ⭐",
        "bonus_ok": "🎉 <b>+{n} ⭐</b> bonus claimed!\n🔥 Streak: <b>{streak} days</b>",
        "bonus_already": "⏰ Already claimed today. Come back tomorrow!",
        "promo_title": "🎟 <b>Promocode</b>\n\nEnter the code to get stars:",
        "promo_ok": "🎉 <b>+{n} ⭐</b> added via promocode!",
        "promo_not_found": "❌ Promocode not found.",
        "promo_used": "❌ You already used this code.",
        "promo_empty": "❌ Promocode expired.",
        "tasks_title": "📌 <b>Tasks</b>\n\nComplete tasks and earn stars:",
        "task_done": "✅ Done",
        "task_claim": "🎁 Claim +{n} ⭐",
        "task_claimed": "✅ Claimed",
        "task_not_done": "⏳ Not done",
        "task_ok": "🎉 <b>+{n} ⭐</b> for task!",
        "contest_title": "🏆 <b>Active contest</b>",
        "contest_none": "🏆 No active contest yet.\n\nA new one starts soon!",
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
    c.execute("ALTER TABLE gifts ADD COLUMN IF NOT EXISTS gift_id BIGINT")

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
        charge_id TEXT UNIQUE,
        payload TEXT,
        status TEXT DEFAULT 'received',
        created_at TEXT
    )""")

    # ═══ KONKURS ═══
    c.execute("""CREATE TABLE IF NOT EXISTS contests (
        id SERIAL PRIMARY KEY,
        title TEXT,
        description TEXT,
        reward_emoji TEXT DEFAULT '🎁',
        reward_name TEXT DEFAULT 'Telegram Gift',
        target INTEGER DEFAULT 0,
        start_at TEXT,
        end_at TEXT,
        status TEXT DEFAULT 'active',
        winner_id BIGINT DEFAULT 0,
        winner_referrals INTEGER DEFAULT 0,
        created_at TEXT
    )""")

    # ═══ KUNLIK BONUS ═══
    c.execute("""CREATE TABLE IF NOT EXISTS daily_bonus (
        user_id BIGINT PRIMARY KEY,
        last_claim TEXT,
        streak INTEGER DEFAULT 0,
        total_claimed INTEGER DEFAULT 0
    )""")

    # ═══ VAZIFALAR ═══
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        title TEXT,
        emoji TEXT DEFAULT '📌',
        reward INTEGER DEFAULT 5,
        link TEXT,
        action TEXT DEFAULT 'manual',
        is_active INTEGER DEFAULT 1,
        once INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_tasks (
        user_id BIGINT,
        task_id INTEGER,
        done INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        updated_at TEXT,
        PRIMARY KEY (user_id, task_id)
    )""")

    # ═══ PROMOKODLAR ═══
    c.execute("""CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        uses_left INTEGER DEFAULT 100,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS promo_uses (
        user_id BIGINT,
        code TEXT,
        used_at TEXT,
        PRIMARY KEY (user_id, code)
    )""")

    defaults = {
        "stars_per_referral": "2",
        "min_withdraw": "50",
        "max_withdraw": "1000000",
        "review_channel": "",
        "gift_channel": "",
        "min_donate": "1",
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
            ("heart",     "💝", "Heart",      15,  5170145012310081615),
            ("teddy",     "🧸", "Teddy Bear", 15,  5170233102089325572),
            ("giftbox",   "🎁", "Gift Box",   25,  5170250435875467955),
            ("rose",      "🌹", "Rose",       25,  5168103777161739235),
            ("cake",      "🎂", "Cake",       50,  5170145012310081620),
            ("bouquet",   "💐", "Bouquet",    50,  5170250435875467960),
            ("rocket",    "🚀", "Rocket",     50,  5170233102089325580),
            ("champagne", "🍾", "Champagne",  50,  5170145012310081630),
            ("trophy",    "🏆", "Trophy",     100, 5170250435875467970),
            ("ring",      "💍", "Ring",       100, 5168103777161739245),
            ("diamond",   "💎", "Diamond",    100, 5170233102089325590),
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
            ("Do'stni taklif qilish",  "👥", 5,  None,          "ref",     1, 0),
            ("Kanalga obuna bo'lish",  "📢", 10, "@StarRushUZ",  "sub",     1, 1),
            ("Mini App'ga kirish",     "🚀", 3,  None,          "webapp",  1, 0),
            ("Profilni to'ldirish",    "✅", 5,  None,          "profile", 1, 0),
        ]
        for t in defaults_tasks:
            c.execute("""INSERT INTO tasks (title, emoji, reward, link, action, is_active, once)
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""", t)

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

def del_setting(key):
    db_exec("DELETE FROM settings WHERE key=%s", (key,))

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

def add_gift(key, emoji, name, stars, gift_id=None):
    db_exec("""INSERT INTO gifts (key, emoji, name, stars, gift_id)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (key) DO UPDATE SET
                 emoji=EXCLUDED.emoji,
                 name=EXCLUDED.name,
                 stars=EXCLUDED.stars,
                 gift_id=EXCLUDED.gift_id""",
            (key, emoji, name, stars, gift_id))

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
# BONUS / VAZIFA / PROMOKOD / KONKURS
# ═══════════════════════════════════════════════════════════
def get_bonus_reward(streak):
    return BONUS_REWARDS[min(streak, len(BONUS_REWARDS) - 1)]

def check_daily_bonus(user_id):
    today = now_uz().strftime("%Y-%m-%d")
    row = db_exec("SELECT * FROM daily_bonus WHERE user_id=%s", (user_id,), fetch=True)
    if not row:
        return {"can_claim": True, "streak": 0, "reward": BONUS_REWARDS[0],
                "next_reward": BONUS_REWARDS[1]}
    last = (row.get("last_claim") or "")[:10]
    streak = int(row.get("streak") or 0)
    can_claim = last != today
    if last and last != today:
        yest = (now_uz() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last != yest:
            streak = 0
    reward = get_bonus_reward(streak)
    next_reward = get_bonus_reward(streak + 1)
    return {"can_claim": can_claim, "streak": streak,
            "reward": reward, "next_reward": next_reward}

def claim_daily_bonus(user_id):
    info = check_daily_bonus(user_id)
    if not info["can_claim"]:
        return None
    reward = info["reward"]
    new_streak = info["streak"] + 1
    db_exec("""INSERT INTO daily_bonus (user_id, last_claim, streak, total_claimed)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                 last_claim = EXCLUDED.last_claim,
                 streak = EXCLUDED.streak,
                 total_claimed = daily_bonus.total_claimed + %s""",
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
    db_exec("""INSERT INTO user_tasks (user_id, task_id, done, updated_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id, task_id) DO UPDATE SET
                 done = EXCLUDED.done, updated_at = EXCLUDED.updated_at""",
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
    my = db_exec(
        "SELECT COUNT(*) AS count FROM users "
        "WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s",
        (uid, contest["start_at"]), fetch=True) or {"count": 0}
    my_rank = db_exec(
        "SELECT COUNT(*) + 1 AS rank FROM ("
        "  SELECT referrer_id, COUNT(*) AS cnt FROM users "
        "  WHERE is_verified=1 AND joined_at >= %s AND referrer_id <> 0 "
        "  GROUP BY referrer_id HAVING COUNT(*) > %s"
        ") t",
        (contest["start_at"], my["count"]), fetch=True)
    u = get_user(uid) or {}
    return {
        "leaders": [{"name": r["name"] or "User", "count": int(r["count"]),
                     "is_me": r["user_id"] == uid} for r in leaders],
        "me": {"rank": my_rank["rank"] if my_rank else 0,
               "name": u.get("first_name", "User"), "count": int(my["count"])},
    }


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
    # YANGI
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

# ═══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════════════
def main_menu(uid):
    lang = get_user_lang(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "profile"), callback_data="m_profile")
    b.button(text=T(lang, "stats"), callback_data="m_stats")
    b.button(text="🔥 " + T(lang, "bonus_menu"), callback_data="m_bonus")
    b.button(text="🏆 " + T(lang, "contest_menu"), callback_data="m_contest")
    b.button(text="📌 " + T(lang, "tasks_menu"), callback_data="m_tasks")
    b.button(text="🎟 " + T(lang, "promo_menu"), callback_data="m_promo")
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
    b.adjust(2, 2, 2, 2, 2, 2, 2, 2)
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
    b.button(text="🏆 Konkurslar", callback_data="a_contests")
    b.button(text="📌 Vazifalar", callback_data="a_tasks")
    b.button(text="🎟 Promokodlar", callback_data="a_promocodes")
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

    correct_idx = next(i for i, (_, ok) in enumerate(answers) if ok)
    b = InlineKeyboardBuilder()
    for i, (ans, _) in enumerate(answers):
        b.button(text=ans, callback_data=f"ans_{i}")
    b.adjust(1)

    await state.update_data(q_id=q["id"], ref_id=user["referrer_id"] or 0,
                            ans_correct=correct_idx)
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
        await cb.message.edit_text(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
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
                    await notify_admins(
                        f"⚠️ <b>Shubhali referal tezligi</b>\n\n"
                        f"Referer: <code>{ref_id}</code>\n"
                        f"Yangi user: <code>{uid}</code>\n"
                        f"Mukofot berilmadi. Tekshirib, kerak bo'lsa qo'lda bering.")
                else:
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
                        # REFERAL VAZIFASINI BAJARILGAN DEB BELGILASH
                        try:
                            ref_tasks = db_exec(
                                "SELECT id FROM tasks WHERE action='ref' AND is_active=1",
                                fetchall=True) or []
                            for rt in ref_tasks:
                                mark_task_done(ref_id, rt["id"])
                        except Exception as e:
                            logger.warning(f"Task mark xato: {e}")

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
        f"🔗 <b>Username:</b> {uname}\n\n"
        f"⭐ <b>Stars:</b> <b>{user['stars']}</b> ⭐\n"
        f"💝 <b>Donat:</b> <b>{donated}</b> ⭐\n"
        f"🏅 <b>Daraja:</b> {lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n"
        f"⬆️ <b>Keyingi:</b> {next_text}\n\n"
        f"👥 <b>Taklif qilganlar:</b> <b>{ref_count}</b> ta\n"
        f"🏆 <b>O'rningiz:</b> <b>#{rank}</b>\n\n"
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
# BONUS
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_bonus")
async def cb_bonus(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    info = check_daily_bonus(uid)

    if info["can_claim"]:
        text = (f"🔥 <b>{T(lang, 'bonus_title')}</b>\n\n" +
                T(lang, "bonus_available", reward=info["reward"],
                  streak=info["streak"], next=info["next_reward"]))
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "bonus_btn", n=info["reward"]), callback_data="claim_daily")
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
    else:
        text = (f"🔥 <b>{T(lang, 'bonus_title')}</b>\n\n" +
                T(lang, "bonus_claimed", streak=info["streak"], next=info["next_reward"]))
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "claim_daily")
async def claim_daily_cb(cb: types.CallbackQuery):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    res = claim_daily_bonus(uid)
    if res is None:
        await cb.answer(T(lang, "bonus_already"), show_alert=True)
        return
    await cb.answer(T(lang, "bonus_ok", n=res["reward"], streak=res["streak"]), show_alert=True)
    # Yangilash
    await cb_bonus(cb, FSMContext.__new__(FSMContext))

# ═══════════════════════════════════════════════════════════
# KONKURS (USER)
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_contest")
async def cb_contest(cb: types.CallbackQuery, state: FSMContext):
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
    days = int(diff // 86400)
    hours = int((diff % 86400) // 3600)

    text = (f"🏆 <b>{esc(contest['title'])}</b>\n\n"
            f"{esc(contest['description'])}\n\n"
            f"🎁 <b>Sovrin:</b> {esc(contest['reward_emoji'])} <b>{esc(contest['reward_name'])}</b>\n"
            f"⏰ <b>Qoldi:</b> {days} kun {hours} soat\n\n"
            f"📊 <b>Leaderboard:</b>\n")
    for i, l in enumerate(lb["leaders"], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        me_tag = " ⬅️" if l["is_me"] else ""
        text += f"{medal} {esc(l['name'])} — <b>{l['count']}</b> ta{me_tag}\n"
    if not lb["leaders"]:
        text += "— Hozircha qatnashuvchi yo'q\n"
    text += (f"\n👤 <b>Siz:</b> #{lb['me']['rank']} — <b>{lb['me']['count']}</b> ta referal")

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
# VAZIFALAR (USER)
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_tasks")
async def cb_tasks(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    tasks = get_user_tasks(uid)

    text = f"📌 <b>{T(lang, 'tasks_title')}</b>\n\n"
    b = InlineKeyboardBuilder()
    for t in tasks:
        if t["claimed"]:
            status = f"✅ {t['reward']} ⭐ olindi"
        elif t["claimable"]:
            status = "🎁 Mukofot tayyor!"
        elif t["done"]:
            status = "✅ Bajarildi"
        else:
            status = "⏳ Bajarilmagan"
        text += f"{esc(t['emoji'])} <b>{esc(t['title'])}</b> — +{t['reward']} ⭐\n   {status}\n\n"

        if t["claimable"]:
            b.button(text=f"🎁 {t['title'][:25]} → +{t['reward']}", callback_data=f"claimtask_{t['id']}")
    if not tasks:
        text += "— Vazifalar yo'q\n"
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("claimtask_"))
async def claim_task_cb(cb: types.CallbackQuery):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    task_id = int(cb.data.replace("claimtask_", ""))
    reward = claim_task_reward(uid, task_id)
    if reward is None:
        await cb.answer("❌ Mukofot olish mumkin emas", show_alert=True)
        return
    await cb.answer(T(lang, "task_ok", n=reward), show_alert=True)
    try:
        await bot.send_message(
            uid,
            T(lang, "stars_added", n=reward, reason="Vazifa mukofoti",
              total=(get_user(uid) or {}).get("stars", 0)),
            parse_mode="HTML")
    except Exception:
        pass
    # Ro'yxatni yangilash
    state = FSMContext.__new__(FSMContext)
    await cb_tasks(cb, state)

# ═══════════════════════════════════════════════════════════
# PROMOKOD (USER)
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_promo")
async def cb_promo(cb: types.CallbackQuery, state: FSMContext):
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
async def promo_code_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    code = (message.text or "").strip().upper()
    if not code:
        await message.answer(T(lang, "promo_not_found"))
        return

    reward, err = use_promocode(uid, code)
    await state.clear()
    if err:
        await message.answer(T(lang, err), parse_mode="HTML")
        return

    await message.answer(T(lang, "promo_ok", n=reward), parse_mode="HTML")
    try:
        await bot.send_message(
            uid,
            T(lang, "stars_added", n=reward, reason=f"Promokod: {code}",
              total=(get_user(uid) or {}).get("stars", 0)),
            parse_mode="HTML")
    except Exception:
        pass
    await message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")

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
# REYTING
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
# DONAT
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
    b.button(text="⭐ 50", callback_data="don_50")
    b.button(text="⭐ 100", callback_data="don_100")
    b.button(text="⭐ 250", callback_data="don_250")
    b.button(text="⭐ 500", callback_data="don_500")
    b.button(text="⭐ 1000", callback_data="don_1000")
    b.button(text="✏️ Boshqa miqdor", callback_data="don_custom")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(3, 2, 1, 1)

    txt = T(lang, "donate_title")
    try:
        await cb.message.edit_text(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("don_") & ~F.data.in_({"don_custom"}))
async def donate_quick(cb: types.CallbackQuery):
    try:
        amount = int(cb.data.replace("don_", ""))
    except ValueError:
        return
    await send_donate_invoice(cb, amount)


@dp.callback_query(F.data == "don_custom")
async def donate_custom(cb: types.CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "cancel"), callback_data="donate_cancel")
    b.adjust(1)
    txt = (
        f"💝 <b>Boshqa miqdor</b>\n\n"
        f"⭐ Nechta Stars yubormoqchisiz?\n"
        f"📉 Min: <b>{MIN_DONATE}</b>\n"
        f"📈 Max: <b>{MAX_DONATE:,}</b>\n\n"
        f"<i>Raqamni yozib yuboring:</i>"
    )
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
async def donate_custom_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    try:
        amount = int((message.text or "").strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer(T(lang, "enter_number"))
        return
    if amount < MIN_DONATE:
        await message.answer(f"❌ Min: {MIN_DONATE} ⭐")
        return
    if amount > MAX_DONATE:
        await message.answer(f"❌ Max: {MAX_DONATE:,} ⭐")
        return
    await state.clear()
    await send_donate_invoice_message(message, amount)


async def send_donate_invoice(cb: types.CallbackQuery, amount: int):
    if amount < MIN_DONATE or amount > MAX_DONATE:
        await cb.answer(f"❌ {MIN_DONATE} – {MAX_DONATE:,} ⭐", show_alert=True)
        return
    try:
        await bot.send_invoice(
            chat_id=cb.from_user.id,
            title=T("uz", "donate_invoice_title"),
            description=T("uz", "donate_invoice_desc", n=amount),
            payload=f"donate:{cb.from_user.id}:{amount}",
            currency="XTR",
            prices=[LabeledPrice(label="Donat", amount=amount)],
            start_parameter=f"donate_{amount}",
        )
        await cb.answer()
    except Exception as e:
        logger.error(f"Invoice xato: {e}")
        await cb.answer(f"❌ Xato: {e}", show_alert=True)


async def send_donate_invoice_message(message: types.Message, amount: int):
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title=T("uz", "donate_invoice_title"),
            description=T("uz", "donate_invoice_desc", n=amount),
            payload=f"donate:{message.from_user.id}:{amount}",
            currency="XTR",
            prices=[LabeledPrice(label="Donat", amount=amount)],
            start_parameter=f"donate_{amount}",
        )
    except Exception as e:
        logger.error(f"Invoice xato: {e}")
        await message.answer(f"❌ Xato: {e}")


@dp.pre_checkout_query()
async def pre_checkout(q: types.PreCheckoutQuery):
    ok = (q.invoice_payload or "").startswith("donate:")
    await q.answer(ok=ok, error_message=None if ok else "Bu to'lov qabul qilinmaydi")


@dp.message(F.successful_payment)
async def on_donate_payment(message: types.Message):
    p = message.successful_payment
    if not (p.invoice_payload or "").startswith("donate:"):
        return

    parts = p.invoice_payload.split(":")
    uid = int(parts[1])
    amount = int(parts[2])
    charge_id = p.telegram_payment_charge_id

    existing = db_exec("SELECT 1 FROM donations WHERE charge_id=%s", (charge_id,), fetch=True)
    if existing:
        return

    db_exec(
        "INSERT INTO donations (user_id, stars, charge_id, payload, status, created_at) "
        "VALUES (%s, %s, %s, %s, 'received', %s) ON CONFLICT (charge_id) DO NOTHING",
        (uid, amount, charge_id, p.invoice_payload, now_uz().isoformat())
    )

    lang = get_user_lang(uid)
    try:
        await bot.send_message(uid, T(lang, "donate_ok", n=amount), parse_mode="HTML")
    except Exception:
        pass

    user = get_user(uid)
    total_don = bot_donate_balance()
    uname = f"@{user['username']}" if user and user['username'] else "—"
    await notify_admins(
        f"💝 <b>YANGI DONAT!</b>\n\n"
        f"👤 <b>User:</b> {user['first_name'] if user else 'User'}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"⭐ <b>Miqdor:</b> {amount} ⭐\n"
        f"💰 <b>Bot donat balansi:</b> {total_don} ⭐\n"
        f"📅 <b>Vaqt:</b> {now_uz().strftime('%Y-%m-%d %H:%M')}"
    )

    logger.info(f"Donat: user={uid} amount={amount} charge={charge_id}")

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


def _extract_gift_emoji(g):
    sticker = getattr(g, "sticker", None)
    if sticker:
        for a in getattr(sticker, "attributes", None) or []:
            if isinstance(a, tt.DocumentAttributeSticker):
                alt = getattr(a, "alt", None)
                if alt:
                    return alt
        emoji = getattr(sticker, "emoji", None)
        if emoji:
            return emoji
    for attr in ("title", "name", "emoji"):
        val = getattr(g, attr, None)
        if val and isinstance(val, str):
            if any(ord(c) > 0x1F000 for c in val):
                return val
    doc = getattr(g, "document", None)
    if doc:
        for a in getattr(doc, "attributes", None) or []:
            if isinstance(a, tt.DocumentAttributeSticker):
                alt = getattr(a, "alt", None)
                if alt:
                    return alt
    return "🎁"


def _extract_gift_name(g):
    title = getattr(g, "title", None)
    if title:
        return title
    name = getattr(g, "name", None)
    if name:
        return name
    sticker = getattr(g, "sticker", None)
    if sticker:
        for a in getattr(sticker, "attributes", None) or []:
            if isinstance(a, tt.DocumentAttributeSticker):
                alt = getattr(a, "alt", None)
                if alt:
                    return alt
    return "Gift"


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
        return False, "Userbot sozlanmagan"
    try:
        if not tg_client.is_connected():
            await tg_client.connect()

        res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
        all_gifts = [
            g for g in getattr(res, "gifts", [])
            if not getattr(g, "limited", False)
            and not getattr(g, "sold_out", False)
        ]
        if not all_gifts:
            return False, "Telegram gift ro'yxati bo'sh qaytdi"

        match = None
        want_id = gift_row.get("gift_id")
        want_emoji = _norm_emoji(gift_row.get("emoji"))
        want_stars = gift_row.get("stars")

        if want_id:
            match = next((g for g in all_gifts if getattr(g, "id", None) == int(want_id)), None)
        if not match:
            cands = [g for g in all_gifts if _norm_emoji(_extract_gift_emoji(g)) == want_emoji]
            if cands:
                match = next((g for g in cands if getattr(g, "stars", None) == want_stars), cands[0])
        if not match and want_stars:
            match = next((g for g in all_gifts if getattr(g, "stars", None) == want_stars), None)

        if not match:
            available = ", ".join(
                f"{_extract_gift_emoji(g)}(ID:{getattr(g,'id','?')}:{getattr(g,'stars','?')}⭐)"
                for g in all_gifts[:8]
            )
            return False, f"Gift topilmadi (ID:{want_id}, {want_emoji}, {want_stars}⭐). Mavjud: {available}"

        peer = await _resolve_user(user_id)
        msg = tt.TextWithEntities(text=comment[:120], entities=[]) if comment else None
        invoice = tt.InputInvoiceStarGift(
            peer=peer,
            gift_id=match.id,
            hide_name=bool(anon),
            message=msg,
        )
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
# POST YASASH VA YUBORISH
# ═══════════════════════════════════════════════════════════
def build_gift_post(user, amount, gift_emoji=None, gift_name=None, is_anon=False, is_stars=False):
    if is_stars:
        title = "🎉 <b>YANGI STARS OLINDI!</b>"
        item_line = "🎁 <b>Stars</b>"
    else:
        title = "🎉 <b>YANGI GIFT OLINDI!</b>"
        item_line = f"🎁 <b>Gift:</b> {esc(gift_emoji or '🎁')} {esc(gift_name or 'Gift')}"

    if is_anon:
        who_line = "👤 <b>User:</b> 🕶 <i>Anonim</i>"
        uname_line = "🔗 <b>Username:</b> <i>yashirin</i>"
        uid_line = "🆔 <b>ID:</b> <i>yashirin</i>"
    else:
        uname = f"@{user['username']}" if user.get("username") else "—"
        who_line = f"👤 <b>User:</b> {esc(user['first_name'] or 'User')}"
        uname_line = f"🔗 <b>Username:</b> {esc(uname)}"
        uid_line = f"🆔 <b>ID:</b> <code>{user['user_id']}</code>"

    time_str = now_uz().strftime("%d.%m.%Y %H:%M")

    return (
        f"{title}\n\n"
        f"{who_line}\n"
        f"{uname_line}\n"
        f"{uid_line}\n"
        f"{item_line}\n"
        f"⭐ <b>Narx:</b> {amount} ⭐\n"
        f"📅 <b>Vaqt:</b> {time_str}"
    )


async def send_gift_post(uid, post_text, is_anon=False):
    channel = get_setting("gift_channel", "")
    if channel:
        try:
            await bot.send_message(channel, post_text, parse_mode="HTML")
            logger.info(f"Post kanalga yuborildi: {channel}")
        except Exception as e:
            logger.warning(f"Kanalga post yuborilmadi ({channel}): {e}")

    try:
        personal_text = post_text.replace("YANGI GIFT OLINDI", "SIZ GIFT OLDINGIZ")
        personal_text = personal_text.replace("YANGI STARS OLINDI", "SIZ STARS OLDINGIZ")
        if channel:
            personal_text += "\n\n📢 <i>Bu e'lon kanalda ham paydo bo'ldi!</i>"
        await bot.send_message(uid, personal_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Foydalanuvchiga post yuborilmadi ({uid}): {e}")

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

        post_text = build_gift_post(
            user=user,
            amount=gift["stars"],
            gift_emoji=gift["emoji"],
            gift_name=gift["name"],
            is_anon=bool(is_anon),
            is_stars=False,
        )
        await send_gift_post(uid, post_text, is_anon)
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
            f"❗ {esc(err)}")


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

    diag_lines = []
    diag_lines.append(f"API_ID: {'✅' if API_ID else '❌'} ({API_ID if API_ID else 'yo`q'})")
    diag_lines.append(f"API_HASH: {'✅' if API_HASH else '❌'} ({'o`rnatilgan' if API_HASH else 'yo`q'})")
    diag_lines.append(f"SESSION_STRING: {'✅' if SESSION_STRING else '❌'} ({len(SESSION_STRING) if SESSION_STRING else 0} belgi)")

    disabled = get_setting("userbot_disabled", "0") == "1"

    if not tg_client:
        status = "⛔ O'chirilgan" if disabled else "❌ Ulanmagan"
        bal_text = "—"
    else:
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
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔍 <b>Diagnostika:</b>\n"
        + "\n".join(diag_lines) + "\n\n"
        "Gift'lar avtomatik, shu akkauntning Stars balansidan yuboriladi.\n\n"
        "╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_userbot")
    if is_super_admin(cb.from_user.id):
        if tg_client or SESSION_STRING:
            b.button(text="🔑 Session almashtirish", callback_data="a_userbot_change")
            b.button(text="🗑 Userbotni o'chirish", callback_data="a_userbot_del")
        else:
            b.button(text="➕ Userbot qo'shish", callback_data="a_userbot_change")
    b.button(text="🧪 Test (o'zimga gift)", callback_data="a_userbot_test")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_test")
async def a_userbot_test(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    if not tg_client:
        await cb.answer("❌ Userbot ulanmagan!", show_alert=True)
        return
    await cb.answer("⏳ Sinab ko'rilmoqda...")
    try:
        me = await tg_client.get_me()
        try:
            st = await tg_client(functions.payments.GetStarsStatusRequest(peer=tt.InputPeerSelf()))
            bal = getattr(st.balance, "amount", st.balance)
        except Exception as e:
            bal = f"xato: {e}"

        try:
            res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
            gift_count = len(getattr(res, "gifts", []))
        except Exception as e:
            gift_count = f"xato: {e}"

        await cb.message.answer(
            f"🧪 <b>Userbot test natijasi:</b>\n\n"
            f"👤 Akkaunt: <b>{esc(me.first_name or '')}</b>\n"
            f"🆔 ID: <code>{me.id}</code>\n"
            f"📞 Telefon: {esc(me.phone or '—')}\n"
            f"💰 Stars: <b>{bal} ⭐</b>\n"
            f"🎁 Mavjud giftlar: <b>{gift_count}</b>\n\n"
            f"✅ Userbot ishlayapti!",
            parse_mode="HTML"
        )
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")


@dp.callback_query(F.data == "a_userbot_change")
async def a_userbot_change(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await state.clear()
    title = "🔑 <b>Userbot sessionni almashtirish</b>" if (tg_client or SESSION_STRING) else "➕ <b>Userbot qo'shish</b>"
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data="a_userbot")
    b.adjust(1)
    await cb.message.edit_text(
        f"{title}\n\n"
        "1️⃣ API_ID ni kiriting (my.telegram.org dan):",
        reply_markup=b.as_markup(),
        parse_mode="HTML")
    await state.set_state(AS.userbot_api)
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_del")
async def a_userbot_del(cb: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data="a_userbot_del_yes")
    b.button(text="❌ Yo'q", callback_data="a_userbot")
    b.adjust(2)
    await cb.message.edit_text(
        "🗑 <b>Userbotni o'chirish</b>\n\n"
        "Userbot uziladi va session, API_ID, API_HASH bot xotirasidan o'chiriladi.\n"
        "Env'dagi <code>SESSION_STRING</code> ham qayta ishga tushganda ishlatilmaydi.\n\n"
        "⚠️ Gift avtomatik yuborish to'xtaydi — yangi userbot qo'shmaguningizcha.\n\n"
        "<b>Rostdan o'chirasizmi?</b>",
        reply_markup=b.as_markup(),
        parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_del_yes")
async def a_userbot_del_yes(cb: types.CallbackQuery, state: FSMContext):
    global tg_client, API_ID, API_HASH, SESSION_STRING
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await state.clear()

    old = tg_client
    tg_client = None
    if old:
        try:
            await old.disconnect()
        except Exception as e:
            logger.warning(f"Userbot uzishda xato: {e}")

    API_ID = 0
    API_HASH = ""
    SESSION_STRING = ""

    for k in ("userbot_api_id", "userbot_api_hash", "userbot_session"):
        del_setting(k)
    set_setting("userbot_disabled", "1")

    logger.info(f"Userbot o'chirildi (admin {cb.from_user.id})")
    await a_userbot(cb, state)


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
        set_setting("userbot_session", security.enc(session_str))
        set_setting("userbot_disabled", "0")

        await state.clear()
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(
            f"✅ <b>Userbot ulandi!</b>\n\n👤 Akkaunt: <b>{esc(name)}</b>\n\n"
            f"<i>Session xabari xavfsizlik uchun o'chirildi.</i>",
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
    await cb.message.edit_text(
        "📢 <b>Kanal username kiriting</b>\n\nMisol: <code>@mychannel</code>\n\n"
        "⚠️ <i>Bot kanalga admin qilingan bo'lishi shart!</i>",
        parse_mode="HTML")
    await state.set_state(AS.channel)
    await cb.answer()


@dp.message(AS.channel)
async def add_ch_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch

    try:
        chat = await bot.get_chat(ch)
        member = await bot.get_chat_member(ch, (await bot.get_me()).id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                f"⚠️ <b>Diqqat!</b>\n\nBot <b>{esc(ch)}</b> kanalida admin emas.\n"
                f"Botni admin qiling va qaytadan urinib ko'ring.",
                parse_mode="HTML")
            return
    except Exception as e:
        await message.answer(
            f"❌ Kanal tekshirib bo'lmadi: <code>{esc(e)}</code>\n\n"
            f"Botni kanalga qo'shganingizga ishonch hosil qiling.",
            parse_mode="HTML")
        return

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
        gid = g.get("gift_id")
        gid_text = f" [ID:{gid}]" if gid else " [ID yo'q]"
        text += f"{esc(g['emoji'])} <b>{esc(g['name'])}</b> — {g['stars']} ⭐{gid_text}\n"
    if not gifts:
        text += "— Giftlar yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_gift")
    b.button(text="✏️ Tahrirlash", callback_data="edit_gift_list")
    b.button(text="➖ O'chirish", callback_data="del_gift_list")
    b.button(text="🔄 Telegram'dan sinxronlash", callback_data="sync_gifts")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "sync_gifts")
async def sync_gifts(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    if not tg_client:
        await cb.answer("❌ Userbot ulanmagan!", show_alert=True)
        return
    await cb.answer("⏳ Sinxronlanmoqda...")
    try:
        res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
        all_gifts = getattr(res, "gifts", []) or []
        lines = []
        for g in all_gifts[:40]:
            emoji = _extract_gift_emoji(g)
            stars = getattr(g, "stars", "?")
            gid = getattr(g, "id", "?")
            name = _extract_gift_name(g)
            limited = "🔒" if getattr(g, "limited", False) else ""
            sold = "❌" if getattr(g, "sold_out", False) else ""
            lines.append(f"{emoji} <b>{esc(name)}</b>\n  ID: <code>{gid}</code> | {stars} ⭐ {limited}{sold}")
        text = "🎁 <b>Telegram'dagi mavjud giftlar:</b>\n\n" + "\n".join(lines)
        if len(text) > 4000:
            text = text[:3990] + "…"
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="a_gifts")
        b.adjust(1)
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")


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
        await state.set_state(AS.gift_name)
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
        await state.set_state(AS.gift_stars)
    else:
        await state.update_data(gift_name=message.text.strip())
        await message.answer(
            "🆔 <b>Telegram Gift ID</b>\n\n"
            "<i>Bu giftning Telegram'dagi ID raqami.\n"
            "Agar bilmasangiz — /skip yuboring (emoji bo'yicha qidiriladi).</i>",
            parse_mode="HTML")
        await state.set_state(AS.gift_id_input)


@dp.message(AS.gift_id_input)
async def gift_id_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    txt = message.text.strip()
    gift_id = None
    if txt != "/skip":
        try:
            gift_id = int(txt)
        except ValueError:
            await message.answer("❌ Raqam kiriting yoki /skip")
            return
    await state.update_data(gift_id=gift_id)
    await message.answer("⭐ <b>Narx (Stars):</b>", parse_mode="HTML")
    await state.set_state(AS.gift_stars)


@dp.message(AS.gift_stars)
async def gift_stars_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            try:
                db_exec("UPDATE gifts SET stars=%s WHERE key=%s",
                        (int(message.text.strip()), data["edit_gift_key"]))
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
        add_gift(
            data["gift_key"],
            data["gift_emoji"],
            data["gift_name"],
            stars,
            data.get("gift_id"),
        )
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
        f"💝 Min donat = <b>{get_setting('min_donate')} ⭐</b>\n"
        f"📢 Sharh kanali: <b>{esc(get_setting('review_channel') or 'yo`q')}</b>\n"
        f"🎁 Gift/Stars kanali: <b>{esc(get_setting('gift_channel') or 'yo`q')}</b>\n\n"
        f"╰━━━━━━━━━━━━━━━━━╯"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal", callback_data="set_ref")
    b.button(text="💰 Min", callback_data="set_minw")
    b.button(text="💎 Max", callback_data="set_maxw")
    b.button(text="📢 Sharh kanali", callback_data="set_rev_ch")
    b.button(text="🎁 Gift/Stars kanali", callback_data="set_gift_ch")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 1)
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


@dp.callback_query(F.data == "set_gift_ch")
async def set_gift_ch_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "🎁 <b>Gift/Stars kanali username kiriting</b>\n\nMisol: <code>@starrush_gifts</code>\n\n"
        "⚠️ Bot kanalga <b>admin</b> qilingan bo'lishi kerak!",
        parse_mode="HTML")
    await state.set_state(AS.gift_channel)
    await cb.answer()


@dp.message(AS.gift_channel)
async def set_gift_ch_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    try:
        await bot.get_chat(ch)
        me = await bot.get_me()
        member = await bot.get_chat_member(ch, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                f"⚠️ Bot <b>{esc(ch)}</b> kanalida admin emas!\n"
                f"Botni admin qiling va qaytadan urinib ko'ring.",
                parse_mode="HTML")
            return
    except Exception as e:
        await message.answer(f"❌ Kanal tekshirilmadi: <code>{esc(e)}</code>", parse_mode="HTML")
        return
    set_setting("gift_channel", ch)
    await state.clear()
    await message.answer(f"✅ Gift/Stars kanali: <b>{esc(ch)}</b>", parse_mode="HTML")
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
    active_contests = q("SELECT COUNT(*) AS c FROM contests WHERE status='active'")
    total_tasks = q("SELECT COUNT(*) AS c FROM tasks WHERE is_active=1")
    total_promos = q("SELECT COUNT(*) AS c FROM promocodes WHERE uses_left > 0")

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
        f"💬 <b>Faol suhbatlar:</b> {open_chats}\n"
        f"🏆 <b>Faol konkurslar:</b> {active_contests}\n"
        f"📌 <b>Faol vazifalar:</b> {total_tasks}\n"
        f"🎟 <b>Faol promokodlar:</b> {total_promos}\n\n"
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
        f"<i>Bu stars'lar botning o'ziga tegishli — Telegram orqali ishlatishingiz mumkin.</i>\n\n"
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

    for i, u in enumerate(users, 1):
        try:
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

            post_text = build_gift_post(
                user=user,
                amount=w["stars"],
                gift_emoji=None,
                gift_name=None,
                is_anon=False,
                is_stars=True,
            )
            await send_gift_post(w["user_id"], post_text, is_anon=False)
        else:
            ok, err = await deliver_gift(w["user_id"], g or {}, anon=bool(w.get("is_anon")), comment=w.get("comment"))
            label = f"{esc((g or {}).get('emoji', '🎁'))} <b>{esc((g or {}).get('name', 'Gift'))}</b>"
            if ok:
                await bot.send_message(w["user_id"], T(u_lang, "gift_done", gift=label, n=w["stars"]), parse_mode="HTML")
                post_text = build_gift_post(
                    user=user,
                    amount=w["stars"],
                    gift_emoji=(g or {}).get("emoji", "🎁"),
                    gift_name=(g or {}).get("name", "Gift"),
                    is_anon=bool(w.get("is_anon")),
                    is_stars=False,
                )
                await send_gift_post(w["user_id"], post_text, is_anon=bool(w.get("is_anon")))
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
# ADMIN: KONKURSLAR
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "a_contests")
async def a_contests(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM contests ORDER BY id DESC LIMIT 10", fetchall=True) or []
    text = "╭━━━〔 🏆 <b>KONKURSLAR</b> 〕━━━╮\n\n"
    if rows:
        for c in rows:
            icon = "🟢" if c["status"] == "active" else "🔴"
            text += (f"{icon} <b>#{c['id']}</b> {esc(c['title'])}\n"
                     f"   🎁 {esc(c['reward_name'])} | "
                     f"{(c['start_at'] or '')[:10]} → {(c['end_at'] or '')[:10]}\n\n")
    else:
        text += "— Konkurslar yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi konkurs", callback_data="add_contest")
    b.button(text="🏁 Tugatish", callback_data="finish_contest_list")
    b.button(text="🗑 O'chirish", callback_data="del_contest_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_contest")
async def add_contest_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🏆 <b>Konkurs nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.contest_title)
    await cb.answer()


@dp.message(AS.contest_title)
async def contest_title_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_title=message.text.strip())
    await message.answer("📝 <b>Tavsif:</b>", parse_mode="HTML")
    await state.set_state(AS.contest_desc)


@dp.message(AS.contest_desc)
async def contest_desc_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_desc=message.text.strip())
    await message.answer("🎁 <b>Sovrin nomi</b> (masalan: <i>Yulduzli Gift</i>):", parse_mode="HTML")
    await state.set_state(AS.contest_reward_name)


@dp.message(AS.contest_reward_name)
async def contest_reward_name_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_reward_name=message.text.strip())
    await message.answer("😀 <b>Sovrin emoji:</b>", parse_mode="HTML")
    await state.set_state(AS.contest_reward_emoji)


@dp.message(AS.contest_reward_emoji)
async def contest_reward_emoji_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_reward_emoji=message.text.strip())
    await message.answer("📅 <b>Necha kun davom etadi?</b> (raqam):", parse_mode="HTML")
    await state.set_state(AS.contest_days)


@dp.message(AS.contest_days)
async def contest_days_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int((message.text or "").strip())
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer("❌ 1-365 oralig'ida raqam.")
        return
    data = await state.get_data()
    now = now_uz()
    end = now + timedelta(days=days)
    db_exec("""INSERT INTO contests
        (title, description, reward_emoji, reward_name, start_at, end_at, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'active', %s)""",
        (data["c_title"], data["c_desc"], data["c_reward_emoji"],
         data["c_reward_name"], now.isoformat(), end.isoformat(), now.isoformat()))
    await state.clear()
    await message.answer(f"✅ <b>Konkurs boshlandi!</b>\n\n🏆 {esc(data['c_title'])}\n"
                         f"📅 {days} kun", parse_mode="HTML")
    await notify_admins(
        f"🏆 <b>YANGI KONKURS!</b>\n\n"
        f"🎯 {esc(data['c_title'])}\n"
        f"{esc(data['c_desc'])}\n\n"
        f"🎁 Sovrin: {esc(data['c_reward_emoji'])} <b>{esc(data['c_reward_name'])}</b>\n"
        f"📅 {days} kun davomida\n\n"
        f"👉 Eng ko'p do'st taklif qilgan yutadi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "finish_contest_list")
async def finish_contest_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM contests WHERE status='active'", fetchall=True) or []
    if not rows:
        await cb.answer("— Faol konkurs yo'q", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for c in rows:
        b.button(text=f"🏁 #{c['id']} {c['title']}", callback_data=f"fincontest_{c['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_contests")
    b.adjust(1)
    await cb.message.edit_text("🏁 <b>Tugatish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("fincontest_"))
async def finish_contest_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    cid = int(cb.data.replace("fincontest_", ""))
    c = db_exec("SELECT * FROM contests WHERE id=%s", (cid,), fetch=True)
    if not c:
        await cb.answer("—", show_alert=True)
        return
    winner = db_exec(
        "SELECT u.user_id, u.first_name, COUNT(r.user_id) AS cnt "
        "FROM users r JOIN users u ON r.referrer_id = u.user_id "
        "WHERE r.is_verified=1 AND r.joined_at >= %s "
        "GROUP BY u.user_id, u.first_name ORDER BY cnt DESC LIMIT 1",
        (c["start_at"],), fetch=True)
    if not winner:
        await cb.answer("— Qatnashuvchi yo'q", show_alert=True)
        return
    db_exec("UPDATE contests SET status='finished', winner_id=%s, winner_referrals=%s WHERE id=%s",
            (winner["user_id"], winner["cnt"], cid))
    await notify_admins(
        f"🏁 <b>KONKURS TUGADI!</b>\n\n"
        f"🏆 {esc(c['title'])}\n\n"
        f"🥇 <b>G'olib:</b> {esc(winner['first_name'])}\n"
        f"🆔 <code>{winner['user_id']}</code>\n"
        f"👥 {winner['cnt']} ta referal\n\n"
        f"🎁 Sovrin: {esc(c['reward_emoji'])} {esc(c['reward_name'])}")
    try:
        await bot.send_message(
            winner["user_id"],
            f"🎉 <b>TABRIKLAYMIZ!</b>\n\n"
            f"Siz <b>{esc(c['title'])}</b> konkursida g'olib bo'ldingiz!\n\n"
            f"🏆 {winner['cnt']} ta referal\n"
            f"🎁 Sovrin: {esc(c['reward_emoji'])} {esc(c['reward_name'])}\n\n"
            f"Admin tez orada bog'lanadi!", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("✅")
    await a_contests(cb)


@dp.callback_query(F.data == "del_contest_list")
async def del_contest_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM contests ORDER BY id DESC LIMIT 20", fetchall=True) or []
    if not rows:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for c in rows:
        b.button(text=f"❌ #{c['id']} {c['title'][:30]}", callback_data=f"delcontest_{c['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_contests")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delcontest_"))
async def del_contest_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM contests WHERE id=%s", (int(cb.data.replace("delcontest_", "")),))
    await cb.answer("✅")
    await a_contests(cb)

# ═══════════════════════════════════════════════════════════
# ADMIN: VAZIFALAR
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "a_tasks")
async def a_tasks(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM tasks ORDER BY id", fetchall=True) or []
    text = "╭━━━〔 📌 <b>VAZIFALAR</b> 〕━━━╮\n\n"
    for t in rows:
        icon = "🟢" if t["is_active"] else "🔴"
        text += (f"{icon} <b>#{t['id']}</b> {esc(t['emoji'])} {esc(t['title'])}\n"
                 f"   +{t['reward']} ⭐ | action: {esc(t['action'])}\n\n")
    if not rows:
        text += "— Vazifalar yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_task")
    b.button(text="🗑 O'chirish", callback_data="del_task_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_task")
async def add_task_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📌 <b>Vazifa nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.task_title)
    await cb.answer()


@dp.message(AS.task_title)
async def task_title_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(t_title=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>")
    await state.set_state(AS.task_emoji)


@dp.message(AS.task_emoji)
async def task_emoji_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(t_emoji=message.text.strip())
    await message.answer("⭐ <b>Mukofot (stars):</b>")
    await state.set_state(AS.task_reward)


@dp.message(AS.task_reward)
async def task_reward_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(t_reward=val)
    await message.answer("🔗 <b>Link</b> (yoki /skip):")
    await state.set_state(AS.task_link)


@dp.message(AS.task_link)
async def task_link_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = (message.text or "").strip()
    await state.update_data(t_link=None if txt == "/skip" else txt)
    await message.answer(
        "⚙️ <b>Action:</b> <code>ref</code> / <code>sub</code> / <code>webapp</code> / <code>profile</code> / <code>manual</code>")
    await state.set_state(AS.task_action)


@dp.message(AS.task_action)
async def task_action_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    action = message.text.strip().lower()
    if action not in ("ref", "sub", "webapp", "profile", "manual"):
        await message.answer("❌ Noto'g'ri action.")
        return
    data = await state.get_data()
    db_exec("""INSERT INTO tasks (title, emoji, reward, link, action, is_active)
               VALUES (%s, %s, %s, %s, %s, 1)""",
            (data["t_title"], data["t_emoji"], data["t_reward"], data["t_link"], action))
    await state.clear()
    await message.answer("✅ <b>Vazifa qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_task_list")
async def del_task_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM tasks ORDER BY id", fetchall=True) or []
    b = InlineKeyboardBuilder()
    for t in rows:
        b.button(text=f"❌ #{t['id']} {t['title'][:30]}", callback_data=f"deltask_{t['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_tasks")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("deltask_"))
async def del_task_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM tasks WHERE id=%s", (int(cb.data.replace("deltask_", "")),))
    await cb.answer("✅")
    await a_tasks(cb)

# ═══════════════════════════════════════════════════════════
# ADMIN: PROMOKODLAR
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "a_promocodes")
async def a_promocodes(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM promocodes ORDER BY created_at DESC LIMIT 20", fetchall=True) or []
    text = "╭━━━〔 🎟 <b>PROMOKODLAR</b> 〕━━━╮\n\n"
    for p in rows:
        text += f"• <code>{esc(p['code'])}</code> — {p['reward']} ⭐ (qoldi: {p['uses_left']})\n"
    if not rows:
        text += "— Promokodlar yo'q\n"
    text += "\n╰━━━━━━━━━━━━━━━━━╯"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yaratish", callback_data="add_promo")
    b.button(text="🗑 O'chirish", callback_data="del_promo_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_promo")
async def add_promo_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🎟 <b>Promokod matni:</b> (masalan: STAR2025)", parse_mode="HTML")
    await state.set_state(AS.promo_code_admin)
    await cb.answer()


@dp.message(AS.promo_code_admin)
async def promo_code_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    code = message.text.strip().upper()
    if db_exec("SELECT 1 FROM promocodes WHERE code=%s", (code,), fetch=True):
        await message.answer("❌ Bu kod bor.")
        return
    await state.update_data(p_code=code)
    await message.answer("⭐ <b>Mukofot (stars):</b>")
    await state.set_state(AS.promo_reward)


@dp.message(AS.promo_reward)
async def promo_reward_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(p_reward=val)
    await message.answer("👥 <b>Necha kishi ishlata oladi?</b>")
    await state.set_state(AS.promo_uses)


@dp.message(AS.promo_uses)
async def promo_uses_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uses = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    db_exec("""INSERT INTO promocodes (code, reward, uses_left, created_at)
               VALUES (%s, %s, %s, %s)""",
            (data["p_code"], data["p_reward"], uses, now_uz().isoformat()))
    await state.clear()
    await message.answer(
        f"✅ <b>Promokod yaratildi!</b>\n\n"
        f"🎟 <code>{esc(data['p_code'])}</code>\n"
        f"⭐ +{data['p_reward']} stars\n"
        f"👥 {uses} kishi", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_promo_list")
async def del_promo_list(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM promocodes ORDER BY created_at DESC LIMIT 20", fetchall=True) or []
    b = InlineKeyboardBuilder()
    for p in rows:
        b.button(text=f"❌ {p['code']}", callback_data=f"delpromo_{p['code']}")
    b.button(text="⬅️ Orqaga", callback_data="a_promocodes")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delpromo_"))
async def del_promo_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM promocodes WHERE code=%s", (cb.data.replace("delpromo_", ""),))
    await cb.answer("✅")
    await a_promocodes(cb)

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


def build_contest_api(uid):
    active_row = get_active_contest()
    active = None
    if active_row:
        lb = get_contest_leaderboard(active_row, uid)
        active = {
            "title": active_row["title"],
            "description": active_row["description"],
            "reward_emoji": active_row["reward_emoji"],
            "reward_name": active_row["reward_name"],
            "target": active_row["target"],
            "end_at": active_row["end_at"],
            "leaders": lb["leaders"],
            "me": lb["me"],
        }
    finished_rows = db_exec(
        "SELECT c.*, u.first_name AS winner_name FROM contests c "
        "LEFT JOIN users u ON c.winner_id = u.user_id "
        "WHERE c.status='finished' ORDER BY c.id DESC LIMIT 5", fetchall=True) or []
    finished = [{
        "title": r["title"],
        "reward_emoji": r["reward_emoji"],
        "reward_name": r["reward_name"],
        "winner_name": r["winner_name"],
        "winner_referrals": r["winner_referrals"],
    } for r in finished_rows]
    return {"active": active, "finished": finished}


def build_bonus_api(uid):
    daily = check_daily_bonus(uid)
    tasks = get_user_tasks(uid)
    return {"daily": daily, "tasks": tasks}


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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


async def api_claim(request):
    tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not tg_user or "id" not in tg_user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=401)
    uid = int(tg_user["id"])
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Xato so'rov"}, status=400)
    cid = str(body.get("id", ""))
    lang = get_user_lang(uid)

    if cid == "daily":
        res = await asyncio.to_thread(claim_daily_bonus, uid)
        if res is None:
            return web.json_response({"error": T(lang, "bonus_already")}, status=400)
        try:
            await bot.send_message(
                uid,
                T(lang, "stars_added", n=res["reward"], reason="Kunlik bonus",
                  total=(get_user(uid) or {}).get("stars", 0)),
                parse_mode="HTML")
        except Exception:
            pass
        return web.json_response({"reward": res["reward"], "streak": res["streak"]})

    if cid.isdigit():
        reward = await asyncio.to_thread(claim_task_reward, uid, int(cid))
        if reward is None:
            return web.json_response({"error": "Mukofot olish mumkin emas"}, status=400)
        try:
            await bot.send_message(
                uid,
                T(lang, "stars_added", n=reward, reason="Vazifa mukofoti",
                  total=(get_user(uid) or {}).get("stars", 0)),
                parse_mode="HTML")
        except Exception:
            pass
        return web.json_response({"reward": reward})

    return web.json_response({"error": "Noma'lum amal"}, status=400)


async def api_promo(request):
    tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not tg_user or "id" not in tg_user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=401)
    uid = int(tg_user["id"])
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Xato so'rov"}, status=400)
    code = str(body.get("code", "")).strip().upper()
    lang = get_user_lang(uid)

    reward, err = await asyncio.to_thread(use_promocode, uid, code)
    if err:
        return web.json_response({"error": T(lang, err)}, status=400)
    try:
        await bot.send_message(
            uid,
            T(lang, "stars_added", n=reward, reason=f"Promokod: {code}",
              total=(get_user(uid) or {}).get("stars", 0)),
            parse_mode="HTML")
    except Exception:
        pass
    return web.json_response({"reward": reward})


# ═══════════════════════════════════════════════════════════
# USERBOT ULANISH
# ═══════════════════════════════════════════════════════════
async def init_userbot():
    global tg_client, API_ID, API_HASH, SESSION_STRING

    if get_setting("userbot_disabled", "0") == "1":
        API_ID = 0
        API_HASH = ""
        SESSION_STRING = ""
        logger.info("Userbot admin tomonidan o'chirilgan — ulanmaydi")
        return

    db_api_id = get_setting("userbot_api_id", "")
    db_api_hash = get_setting("userbot_api_hash", "")
    db_session = get_setting("userbot_session", "")

    if db_api_id and db_api_hash and db_session:
        try:
            API_ID = int(db_api_id)
        except ValueError:
            pass
        API_HASH = db_api_hash
        SESSION_STRING = security.dec(db_session)
        logger.info("Userbot sozlamalari DB'dan olindi")

    if not API_ID:
        logger.warning("❌ API_ID yo'q — userbot ulanmaydi")
        return
    if not API_HASH:
        logger.warning("❌ API_HASH yo'q — userbot ulanmaydi")
        return
    if not SESSION_STRING:
        logger.warning("❌ SESSION_STRING yo'q — userbot ulanmaydi")
        return

    logger.info(f"Userbot ulanmoqda (API_ID={API_ID}, SESSION={len(SESSION_STRING)} belgi)...")

    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Userbot sessiyasi YAROQSIZ — session.py ni qayta ishga tushiring")
            await client.disconnect()
            return
        tg_client = client
        me = await client.get_me()
        logger.info(f"✅ Userbot ulandi: {me.first_name} (id {me.id})")
    except Exception as e:
        logger.error(f"❌ Userbot ulanmadi: {e}")
        tg_client = None

# ═══════════════════════════════════════════════════════════
# ISHGA TUSHIRISH
# ═══════════════════════════════════════════════════════════
async def main():
    init_db()
    await init_userbot()
    security.setup(
        dp, db_exec=db_exec, now_uz=now_uz, T=T, LANGS=LANGS,
        is_admin=is_admin, check_subs=check_subs, subs_kb=subs_kb,
    )

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
        ("/api/contest", build_contest_api),
        ("/api/bonus", build_bonus_api),
    ):
        app.router.add_get(path, make_api(builder))
    app.router.add_post("/api/claim", api_claim)
    app.router.add_post("/api/promo", api_promo)

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
