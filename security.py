"""
security.py - StarRush Bot uchun himoya moduli.

Ichida:
  1. Guard middleware: ban, majburiy obuna, tasdiqlanmagan userlar, flood (rate limit)
  2. adb / aio: sinxron DB funksiyalarini event loopni bloklamasdan chaqirish
  3. Referal tezligi (velocity) tekshiruvi - fraud uchun
  4. Session shifrlash (Fernet, SECRET_KEY env orqali)

Ulash: PATCHES.md ga qarang.
"""
import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from datetime import timedelta

from aiogram import BaseMiddleware, types

logger = logging.getLogger(__name__)

# main.py dan setup() orqali beriladi
_db_exec = None
_now_uz = None
_T = None
_LANGS = None
_is_admin = None
_check_subs = None
_subs_kb = None

# ───────────── Sozlamalar ─────────────
FLOOD_LIMIT = 10          # shuncha hodisa
FLOOD_WINDOW = 5.0        # shuncha soniyada bo'lsa - flood
SUB_CACHE_TTL = 60        # obuna natijasini keshlash (soniya)
REF_HOURLY_LIMIT = 15     # 1 soatda bitta userga ko'pi bilan shuncha referal
REF_DAILY_LIMIT = 60      # 24 soatda


# ───────────── Async DB ─────────────
async def adb(query, params=(), fetch=False, fetchall=False):
    """db_exec ni alohida threadda ishga tushiradi (event loop qotmaydi)."""
    return await asyncio.to_thread(_db_exec, query, params, fetch, fetchall)


async def aio(fn, *args, **kwargs):
    """Istalgan sinxron funksiyani threadda chaqirish: await aio(get_user, uid)"""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ───────────── Session shifrlash ─────────────
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception

_SECRET_KEY = os.environ.get("SECRET_KEY", "")
_fernet = Fernet(_SECRET_KEY.encode()) if (Fernet and _SECRET_KEY) else None
if not _fernet:
    logger.warning("SECRET_KEY yo'q - userbot session shifrlanmasdan saqlanadi!")


def enc(value):
    """Matnni shifrlaydi. Kalit yo'q bo'lsa o'zgarishsiz qaytaradi."""
    if not value or not _fernet:
        return value
    return "enc:" + _fernet.encrypt(value.encode()).decode()


def dec(value):
    """enc() natijasini ochadi. Eski (shifrlanmagan) qiymatlar ham ishlaydi."""
    if not value or not value.startswith("enc:"):
        return value
    if not _fernet:
        raise RuntimeError("Session shifrlangan, lekin SECRET_KEY o'rnatilmagan")
    try:
        return _fernet.decrypt(value[4:].encode()).decode()
    except InvalidToken:
        raise RuntimeError("SECRET_KEY noto'g'ri - session ochilmadi")


# ───────────── Fraud: referal tezligi ─────────────
async def referral_velocity_ok(referrer_id):
    """Referer juda tez ko'p odam keltirsa False qaytaradi (mukofot berilmasin)."""
    now = _now_uz()
    h = (now - timedelta(hours=1)).isoformat()
    d = (now - timedelta(hours=24)).isoformat()
    row = await adb(
        "SELECT "
        " COUNT(*) FILTER (WHERE joined_at >= %s) AS h, "
        " COUNT(*) FILTER (WHERE joined_at >= %s) AS d "
        "FROM users WHERE referrer_id=%s AND is_verified=1",
        (h, d, referrer_id), fetch=True)
    if not row:
        return True
    return int(row["h"]) <= REF_HOURLY_LIMIT and int(row["d"]) <= REF_DAILY_LIMIT


# ───────────── Guard middleware ─────────────
_UNVERIFIED_CB_OK = ("lang_", "ans_", "check_sub")


class Guard(BaseMiddleware):
    def __init__(self):
        self.hits = defaultdict(lambda: deque(maxlen=FLOOD_LIMIT))
        self.sub_cache = {}

    # --- flood ---
    def _flooded(self, uid):
        now = time.monotonic()
        q = self.hits[uid]
        q.append(now)
        if len(self.hits) > 50000:  # xotira tozalash
            self.hits.clear()
        return len(q) == FLOOD_LIMIT and now - q[0] < FLOOD_WINDOW

    # --- obuna (kesh bilan) ---
    async def _subscribed(self, uid):
        ts_ok = self.sub_cache.get(uid)
        if ts_ok and time.monotonic() - ts_ok[0] < SUB_CACHE_TTL:
            return ts_ok[1]
        ok = await _check_subs(uid)
        self.sub_cache[uid] = (time.monotonic(), ok)
        if len(self.sub_cache) > 50000:
            self.sub_cache.clear()
        return ok

    @staticmethod
    async def _reply(event, text, kb=None):
        try:
            if isinstance(event, types.CallbackQuery):
                await event.answer()
                if event.message:
                    await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            else:
                await event.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.debug(f"Guard reply xato: {e}")

    @staticmethod
    def _unverified_allowed(event, data):
        raw = data.get("raw_state") or ""
        if raw.startswith("US:phone") or raw.startswith("US:answer"):
            return True
        if isinstance(event, types.CallbackQuery):
            return (event.data or "").startswith(_UNVERIFIED_CB_OK)
        if isinstance(event, types.Message):
            if event.contact:
                return True
            return (event.text or "").startswith("/start")
        return False

    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u is None or u.is_bot:
            return await handler(event, data)
        uid = u.id

        # Adminlar tekshiruvdan o'tmaydi
        if await asyncio.to_thread(_is_admin, uid):
            return await handler(event, data)

        # 1) Flood
        if self._flooded(uid):
            if isinstance(event, types.CallbackQuery):
                try:
                    await event.answer("⏳", show_alert=False)
                except Exception:
                    pass
            return

        # 2) Ban / tasdiqlash holati
        row = await adb(
            "SELECT is_banned, is_verified, language FROM users WHERE user_id=%s",
            (uid,), fetch=True)
        if row is None:
            return await handler(event, data)   # yangi user - /start hal qiladi

        lang = row["language"] if row.get("language") in _LANGS else "uz"

        if row["is_banned"]:
            await self._reply(event, _T(lang, "banned"))
            return

        if not row["is_verified"]:
            if self._unverified_allowed(event, data):
                return await handler(event, data)
            await self._reply(event, _T(lang, "start_first"))
            return

        # 3) Majburiy obuna (verified userlar uchun HAR safar, kesh bilan)
        is_start = isinstance(event, types.Message) and (event.text or "").startswith("/start")
        is_sub_cb = isinstance(event, types.CallbackQuery) and (event.data or "") in ("check_sub",)
        is_lang_cb = isinstance(event, types.CallbackQuery) and (event.data or "").startswith("lang_")
        if not (is_start or is_sub_cb or is_lang_cb):
            if not await self._subscribed(uid):
                self.sub_cache.pop(uid, None)   # keyingi bosishda qayta tekshirilsin
                kb = await _subs_kb(uid)
                await self._reply(event, _T(lang, "subscribe"), kb)
                return

        return await handler(event, data)


def setup(dp, *, db_exec, now_uz, T, LANGS, is_admin, check_subs, subs_kb):
    """main() ichida, polling boshlanishidan oldin chaqiring."""
    global _db_exec, _now_uz, _T, _LANGS, _is_admin, _check_subs, _subs_kb
    _db_exec, _now_uz, _T, _LANGS = db_exec, now_uz, T, LANGS
    _is_admin, _check_subs, _subs_kb = is_admin, check_subs, subs_kb

    guard = Guard()
    dp.message.outer_middleware(guard)
    dp.callback_query.outer_middleware(guard)
    logger.info("Guard middleware ulandi")
