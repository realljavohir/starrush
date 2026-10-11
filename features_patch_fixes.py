# ═══════════════════════════════════════════════════════════
# features_patch_fixes.py — features_patch.py dagi xatolarning tuzatishlari
#
# TARTIB: features_patch.py ni qo'llab bo'lgach, bu fayldagi bloklar bilan
# ko'rsatilgan joylarni ALMASHTIRING / QO'SHING.
# ═══════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────
# 1. IMPORTLAR — main.py boshiga (yo'q bo'lganlarini qo'shing)
# ───────────────────────────────────────────────────────────
import asyncio
import hashlib
import io
import logging
import re
from datetime import datetime, timedelta

from PIL import Image, ImageDraw
from aiogram import BaseMiddleware, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import (BufferedInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, WebAppInfo)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ───────────────────────────────────────────────────────────
# 2. pay_referral — features_patch.py dagisini TO'LIQ ALMASHTIRING
#    Xato: status 'paid' bo'lgach add_stars None qaytarsa, Stars berilmasdi,
#    lekin referal "to'langan" bo'lib qolardi. Endi status qaytariladi.
# ───────────────────────────────────────────────────────────
async def pay_referral(rid, from_status):
    r = await _adb(
        "UPDATE referral_rewards SET status='paid', paid_at=%s WHERE id=%s AND status=%s RETURNING *",
        (now_uz().isoformat(), rid, from_status), fetch=True)
    if not r:
        return False

    try:
        new_total = await asyncio.to_thread(add_stars, r["referrer_id"], r["amount"])
    except Exception:
        logger.exception("pay_referral add_stars")
        new_total = None

    if new_total is None:
        # Stars berilmadi -> statusni qaytaramiz (keyingi aylanishda qayta uriniladi)
        back = "pending" if from_status == "processing" else from_status
        await _adb("UPDATE referral_rewards SET status=%s, paid_at=NULL WHERE id=%s AND status='paid'",
                   (back, rid))
        return False

    lang = get_user_lang(r["referrer_id"])
    try:
        await bot.send_message(
            r["referrer_id"],
            T(lang, "referral_reward", n=r["amount"]) + f"\n💰 {T(lang, 'total')}: <b>{new_total} ⭐</b>",
            parse_mode="HTML")
    except Exception:
        pass
    try:
        await check_level_up(r["referrer_id"], new_total - r["amount"], new_total)
    except Exception:
        logger.exception("check_level_up")
    try:
        for rt in (await _adb("SELECT id FROM tasks WHERE action='ref' AND is_active=1", fetchall=True) or []):
            await asyncio.to_thread(mark_task_done, r["referrer_id"], rt["id"])
    except Exception as e:
        logger.warning(f"Task mark xato: {e}")
    return True


# release_loop ning boshida, bot qayta ishga tushganda "processing" da qolib
# ketgan yozuvlarni qaytaring (ALMASHTIRING):
async def release_loop():
    try:
        await _adb("UPDATE referral_rewards SET status='pending' WHERE status='processing'")
    except Exception:
        logger.exception("release_loop reset")
    while True:
        try:
            await release_referrals()
        except Exception:
            logger.exception("release_loop")
        await asyncio.sleep(300)


# ───────────────────────────────────────────────────────────
# 3. OBUNANI QAYTA TEKSHIRISH — soxta jarimalarga qarshi
#    Xato: Telegram vaqtincha xato bersa, odam noto'g'ri jarimalanardi.
#    Endi: 2 marta tekshiriladi (3 soniya oraliq); API xatosi = jarima yo'q.
# ───────────────────────────────────────────────────────────
async def check_subs_strict(uid):
    for attempt in range(2):
        try:
            if await check_subs(uid):
                return True
        except Exception:
            logger.warning(f"check_subs xato ({uid}) — jarima qo'llanmadi")
            return True
        if attempt == 0:
            await asyncio.sleep(3)
    return False

# release_referrals ichida:   await check_subs(r["referred_id"])
#                       ->    await check_subs_strict(r["referred_id"])


async def recheck_subscriptions():
    if not get_channels():
        return
    rows = await _adb("SELECT user_id FROM users WHERE is_verified=1 AND is_banned=0 AND sub_ok=1",
                      fetchall=True) or []
    for r in rows:
        uid = r["user_id"]
        if is_admin(uid):
            continue
        if not await check_subs_strict(uid):
            await _adb("UPDATE users SET sub_ok=0 WHERE user_id=%s", (uid,))
            _SUB_OK_CACHE.pop(uid, None)
            await clawback_for(uid)
            try:
                await bot.send_message(uid, T(get_user_lang(uid), "subscribe"),
                                       reply_markup=await subs_kb(uid), parse_mode="HTML")
            except Exception:
                pass
        await asyncio.sleep(0.08)

# MUHIM: check_subs ning o'zi ichida try/except bilan xatoni yutib False
# qaytarsa, yuqoridagi himoya ishlamaydi. U funksiyada xatoda exception
# ko'taring (yoki True qaytaring), faqat "a'zo emas" holatida False qaytaring.


# ───────────────────────────────────────────────────────────
# 4. SubGate — keshli versiya (features_patch.py dagini ALMASHTIRING)
#    Obunasi tasdiqlangan userlar uchun 60 soniya DB ga so'rov yuborilmaydi.
# ───────────────────────────────────────────────────────────
import time
_SUB_OK_CACHE = {}          # uid -> keshlangan vaqt (faqat sub_ok != 0 holati)
_SUB_OK_TTL = 60


class SubGate(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user or is_admin(user.id):
            return await handler(event, data)

        ts = _SUB_OK_CACHE.get(user.id)
        if ts and time.monotonic() - ts < _SUB_OK_TTL:
            return await handler(event, data)

        row = await _adb("SELECT sub_ok FROM users WHERE user_id=%s", (user.id,), fetch=True)
        if not row or row["sub_ok"] != 0:
            _SUB_OK_CACHE[user.id] = time.monotonic()
            return await handler(event, data)

        # sub_ok == 0 -> menyu yopiq
        lang = get_user_lang(user.id)
        if isinstance(event, types.CallbackQuery):
            if event.data == "check_sub":
                return await handler(event, data)
            await event.answer()
            await event.message.answer(T(lang, "subscribe"), reply_markup=await subs_kb(user.id),
                                       parse_mode="HTML")
            return
        if isinstance(event, types.Message):
            if (event.text or "").startswith("/start") or event.successful_payment:
                return await handler(event, data)
            await event.answer(T(lang, "subscribe"), reply_markup=await subs_kb(user.id), parse_mode="HTML")
            return
        return await handler(event, data)


# ───────────────────────────────────────────────────────────
# 5. ESKI REFERALLAR — init_extra_db() oxiriga qo'shing (c.close() dan OLDIN)
#    Patchdan oldingi tasdiqlangan referallar referral_rewards ga "paid"
#    sifatida yoziladi (faqat bir marta), shunda TOP va clawback ular bilan ham ishlaydi.
# ───────────────────────────────────────────────────────────
#     c.execute("SELECT value FROM settings WHERE key='rr_backfilled'")
#     if not c.fetchone():
#         c.execute(
#             "INSERT INTO referral_rewards (referrer_id, referred_id, amount, status, created_at, release_at, paid_at) "
#             "SELECT referrer_id, user_id, %s, 'paid', joined_at, joined_at, joined_at "
#             "FROM users WHERE referrer_id IS NOT NULL AND is_verified=1 "
#             "ON CONFLICT (referred_id) DO NOTHING",
#             (int(defaults_ref_reward),))
#         c.execute("INSERT INTO settings (key, value) VALUES ('rr_backfilled', '1') ON CONFLICT (key) DO NOTHING")
#
# (defaults_ref_reward o'rniga hozirgi stars_per_referral qiymatini qo'ying, masalan 2.
#  Eslatma: Bu yozuvlar shu paytgacha berilgan Stars ni hisobga oladi, qo'shimcha Stars bermaydi.)


# ───────────────────────────────────────────────────────────
# 6. TOP MUKOFOTLARNI TAHRIRLASH — /rewards buyrug'i (faqat bosh admin)
#    Misol:  /rewards weekly 10,5,3     /rewards monthly 50,25,10
# ───────────────────────────────────────────────────────────
@dp.message(Command("rewards"))
async def cmd_rewards(message: types.Message):
    if not is_super_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1] not in ("weekly", "monthly"):
        await message.answer(
            "Foydalanish:\n<code>/rewards weekly 10,5,3</code>\n<code>/rewards monthly 50,25,10</code>\n\n"
            f"Hozir: haftalik <b>{get_setting('weekly_rewards', '10,5,3')}</b>, "
            f"oylik <b>{get_setting('monthly_rewards', '50,25,10')}</b>", parse_mode="HTML")
        return
    vals = parts[2].split(",")
    if not (1 <= len(vals) <= 10) or not all(v.isdigit() and int(v) > 0 for v in vals):
        await message.answer("❌ Format: vergul bilan ajratilgan musbat sonlar (1-10 ta).")
        return
    set_setting(f"{parts[1]}_rewards", ",".join(vals))
    audit(message.from_user.id, "setting", None, None, f"{parts[1]}_rewards={','.join(vals)}")
    await message.answer(f"✅ {parts[1]}: <b>{','.join(vals)}</b>", parse_mode="HTML")


# ───────────────────────────────────────────────────────────
# 7. ISHGA TUSHIRISHDA BOG'LIQLIKLARNI TEKSHIRISH
#    main() da init_extra_db() dan keyin chaqiring:  check_dependencies()
#    Yetishmayotgan funksiyalar logga chiqadi, bot yiqilmaydi.
# ───────────────────────────────────────────────────────────
def check_dependencies():
    needed = [
        "_adb", "db_exec", "get_user", "get_user_lang", "update_user", "add_stars",
        "get_setting", "set_setting", "now_uz", "T", "LANGS", "esc", "format_number",
        "DIV", "box_title", "kv", "progress_bar", "notify_admins", "is_admin",
        "is_super_admin", "list_admins", "get_channels", "check_subs", "subs_kb",
        "check_level_up", "mark_task_done", "get_user_level", "_next_level",
        "total_donated", "get_active_contest", "get_contest_leaderboard",
        "get_user_tasks", "refresh_task_status", "_load_font", "WEBAPP_URL",
        "DATABASE_URL", "BOT_TOKEN",
    ]
    missing = [n for n in needed if n not in globals()]
    if missing:
        logger.error("YETISHMAYOTGAN nomlar: " + ", ".join(missing))
    else:
        logger.info("Bog'liqliklar tekshiruvi: hammasi joyida")
    return missing


# ───────────────────────────────────────────────────────────
# 8. TUGMA CALLBACKLARINI TEKSHIRISH (terminalda bir marta ishga tushiring)
# ───────────────────────────────────────────────────────────
#   for c in m_menu m_reflink m_bonus m_tasks m_contest m_rating m_withdraw \
#            m_profile m_more m_stats m_history m_promo m_gift m_donate \
#            m_banner m_review m_support m_remind m_lang m_admin; do
#       grep -q "\"$c\"" main.py || echo "HANDLER YO'Q: $c"
#   done
#
# "HANDLER YO'Q" chiqqan har bir nom uchun eski reply-tugma handleri
# shu callback_data ga ulanmagan: uni @dp.callback_query(F.data == "<nom>")
# ostiga ko'chiring.
