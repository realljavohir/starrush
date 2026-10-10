"""
hardening.py — bot.py uchun tayyor tuzatishlar:
  1) levels keshi (get_levels har chaqiruvda DB'ga bormaydi)
  2) async DB wrapper (event loop bloklanmasligi uchun)
  3) majburiy kanal xatosi haqida adminlarga (spamsiz) ogohlantirish
"""
import asyncio
import logging
import time
from functools import wraps

log = logging.getLogger("hardening")


# 1) TTL kesh -----------------------------------------------------------
def ttl_cache(seconds=60):
    def deco(fn):
        state = {"t": 0.0, "v": None}

        @wraps(fn)
        def wrapper(*a, **kw):
            if state["v"] is None or time.monotonic() - state["t"] > seconds:
                state["v"] = fn(*a, **kw)
                state["t"] = time.monotonic()
            return state["v"]

        wrapper.invalidate = lambda: state.update(t=0.0, v=None)
        return wrapper
    return deco


# 2) Async DB -----------------------------------------------------------
def make_adb(db_exec):
    """await adb(sql, params, fetch=True) — db_exec ni alohida thread'da ishlatadi."""
    async def adb(query, params=(), fetch=False, fetchall=False):
        return await asyncio.to_thread(db_exec, query, params, fetch, fetchall)
    return adb


# 3) Kanal xatosi ogohlantirishi ----------------------------------------
_alerted = {}


async def alert_channel_problem(notify_admins, channel, err, cooldown=6 * 3600):
    """Bir kanal uchun 6 soatda bir marta adminlarga xabar beradi."""
    now = time.monotonic()
    if now - _alerted.get(channel, -cooldown - 1) < cooldown:
        return
    _alerted[channel] = now
    await notify_admins(
        f"⚠️ <b>Majburiy kanal tekshirilmayapti</b>\n\n📢 {channel}\n❗ <code>{str(err)[:200]}</code>\n\n"
        f"Bot kanalda admin ekanini tekshiring. Shu vaqtgacha bu kanal obuna tekshiruvida o'tkazib yuboriladi.")
