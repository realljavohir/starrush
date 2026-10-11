# ═══════════════════════════════════════════════════════════
# features_patch.py — yangi menyu + 1-8 funksiyalar
#
# TARTIB: avval main_design_patch.py va fixes_patch.py qo'llangan bo'lsin.
# Bu fayl ular bergan DIV, box_title, kv, progress_bar, _adb, notify_admins
# funksiyalaridan foydalanadi.
# ═══════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────
# 0. IMPORT — fayl boshiga qo'shing
#   from aiogram import BaseMiddleware
# ───────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════
# A. YANGI INLINE MENYU
#    main_menu() ni ALMASHTIRING. Mini App eng tepada, asosiy 9 tugma,
#    qolganlari «Ko'proq» ichida, Admin alohida qatorda.
# ═══════════════════════════════════════════════════════════
def main_menu(uid):
    lang = get_user_lang(uid)
    cb = lambda text, data: InlineKeyboardButton(text=text, callback_data=data)
    rows = []
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton(text="🚀 " + T(lang, "webapp").replace("🚀", "").strip(),
                                          web_app=WebAppInfo(url=WEBAPP_URL))])
    rows += [
        [cb(T(lang, "ref_link"), "m_reflink")],
        [cb("🔥 " + T(lang, "bonus_menu"), "m_bonus"), cb("📌 " + T(lang, "tasks_menu"), "m_tasks")],
        [cb("🏆 " + T(lang, "contest_menu"), "m_contest"), cb("📊 " + T(lang, "rating").replace("🏆", "").strip(), "m_rating")],
        [cb(T(lang, "withdraw"), "m_withdraw"), cb(T(lang, "profile"), "m_profile")],
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
        [cb("🎟 " + T(lang, "promo_menu"), "m_promo"), cb(T(lang, "gift_stars"), "m_gift")],
        [cb(T(lang, "donate"), "m_donate"), cb(T(lang, "banner"), "m_banner")],
        [cb(T(lang, "review"), "m_review"), cb(T(lang, "support"), "m_support")],
        [cb(remind, "m_remind"), cb("🌐 Til / Язык / Lang", "m_lang")],
        [cb(T(lang, "back"), "m_menu")],
    ])


@dp.callback_query(F.data == "m_more")
async def cb_more(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    try:
        await cb.message.edit_text(T(lang, "more_title"), reply_markup=more_menu(uid), parse_mode="HTML")
    except Exception:
        await cb.message.answer(T(lang, "more_title"), reply_markup=more_menu(uid), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "m_remind")
async def cb_remind(cb: types.CallbackQuery):
    uid = cb.from_user.id
    db_exec("UPDATE users SET remind = 1 - COALESCE(remind, 1) WHERE user_id=%s", (uid,))
    try:
        await cb.message.edit_reply_markup(reply_markup=more_menu(uid))
    except Exception:
        pass
    await cb.answer("✅")


# ═══════════════════════════════════════════════════════════
# B. YANGI JADVALLAR + SOZLAMALAR
#    Quyidagi funksiyani qo'shing va main() da init_db() dan KEYIN chaqiring:
#        init_extra_db()
# ═══════════════════════════════════════════════════════════
def init_extra_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    c = conn.cursor()
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_ok INTEGER DEFAULT 1")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS remind INTEGER DEFAULT 1")
    c.execute("""CREATE TABLE IF NOT EXISTS referral_rewards (
        id SERIAL PRIMARY KEY, referrer_id BIGINT, referred_id BIGINT UNIQUE,
        amount INTEGER, status TEXT DEFAULT 'pending',
        created_at TEXT, release_at TEXT, paid_at TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rr_status ON referral_rewards(status, release_at)")
    c.execute("""CREATE TABLE IF NOT EXISTS user_ips (
        user_id BIGINT, ip_hash TEXT, seen_at TEXT, PRIMARY KEY (user_id, ip_hash))""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ips_hash ON user_ips(ip_hash)")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY, actor_id BIGINT, action TEXT, target_id BIGINT,
        amount INTEGER, details TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reminders_log (
        kind TEXT, ref TEXT, user_id BIGINT, sent_at TEXT, PRIMARY KEY (kind, ref, user_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS period_rewards (
        period TEXT, rank INTEGER, user_id BIGINT, amount INTEGER, created_at TEXT,
        PRIMARY KEY (period, rank))""")
    defaults = {
        "ref_hold_hours": "24",          # referal Stars i necha soatdan keyin beriladi
        "ref_clawback_days": "7",        # shu muddat ichida chiqib ketsa, Stars ayiriladi
        "ip_max_accounts": "4",          # bir IP dan shundan ko'p akkaunt -> qo'lda tekshiruv
        "daily_withdraw_limit": "500",   # kuniga maksimal yechish (⭐)
        "min_account_age_days": "3",     # yechish uchun akkaunt yoshi
        "reminder_hour": "19",           # eslatma vaqti (Toshkent)
        "weekly_rewards": "10,5,3",      # haftalik TOP-3
        "monthly_rewards": "50,25,10",   # oylik TOP-3
    }
    for k, v in defaults.items():
        c.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v))
    c.close()
    conn.close()


# ═══════════════════════════════════════════════════════════
# 8. KO'P TILLILIK — yangi matnlar (LANGS dan KEYIN, def T dan OLDIN qo'shing)
# ═══════════════════════════════════════════════════════════
EXTRA_TEXT = {
    "uz": {
        "more_btn": "⚙️ Ko'proq", "more_title": "⚙️ <b>KO'PROQ</b>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nQo'shimcha bo'limlar 👇",
        "history": "📜 So'rovlarim", "remind_on": "🔔 Eslatma: yoqilgan", "remind_off": "🔕 Eslatma: o'chiq",
        "hist_title": "📜 SO'ROVLARIM", "hist_empty": "<i>Hozircha so'rovlar yo'q</i>",
        "st_pending": "Kutilmoqda", "st_processing": "Jarayonda", "st_approved": "Bajarildi",
        "st_rejected": "Rad etildi", "st_failed": "Xato (qaytarildi)",
        "ref_pending": "👥 <b>Yangi referal!</b>\n<b>+{n} ⭐</b> {h} soatdan keyin hisobingizga tushadi (tekshiruv).",
        "ref_clawback": "⚠️ Referalingiz kanaldan chiqib ketdi. <b>-{n} ⭐</b> ayirildi.",
        "wd_too_new": "❌ Yechib olish ro'yxatdan o'tgach {n} kundan keyin ochiladi.",
        "wd_daily_limit": "❌ Kunlik limit: {limit} ⭐. Bugun yana {left} ⭐ yechishingiz mumkin.",
        "rem_bonus": "🔥 <b>Kunlik bonusingiz kutmoqda!</b>\nSeriyani uzmang — bugun oling 👇", "rem_btn": "🎁 Bonusni olish",
        "rem_contest": "⏰ <b>{title}</b> konkursi tugashiga {h} soat qoldi!\nO'rningizni mustahkamlang 👇", "rem_contest_btn": "🏆 Konkursga o'tish",
        "period_reward": "🏅 <b>{kind} TOP-{rank}!</b>\nSiz <b>+{n} ⭐</b> mukofot oldingiz. Tabriklaymiz!",
        "kind_week": "Haftalik", "kind_month": "Oylik",
        "err_min": "❌ Minimal: {n} ⭐", "err_max": "❌ Maksimal: {n} ⭐", "err_unsupported": "❌ Bu turdagi xabar qo'llab-quvvatlanmaydi.",
        "err_review_short": "❌ Sharh juda qisqa (kamida 5 belgi).", "err_no_admin": "⚠️ Hozir admin topilmadi.",
        "err_generic": "❌ Xato. Qayta urinib ko'ring.", "err_claim": "❌ Mukofot olish mumkin emas",
        "reason_bonus": "Kunlik bonus", "reason_task": "Vazifa mukofoti", "reason_promo": "Promokod",
        "pf_title": "👤 PROFIL", "st_title": "📊 STATISTIKA", "lbl_stars": "Stars", "lbl_donate": "Donat",
        "lbl_next": "Keyingi", "lbl_maxlvl": "👑 Eng yuqori daraja!", "lbl_refs": "Takliflar", "lbl_rank": "O'rin",
        "lbl_week": "Bu hafta", "lbl_verified": "Tasdiqlangan", "lbl_joined": "Qo'shilgan", "lbl_unit": "ta", "btn_refresh": "🔄 Yangilash",
        "ct_prize": "Sovrin", "ct_left": "Qoldi: {d} kun {h} soat", "ct_board": "LEADERBOARD", "ct_me": "SIZ",
        "ct_nobody": "<i>Hozircha qatnashuvchi yo'q</i>", "task_claimed": "olindi", "task_ready": "Mukofot tayyor!",
        "task_done": "Bajarildi", "task_todo": "Bajarilmagan", "task_none": "<i>Vazifalar yo'q</i>",
    },
    "ru": {
        "more_btn": "⚙️ Ещё", "more_title": "⚙️ <b>ЕЩЁ</b>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nДополнительные разделы 👇",
        "history": "📜 Мои заявки", "remind_on": "🔔 Напоминания: вкл", "remind_off": "🔕 Напоминания: выкл",
        "hist_title": "📜 МОИ ЗАЯВКИ", "hist_empty": "<i>Заявок пока нет</i>",
        "st_pending": "Ожидает", "st_processing": "В процессе", "st_approved": "Выполнено",
        "st_rejected": "Отклонено", "st_failed": "Ошибка (возврат)",
        "ref_pending": "👥 <b>Новый реферал!</b>\n<b>+{n} ⭐</b> поступит через {h} ч. (проверка).",
        "ref_clawback": "⚠️ Ваш реферал вышел из канала. <b>-{n} ⭐</b> списано.",
        "wd_too_new": "❌ Вывод откроется через {n} дн. после регистрации.",
        "wd_daily_limit": "❌ Дневной лимит: {limit} ⭐. Сегодня можно вывести ещё {left} ⭐.",
        "rem_bonus": "🔥 <b>Ваш ежедневный бонус ждёт!</b>\nНе прерывайте серию — заберите 👇", "rem_btn": "🎁 Забрать бонус",
        "rem_contest": "⏰ До конца конкурса <b>{title}</b> осталось {h} ч.!\nУкрепите свою позицию 👇", "rem_contest_btn": "🏆 К конкурсу",
        "period_reward": "🏅 <b>{kind} ТОП-{rank}!</b>\nВы получили <b>+{n} ⭐</b>. Поздравляем!",
        "kind_week": "Недельный", "kind_month": "Месячный",
        "err_min": "❌ Минимум: {n} ⭐", "err_max": "❌ Максимум: {n} ⭐", "err_unsupported": "❌ Этот тип сообщений не поддерживается.",
        "err_review_short": "❌ Отзыв слишком короткий (минимум 5 символов).", "err_no_admin": "⚠️ Админ сейчас недоступен.",
        "err_generic": "❌ Ошибка. Попробуйте ещё раз.", "err_claim": "❌ Получить награду нельзя",
        "reason_bonus": "Ежедневный бонус", "reason_task": "Награда за задание", "reason_promo": "Промокод",
        "pf_title": "👤 ПРОФИЛЬ", "st_title": "📊 СТАТИСТИКА", "lbl_stars": "Stars", "lbl_donate": "Донат",
        "lbl_next": "Следующий", "lbl_maxlvl": "👑 Максимальный уровень!", "lbl_refs": "Приглашено", "lbl_rank": "Место",
        "lbl_week": "За неделю", "lbl_verified": "Подтверждён", "lbl_joined": "Регистрация", "lbl_unit": "шт.", "btn_refresh": "🔄 Обновить",
        "ct_prize": "Приз", "ct_left": "Осталось: {d} дн. {h} ч.", "ct_board": "ЛИДЕРБОРД", "ct_me": "ВЫ",
        "ct_nobody": "<i>Участников пока нет</i>", "task_claimed": "получено", "task_ready": "Награда готова!",
        "task_done": "Выполнено", "task_todo": "Не выполнено", "task_none": "<i>Заданий нет</i>",
    },
    "en": {
        "more_btn": "⚙️ More", "more_title": "⚙️ <b>MORE</b>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nExtra sections 👇",
        "history": "📜 My requests", "remind_on": "🔔 Reminders: on", "remind_off": "🔕 Reminders: off",
        "hist_title": "📜 MY REQUESTS", "hist_empty": "<i>No requests yet</i>",
        "st_pending": "Pending", "st_processing": "Processing", "st_approved": "Completed",
        "st_rejected": "Rejected", "st_failed": "Failed (refunded)",
        "ref_pending": "👥 <b>New referral!</b>\n<b>+{n} ⭐</b> will be credited in {h}h (verification).",
        "ref_clawback": "⚠️ Your referral left the channel. <b>-{n} ⭐</b> deducted.",
        "wd_too_new": "❌ Withdrawals unlock {n} day(s) after registration.",
        "wd_daily_limit": "❌ Daily limit: {limit} ⭐. You can withdraw {left} ⭐ more today.",
        "rem_bonus": "🔥 <b>Your daily bonus is waiting!</b>\nKeep your streak — claim it 👇", "rem_btn": "🎁 Claim bonus",
        "rem_contest": "⏰ <b>{title}</b> ends in {h}h!\nSecure your spot 👇", "rem_contest_btn": "🏆 Open contest",
        "period_reward": "🏅 <b>{kind} TOP-{rank}!</b>\nYou earned <b>+{n} ⭐</b>. Congratulations!",
        "kind_week": "Weekly", "kind_month": "Monthly",
        "err_min": "❌ Minimum: {n} ⭐", "err_max": "❌ Maximum: {n} ⭐", "err_unsupported": "❌ This message type is not supported.",
        "err_review_short": "❌ Review too short (min 5 characters).", "err_no_admin": "⚠️ No admin available right now.",
        "err_generic": "❌ Error. Please try again.", "err_claim": "❌ Reward can't be claimed",
        "reason_bonus": "Daily bonus", "reason_task": "Task reward", "reason_promo": "Promocode",
        "pf_title": "👤 PROFILE", "st_title": "📊 STATISTICS", "lbl_stars": "Stars", "lbl_donate": "Donated",
        "lbl_next": "Next", "lbl_maxlvl": "👑 Max level!", "lbl_refs": "Invited", "lbl_rank": "Rank",
        "lbl_week": "This week", "lbl_verified": "Verified", "lbl_joined": "Joined", "lbl_unit": "pcs", "btn_refresh": "🔄 Refresh",
        "ct_prize": "Prize", "ct_left": "Left: {d}d {h}h", "ct_board": "LEADERBOARD", "ct_me": "YOU",
        "ct_nobody": "<i>No participants yet</i>", "task_claimed": "claimed", "task_ready": "Reward ready!",
        "task_done": "Done", "task_todo": "Not done", "task_none": "<i>No tasks</i>",
    },
}
for _code, _d in EXTRA_TEXT.items():
    LANGS[_code].update(_d)

# Qolgan qattiq yozilgan matnlarni almashtiring (qidiring -> almashtiring):
#   f"❌ Min: {MIN_DONATE} ⭐"                -> T(lang, "err_min", n=MIN_DONATE)
#   f"❌ Max: {format_number(MAX_DONATE)} ⭐"  -> T(lang, "err_max", n=format_number(MAX_DONATE))
#   "❌ Bu turdagi xabar qo'llab-quvvatlanmaydi." -> T(lang, "err_unsupported")
#   "❌ Sharh juda qisqa. Kamida 5 ta belgi."  -> T(lang, "err_review_short")
#   "⚠️ Hech qanday admin topilmadi."          -> T(lang, "err_no_admin")
#   "❌ Mukofot olish mumkin emas"             -> T(lang, "err_claim")
#   reason="Kunlik bonus"                      -> reason=T(lang, "reason_bonus")
#   reason="Vazifa mukofoti"                   -> reason=T(lang, "reason_task")
#   reason=f"Promokod: {code}"                 -> reason=f"{T(lang, 'reason_promo')}: {code}"
#   (bu 3 reason cb ichida ham, api_claim/api_promo ichida ham bor)
# Admin xabarlari (admin panel, adminga bildirishnomalar) o'zbekcha qolaveradi.


# ═══════════════════════════════════════════════════════════
# 1. SOXTA REFERALGA QARSHI HIMOYA
# ═══════════════════════════════════════════════════════════
async def queue_referral_reward(ref_id, uid):
    """Referal Stars i darhol emas, kutish muddatidan keyin beriladi."""
    reward = int(get_setting("stars_per_referral", "2"))
    hold = int(get_setting("ref_hold_hours", "24"))
    now = now_uz()
    row = await _adb(
        "INSERT INTO referral_rewards (referrer_id, referred_id, amount, status, created_at, release_at) "
        "VALUES (%s, %s, %s, 'pending', %s, %s) ON CONFLICT (referred_id) DO NOTHING RETURNING id",
        (ref_id, uid, reward, now.isoformat(), (now + timedelta(hours=hold)).isoformat()), fetch=True)
    if row:
        try:
            await bot.send_message(ref_id, T(get_user_lang(ref_id), "ref_pending", n=reward, h=hold),
                                   parse_mode="HTML")
        except Exception:
            pass

# check_ans ichida eski blokni ALMASHTIRING:
#     else:
#         reward = int(get_setting("stars_per_referral", "2"))
#         new_stars = add_stars(ref_id, reward)
#         ... (check_level_up va ref_tasks bilan birga, butun else: tanasi)
#   shunga:
#     else:
#         await queue_referral_reward(ref_id, uid)


def _client_ip(request):
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.remote or "")


def record_ip(uid, ip):
    if not ip:
        return
    h = hashlib.sha256((BOT_TOKEN[:20] + ip).encode()).hexdigest()
    db_exec("INSERT INTO user_ips (user_id, ip_hash, seen_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (uid, h, now_uz().isoformat()))

# make_api va api_bonus ichida, ban tekshiruvidan keyin qo'shing:
#       await asyncio.to_thread(record_ip, int(tg_user["id"]), _client_ip(request))


def ip_shared_accounts(uid):
    r = db_exec(
        "SELECT COUNT(DISTINCT user_id) AS c FROM user_ips "
        "WHERE ip_hash IN (SELECT ip_hash FROM user_ips WHERE user_id=%s)", (uid,), fetch=True)
    return int(r["c"]) if r else 0


async def pay_referral(rid, from_status):
    r = await _adb(
        "UPDATE referral_rewards SET status='paid', paid_at=%s WHERE id=%s AND status=%s RETURNING *",
        (now_uz().isoformat(), rid, from_status), fetch=True)
    if not r:
        return False
    old_new = await asyncio.to_thread(add_stars, r["referrer_id"], r["amount"])
    if old_new is None:
        return False
    lang = get_user_lang(r["referrer_id"])
    try:
        await bot.send_message(
            r["referrer_id"],
            T(lang, "referral_reward", n=r["amount"]) + f"\n💰 {T(lang, 'total')}: <b>{old_new} ⭐</b>",
            parse_mode="HTML")
    except Exception:
        pass
    await check_level_up(r["referrer_id"], old_new - r["amount"], old_new)
    try:
        for rt in (await _adb("SELECT id FROM tasks WHERE action='ref' AND is_active=1", fetchall=True) or []):
            await asyncio.to_thread(mark_task_done, r["referrer_id"], rt["id"])
    except Exception as e:
        logger.warning(f"Task mark xato: {e}")
    return True


async def release_referrals():
    due = await _adb(
        "SELECT * FROM referral_rewards WHERE status='pending' AND release_at <= %s ORDER BY id LIMIT 200",
        (now_uz().isoformat(),), fetchall=True) or []
    max_ip = int(get_setting("ip_max_accounts", "4"))
    for r in due:
        got = await _adb("UPDATE referral_rewards SET status='processing' WHERE id=%s AND status='pending' RETURNING id",
                         (r["id"],), fetch=True)
        if not got:
            continue
        ref, red = get_user(r["referrer_id"]), get_user(r["referred_id"])
        good = bool(ref and red and not ref["is_banned"] and not red["is_banned"]
                    and red["is_verified"] and red.get("sub_ok", 1) != 0
                    and await check_subs(r["referred_id"]))
        if not good:
            await _adb("UPDATE referral_rewards SET status='cancelled' WHERE id=%s", (r["id"],))
            continue
        shared = await asyncio.to_thread(ip_shared_accounts, r["referred_id"])
        if shared >= max_ip:
            await _adb("UPDATE referral_rewards SET status='flagged' WHERE id=%s", (r["id"],))
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ To'lash", callback_data=f"rr_ok_{r['id']}")
            kb.button(text="❌ Bekor", callback_data=f"rr_no_{r['id']}")
            kb.adjust(2)
            await notify_admins(
                f"🚩 <b>Shubhali referal</b> #{r['id']}\n"
                f"Referer: <code>{r['referrer_id']}</code>\nYangi: <code>{r['referred_id']}</code>\n"
                f"Bir xil IP dagi akkauntlar: <b>{shared}</b>\n<i>(mobil operator IP si bo'lishi ham mumkin)</i>",
                kb.as_markup())
            continue
        await pay_referral(r["id"], "processing")


@dp.callback_query(F.data.startswith("rr_ok_") | F.data.startswith("rr_no_"))
async def referral_review(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    rid = int(cb.data.rsplit("_", 1)[1])
    if cb.data.startswith("rr_ok_"):
        ok = await pay_referral(rid, "flagged")
        audit(cb.from_user.id, "referral_flag_pay", None, None, f"#{rid}")
    else:
        await _adb("UPDATE referral_rewards SET status='cancelled' WHERE id=%s AND status='flagged'", (rid,))
        ok = True
        audit(cb.from_user.id, "referral_flag_cancel", None, None, f"#{rid}")
    try:
        await cb.message.edit_text(cb.message.html_text + ("\n\n✅ <b>HAL QILINDI</b>" if ok else "\n\n—"),
                                   parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("✅")


async def clawback_for(referred_id):
    """Referal chiqib ketsa/banlansa: kutayotganini bekor qiladi, to'langanini ayiradi."""
    await _adb("UPDATE referral_rewards SET status='cancelled' "
               "WHERE referred_id=%s AND status IN ('pending','flagged')", (referred_id,))
    days = int(get_setting("ref_clawback_days", "7"))
    cutoff = (now_uz() - timedelta(days=days)).isoformat()
    r = await _adb(
        "UPDATE referral_rewards SET status='clawed' "
        "WHERE referred_id=%s AND status='paid' AND paid_at >= %s RETURNING *", (referred_id, cutoff), fetch=True)
    if r:
        await _adb("UPDATE users SET stars = GREATEST(stars - %s, 0) WHERE user_id=%s", (r["amount"], r["referrer_id"]))
        audit(0, "referral_clawback", r["referrer_id"], -r["amount"], f"referred {referred_id}")
        try:
            await bot.send_message(r["referrer_id"], T(get_user_lang(r["referrer_id"]), "ref_clawback", n=r["amount"]),
                                   parse_mode="HTML")
        except Exception:
            pass

# toggle_ban ichida, update_user(uid, is_banned=new_val) dan keyin qo'shing:
#       if new_val:
#           await clawback_for(uid)


async def release_loop():
    while True:
        try:
            await release_referrals()
        except Exception:
            logger.exception("release_loop")
        await asyncio.sleep(300)


# ═══════════════════════════════════════════════════════════
# 5. HOMIY KANALLARNI QAYTA TEKSHIRISH + MENYUNI YOPISH
# ═══════════════════════════════════════════════════════════
class SubGate(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user and not is_admin(user.id):
            row = await _adb("SELECT sub_ok FROM users WHERE user_id=%s", (user.id,), fetch=True)
            if row and row["sub_ok"] == 0:
                if isinstance(event, types.CallbackQuery):
                    if event.data == "check_sub":
                        return await handler(event, data)
                    lang = get_user_lang(user.id)
                    await event.answer()
                    await event.message.answer(T(lang, "subscribe"), reply_markup=await subs_kb(user.id),
                                               parse_mode="HTML")
                    return
                if isinstance(event, types.Message):
                    if (event.text or "").startswith("/start") or event.successful_payment:
                        return await handler(event, data)
                    lang = get_user_lang(user.id)
                    await event.answer(T(lang, "subscribe"), reply_markup=await subs_kb(user.id), parse_mode="HTML")
                    return
        return await handler(event, data)

# main() ichida, security.setup(...) dan OLDIN qo'shing:
#       dp.message.outer_middleware(SubGate())
#       dp.callback_query.outer_middleware(SubGate())
#
# check_sub_cb ichida, `await cb.answer(T(lang, "correct"))` dan keyin qo'shing:
#       update_user(uid, sub_ok=1)
# cmd_start ichida, `if not await check_subs(uid): ... return` bloki O'TGANIDAN keyin qo'shing:
#       update_user(uid, sub_ok=1)


async def recheck_subscriptions():
    if not get_channels():
        return
    rows = await _adb("SELECT user_id FROM users WHERE is_verified=1 AND is_banned=0 AND sub_ok=1",
                      fetchall=True) or []
    for r in rows:
        uid = r["user_id"]
        if is_admin(uid):
            continue
        if not await check_subs(uid):
            await _adb("UPDATE users SET sub_ok=0 WHERE user_id=%s", (uid,))
            await clawback_for(uid)
            try:
                await bot.send_message(uid, T(get_user_lang(uid), "subscribe"),
                                       reply_markup=await subs_kb(uid), parse_mode="HTML")
            except Exception:
                pass
        await asyncio.sleep(0.08)


async def sub_recheck_loop():
    await asyncio.sleep(600)
    while True:
        try:
            await recheck_subscriptions()
        except Exception:
            logger.exception("sub_recheck_loop")
        await asyncio.sleep(24 * 3600)


# ═══════════════════════════════════════════════════════════
# 2. YECHISHDA LIMIT + "SO'ROVLARIM" TARIXI
# ═══════════════════════════════════════════════════════════
async def withdraw_guard(uid, amount, lang):
    """Xato matni (oddiy matn) yoki None."""
    u = await _adb("SELECT joined_at FROM users WHERE user_id=%s", (uid,), fetch=True)
    min_days = int(get_setting("min_account_age_days", "3"))
    try:
        age = (now_uz() - datetime.fromisoformat(u["joined_at"])).days
    except Exception:
        age = min_days
    if age < min_days:
        return re.sub(r"<[^>]+>", "", T(lang, "wd_too_new", n=min_days - age))
    limit = int(get_setting("daily_withdraw_limit", "500"))
    start = now_uz().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    row = await _adb(
        "SELECT COALESCE(SUM(stars),0) AS s FROM withdrawals "
        "WHERE user_id=%s AND created_at >= %s AND status IN ('pending','processing','approved')",
        (uid, start), fetch=True)
    used = int(row["s"]) if row else 0
    if used + amount > limit:
        return re.sub(r"<[^>]+>", "", T(lang, "wd_daily_limit", limit=limit, left=max(limit - used, 0)))
    return None

# w_stars_process ichida, max_w tekshiruvidan keyin qo'shing:
#       err = await withdraw_guard(uid, amount, lang)
#       if err:
#           await message.answer(err)
#           return
# gift_select ichida, "not_enough" tekshiruvidan keyin qo'shing:
#       err = await withdraw_guard(uid, gift["stars"], lang)
#       if err:
#           await cb.answer(err, show_alert=True)
#           return


@dp.callback_query(F.data == "m_history")
async def cb_history(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    rows = db_exec(
        "SELECT w.id, w.stars, w.reward_type, w.status, w.created_at, g.emoji, g.name "
        "FROM withdrawals w LEFT JOIN gifts g ON g.key = w.gift_key "
        "WHERE w.user_id=%s ORDER BY w.id DESC LIMIT 15", (uid,), fetchall=True) or []
    icons = {"pending": "⏳", "processing": "🔄", "approved": "✅", "rejected": "❌", "failed": "⚠️"}
    text = box_title(T(lang, "hist_title")) + "\n"
    if not rows:
        text += "\n" + T(lang, "hist_empty")
    for r in rows:
        item = f"{esc(r['emoji'] or '🎁')} {esc(r['name'] or 'Gift')}" if r["reward_type"] == "gift" else "⭐ Stars"
        d = (r["created_at"] or "")
        date = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else ""
        st = T(lang, "st_" + r["status"]) if ("st_" + r["status"]) in LANGS[lang] else r["status"]
        text += (f"\n{icons.get(r['status'], '•')} <b>#{r['id']}</b> {item} · {format_number(r['stars'])} ⭐\n"
                 f"    {st} · <i>{date}</i>")
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "back"), callback_data="m_more")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()

# Admin sozlamalariga yangi qiymatlar (a_settings tugmalariga qo'shing):
#   b.button(text="📅 Kunlik limit", callback_data="set_dlim")
#   b.button(text="🕒 Min akkaunt yoshi", callback_data="set_age")
#   b.button(text="⏳ Referal kutish", callback_data="set_hold")
# set_val_start dagi  F.data.in_({"set_ref","set_minw","set_maxw"})  ga yangilarini qo'shing va mapping ga:
#   "set_dlim": ("daily_withdraw_limit", "📅 <b>Kunlik yechish limiti (⭐):</b>"),
#   "set_age":  ("min_account_age_days", "🕒 <b>Minimal akkaunt yoshi (kun):</b>"),
#   "set_hold": ("ref_hold_hours", "⏳ <b>Referal Stars kutish muddati (soat):</b>"),


# ═══════════════════════════════════════════════════════════
# 3. AUDIT LOG
# ═══════════════════════════════════════════════════════════
def audit(actor, action, target=None, amount=None, details=""):
    try:
        db_exec("INSERT INTO audit_log (actor_id, action, target_id, amount, details, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (actor, action, target, amount, (details or "")[:300], now_uz().isoformat()))
    except Exception:
        logger.exception("audit")


@dp.callback_query(F.data == "a_audit")
async def a_audit(cb: types.CallbackQuery):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    rows = db_exec("SELECT * FROM audit_log ORDER BY id DESC LIMIT 25", fetchall=True) or []
    text = box_title("📜 AUDIT LOG") + "\n"
    if not rows:
        text += "\n<i>Bo'sh</i>"
    for r in rows:
        d = r["created_at"] or ""
        when = f"{d[8:10]}.{d[5:7]} {d[11:16]}"
        amt = f" {r['amount']:+d}⭐" if r["amount"] is not None else ""
        tgt = f" → <code>{r['target_id']}</code>" if r["target_id"] else ""
        text += (f"\n<code>{when}</code> <code>{r['actor_id']}</code>{tgt}\n"
                 f"   {esc(r['action'])}{amt} {esc(r['details'] or '')}")
    if len(text) > 4000:
        text = text[:3990] + "…"
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_audit")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()
# admin_menu ichida, `if is_super_admin(uid):` blokiga qo'shing:
#       b.button(text="📜 Audit log", callback_data="a_audit")
#
# audit() chaqiruvlarini quyidagi joylarga qo'ying (har biri 1 qator):
#   stars_reason_input  (Stars qo'shish/ayirish), oxirida:
#       audit(message.from_user.id, "stars_add" if action == "add" else "stars_remove",
#             uid, amount if action == "add" else -amount, reason)
#   approve_w  (cb.answer("✅") dan oldin):   audit(cb.from_user.id, "withdraw_approve", w["user_id"], -w["stars"], f"#{w_id}")
#   reject_w   (cb.answer("❌") dan oldin):   audit(cb.from_user.id, "withdraw_reject", w["user_id"], None, f"#{w_id}")
#   toggle_ban (update_user dan keyin):       audit(cb.from_user.id, "ban" if new_val else "unban", uid)
#   add_admin_do:                             audit(message.from_user.id, "admin_add", uid)
#   del_admin_do:                             audit(cb.from_user.id, "admin_remove", uid)
#   set_val_do:                               audit(message.from_user.id, "setting", None, val, data["setting_key"])
#   promo_uses_input:                         audit(message.from_user.id, "promo_create", None, data["p_reward"], data["p_code"])
#   finish_contest_do / del_contest_do / del_task_do / del_promo_do:  audit(cb.from_user.id, "<nom>", None, None, <id>)
#   a_userbot_del_yes, userbot_session_input: audit(<admin id>, "userbot_remove" / "userbot_change")


# ═══════════════════════════════════════════════════════════
# 4. ADMIN STATISTIKA: /stats + HAFTALIK HISOBOT (grafik bilan)
# ═══════════════════════════════════════════════════════════
def collect_stats(days=7):
    today = now_uz().replace(hour=0, minute=0, second=0, microsecond=0)
    labels = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    since = labels[0]

    def series(sql):
        rows = db_exec(sql, (since,), fetchall=True) or []
        m = {r["d"]: int(r["v"]) for r in rows}
        return [m.get(d, 0) for d in labels]

    return {
        "labels": labels,
        "users": series("SELECT LEFT(joined_at,10) AS d, COUNT(*) AS v FROM users WHERE joined_at >= %s GROUP BY 1"),
        "refs": series("SELECT LEFT(paid_at,10) AS d, COUNT(*) AS v FROM referral_rewards "
                       "WHERE status='paid' AND paid_at >= %s GROUP BY 1"),
        "withdrawn": series("SELECT LEFT(created_at,10) AS d, COALESCE(SUM(stars),0) AS v FROM withdrawals "
                            "WHERE status='approved' AND created_at >= %s GROUP BY 1"),
        "donated": series("SELECT LEFT(created_at,10) AS d, COALESCE(SUM(stars),0) AS v FROM donations "
                          "WHERE created_at >= %s GROUP BY 1"),
    }


def _spark(vals):
    bars = "▁▂▃▄▅▆▇█"
    mx = max(vals) or 1
    return "".join(bars[min(7, int(v / mx * 7))] if v else "▁" for v in vals)


def make_stats_chart(s):
    W, H = 900, 460
    img = Image.new("RGB", (W, H), (12, 16, 32))
    d = ImageDraw.Draw(img)
    f_t, f_s = _load_font(30, True), _load_font(18)
    d.text((40, 24), "StarRush — 7 kunlik statistika", font=f_t, fill=(255, 255, 255))
    d.rectangle([40, 70, 140, 74], fill=(245, 179, 53))
    x0, y0, x1, y1 = 50, 110, W - 40, H - 70
    mx = max(max(s["users"]), max(s["refs"]), 1)
    n = len(s["labels"])
    gw = (x1 - x0) / n
    for i in range(5):
        y = y1 - (y1 - y0) * i / 4
        d.line([x0, y, x1, y], fill=(32, 40, 66))
        d.text((8, y - 9), str(int(mx * i / 4)), font=f_s, fill=(120, 130, 160))
    for i, lab in enumerate(s["labels"]):
        cx = x0 + gw * i + gw / 2
        for off, val, col in ((-14, s["users"][i], (108, 92, 231)), (14, s["refs"][i], (245, 179, 53))):
            h = (y1 - y0) * val / mx
            d.rounded_rectangle([cx + off - 11, y1 - h, cx + off + 11, y1], radius=5, fill=col)
            if val:
                d.text((cx + off - 8, y1 - h - 22), str(val), font=f_s, fill=(220, 225, 240))
        d.text((cx - 20, y1 + 10), lab[5:], font=f_s, fill=(150, 160, 190))
    d.rectangle([W - 330, 30, W - 312, 48], fill=(108, 92, 231))
    d.text((W - 304, 26), "Yangi userlar", font=f_s, fill=(220, 225, 240))
    d.rectangle([W - 170, 30, W - 152, 48], fill=(245, 179, 53))
    d.text((W - 144, 26), "Referal", font=f_s, fill=(220, 225, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def stats_caption(s):
    return (
        f"{box_title('📊 7 KUNLIK HISOBOT')}\n"
        f"👥 Yangi userlar: <b>{sum(s['users'])}</b>  {_spark(s['users'])}\n"
        f"🔗 To'langan referal: <b>{sum(s['refs'])}</b>  {_spark(s['refs'])}\n"
        f"💸 Yechilgan: <b>{format_number(sum(s['withdrawn']))} ⭐</b>  {_spark(s['withdrawn'])}\n"
        f"💝 Donat: <b>{format_number(sum(s['donated']))} ⭐</b>  {_spark(s['donated'])}\n\n"
        f"Bugun: +{s['users'][-1]} user · {s['refs'][-1]} referal · {format_number(s['withdrawn'][-1])} ⭐ yechildi"
    )


async def send_stats(chat_id):
    s = await asyncio.to_thread(collect_stats, 7)
    png = await asyncio.to_thread(make_stats_chart, s)
    await bot.send_photo(chat_id, BufferedInputFile(png, filename="stats.png"),
                         caption=stats_caption(s), parse_mode="HTML")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await send_stats(message.chat.id)


async def weekly_report_loop():
    while True:
        try:
            now = now_uz()
            mon = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            label = f"R{mon:%G-%V}"
            if now >= mon + timedelta(hours=9) and get_setting("last_weekly_report") != label:
                set_setting("last_weekly_report", label)
                for a in list_admins():
                    try:
                        await send_stats(a["user_id"])
                    except Exception as e:
                        logger.warning(f"Hisobot yuborilmadi ({a['user_id']}): {e}")
        except Exception:
            logger.exception("weekly_report_loop")
        await asyncio.sleep(600)


# ═══════════════════════════════════════════════════════════
# 6. ESLATMALAR (kunlik bonus + konkurs tugashi)
# ═══════════════════════════════════════════════════════════
async def _send_reminders(rows, kind, ref, build):
    for r in rows:
        uid = r["user_id"]
        lang = r.get("language") if r.get("language") in LANGS else "uz"
        ins = await _adb("INSERT INTO reminders_log (kind, ref, user_id, sent_at) VALUES (%s,%s,%s,%s) "
                         "ON CONFLICT DO NOTHING RETURNING user_id",
                         (kind, ref, uid, now_uz().isoformat()), fetch=True)
        if not ins:
            continue
        text, kb = build(lang)
        try:
            await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
        except TelegramForbiddenError:
            await _adb("UPDATE users SET remind=0 WHERE user_id=%s", (uid,))
        except Exception:
            pass
        await asyncio.sleep(0.06)


async def reminder_loop():
    while True:
        try:
            now = now_uz()
            today = now.strftime("%Y-%m-%d")
            base = "u.is_verified=1 AND u.is_banned=0 AND u.sub_ok=1 AND COALESCE(u.remind,1)=1"

            if now.hour == int(get_setting("reminder_hour", "19")):
                rows = await _adb(
                    f"SELECT u.user_id, u.language FROM users u LEFT JOIN daily_bonus d ON d.user_id=u.user_id "
                    f"WHERE {base} AND COALESCE(LEFT(d.last_claim,10),'') <> %s "
                    f"AND NOT EXISTS (SELECT 1 FROM reminders_log r WHERE r.kind='bonus' AND r.ref=%s AND r.user_id=u.user_id)",
                    (today, today), fetchall=True) or []

                def build_bonus(lang):
                    kb = InlineKeyboardBuilder()
                    kb.button(text=T(lang, "rem_btn"), callback_data="m_bonus")
                    return T(lang, "rem_bonus"), kb.as_markup()
                await _send_reminders(rows, "bonus", today, build_bonus)

            c = get_active_contest()
            if c:
                try:
                    left = datetime.fromisoformat(c["end_at"]) - now
                except Exception:
                    left = None
                if left and timedelta(0) < left <= timedelta(hours=24):
                    hours = max(1, int(left.total_seconds() // 3600))
                    rows = await _adb(
                        f"SELECT u.user_id, u.language FROM users u WHERE {base} "
                        f"AND NOT EXISTS (SELECT 1 FROM reminders_log r WHERE r.kind='contest' AND r.ref=%s AND r.user_id=u.user_id)",
                        (str(c["id"]),), fetchall=True) or []

                    def build_contest(lang):
                        kb = InlineKeyboardBuilder()
                        kb.button(text=T(lang, "rem_contest_btn"), callback_data="m_contest")
                        return T(lang, "rem_contest", title=esc(c["title"]), h=hours), kb.as_markup()
                    await _send_reminders(rows, "contest", str(c["id"]), build_contest)
        except Exception:
            logger.exception("reminder_loop")
        await asyncio.sleep(900)


# ═══════════════════════════════════════════════════════════
# 7. HAFTALIK / OYLIK TOP-3 MUKOFOT
# ═══════════════════════════════════════════════════════════
def _parse_rewards(key, default):
    vals = [int(x) for x in str(get_setting(key, default)).split(",") if x.strip().isdigit()]
    return vals or [int(x) for x in default.split(",")]


async def award_period(kind, label, start, end, rewards):
    rows = await _adb(
        "SELECT rr.referrer_id AS uid, u.first_name, COUNT(*) AS cnt, MIN(rr.paid_at) AS first_at "
        "FROM referral_rewards rr JOIN users u ON u.user_id = rr.referrer_id "
        "WHERE rr.status='paid' AND rr.paid_at >= %s AND rr.paid_at < %s AND u.is_banned=0 "
        "GROUP BY rr.referrer_id, u.first_name ORDER BY cnt DESC, first_at ASC LIMIT %s",
        (start.isoformat(), end.isoformat(), len(rewards)), fetchall=True) or []
    lines = []
    for rank, (r, amount) in enumerate(zip(rows, rewards), 1):
        ins = await _adb("INSERT INTO period_rewards (period, rank, user_id, amount, created_at) "
                         "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING rank",
                         (label, rank, r["uid"], amount, now_uz().isoformat()), fetch=True)
        if not ins:
            continue
        new = await asyncio.to_thread(add_stars, r["uid"], amount)
        audit(0, f"{kind}_reward", r["uid"], amount, f"{label} #{rank}")
        lang = get_user_lang(r["uid"])
        try:
            await bot.send_message(
                r["uid"], T(lang, "period_reward", kind=T(lang, f"kind_{kind}"), rank=rank, n=amount), parse_mode="HTML")
        except Exception:
            pass
        if new is not None:
            await check_level_up(r["uid"], new - amount, new)
        medal = ("🥇", "🥈", "🥉")[rank - 1] if rank <= 3 else f"{rank}."
        lines.append(f"{medal} {esc(r['first_name'] or 'User')} — {r['cnt']} · +{amount} ⭐")
    if lines:
        title = "🏅 <b>HAFTALIK TOP</b>" if kind == "week" else "🏅 <b>OYLIK TOP</b>"
        text = f"{title}\n{DIV}\n" + "\n".join(lines)
        channel = get_setting("gift_channel", "")
        if channel:
            try:
                await bot.send_message(channel, text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"TOP kanalga yuborilmadi: {e}")
        await notify_admins(text)


async def period_loop():
    while True:
        try:
            now = now_uz()
            mon = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            ws = mon - timedelta(days=7)
            wlabel = f"W{ws:%G-%V}"
            if now >= mon + timedelta(minutes=5) and get_setting("last_weekly") != wlabel:
                await award_period("week", wlabel, ws, mon, _parse_rewards("weekly_rewards", "10,5,3"))
                set_setting("last_weekly", wlabel)

            first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ms = (first - timedelta(days=1)).replace(day=1)
            mlabel = f"M{ms:%Y-%m}"
            if now >= first + timedelta(minutes=10) and get_setting("last_monthly") != mlabel:
                await award_period("month", mlabel, ms, first, _parse_rewards("monthly_rewards", "50,25,10"))
                set_setting("last_monthly", mlabel)
        except Exception:
            logger.exception("period_loop")
        await asyncio.sleep(600)


# ═══════════════════════════════════════════════════════════
# 8 (davomi). KO'P TILLI PROFIL / STATISTIKA / KONKURS / VAZIFALAR
#    Eski cb_profile, cb_stats, cb_contest, cb_tasks ni TO'LIQ ALMASHTIRING.
# ═══════════════════════════════════════════════════════════
def _profile_data(uid, user):
    refs = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    wk = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s",
                 (uid, week_ago), fetch=True)
    rk = db_exec("SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0",
                 (user["stars"],), fetch=True)
    return (refs["c"] if refs else 0, wk["c"] if wk else 0, rk["rank"] if rk else "—", total_donated(uid))


def _level_block(lang, stars):
    lvl = get_user_level(stars)
    nxt = _next_level(stars)
    bar, pct = progress_bar(stars, lvl.get("min_stars", 0), lvl.get("max_stars", 10))
    if nxt:
        nxt_text = f"{nxt.get('emoji', '')} {nxt.get('name', '')} · {format_number(nxt['min_stars'] - stars)} ⭐"
    else:
        nxt_text = T(lang, "lbl_maxlvl")
    return (f"{lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n{bar}  {pct}%\n"
            f"⬆️ {T(lang, 'lbl_next')}: {nxt_text}")


async def _edit_or_send(cb, text, kb):
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


def _nav_kb(lang, refresh=None):
    b = InlineKeyboardBuilder()
    if refresh:
        b.button(text=T(lang, "btn_refresh"), callback_data=refresh)
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    return b.as_markup()


@dp.callback_query(F.data == "m_profile")
async def cb_profile(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    refs, _wk, rank, donated = _profile_data(uid, user)
    uname = f"@{user['username']}" if user["username"] else "—"
    unit = T(lang, "lbl_unit")
    text = (
        f"{box_title(T(lang, 'pf_title'))}\n"
        f"<b>{user['first_name'] or 'N/A'}</b> · {uname}\n<code>{uid}</code>\n\n"
        f"{_level_block(lang, user['stars'])}\n\n{DIV}\n"
        f"{kv('⭐', T(lang, 'lbl_stars'), format_number(user['stars']))}\n"
        f"{kv('👥', T(lang, 'lbl_refs'), format_number(refs) + ' ' + unit)}\n"
        f"{kv('🏆', T(lang, 'lbl_rank'), '#' + format_number(rank))}\n"
        f"{kv('💝', T(lang, 'lbl_donate'), format_number(donated) + ' ⭐')}\n\n{DIV}\n"
        f"{'✅' if user['is_verified'] else '❌'} {T(lang, 'lbl_verified')}   "
        f"📅 {(user['joined_at'] or '—')[:10]}"
    )
    await _edit_or_send(cb, text, _nav_kb(lang, "m_profile"))


@dp.callback_query(F.data == "m_stats")
async def cb_stats(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    user = get_user(uid)
    if not user:
        await cb.answer(T(lang, "start_first"), show_alert=True)
        return
    refs, wk, rank, donated = _profile_data(uid, user)
    lvl = get_user_level(user["stars"])
    unit = T(lang, "lbl_unit")
    top = lvl.get("max_stars", 0)
    text = (
        f"{box_title(T(lang, 'st_title'))}\n<b>{user['first_name']}</b>\n\n"
        f"{_level_block(lang, user['stars'])}\n"
        f"<b>{format_number(user['stars'])}</b> / {format_number(top) if top < 999_999_999 else '∞'} ⭐\n\n{DIV}\n"
        f"{kv('⭐', T(lang, 'lbl_stars'), format_number(user['stars']))}\n"
        f"{kv('💝', T(lang, 'lbl_donate'), format_number(donated) + ' ⭐')}\n"
        f"{kv('👥', T(lang, 'lbl_refs'), format_number(refs) + ' ' + unit)}\n"
        f"{kv('📈', T(lang, 'lbl_week'), '+' + format_number(wk))}\n"
        f"{kv('🏆', T(lang, 'lbl_rank'), '#' + format_number(rank))}"
    )
    await _edit_or_send(cb, text, _nav_kb(lang, "m_stats"))


@dp.callback_query(F.data == "m_contest")
async def cb_contest(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    contest = get_active_contest()
    if not contest:
        await _edit_or_send(cb, T(lang, "contest_none"), _nav_kb(lang))
        return
    lb = get_contest_leaderboard(contest, uid, limit=10)
    try:
        diff = (datetime.fromisoformat(contest["end_at"]) - now_uz()).total_seconds()
    except Exception:
        diff = 0
    diff = max(diff, 0)
    unit = T(lang, "lbl_unit")
    text = (
        f"{box_title('🏆 ' + T(lang, 'contest_title'))}\n"
        f"🎯 <b>{esc(contest['title'])}</b>\n<i>{esc(contest['description'])}</i>\n\n"
        f"🎁 <b>{T(lang, 'ct_prize')}:</b> {esc(contest['reward_emoji'])} <b>{esc(contest['reward_name'])}</b>\n"
        f"⏰ {T(lang, 'ct_left', d=int(diff // 86400), h=int((diff % 86400) // 3600))}\n\n"
        f"{DIV}\n<b>{T(lang, 'ct_board')}</b>\n\n"
    )
    if lb["leaders"]:
        for i, l in enumerate(lb["leaders"], 1):
            medal = ("🥇", "🥈", "🥉")[i - 1] if i <= 3 else f"<b>{i}.</b>"
            tag = f"  ⬅️ <b>{T(lang, 'ct_me')}</b>" if l["is_me"] else ""
            text += f"{medal} {esc(l['name'])} — <b>{format_number(l['count'])}</b> {unit}{tag}\n"
    else:
        text += T(lang, "ct_nobody") + "\n"
    text += f"\n{DIV}\n👤 <b>{T(lang, 'ct_me')}:</b> #{format_number(lb['me']['rank'])} — <b>{format_number(lb['me']['count'])}</b> {unit}"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "share"), callback_data="m_reflink")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    await _edit_or_send(cb, text, b.as_markup())


@dp.callback_query(F.data == "m_tasks")
async def cb_tasks(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    await refresh_task_status(uid)          # fixes_patch.py dan
    tasks = get_user_tasks(uid)
    text = f"{box_title('📌 ' + T(lang, 'tasks_title'))}\n\n"
    b = InlineKeyboardBuilder()
    if tasks:
        for t in tasks:
            if t["claimed"]:
                status = f"✅ {t['reward']} ⭐ {T(lang, 'task_claimed')}"
            elif t["claimable"]:
                status = f"🎁 <b>{T(lang, 'task_ready')}</b>"
                b.button(text=f"🎁 {t['title'][:25]} → +{t['reward']}", callback_data=f"claimtask_{t['id']}")
            elif t["done"]:
                status = f"✅ {T(lang, 'task_done')}"
            else:
                status = f"⏳ <i>{T(lang, 'task_todo')}</i>"
            text += f"{esc(t['emoji'])} <b>{esc(t['title'])}</b>\n   +{t['reward']} ⭐ — {status}\n\n"
    else:
        text += T(lang, "task_none") + "\n"
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    await _edit_or_send(cb, text, b.as_markup())


# ═══════════════════════════════════════════════════════════
# main() — YAKUNIY TARTIB
# ═══════════════════════════════════════════════════════════
#     init_db()
#     init_extra_db()                       # <-- YANGI
#     await init_userbot()
#     dp.message.outer_middleware(SubGate())          # <-- YANGI
#     dp.callback_query.outer_middleware(SubGate())   # <-- YANGI
#     security.setup(...)
#     ...
#     await bot.delete_webhook(drop_pending_updates=True)
#     bg = [asyncio.create_task(f()) for f in (
#         contest_watcher, keepalive, backup_loop,                        # fixes_patch.py
#         release_loop, sub_recheck_loop, reminder_loop,                  # features_patch.py
#         period_loop, weekly_report_loop)]
#     try:
#         await dp.start_polling(bot)
#     finally:
#         for t in bg:
#             t.cancel()
#         if tg_client:
#             await tg_client.disconnect()
