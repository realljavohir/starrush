# ═══════════════════════════════════════════════════════════
# fixes_patch.py — main.py uchun 1-7 tuzatishlar + gift ID tahrirlash
# Har bo'limda "ALMASHTIRING" yoki "QO'SHING" deb yozilgan.
# ═══════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────
# 0. IMPORTLAR — fayl boshiga qo'shing
# ───────────────────────────────────────────────────────────
# import gzip
# import aiohttp


# ═══════════════════════════════════════════════════════════
# 7. LEVELS KESH — get_levels() ni ALMASHTIRING
# ═══════════════════════════════════════════════════════════
_levels_cache = {"t": 0.0, "v": None}


def get_levels():
    if _levels_cache["v"] is not None and time.time() - _levels_cache["t"] < 60:
        return _levels_cache["v"]
    rows = db_exec("SELECT * FROM levels ORDER BY min_stars ASC", fetchall=True)
    v = [dict(r) for r in rows] if rows else DEFAULT_LEVELS
    _levels_cache["v"], _levels_cache["t"] = v, time.time()
    return v


def invalidate_levels():
    _levels_cache["v"] = None

# Daraja qo'shilganda/o'chirilganda keshni tozalang:
#   level_max_input ichida  db_exec("INSERT INTO levels ...") dan keyin:  invalidate_levels()
#   del_level_do ichida     db_exec("DELETE FROM levels ...") dan keyin:  invalidate_levels()


# ═══════════════════════════════════════════════════════════
# 2. ATOMIK BONUS / PROMOKOD / VAZIFA
#    Eski claim_daily_bonus, use_promocode, claim_task_reward,
#    mark_task_done funksiyalarini ALMASHTIRING.
# ═══════════════════════════════════════════════════════════
def claim_daily_bonus(user_id):
    info = check_daily_bonus(user_id)
    if not info["can_claim"]:
        return None
    reward = info["reward"]
    new_streak = info["streak"] + 1
    now = now_uz()
    today = now.strftime("%Y-%m-%d")
    # WHERE sharti tufayli bir kunda faqat BITTA so'rov o'tadi (poyga holatida ham)
    row = db_exec(
        """INSERT INTO daily_bonus (user_id, last_claim, streak, total_claimed)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (user_id) DO UPDATE SET
             last_claim = EXCLUDED.last_claim,
             streak = EXCLUDED.streak,
             total_claimed = daily_bonus.total_claimed + EXCLUDED.total_claimed
           WHERE COALESCE(LEFT(daily_bonus.last_claim, 10), '') <> %s
           RETURNING streak""",
        (user_id, now.isoformat(), new_streak, reward, today), fetch=True)
    if not row:
        return None
    add_stars(user_id, reward)
    return {"reward": reward, "streak": new_streak}


def use_promocode(user_id, code):
    code = (code or "").strip().upper()
    if not code:
        return None, "promo_not_found"
    p = db_exec("SELECT reward FROM promocodes WHERE code=%s", (code,), fetch=True)
    if not p:
        return None, "promo_not_found"
    # 1) avval foydalanuvchini yozamiz (PRIMARY KEY ikki marta ishlatishga yo'l qo'ymaydi)
    ins = db_exec(
        "INSERT INTO promo_uses (user_id, code, used_at) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING RETURNING code",
        (user_id, code, now_uz().isoformat()), fetch=True)
    if not ins:
        return None, "promo_used"
    # 2) limitni atomik kamaytiramiz
    dec = db_exec(
        "UPDATE promocodes SET uses_left = uses_left - 1 "
        "WHERE code=%s AND uses_left > 0 RETURNING reward", (code,), fetch=True)
    if not dec:
        db_exec("DELETE FROM promo_uses WHERE user_id=%s AND code=%s", (user_id, code))
        return None, "promo_empty"
    add_stars(user_id, dec["reward"])
    return dec["reward"], None


def claim_task_reward(user_id, task_id):
    t = db_exec("SELECT reward FROM tasks WHERE id=%s AND is_active=1", (task_id,), fetch=True)
    if not t:
        return None
    row = db_exec(
        "UPDATE user_tasks SET claimed=1, updated_at=%s "
        "WHERE user_id=%s AND task_id=%s AND done=1 AND claimed=0 RETURNING task_id",
        (now_uz().isoformat(), user_id, task_id), fetch=True)
    if not row:
        return None
    add_stars(user_id, t["reward"])
    return t["reward"]


def mark_task_done(user_id, task_id, done=True):
    # Faqat takrorlanadigan 'ref' vazifasi har yangi referalda qayta ochiladi.
    db_exec(
        """INSERT INTO user_tasks (user_id, task_id, done, updated_at)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (user_id, task_id) DO UPDATE SET
             done = EXCLUDED.done,
             claimed = CASE
                 WHEN EXCLUDED.done = 1 AND user_tasks.claimed = 1
                  AND (SELECT action FROM tasks WHERE id = EXCLUDED.task_id) = 'ref'
                  AND (SELECT once FROM tasks WHERE id = EXCLUDED.task_id) = 0
                 THEN 0 ELSE user_tasks.claimed END,
             updated_at = EXCLUDED.updated_at""",
        (user_id, task_id, 1 if done else 0, now_uz().isoformat()))


# ═══════════════════════════════════════════════════════════
# 1. VAZIFALARNI HAQIQATAN TEKSHIRISH
#    Yuqoridagi funksiyalardan KEYIN qo'shing.
# ═══════════════════════════════════════════════════════════
async def _adb(query, params=(), fetch=False, fetchall=False):
    return await asyncio.to_thread(db_exec, query, params, fetch, fetchall)


def _task_channel(link):
    """'@kanal' yoki 'https://t.me/kanal' -> '@kanal'. Yopiq (invite) havola -> None."""
    if not link:
        return None
    l = link.strip()
    if l.startswith("@"):
        return l
    m = re.match(r"^https?://t\.me/([A-Za-z0-9_]{4,})/?$", l)
    return "@" + m.group(1) if m else None


async def task_satisfied(uid, t):
    """True = bajarilgan, False = bajarilmagan, None = o'zgartirma."""
    action = t["action"]
    if action == "sub":
        ch = _task_channel(t["link"])
        if not ch:
            return None
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=uid)
            return m.status not in ("left", "kicked")
        except Exception as e:
            logger.warning(f"Vazifa obuna tekshiruvi ({ch}): {e}")
            return False
    if action == "profile":
        u = await _adb("SELECT phone, username FROM users WHERE user_id=%s", (uid,), fetch=True)
        return bool(u and u.get("phone") and u.get("username"))
    return None   # ref / webapp / manual — boshqa joyda belgilanadi


async def refresh_task_status(uid, only=None):
    rows = await _adb(
        "SELECT t.*, COALESCE(ut.done,0) AS u_done, COALESCE(ut.claimed,0) AS u_claimed "
        "FROM tasks t LEFT JOIN user_tasks ut ON ut.task_id=t.id AND ut.user_id=%s "
        "WHERE t.is_active=1", (uid,), fetchall=True) or []
    for t in rows:
        if only is not None and t["id"] != only:
            continue
        if t["u_claimed"] or t["u_done"]:
            continue
        ok = await task_satisfied(uid, t)
        if ok:
            await asyncio.to_thread(mark_task_done, uid, t["id"])


async def claim_task_reward_async(uid, task_id):
    await refresh_task_status(uid, only=task_id)
    return await asyncio.to_thread(claim_task_reward, uid, task_id)


def mark_action_tasks(uid, action):
    """Mini App ochilganda 'webapp' vazifasini BIR MARTA bajarilgan deb belgilaydi."""
    rows = db_exec("SELECT id FROM tasks WHERE action=%s AND is_active=1", (action,), fetchall=True) or []
    for t in rows:
        db_exec(
            "INSERT INTO user_tasks (user_id, task_id, done, updated_at) VALUES (%s,%s,1,%s) "
            "ON CONFLICT (user_id, task_id) DO NOTHING",
            (uid, t["id"], now_uz().isoformat()))


# --- Botdagi o'zgarishlar ---
# cb_tasks ichida, `tasks = get_user_tasks(uid)` dan OLDIN qo'shing:
#       await refresh_task_status(uid)
# claim_task_cb ichida:
#       reward = claim_task_reward(uid, task_id)
#   ni quyidagiga almashtiring:
#       reward = await claim_task_reward_async(uid, task_id)

# --- Mini App API ---
# api_claim ichida:
#       reward = await asyncio.to_thread(claim_task_reward, uid, int(cid))
#   ni quyidagiga almashtiring:
#       reward = await claim_task_reward_async(uid, int(cid))
#
# make_api ichida, ban tekshiruvidan keyin qo'shing:
#       if request.path == "/api/profile":
#           await asyncio.to_thread(mark_action_tasks, int(tg_user["id"]), "webapp")
#
# Va yangi handler (bonus endi async tekshiruv bilan):
async def api_bonus(request):
    tg_user = _auth(request)
    if not tg_user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=401)
    try:
        user = await asyncio.to_thread(ensure_user, tg_user)
        if user and user.get("is_banned"):
            return web.json_response({"error": "Siz banlangansiz."}, status=403)
        uid = int(tg_user["id"])
        await refresh_task_status(uid)
        data = await asyncio.to_thread(build_bonus_api, uid)
    except Exception:
        logger.exception("API bonus xato")
        return web.json_response({"error": "Server xatosi. Birozdan so'ng urinib ko'ring."}, status=500)
    return web.json_response(data)
# main() ichida ro'yxatdagi ("/api/bonus", build_bonus_api) qatorini O'CHIRING va qo'shing:
#       app.router.add_get("/api/bonus", api_bonus)
#
# Eslatma: 'sub' vazifasi ishlashi uchun bot o'sha kanalda admin bo'lishi shart.
# 'manual' vazifa hech qachon o'zi bajarilmaydi — admin buni qo'lda qilmasa, undan foydalanmang.


# ═══════════════════════════════════════════════════════════
# 3. KONKURS AVTO-TUGASH
#    finish_contest_do ni ALMASHTIRING va yangi funksiyalarni qo'shing.
# ═══════════════════════════════════════════════════════════
async def finalize_contest(cid):
    """(contest, winner|None) qaytaradi. Allaqachon tugagan bo'lsa (None, None)."""
    c = await _adb(
        "UPDATE contests SET status='finished' WHERE id=%s AND status='active' RETURNING *",
        (cid,), fetch=True)
    if not c:
        return None, None
    winner = await _adb(
        "SELECT u.user_id, u.first_name, COUNT(r.user_id) AS cnt "
        "FROM users r JOIN users u ON r.referrer_id = u.user_id "
        "WHERE r.is_verified=1 AND r.joined_at >= %s AND r.joined_at <= %s AND u.is_banned=0 "
        "GROUP BY u.user_id, u.first_name "
        "ORDER BY cnt DESC, MIN(r.joined_at) ASC LIMIT 1",
        (c["start_at"], c["end_at"]), fetch=True)

    if not winner:
        await notify_admins(f"🏁 <b>KONKURS TUGADI</b>\n\n🏆 {esc(c['title'])}\n\nQatnashuvchi bo'lmadi.")
        return c, None

    await _adb("UPDATE contests SET winner_id=%s, winner_referrals=%s WHERE id=%s",
               (winner["user_id"], winner["cnt"], cid))
    prize = f"{esc(c['reward_emoji'])} {esc(c['reward_name'])}"
    text = (
        f"🏁 <b>KONKURS TUGADI!</b>\n\n🏆 {esc(c['title'])}\n\n"
        f"🥇 <b>G'olib:</b> {esc(winner['first_name'])}\n"
        f"🆔 <code>{winner['user_id']}</code>\n"
        f"👥 {winner['cnt']} ta referal\n\n🎁 Sovrin: {prize}")
    await notify_admins(text)
    channel = get_setting("gift_channel", "")
    if channel:
        try:
            await bot.send_message(channel, text.replace(f"\n🆔 <code>{winner['user_id']}</code>", ""),
                                   parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Konkurs e'loni kanalga yuborilmadi: {e}")
    try:
        await bot.send_message(
            winner["user_id"],
            f"🎉 <b>TABRIKLAYMIZ!</b>\n\nSiz <b>{esc(c['title'])}</b> konkursida g'olib bo'ldingiz!\n\n"
            f"🏆 {winner['cnt']} ta referal\n🎁 Sovrin: {prize}\n\nAdmin tez orada bog'lanadi!",
            parse_mode="HTML")
    except Exception:
        pass
    return c, winner


@dp.callback_query(F.data.startswith("fincontest_"))
async def finish_contest_do(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    c, winner = await finalize_contest(int(cb.data.replace("fincontest_", "")))
    if not c:
        await cb.answer("— Allaqachon tugagan", show_alert=True)
        return
    await cb.answer("✅ G'olib aniqlandi" if winner else "✅ Tugatildi (g'olib yo'q)", show_alert=not winner)
    await a_contests(cb)


async def contest_watcher():
    while True:
        try:
            rows = await _adb("SELECT id, end_at FROM contests WHERE status='active'", fetchall=True) or []
            for r in rows:
                try:
                    end = datetime.fromisoformat(r["end_at"])
                except Exception:
                    continue
                if end <= now_uz():
                    await finalize_contest(r["id"])
        except Exception:
            logger.exception("contest_watcher")
        await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════
# 4. GIFT ID SINXRONLASH — sync_gifts ni ALMASHTIRING + import qo'shing
# ═══════════════════════════════════════════════════════════
async def fetch_real_gifts():
    if not tg_client:
        raise ValueError("Userbot ulanmagan")
    if not tg_client.is_connected():
        await tg_client.connect()
    res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
    return [g for g in (getattr(res, "gifts", None) or [])
            if not getattr(g, "limited", False) and not getattr(g, "sold_out", False)]


@dp.callback_query(F.data == "sync_gifts")
async def sync_gifts(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.answer("⏳ Sinxronlanmoqda...")
    try:
        real = await fetch_real_gifts()
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")
        return

    real_ids = {g.id for g in real}
    fixed, broken = [], []
    for row in get_all_gifts():
        if row.get("gift_id") in real_ids:
            continue
        emoji = _norm_emoji(row["emoji"])
        m = next((g for g in real
                  if _norm_emoji(_extract_gift_emoji(g)) == emoji and getattr(g, "stars", None) == row["stars"]),
                 None)
        if m:
            db_exec("UPDATE gifts SET gift_id=%s WHERE key=%s", (m.id, row["key"]))
            fixed.append(f"{esc(row['emoji'])} {esc(row['name'])} → <code>{m.id}</code>")
        else:
            broken.append(f"{esc(row['emoji'])} {esc(row['name'])} ({row['stars']}⭐)")

    lines = [f"{esc(_extract_gift_emoji(g))} <code>{g.id}</code> — {getattr(g, 'stars', '?')} ⭐" for g in real[:30]]
    text = "🎁 <b>SINXRONLASH</b>\n\n"
    text += ("✅ <b>ID tuzatildi:</b>\n" + "\n".join(fixed) + "\n\n") if fixed else "✅ Hammasi joyida yoki o'zgarish yo'q.\n\n"
    if broken:
        text += "⚠️ <b>Mos gift topilmadi</b> (ID ni qo'lda kiriting):\n" + "\n".join(broken) + "\n\n"
    text += "📋 <b>Telegram'dagi mavjud giftlar:</b>\n" + "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "…"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Hammasini import qilish", callback_data="import_gifts")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "import_gifts")
async def import_gifts(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    try:
        real = await fetch_real_gifts()
    except Exception as e:
        await cb.answer(f"❌ {e}"[:190], show_alert=True)
        return
    have = {g.get("gift_id") for g in get_all_gifts()}
    added = 0
    for g in real:
        if g.id in have:
            continue
        add_gift(f"g{g.id}", _extract_gift_emoji(g), _extract_gift_name(g), getattr(g, "stars", 0), g.id)
        added += 1
    await cb.answer(f"✅ {added} ta gift qo'shildi", show_alert=True)
    await a_gifts(cb)


# ═══════════════════════════════════════════════════════════
# GIFT TAHRIRLASH — ID ni ham o'zgartirish
# edit_gift_start, gift_name_process, gift_id_input ni ALMASHTIRING
# ═══════════════════════════════════════════════════════════
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
        f"✏️ <b>{esc(gift['emoji'])} {esc(gift['name'])}</b>\n"
        f"⭐ {gift['stars']}  |  🆔 <code>{gift.get('gift_id') or 'yoq'}</code>\n\n"
        f"Yangi emoji (yoki /skip):",
        parse_mode="HTML")
    await state.set_state(AS.gift_emoji)
    await cb.answer()


@dp.message(AS.gift_name)
async def gift_name_process(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    key = data.get("edit_gift_key")
    if key:
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET name=%s WHERE key=%s", (message.text.strip(), key))
        cur = (get_gift(key) or {}).get("gift_id") or "yoq"
        await message.answer(
            f"🆔 <b>Telegram Gift ID</b> (hozir: <code>{cur}</code>)\n\n"
            f"Yangi ID yuboring yoki /skip",
            parse_mode="HTML")
        await state.set_state(AS.gift_id_input)
    else:
        await state.update_data(gift_name=message.text.strip())
        await message.answer(
            "🆔 <b>Telegram Gift ID</b>\n\n"
            "<i>Bilmasangiz — /skip. Keyin «🔄 Sinxronlash» o'zi topadi.</i>",
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
    data = await state.get_data()
    key = data.get("edit_gift_key")
    if key:
        if gift_id is not None:
            db_exec("UPDATE gifts SET gift_id=%s WHERE key=%s", (gift_id, key))
        await message.answer("⭐ <b>Narx (yoki /skip):</b>", parse_mode="HTML")
    else:
        await state.update_data(gift_id=gift_id)
        await message.answer("⭐ <b>Narx (Stars):</b>", parse_mode="HTML")
    await state.set_state(AS.gift_stars)


# ═══════════════════════════════════════════════════════════
# 5. RENDER UYQUSINI OLDINI OLISH
# ═══════════════════════════════════════════════════════════
async def keepalive():
    base = (os.environ.get("RENDER_EXTERNAL_URL") or WEBAPP_URL or "").rstrip("/")
    if not base:
        return
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        while True:
            await asyncio.sleep(600)
            try:
                async with s.get(base + "/health") as r:
                    await r.read()
            except Exception as e:
                logger.warning(f"keepalive: {e}")
# Qo'shimcha: UptimeRobot da  https://SIZNING-DOMEN/health  uchun 5 daqiqalik monitor oching.


# ═══════════════════════════════════════════════════════════
# 6. AVTOMATIK ZAXIRA NUSXA (har kuni 03:00 Toshkent vaqti, bosh adminga fayl)
# ═══════════════════════════════════════════════════════════
BACKUP_TABLES = [
    "users", "channels", "questions", "gifts", "withdrawals", "settings", "admins",
    "reviews", "levels", "donations", "contests", "daily_bonus", "tasks",
    "user_tasks", "promocodes", "promo_uses", "support_chats",
]


def _dump_db_sync():
    data = {}
    for t in BACKUP_TABLES:
        rows = db_exec(f"SELECT * FROM {t}", fetchall=True) or []
        if t == "settings":   # userbot session va kalitlarini zaxiraga YOZMAYMIZ
            rows = [r for r in rows if not str(r["key"]).startswith("userbot_")]
        data[t] = [dict(r) for r in rows]
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return gzip.compress(raw)


async def send_backup(chat_ids=None):
    blob = await asyncio.to_thread(_dump_db_sync)
    name = f"starrush_backup_{now_uz():%Y%m%d_%H%M}.json.gz"
    for aid in (chat_ids or SUPER_ADMIN_IDS):
        try:
            if len(blob) > 49 * 1024 * 1024:
                await bot.send_message(aid, "⚠️ Zaxira 50 MB dan katta — Telegram orqali yuborib bo'lmaydi.")
            else:
                await bot.send_document(
                    aid, BufferedInputFile(blob, filename=name),
                    caption=f"💾 <b>Zaxira nusxa</b>\n📅 {now_uz():%d.%m.%Y %H:%M}\n📦 {len(blob)//1024} KB",
                    parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Backup yuborilmadi ({aid}): {e}")


async def backup_loop():
    while True:
        now = now_uz()
        nxt = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        await asyncio.sleep((nxt - now).total_seconds())
        try:
            await send_backup()
        except Exception:
            logger.exception("backup_loop")


@dp.callback_query(F.data == "a_backup")
async def a_backup(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await cb.answer("⏳ Tayyorlanmoqda...")
    await send_backup([cb.from_user.id])
# admin_menu ichida, `if is_super_admin(uid):` bloki ichiga qo'shing:
#       b.button(text="💾 Backup", callback_data="a_backup")


# ═══════════════════════════════════════════════════════════
# main() — fon vazifalarini ishga tushirish
# `await bot.delete_webhook(...)` qatoridan KEYIN qo'shing:
# ═══════════════════════════════════════════════════════════
#     bg = [asyncio.create_task(f()) for f in (contest_watcher, keepalive, backup_loop)]
#
# va oxiridagi finally blokini shunday qiling:
#     finally:
#         for t in bg:
#             t.cancel()
#         if tg_client:
#             await tg_client.disconnect()
