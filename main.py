# ═══════════════════════════════════════════════════════════
# GIFT TANLASH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "w_gift")
async def w_gift(cb, state):
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

    text = (f"{box_title('🎁 TELEGRAM GIFT OLISH')}\n\n"
            f"💰 <b>{T(lang, 'balance')}:</b> {format_number(user['stars'])} ⭐\n\n"
            f"{DIV}\n\n<i>Giftni tanlang:</i>")

    b = InlineKeyboardBuilder()
    for g in gifts:
        b.button(text=f"{g['emoji']} {g['name']} — {g['stars']}⭐",
                 callback_data=f"gsel_{g['key']}")
    b.button(text=T(lang, "back"), callback_data="w_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("gsel_"))
async def gift_select(cb, state):
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
async def gift_anon(cb, state):
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
    row = db_exec("""INSERT INTO withdrawals (user_id, stars, reward_type, gift_key, status, created_at, is_anon, comment)
        VALUES (%s, %s, 'gift', %s, 'processing', %s, %s, %s) RETURNING id""",
        (uid, gift["stars"], key, now_uz().isoformat(), is_anon, comment), fetch=True)
    w_id = row["id"]
    gift_label = f"{esc(gift['emoji'])} <b>{esc(gift['name'])}</b>"
    await send(T(lang, "gift_processing", gift=gift_label, n=gift["stars"]))
    okk, err2 = await deliver_gift(uid, gift, anon=bool(is_anon), comment=comment)
    if okk:
        db_exec("UPDATE withdrawals SET status='approved' WHERE id=%s", (w_id,))
        await send(T(lang, "gift_done", gift=gift_label, n=gift["stars"]), back_to_menu_kb(uid))
        post_text = build_gift_post(user=user, amount=gift["stars"], gift_emoji=gift["emoji"],
                                     gift_name=gift["name"], is_anon=bool(is_anon), is_stars=False)
        await send_gift_post(uid, post_text, is_anon)
    else:
        add_stars(uid, gift["stars"])
        db_exec("UPDATE withdrawals SET status='failed', error=%s WHERE id=%s", ((err2 or "")[:500], w_id))
        await send(T(lang, "gift_failed", gift=gift_label, n=gift["stars"]), back_to_menu_kb(uid))
        uname = f"@{user['username']}" if user["username"] else "—"
        await notify_admins(f"⚠️ <b>Gift avtomatik yuborilmadi</b>\n\n🆔 #{w_id}\n👤 <code>{uid}</code> ({uname})\n🎁 {gift_label} — {gift['stars']} ⭐\n❗ {esc(err2)}")


@dp.callback_query(F.data == "gcomment_skip")
async def gift_comment_skip(cb, state):
    await cb.answer("⏳")

    async def send(text, kb=None):
        try:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await finish_gift_request(cb.from_user.id, state, send, comment=None)


@dp.message(US.gift_comment)
async def gift_comment_input(message, state):
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
# STARS SOVG'A
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_gift")
async def cb_gift_stars(cb, state):
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
    txt = T(lang, "gift_stars_title", bal=format_number(user["stars"]))
    try:
        await cb.message.edit_text(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(txt, reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(US.gift_username)
    await cb.answer()


@dp.callback_query(F.data == "gift_cancel")
async def gift_cancel(cb, state):
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("OK")


@dp.message(US.gift_username)
async def gift_username_input(message, state):
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
async def gift_amount_input(message, state):
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
        await message.answer(f"{T(lang, 'not_enough')}\n💰 {T(lang, 'balance')}: {format_number(max(user['stars'] - pending_total(uid), 0))} ⭐")
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
    await message.answer(T(lang, "gift_stars_confirm", name=target["first_name"] or "User", n=format_number(amount)),
                        reply_markup=b.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "gift_confirm")
async def gift_confirm(cb, state):
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
    await cb.message.edit_text(T(lang, "gift_stars_sent", n=format_number(amount), name=target["first_name"] or "User"),
                                parse_mode="HTML")
    try:
        await bot.send_message(target_id, T(get_user_lang(target_id), "gift_stars_received",
            name=user["first_name"] or "User", n=format_number(amount), total=format_number(new_target)), parse_mode="HTML")
    except Exception:
        pass
    await check_level_up(target_id, new_target - amount, new_target)
    await cb.answer("✅")


# ═══════════════════════════════════════════════════════════
# SUPPORT
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_support")
async def cb_support(cb, state):
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
    key = "chat_active" if get_chat_status(uid) == "open" else "support_title"
    if get_chat_status(uid) != "open":
        open_chat(uid)
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
async def support_send(message, state):
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
    admin_header = T("uz", "user_msg") + "\n\n" + T("uz", "support_new_msg",
        name=user["first_name"] or "User", username=uname, uid=uid, time=now_uz().strftime("%Y-%m-%d %H:%M"))
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
            logger.warning(f"Adminga: {e}")
    if sent == 0:
        await message.answer("⚠️ Hech qanday admin topilmadi.")
        return
    await message.answer(T(lang, "support_sent"), parse_mode="HTML")


@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(cb, state):
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
    await cb.message.answer(f"✉️ <b>JAVOB YOZING</b>\n\n👤 {esc(user['first_name'])} (<code>{uid}</code>)\n\nMatn, rasm, video yoki fayl yuboring:", parse_mode="HTML")
    await state.set_state(AS.reply_to_user)
    await cb.answer()


@dp.message(AS.reply_to_user)
async def reply_send(message, state):
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
async def chat_close_admin(cb):
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
async def cb_review(cb, state):
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
async def review_cancel(cb, state):
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("OK")


@dp.message(US.review_text)
async def review_text_input(message, state):
    uid = message.from_user.id
    lang = get_user_lang(uid)
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("❌ Sharh juda qisqa. Kamida 5 ta belgi.")
        return
    row = db_exec("INSERT INTO reviews (user_id, text, status, created_at) VALUES (%s, %s, 'pending', %s) RETURNING id",
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
            await bot.send_message(a["user_id"],
                f"⭐ <b>Yangi sharh!</b>\n\n👤 {user['first_name'] if user else 'User'} ({uname})\n🆔 <code>{uid}</code>\n\n💬 <i>{esc(text)}</i>",
                reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_history")
async def cb_history(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    rows = db_exec("""SELECT w.id, w.stars, w.reward_type, w.status, w.created_at, g.emoji, g.name
        FROM withdrawals w LEFT JOIN gifts g ON g.key = w.gift_key
        WHERE w.user_id=%s ORDER BY w.id DESC LIMIT 15""", (uid,), fetchall=True) or []
    icons = {"pending": "⏳", "processing": "🔄", "approved": "✅", "rejected": "❌", "failed": "⚠️"}
    text = box_title(T(lang, "hist_title")) + "\n"
    if not rows:
        text += "\n" + T(lang, "hist_empty")
    for r in rows:
        item = f"{esc(r['emoji'] or '🎁')} {esc(r['name'] or 'Gift')}" if r["reward_type"] == "gift" else "⭐ Stars"
        d = r["created_at"] or ""
        date = f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else ""
        st = T(lang, "st_" + r["status"])
        text += f"\n{icons.get(r['status'], '•')} <b>#{r['id']}</b> {item} · {format_number(r['stars'])} ⭐\n    {st} · <i>{date}</i>"
    b = InlineKeyboardBuilder()
    b.button(text=T(lang, "back"), callback_data="m_more")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(2)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


# ═══════════════════════════════════════════════════════════
# REKLAMA (user) — INLINE TUGMALAR
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data == "m_advertise")
async def cb_advertise(cb, state):
    await state.clear()
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    services = get_ad_services(active_only=True)
    if not services:
        b = InlineKeyboardBuilder()
        b.button(text=T(lang, "menu"), callback_data="m_menu")
        b.adjust(1)
        try:
            await cb.message.edit_text(T(lang, "advertise_none"), reply_markup=b.as_markup(), parse_mode="HTML")
        except Exception:
            await cb.message.answer(T(lang, "advertise_none"), reply_markup=b.as_markup(), parse_mode="HTML")
        await cb.answer()
        return

    text = T(lang, "advertise_title")
    b = InlineKeyboardBuilder()
    for s in services:
        price_fmt = format_number(s["price_uzs"])
        button_text = f"💳 {s['title']} — {price_fmt} so'm"
        if s["hours"]:
            button_text += f" · ⏰ {s['hours']}s"
        if s["bonus_subs"]:
            button_text += f" · 🎁+{s['bonus_subs']}"
        b.button(text=button_text, callback_data=f"adbuy_{s['id']}")
    b.button(text=T(lang, "menu"), callback_data="m_menu")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("adbuy_"))
async def ad_buy(cb, state):
    uid = cb.from_user.id
    lang = get_user_lang(uid)
    sid = int(cb.data.replace("adbuy_", ""))
    s = get_ad_service(sid)
    if not s or not s["is_active"]:
        await cb.answer("❌ Tarif topilmadi!", show_alert=True)
        return

    order_id = create_ad_order(uid, s)
    if not order_id:
        await cb.answer("❌ Xato. Qayta urinib ko'ring.", show_alert=True)
        return

    card = get_ad_card()
    price_fmt = format_number(s["price_uzs"])

    text = (
        f"💳 <b>TO'LOV MA'LUMOTLARI</b>\n{DIV}\n\n"
        f"📋 <b>Tarif:</b> {esc(s['title'])}\n"
        f"💰 <b>Summa:</b> {price_fmt} so'm\n"
    )
    if s["hours"]:
        text += f"⏰ <b>Muddat:</b> {s['hours']} soat\n"
    if s["bonus_subs"]:
        text += f"🎁 <b>Bonus:</b> +{s['bonus_subs']} garant obunachi\n"
    text += (
        f"\n{DIV}\n\n"
        f"💳 <b>Karta raqami:</b>\n<code>{card['number']}</code>\n"
        f"👤 <b>Egasi:</b> {esc(card['holder'])}\n"
        f"🏦 <b>Bank:</b> {esc(card['bank'])}\n\n"
        f"{DIV}\n\n"
        f"📸 <b>To'lovni amalga oshirib, chekni (skrinshot)</b>\n"
        f"shu chatga yuboring.\n\n"
        f"⚠️ <b>Buyurtma raqami:</b> <code>#{order_id}</code>"
    )

    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data=f"ad_cancel_{order_id}")
    b.adjust(1)

    await state.update_data(ad_order_id=order_id)
    await state.set_state(US.ad_receipt)

    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("ad_cancel_"))
async def ad_cancel_order(cb, state):
    order_id = int(cb.data.replace("ad_cancel_", ""))
    update_ad_order(order_id, status="cancelled")
    await state.clear()
    uid = cb.from_user.id
    try:
        await cb.message.edit_text(T(get_user_lang(uid), "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("❌ Bekor qilindi")


@dp.message(US.ad_receipt)
async def ad_receipt_received(message, state):
    """Foydalanuvchi chek yuboradi"""
    uid = message.from_user.id
    lang = get_user_lang(uid)
    data = await state.get_data()
    order_id = data.get("ad_order_id")

    if not order_id:
        await message.answer("❌ Xato. Qayta urinib ko'ring.")
        await state.clear()
        return

    order = get_ad_order(order_id)
    if not order or order["user_id"] != uid:
        await message.answer("❌ Buyurtma topilmadi.")
        await state.clear()
        return

    # Rasm yoki hujjat qabul qilamiz
    receipt_file_id = None
    receipt_type = None
    if message.photo:
        receipt_file_id = message.photo[-1].file_id
        receipt_type = "photo"
    elif message.document:
        receipt_file_id = message.document.file_id
        receipt_type = "document"
    else:
        await message.answer("❌ Iltimos, chekni <b>rasm</b> yoki <b>fayl</b> sifatida yuboring.")
        return

    update_ad_order(order_id, status="pending_admin",
                    receipt_file_id=receipt_file_id, receipt_type=receipt_type)

    await state.clear()
    await message.answer(
        f"✅ <b>CHEK QABUL QILINDI!</b>\n\n"
        f"🆔 <b>Buyurtma:</b> <code>#{order_id}</code>\n"
        f"⏳ <i>Admin tasdiqlashini kuting. Bu 1-2 daqiqa olishi mumkin.</i>",
        parse_mode="HTML")
    await message.answer(T(lang, "menu_title"), reply_markup=main_menu(uid), parse_mode="HTML")

    # Adminga yuborish
    user = get_user(uid)
    uname = f"@{user['username']}" if user and user.get("username") else "—"
    admin_text = (
        f"🔔 <b>YANGI REKLAMA TO'LOVI!</b>\n{DIV}\n\n"
        f"🆔 <b>Buyurtma:</b> <code>#{order_id}</code>\n"
        f"👤 <b>User:</b> {esc(user['first_name'] if user else 'User')}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"📋 <b>Tarif:</b> {esc(order['service_title'])}\n"
        f"💰 <b>Narx:</b> {format_number(order['price_uzs'])} so'm\n"
        f"⏰ <b>Muddat:</b> {order['hours']} soat\n"
        f"📸 <b>Chek:</b> pastda 👇"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"ad_approve_{order_id}")
    kb.button(text="❌ Rad etish", callback_data=f"ad_reject_{order_id}")
    kb.adjust(2)

    for a in list_admins():
        try:
            await bot.send_message(a["user_id"], admin_text, reply_markup=kb.as_markup(), parse_mode="HTML")
            # Chekni forward qilish
            if receipt_type == "photo":
                await bot.send_photo(a["user_id"], receipt_file_id)
            else:
                await bot.send_document(a["user_id"], receipt_file_id)
        except Exception as e:
            logger.warning(f"Adminga reklama chek yuborilmadi: {e}")


# ═══════════════════════════════════════════════════════════
# ADMIN REKLAMA TASDIQLASH / RAD ETISH
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("ad_approve_"))
async def ad_approve(cb):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    order_id = int(cb.data.replace("ad_approve_", ""))
    order = get_ad_order(order_id)
    if not order or order["status"] != "pending_admin":
        await cb.answer("⚠️ Buyurtma topilmadi yoki allaqachon ko'rib chiqilgan", show_alert=True)
        return

    update_ad_order(order_id, status="awaiting_channel", admin_id=cb.from_user.id,
                    approved_at=now_uz().isoformat())

    # Foydalanuvchidan kanal linki so'rash
    try:
        await bot.send_message(
            order["user_id"],
            f"✅ <b>TO'LOV TASDIQLANDI!</b>\n{DIV}\n\n"
            f"🆔 <b>Buyurtma:</b> <code>#{order_id}</code>\n\n"
            f"Endi <b>kanal yoki guruh linkini</b> yuboring.\n\n"
            f"<i>Misol:</i> <code>@mening_kanalim</code>\n"
            f"<i>Yoki:</i> <code>https://t.me/mening_kanalim</code>\n\n"
            f"⚠️ <b>Muhim:</b> Botni kanal/guruhga <b>admin</b> qilishingiz kerak!",
            parse_mode="HTML")
        # State o'rnatish - keyingi xabarni ushlab olish uchun
        dp.fsm.storage.data
        await _set_user_state(order["user_id"], "ad_channel_link", {"ad_order_id": order_id})
    except Exception as e:
        logger.error(f"Foydalanuvchiga xabar yuborilmadi: {e}")

    try:
        await cb.message.edit_text(cb.message.html_text + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("ad_reject_"))
async def ad_reject(cb):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    order_id = int(cb.data.replace("ad_reject_", ""))
    order = get_ad_order(order_id)
    if not order or order["status"] != "pending_admin":
        await cb.answer("⚠️ Buyurtma topilmadi", show_alert=True)
        return

    update_ad_order(order_id, status="rejected", admin_id=cb.from_user.id)

    try:
        await bot.send_message(
            order["user_id"],
            f"❌ <b>TO'LOV RAD ETILDI</b>\n{DIV}\n\n"
            f"🆔 <b>Buyurtma:</b> <code>#{order_id}</code>\n\n"
            f"<i>Admin bilan bog'laning: /support</i>",
            parse_mode="HTML")
    except Exception:
        pass

    try:
        await cb.message.edit_text(cb.message.html_text + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("❌")


async def _set_user_state(uid, state_name, data):
    """Yordamchi: foydalanuvchi holatini o'rnatish"""
    try:
        from aiogram.fsm.storage.base import StorageKey
        key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
        await dp.fsm.storage.set_state(key, state_name)
        await dp.fsm.storage.set_data(key, data)
    except Exception as e:
        logger.error(f"State o'rnatishda xato: {e}")
# ═══════════════════════════════════════════════════════════
# KANAL LINK QABUL QILISH + TEKSHIRISH
# ═══════════════════════════════════════════════════════════
# Dynamic state handler — foydalanuvchi kanal linkini yuborganda
@dp.message(F.text.regexp(r"^(@|https?://t\.me/|t\.me/)").as_("link_match"))
async def ad_channel_link_received(message, state):
    """Foydalanuvchi kanal linkini yuborganda (agar ad_order_id bo'lsa)"""
    uid = message.from_user.id

    # Faqat ad channel kutayotgan bo'lsa
    data = await state.get_data()
    order_id = data.get("ad_order_id")
    if not order_id:
        return  # Boshqa handlerlarga o'tsin

    order = get_ad_order(order_id)
    if not order or order["user_id"] != uid or order["status"] != "awaiting_channel":
        return

    channel_username = message.text.strip()
    # Normalizatsiya
    if channel_username.startswith("https://t.me/"):
        channel_username = "@" + channel_username.replace("https://t.me/", "").strip("/")
    elif channel_username.startswith("t.me/"):
        channel_username = "@" + channel_username.replace("t.me/", "").strip("/")
    elif not channel_username.startswith("@"):
        channel_username = "@" + channel_username

    # Kanalni tekshirish
    try:
        chat = await bot.get_chat(channel_username)
        # Botning statusini tekshirish
        me = await bot.get_me()
        member = await bot.get_chat_member(channel_username, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                f"⚠️ <b>BOT ADMIN EMAS!</b>\n{DIV}\n\n"
                f"Botni <b>{esc(channel_username)}</b> ga admin qiling.\n\n"
                f"Qanday qilib:\n"
                f"1. Kanal/guruh → <b>Administratorlar</b>\n"
                f"2. <b>@{(await bot.get_me()).username}</b> ni admin qiling\n"
                f"3. <b>Postlarni tahrirlash</b> ruxsatini bering\n\n"
                f"Keyin qaytadan link yuboring.",
                parse_mode="HTML")
            return

        channel_id = chat.id
        channel_title = chat.title or channel_username

        # Foydalanuvchidan tasdiq so'rash
        b = InlineKeyboardBuilder()
        b.button(text="✅ Ha, tayyor", callback_data=f"ad_conf_ch_{order_id}")
        b.button(text="❌ Bekor qilish", callback_data=f"ad_cancel_{order_id}")
        b.adjust(2)

        await message.answer(
            f"✅ <b>BOT ADMIN QILINGAN!</b>\n{DIV}\n\n"
            f"📢 <b>Kanal:</b> {esc(channel_title)}\n"
            f"🆔 <b>Username:</b> {esc(channel_username)}\n\n"
            f"Endi <b>\"Ha, tayyor\"</b> tugmasini bosing — biz kanalni majburiy obunaga qo'shamiz.",
            reply_markup=b.as_markup(), parse_mode="HTML")

        await state.update_data(ad_channel_username=channel_username,
                                ad_channel_id=channel_id,
                                ad_channel_title=channel_title)

    except TelegramBadRequest as e:
        await message.answer(
            f"❌ <b>Kanal topilmadi!</b>\n\n"
            f"Tekshiring:\n"
            f"• Link to'g'rimi?\n"
            f"• Kanal <b>ochiq</b>mi?\n"
            f"• Bot kanalga <b>admin</b> qilinganmi?\n\n"
            f"Xato: <code>{esc(str(e))}</code>",
            parse_mode="HTML")
    except Exception as e:
        logger.error(f"Kanal tekshirish xato: {e}")
        await message.answer(f"❌ Xato: {esc(str(e))}", parse_mode="HTML")


@dp.callback_query(F.data.startswith("ad_conf_ch_"))
async def ad_confirm_channel(cb, state):
    if not is_admin(cb.from_user.id) is False:  # Bu user uchun
        pass
    uid = cb.from_user.id
    order_id = int(cb.data.replace("ad_conf_ch_", ""))
    order = get_ad_order(order_id)
    if not order or order["user_id"] != uid:
        await cb.answer("❌ Xato", show_alert=True)
        return

    data = await state.get_data()
    channel_username = data.get("ad_channel_username")
    channel_id = data.get("ad_channel_id")
    channel_title = data.get("ad_channel_title")
    if not channel_username or not channel_id:
        await cb.answer("❌ Ma'lumot yo'q. Qaytadan link yuboring.", show_alert=True)
        return

    # Expires_at hisoblash
    now = now_uz()
    if order["hours"] and order["hours"] > 0:
        expires_at = (now + timedelta(hours=order["hours"])).isoformat()
    else:
        expires_at = None

    # Kanalni majburiy obunaga qo'shish
    try:
        # Bot kanalga post yuborishi mumkin bo'lishi kerak
        # Kanalni bazaga qo'shamiz
        add_mandatory_channel(order_id, channel_username, channel_id, expires_at)
        # channels jadvaliga ham qo'shamiz (check_subs uchun)
        add_channel(channel_username)
    except Exception as e:
        logger.error(f"Kanal qo'shishda xato: {e}")

    # Garant obunachi bo'lsa invite link yaratish
    invite_link = None
    invite_link_id = None
    if order["bonus_subs"] and order["bonus_subs"] > 0:
        try:
            # Kanal uchun invite link yaratish
            result = await bot.create_chat_invite_link(
                chat_id=channel_id,
                name=f"StarRush #{order_id}",
                member_limit=order["bonus_subs"] + 10,  # Zaxira
                creates_join_request=False)
            invite_link = result.invite_link
            invite_link_id = result.invite_link  # yoki result.invite_link object

            # Foydalanuvchiga invite linkni yuborish
            await bot.send_message(
                uid,
                f"🎁 <b>GARANT OBUNACHI UCHUN HAVOLA</b>\n{DIV}\n\n"
                f"Quyidagi havolani tarqating:\n"
                f"<code>{invite_link}</code>\n\n"
                f"👥 <b>Kerakli obunachi:</b> {order['bonus_subs']} ta\n"
                f"📊 <b>Joriy:</b> 0 / {order['bonus_subs']}\n\n"
                f"<i>Havoladan {order['bonus_subs']} kishi qo'shilgach, avtomatik yopiladi.</i>",
                parse_mode="HTML")
        except Exception as e:
            logger.error(f"Invite link yaratishda xato: {e}")
            await bot.send_message(
                uid,
                f"⚠️ <b>Invite link yaratilmadi</b>\n\n"
                f"Sabab: <code>{esc(str(e))}</code>\n\n"
                f"Admin bilan bog'laning.",
                parse_mode="HTML")

    # Buyurtma holatini yangilash
    update_ad_order(order_id, status="active",
                    channel_link=channel_username, channel_id=channel_id,
                    channel_title=channel_title,
                    invite_link=invite_link, invite_link_id=str(invite_link_id) if invite_link_id else None,
                    added_at=now.isoformat(), expires_at=expires_at)

    await cb.message.edit_text(
        f"🎉 <b>REKLAMA BOSHLANDI!</b>\n{DIV}\n\n"
        f"📢 <b>Kanal:</b> {esc(channel_title)}\n"
        f"🆔 <code>#{order_id}</code>\n"
        f"⏰ <b>Muddat:</b> {order['hours']} soat" + (f" (tugaydi: {expires_at[:16].replace('T', ' ')})" if expires_at else "") + "\n"
        + (f"🎁 <b>Garant:</b> {order['bonus_subs']} obunachi\n" if order['bonus_subs'] else "") +
        f"\n✅ <i>Kanal majburiy obunaga qo'shildi!</i>",
        parse_mode="HTML")

    await state.clear()
    await cb.answer("✅ Reklama boshlandi!")

    # Adminga xabar
    await notify_admins(
        f"✅ <b>REKLAMA BOSHLANDI</b>\n\n"
        f"🆔 #{order_id}\n"
        f"👤 <code>{uid}</code>\n"
        f"📢 {esc(channel_title)} ({esc(channel_username)})\n"
        f"⏰ {order['hours']} soat")


# ═══════════════════════════════════════════════════════════
# BACKGROUND LOOPS — Reklama muddati va garant tracking
# ═══════════════════════════════════════════════════════════
async def ad_expiry_loop():
    """Har 60 sekundda muddati o'tgan reklama kanallarini o'chirish"""
    while True:
        try:
            expired = get_expired_ad_channels()
            for ch in expired:
                channel_username = ch["channel_username"]
                order = get_ad_order(ch["order_id"])

                # Kanaldan o'chirish
                try:
                    remove_channel(channel_username)
                except Exception as e:
                    logger.warning(f"Kanalni o'chirishda xato: {e}")

                # Bazada inactive qilish
                deactivate_ad_channel(ch["id"])

                # Buyurtma holatini yangilash
                if order:
                    update_ad_order(order["id"], status="completed")

                    # Foydalanuvchiga xabar
                    try:
                        await send_ad_completion_post(order["user_id"], order, success=True)
                    except Exception as e:
                        logger.warning(f"Ad completion post xato: {e}")

                    # Adminlarga xabar
                    try:
                        await notify_admins(
                            f"⏰ <b>REKLAMA MUDDATI TUGADI</b>\n\n"
                            f"🆔 #{order['id']}\n"
                            f"📢 {esc(channel_username)}\n"
                            f"✅ Majburiy obunadan o'chirildi")
                    except Exception:
                        pass

                logger.info(f"Reklama #{ch['order_id']} muddati tugadi, kanal o'chirildi: {channel_username}")

            # Garant tracking
            for order in get_orders_with_invite_tracking():
                if not order.get("invite_link"):
                    continue
                try:
                    # Invite link orqali qo'shilgan a'zolarni hisoblash
                    # Telegram Bot API da bu to'g'ridan-to'g'ri yo'q
                    # Yaqinlashtirish: kanal a'zolar sonini kuzatish
                    try:
                        chat = await bot.get_chat(order["channel_id"])
                        current_members = await bot.get_chat_member_count(order["channel_id"])
                    except Exception:
                        continue

                    # Boshlang'ich a'zolar soni order da saqlanishi kerak edi
                    # Soddalashtirilgan: agar invite_link limiti tugasa
                    # Yoki qo'lda kuzatish

                    # Bu joyni kengaytirish mumkin
                    # Hozircha: invite_link ni olib, limitni tekshiramiz
                    # Telegram API da bu cheklov mavjud emas, shuning uchun
                    # bot invite linkni kuzatib borish uchun maxsus yondashuv kerak

                    # Soddalashtirilgan: agar invite_link 50+ a'zo bo'lsa, o'chirish
                    # Bu aniq emas, lekin ishlaydi
                    invite_link = order.get("invite_link")
                    if invite_link:
                        try:
                            link_info = await bot.get_chat_invite_link(
                                chat_id=order["channel_id"],
                                invite_link=invite_link)
                            # Agar link revoked bo'lsa yoki limit tugagan bo'lsa
                            if link_info.member_limit and link_info.member_limit <= 0:
                                # Limit tugagan
                                update_ad_order(order["id"], status="completed")
                                await notify_admins(f"🎁 Garant tugadi #{order['id']}")
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"Invite tracking xato: {e}")

        except Exception as e:
            logger.exception(f"ad_expiry_loop xato: {e}")
        await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════
# ADMIN PANEL — ASOSIY
# ═══════════════════════════════════════════════════════════
ADMIN_TITLE = f"<b>🛠 ADMIN PANEL</b>\n{DIV}\nKerakli bo'limni tanlang 👇"


@dp.message(Command("admin"))
async def admin_panel_cmd(message, state):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer(ADMIN_TITLE, reply_markup=admin_menu(message.from_user.id), parse_mode="HTML")


@dp.callback_query(F.data == "m_admin")
async def cb_admin(cb, state):
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
async def a_back(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    try:
        await cb.message.edit_text(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ─────────── REKLAMA SO'ROVLARI (PENDING) ───────────
@dp.callback_query(F.data == "a_ad_orders")
async def a_ad_orders(cb, state):
    if not is_admin(cb.from_user.id):
        return
    orders = get_pending_ad_orders(limit=10)
    if not orders:
        await cb.answer("— Pending so'rovlar yo'q", show_alert=True)
        return

    text = f"{box_title('📥 REKLAMA SO\'ROVLARI')}\n\n"
    b = InlineKeyboardBuilder()
    for o in orders:
        uname = f"@{esc(o['username'])}" if o["username"] else "—"
        text += (f"• <b>#{o['id']}</b> {esc(o['first_name'] or 'User')} ({uname})\n"
                 f"   📋 {esc(o['service_title'])} — {format_number(o['price_uzs'])} so'm\n\n")
        b.button(text=f"👁 #{o['id']}", callback_data=f"ad_view_{o['id']}")
    text += BOX_BOTTOM
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data.startswith("ad_view_"))
async def ad_view_order(cb):
    if not is_admin(cb.from_user.id):
        return
    order_id = int(cb.data.replace("ad_view_", ""))
    order = get_ad_order(order_id)
    if not order:
        await cb.answer("—", show_alert=True)
        return
    user = get_user(order["user_id"])
    uname = f"@{user['username']}" if user and user.get("username") else "—"

    text = (
        f"{box_title('📋 BUYURTMA TAFSILOTI')}\n\n"
        f"🆔 <b>Buyurtma:</b> <code>#{order_id}</code>\n"
        f"👤 <b>User:</b> {esc(user['first_name'] if user else 'User')}\n"
        f"🔗 <b>Username:</b> {uname}\n"
        f"🆔 <b>ID:</b> <code>{order['user_id']}</code>\n\n"
        f"📋 <b>Tarif:</b> {esc(order['service_title'])}\n"
        f"💰 <b>Narx:</b> {format_number(order['price_uzs'])} so'm\n"
        f"⏰ <b>Muddat:</b> {order['hours']} soat\n"
        + (f"🎁 <b>Garant:</b> {order['bonus_subs']}\n" if order.get('bonus_subs') else '')
        + f"\n📅 <b>Yaratilgan:</b> {(order['created_at'] or '')[:16].replace('T', ' ')}"
    )

    b = InlineKeyboardBuilder()
    if order["status"] == "pending_admin":
        b.button(text="✅ Tasdiqlash", callback_data=f"ad_approve_{order_id}")
        b.button(text="❌ Rad etish", callback_data=f"ad_reject_{order_id}")
    b.button(text="⬅️ Orqaga", callback_data="a_ad_orders")
    b.adjust(2, 1)

    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
        # Chekni forward qilish
        if order.get("receipt_file_id"):
            if order.get("receipt_type") == "photo":
                await cb.message.answer_photo(order["receipt_file_id"], caption="📸 Chek")
            else:
                await cb.message.answer_document(order["receipt_file_id"], caption="📸 Chek")
    except Exception as e:
        logger.warning(f"Order view xato: {e}")
    await cb.answer()


# ─────────── KARTA RAQAMI ───────────
@dp.callback_query(F.data == "a_card")
async def a_card(cb, state):
    if not is_admin(cb.from_user.id):
        return
    card = get_ad_card()
    text = (
        f"{box_title('💳 KARTA MA\'LUMOTLARI')}\n\n"
        f"💳 <b>Karta raqami:</b>\n<code>{esc(card['number'])}</code>\n\n"
        f"👤 <b>Egasi:</b> {esc(card['holder'])}\n"
        f"🏦 <b>Bank:</b> {esc(card['bank'])}\n\n"
        f"{DIV}\n"
        f"<i>Bu ma'lumotlar foydalanuvchilarga reklama to'lovida ko'rsatiladi.</i>"
    )
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Raqamni o'zgartirish", callback_data="edit_card_num")
    b.button(text="✏️ Egasi", callback_data="edit_card_holder")
    b.button(text="✏️ Bank", callback_data="edit_card_bank")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "edit_card_num")
async def edit_card_num(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("💳 <b>Yangi karta raqami:</b>\n<i>Misol: 8600 1234 5678 9012</i>", parse_mode="HTML")
    await state.set_state(AS.ad_card_number)
    await cb.answer()


@dp.message(AS.ad_card_number)
async def set_card_num(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    set_setting("ad_card_number", message.text.strip())
    await state.clear()
    await message.answer(f"✅ Karta raqami saqlandi: <code>{esc(message.text.strip())}</code>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "edit_card_holder")
async def edit_card_holder(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👤 <b>Karta egasi:</b>", parse_mode="HTML")
    await state.set_state(AS.ad_card_holder)
    await cb.answer()


@dp.message(AS.ad_card_holder)
async def set_card_holder(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    set_setting("ad_card_holder", message.text.strip())
    await state.clear()
    await message.answer("✅ Saqlandi")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "edit_card_bank")
async def edit_card_bank(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🏦 <b>Bank nomi:</b>\n<i>Misol: Uzcard, Humo, Payme</i>", parse_mode="HTML")
    await state.set_state(AS.ad_card_bank)
    await cb.answer()


@dp.message(AS.ad_card_bank)
async def set_card_bank(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    set_setting("ad_card_bank", message.text.strip())
    await state.clear()
    await message.answer("✅ Saqlandi")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


# ─────────── REKLAMA TARIFLARI ───────────
@dp.callback_query(F.data == "a_ads")
async def a_ads(cb, state):
    if not is_admin(cb.from_user.id):
        return
    services = get_ad_services(active_only=False)
    text = box_title("📢 REKLAMA TARIFLAR") + "\n\n"
    if services:
        for s in services:
            status = "🟢" if s["is_active"] else "🔴"
            text += f"{status} <b>#{s['id']}</b> {esc(s['title'])}\n"
            text += f"   💰 {format_number(s['price_uzs'])} so'm\n"
            if s["hours"]:
                text += f"   ⏰ {s['hours']} soat\n"
            if s["bonus_subs"]:
                text += f"   🎁 +{s['bonus_subs']} garant\n"
            text += "\n"
    else:
        text += "<i>Tariflar yo'q</i>\n"
    text += BOX_BOTTOM
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi tarif", callback_data="add_ad")
    b.button(text="🗑 O'chirish", callback_data="del_ad_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "add_ad")
async def add_ad_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📢 <b>Tarif nomi:</b>\n<i>Masalan: 12 soat reklama</i>", parse_mode="HTML")
    await state.set_state(AS.ad_title)
    await cb.answer()


@dp.message(AS.ad_title)
async def ad_title_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(ad_title=message.text.strip())
    await message.answer("📝 <b>Tavsif:</b>")
    await state.set_state(AS.ad_desc)


@dp.message(AS.ad_desc)
async def ad_desc_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(ad_desc=message.text.strip())
    await message.answer("⏰ <b>Necha soat?</b> (0 = yo'q)")
    await state.set_state(AS.ad_hours)


@dp.message(AS.ad_hours)
async def ad_hours_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        h = int((message.text or "0").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(ad_hours=h)
    await message.answer("💰 <b>Narx (so'm):</b>")
    await state.set_state(AS.ad_price)


@dp.message(AS.ad_price)
async def ad_price_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        p = int((message.text or "").strip().replace(" ", ""))
    except Exception:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(ad_price=p)
    await message.answer("🎁 <b>Garant obunachi soni:</b> (0 = yo'q)")
    await state.set_state(AS.ad_subs)


@dp.message(AS.ad_subs)
async def ad_subs_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        s = int((message.text or "0").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    db_exec("""INSERT INTO ad_services (title, description, hours, price_uzs, bonus_subs, is_active, created_at)
               VALUES (%s, %s, %s, %s, %s, 1, %s)""",
            (data["ad_title"], data["ad_desc"], data["ad_hours"], data["ad_price"], s, now_uz().isoformat()))
    await state.clear()
    await message.answer(f"✅ Tarif qo'shildi!\n\n<b>{esc(data['ad_title'])}</b>\n💰 {format_number(data['ad_price'])} so'm", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_ad_list")
async def del_ad_list(cb):
    if not is_admin(cb.from_user.id):
        return
    services = get_ad_services(active_only=False)
    if not services:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for s in services:
        b.button(text=f"❌ #{s['id']} {s['title'][:30]}", callback_data=f"delad_{s['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_ads")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delad_"))
async def del_ad_do(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM ad_services WHERE id=%s", (int(cb.data.replace("delad_", "")),))
    await cb.answer("✅")
    await a_ads(cb, None)


# ─────────── BONUS CONFIG ───────────
@dp.callback_query(F.data == "a_bonus")
async def a_bonus(cb, state):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM bonus_config ORDER BY day_num", fetchall=True) or []
    text = box_title("🎁 KUNLIK BONUS CONFIG") + "\n\n"
    for r in rows:
        status = "🟢" if r["is_active"] else "🔴"
        text += f"{status} <b>{r['day_num']}-kun:</b> {r['reward']} ⭐\n"
    if not rows:
        text += "<i>Config yo'q</i>\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Tahrirlash", callback_data="edit_bonus")
    b.button(text="🔄 Reset", callback_data="reset_bonus")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "reset_bonus")
async def reset_bonus(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM bonus_config")
    for i, r in enumerate(BONUS_REWARDS, 1):
        db_exec("INSERT INTO bonus_config (day_num, reward, is_active) VALUES (%s, %s, 1)", (i, r))
    await cb.answer("✅ Reset qilindi!")
    await a_bonus(cb, None)


@dp.callback_query(F.data == "edit_bonus")
async def edit_bonus_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "🎁 <b>KUNLIK BONUS TAHRIRLASH</b>\n\n"
        "Format: <code>kun:miqdor</code>\n"
        "<i>Masalan:</i> <code>3:5</code> — 3-kun uchun 5 ⭐\n\n"
        "Yoki barcha kunlar uchun: <code>1:1,2:2,3:3,4:5,5:5,6:7,7:10</code>",
        parse_mode="HTML")
    await state.set_state(AS.bonus_reward)
    await cb.answer()


@dp.message(AS.bonus_reward)
async def bonus_reward_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    txt = message.text.strip()
    try:
        if "," in txt:
            for pair in txt.split(","):
                d, r = pair.split(":")
                db_exec("""INSERT INTO bonus_config (day_num, reward, is_active) VALUES (%s, %s, 1)
                           ON CONFLICT (day_num) DO UPDATE SET reward=EXCLUDED.reward""", (int(d), int(r)))
        else:
            d, r = txt.split(":")
            db_exec("UPDATE bonus_config SET reward=%s WHERE day_num=%s", (int(r), int(d)))
    except Exception as e:
        await message.answer(f"❌ Xato format: {e}")
        return
    await state.clear()
    await message.answer("✅ Yangilandi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


# ─────────── PREMIUM EMOJI ───────────
PREMIUM_KEYS = ["star", "gift", "flame", "crown", "rank", "trophy", "rocket", "contest"]


@dp.callback_query(F.data == "a_pe")
async def a_pe(cb, state):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM premium_emojis", fetchall=True) or []
    text = box_title("✨ PREMIUM EMOJI") + "\n\n"
    if rows:
        for r in rows:
            text += f"• <code>{esc(r['key'])}</code> → ID: <code>{esc(r['emoji_id'])}</code>\n"
    else:
        text += "<i>Hech qanday premium emoji yo'q</i>\n"
    text += f"\n{DIV}\n<b>Mavjud kalitlar:</b>\n" + ", ".join(f"<code>{k}</code>" for k in PREMIUM_KEYS)
    text += f"\n\n{DIV}\nPremium emoji qo'shish uchun:\n1. Premium emoji yuboring\n2. Forward qilib, ID sini oling"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish/Tahrirlash", callback_data="add_pe")
    b.button(text="🗑 O'chirish", callback_data="del_pe_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "add_pe")
async def add_pe_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(
        "✨ <b>PREMIUM EMOJI QO'SHISH</b>\n\n"
        "1️⃣ Kalit nomini yuboring (masalan: <code>star</code>)\n\n"
        f"Mavjud: {', '.join(PREMIUM_KEYS)}", parse_mode="HTML")
    await state.set_state(AS.pe_key)
    await cb.answer()


@dp.message(AS.pe_key)
async def pe_key_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(pe_key=message.text.strip().lower())
    await message.answer("2️⃣ <b>Emoji ID</b> ni yuboring:\n<i>(Premium emoji ID raqami)</i>", parse_mode="HTML")
    await state.set_state(AS.pe_id)


@dp.message(AS.pe_id)
async def pe_id_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(pe_id=message.text.strip())
    await message.answer("3️⃣ <b>Fallback emoji</b> (oddiy emoji, masalan ⭐):")
    await state.set_state(AS.pe_fallback)


@dp.message(AS.pe_fallback)
async def pe_fallback_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    set_premium_emoji(data["pe_key"], data["pe_id"], message.text.strip())
    await state.clear()
    await message.answer(f"✅ <b>{esc(data['pe_key'])}</b> saqlandi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_pe_list")
async def del_pe_list(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM premium_emojis", fetchall=True) or []
    if not rows:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"❌ {r['key']}", callback_data=f"delpe_{r['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_pe")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delpe_"))
async def del_pe_do(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM premium_emojis WHERE key=%s", (cb.data.replace("delpe_", ""),))
    await cb.answer("✅")
    await a_pe(cb, None)


# ─────────── Kanallar ───────────
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb):
    if not is_admin(cb.from_user.id):
        return
    channels = get_channels()
    text = box_title("📢 KANALLAR") + "\n\n"
    if channels:
        for ch in channels:
            text += f"• {esc(ch)}\n"
    else:
        text += "<i>Kanallar yo'q</i>\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_ch")
    b.button(text="➖ O'chirish", callback_data="del_ch_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_ch")
async def add_ch_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📢 <b>KANAL USERNAME KIRITING</b>\n\nMisol: <code>@mychannel</code>\n\n⚠️ Bot admin qilingan bo'lishi shart!", parse_mode="HTML")
    await state.set_state(AS.channel)
    await cb.answer()


@dp.message(AS.channel)
async def add_ch_process(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    try:
        chat = await bot.get_chat(ch)
        member = await bot.get_chat_member(ch, (await bot.get_me()).id)
        if member.status not in ("administrator", "creator"):
            await message.answer(f"⚠️ Bot <b>{esc(ch)}</b> kanalida admin emas!", parse_mode="HTML")
            return
    except Exception as e:
        await message.answer(f"❌ Kanal tekshirilmadi:\n<code>{esc(e)}</code>", parse_mode="HTML")
        return
    add_channel(ch)
    await state.clear()
    await message.answer(f"✅ <b>{esc(ch)}</b> qo'shildi!", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_ch_list")
async def del_ch_list(cb):
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
async def del_ch_do(cb):
    if not is_admin(cb.from_user.id):
        return
    remove_channel(cb.data.replace("delch_", ""))
    await cb.answer("✅")
    await a_channels(cb)


# ─────────── Savollar ───────────
@dp.callback_query(F.data == "a_questions")
async def a_questions(cb):
    if not is_admin(cb.from_user.id):
        return
    qs = get_questions()
    text = box_title("❓ SAVOLLAR") + "\n\n"
    if qs:
        for q in qs:
            text += f"📝 {esc(q['question'])}\n✅ {esc(q['correct_answer'])}\n❌ {esc(q['wrong1'])} | {esc(q['wrong2'])}\n\n"
    else:
        text += "<i>Savollar yo'q</i>\n"
    text += BOX_BOTTOM
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
async def add_q_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("❓ <b>Savolni kiriting:</b>", parse_mode="HTML")
    await state.set_state(AS.q_text)
    await cb.answer()


@dp.message(AS.q_text)
async def add_q_text(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(q_text=message.text.strip())
    await message.answer("✅ <b>To'g'ri javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_correct)


@dp.message(AS.q_correct)
async def add_q_correct(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(q_correct=message.text.strip())
    await message.answer("❌ <b>1-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong1)


@dp.message(AS.q_wrong1)
async def add_q_wrong1(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(q_wrong1=message.text.strip())
    await message.answer("❌ <b>2-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong2)


@dp.message(AS.q_wrong2)
async def add_q_wrong2(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    add_question(data["q_text"], data["q_correct"], data["q_wrong1"], message.text.strip())
    await state.clear()
    await message.answer("✅ <b>Savol qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_q_list")
async def del_q_list(cb):
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
async def del_q_do(cb):
    if not is_admin(cb.from_user.id):
        return
    remove_question(int(cb.data.replace("delq_", "")))
    await cb.answer("✅")
    await a_questions(cb)


# ─────────── Giftlar ───────────
@dp.callback_query(F.data == "a_gifts")
async def a_gifts(cb):
    if not is_admin(cb.from_user.id):
        return
    gifts = get_all_gifts()
    text = box_title("🎁 GIFTLAR") + "\n\n"
    for g in gifts:
        gid = g.get("gift_id")
        gid_text = f" [ID:{gid}]" if gid else " [ID yo'q]"
        pe_id = g.get("premium_emoji_id")
        pe_text = f" [PE:{pe_id[:8]}...]" if pe_id else ""
        text += f"{esc(g['emoji'])} <b>{esc(g['name'])}</b> — {g['stars']} ⭐{gid_text}{pe_text}\n"
    if not gifts:
        text += "<i>Giftlar yo'q</i>\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_gift")
    b.button(text="✏️ Tahrirlash", callback_data="edit_gift_list")
    b.button(text="✏️ ID tahrirlash", callback_data="edit_gift_ids")
    b.button(text="🎨 PE tahrirlash", callback_data="edit_gift_pe")
    b.button(text="➖ O'chirish", callback_data="del_gift_list")
    b.button(text="🔄 Sinxronlash", callback_data="sync_gifts")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "edit_gift_ids")
async def edit_gift_ids_list(cb):
    if not is_admin(cb.from_user.id):
        return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for g in gifts:
        gid = g.get("gift_id") or "yo'q"
        b.button(text=f"✏️ {g['emoji']} {g['name']} [{gid}]", callback_data=f"editgid_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("✏️ <b>Gift ID tahrirlash:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("editgid_"))
async def edit_gift_id_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    key = cb.data.replace("editgid_", "")
    g = get_gift(key)
    if not g:
        await cb.answer("—", show_alert=True)
        return
    await state.update_data(edit_gift_key=key, edit_mode="gift_id")
    await cb.message.edit_text(
        f"✏️ <b>{esc(g['emoji'])} {esc(g['name'])}</b>\n\n"
        f"Hozirgi ID: <code>{g.get('gift_id') or 'yo`q'}</code>\n\n"
        f"Yangi <b>Telegram Gift ID</b> raqamini yuboring:", parse_mode="HTML")
    await state.set_state(AS.gift_id_input)
    await cb.answer()


@dp.callback_query(F.data == "edit_gift_pe")
async def edit_gift_pe_list(cb):
    if not is_admin(cb.from_user.id):
        return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    for g in gifts:
        b.button(text=f"🎨 {g['emoji']} {g['name']}", callback_data=f"editgpe_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("🎨 <b>Premium emoji tahrirlash:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("editgpe_"))
async def edit_gift_pe_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    key = cb.data.replace("editgpe_", "")
    g = get_gift(key)
    if not g:
        await cb.answer("—", show_alert=True)
        return
    await state.update_data(edit_gift_key=key, edit_mode="pe")
    await cb.message.edit_text(
        f"🎨 <b>{esc(g['emoji'])} {esc(g['name'])}</b>\n\n"
        f"Hozirgi PE ID: <code>{g.get('premium_emoji_id') or 'yo`q'}</code>\n\n"
        f"Yangi <b>Premium emoji ID</b> raqamini yuboring:\n"
        f"<i>(yoki /skip — o'chirish uchun)</i>", parse_mode="HTML")
    await state.set_state(AS.gift_premium_id)
    await cb.answer()


@dp.message(AS.gift_premium_id)
async def gift_pe_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    key = data.get("edit_gift_key")
    txt = message.text.strip()
    if txt == "/skip":
        db_exec("UPDATE gifts SET premium_emoji_id=NULL WHERE key=%s", (key,))
    else:
        db_exec("UPDATE gifts SET premium_emoji_id=%s WHERE key=%s", (txt, key))
    await state.clear()
    await message.answer("✅ Saqlandi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.message(AS.gift_id_input)
async def gift_id_edit_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    edit_key = data.get("edit_gift_key")
    edit_mode = data.get("edit_mode")
    txt = message.text.strip()
    if edit_key and edit_mode == "gift_id":
        try:
            gid = int(txt)
            db_exec("UPDATE gifts SET gift_id=%s WHERE key=%s", (gid, edit_key))
            await state.clear()
            await message.answer(f"✅ Gift ID <b>{gid}</b> saqlandi!", parse_mode="HTML")
            await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))
        except ValueError:
            await message.answer("❌ Raqam kiriting yoki /skip")
        return
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


@dp.callback_query(F.data == "sync_gifts")
async def sync_gifts(cb):
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
        text = "🎁 <b>Mavjud giftlar:</b>\n\n" + "\n".join(lines)
        if len(text) > 4000:
            text = text[:3990] + "…"
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="a_gifts")
        b.adjust(1)
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")


@dp.callback_query(F.data == "add_gift")
async def add_gift_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🎁 <b>Kalit so'z:</b>", parse_mode="HTML")
    await state.set_state(AS.gift_key)
    await cb.answer()


@dp.message(AS.gift_key)
async def gift_key_process(message, state):
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
async def gift_emoji_process(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key") and data.get("edit_mode") != "gift_id":
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET emoji=%s WHERE key=%s", (message.text.strip(), data["edit_gift_key"]))
        await message.answer("📝 <b>Nom (yoki /skip):</b>", parse_mode="HTML")
        await state.set_state(AS.gift_name)
    else:
        await state.update_data(gift_emoji=message.text.strip())
        await message.answer("📝 <b>Nom:</b>", parse_mode="HTML")
        await state.set_state(AS.gift_name)


@dp.message(AS.gift_name)
async def gift_name_process(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key") and data.get("edit_mode") != "gift_id":
        if message.text.strip() != "/skip":
            db_exec("UPDATE gifts SET name=%s WHERE key=%s", (message.text.strip(), data["edit_gift_key"]))
        await message.answer("⭐ <b>Narx (yoki /skip):</b>", parse_mode="HTML")
        await state.set_state(AS.gift_stars)
    else:
        await state.update_data(gift_name=message.text.strip())
        await message.answer("🆔 <b>Telegram Gift ID</b>\n\n<i>/skip — agar bilmasangiz</i>", parse_mode="HTML")
        await state.set_state(AS.gift_id_input)


@dp.message(AS.gift_stars)
async def gift_stars_process(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            try:
                db_exec("UPDATE gifts SET stars=%s WHERE key=%s", (int(message.text.strip()), data["edit_gift_key"]))
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
        add_gift(data["gift_key"], data["gift_emoji"], data["gift_name"], stars, data.get("gift_id"))
        await state.clear()
        await message.answer("✅ <b>Gift qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_gift_list")
async def del_gift_list(cb):
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
async def del_gift_do(cb):
    if not is_admin(cb.from_user.id):
        return
    remove_gift(cb.data.replace("delgift_", ""))
    await cb.answer("✅")
    await a_gifts(cb)


@dp.callback_query(F.data == "edit_gift_list")
async def edit_gift_list(cb):
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
async def edit_gift_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    key = cb.data.replace("editgift_", "")
    gift = get_gift(key)
    if not gift:
        await cb.answer("—", show_alert=True)
        return
    await state.update_data(edit_gift_key=key, edit_mode="basic")
    await cb.message.edit_text(
        f"✏️ <b>{esc(gift['emoji'])} {esc(gift['name'])}</b> ({gift['stars']}⭐)\n\nYangi emoji (yoki /skip):",
        parse_mode="HTML")
    await state.set_state(AS.gift_emoji)
    await cb.answer()


# ─────────── Sozlamalar ───────────
@dp.callback_query(F.data == "a_settings")
async def a_settings(cb):
    if not is_admin(cb.from_user.id):
        return
    text = (
        f"{box_title('⚙️ SOZLAMALAR')}\n\n"
        f"🎯 <b>1 referal:</b> {get_setting('stars_per_referral')} ⭐\n"
        f"💰 <b>Min yechish:</b> {get_setting('min_withdraw')} ⭐\n"
        f"💎 <b>Max yechish:</b> {get_setting('max_withdraw')} ⭐\n"
        f"💝 <b>Min donat:</b> {get_setting('min_donate')} ⭐\n"
        f"📅 <b>Kunlik limit:</b> {get_setting('daily_withdraw_limit')} ⭐\n"
        f"🕒 <b>Min akkaunt yoshi:</b> {get_setting('min_account_age_days')} kun\n"
        f"⏳ <b>Referal kutish:</b> {get_setting('ref_hold_hours')} soat\n\n"
        f"{DIV}\n"
        f"📢 <b>Sharh kanali:</b> {esc(get_setting('review_channel') or 'yo`q')}\n"
        f"🎁 <b>Gift kanali:</b> {esc(get_setting('gift_channel') or 'yo`q')}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Referal", callback_data="set_ref")
    b.button(text="💰 Min", callback_data="set_minw")
    b.button(text="💎 Max", callback_data="set_maxw")
    b.button(text="📅 Kunlik", callback_data="set_dlim")
    b.button(text="🕒 Yosh", callback_data="set_age")
    b.button(text="⏳ Kutish", callback_data="set_hold")
    b.button(text="📢 Sharh kanal", callback_data="set_rev_ch")
    b.button(text="🎁 Gift kanal", callback_data="set_gift_ch")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(3, 3, 2, 1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data.in_({"set_ref", "set_minw", "set_maxw", "set_dlim", "set_age", "set_hold"}))
async def set_val_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    mapping = {
        "set_ref": ("stars_per_referral", "🎯 <b>1 referal uchun nechta stars?</b>"),
        "set_minw": ("min_withdraw", "💰 <b>Minimal yechish:</b>"),
        "set_maxw": ("max_withdraw", "💎 <b>Maksimal yechish:</b>"),
        "set_dlim": ("daily_withdraw_limit", "📅 <b>Kunlik limit:</b>"),
        "set_age": ("min_account_age_days", "🕒 <b>Min akkaunt yoshi (kun):</b>"),
        "set_hold": ("ref_hold_hours", "⏳ <b>Referal kutish (soat):</b>"),
    }
    key, prompt = mapping[cb.data]
    await state.update_data(setting_key=key)
    await cb.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(AS.setting_val)
    await cb.answer()


@dp.callback_query(F.data == "set_rev_ch")
async def set_rev_ch_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📢 <b>Sharh kanali username:</b>\nMisol: <code>@my_reviews</code>", parse_mode="HTML")
    await state.set_state(AS.review_channel)
    await cb.answer()


@dp.message(AS.review_channel)
async def set_rev_ch_process(message, state):
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
async def set_gift_ch_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🎁 <b>Gift kanali username:</b>\nMisol: <code>@starrush_gifts</code>", parse_mode="HTML")
    await state.set_state(AS.gift_channel)
    await cb.answer()


@dp.message(AS.gift_channel)
async def set_gift_ch_process(message, state):
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
            await message.answer(f"⚠️ Bot <b>{esc(ch)}</b> kanalida admin emas!", parse_mode="HTML")
            return
    except Exception as e:
        await message.answer(f"❌ {esc(e)}", parse_mode="HTML")
        return
    set_setting("gift_channel", ch)
    await state.clear()
    await message.answer(f"✅ Gift kanali: <b>{esc(ch)}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.message(AS.setting_val)
async def set_val_do(message, state):
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


# ─────────── Statistika ───────────
@dp.callback_query(F.data == "a_stats")
async def a_stats(cb):
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
    ad_reqs = q("SELECT COUNT(*) AS c FROM ad_orders WHERE status='pending_admin'")
    text = (
        f"{box_title('📊 STATISTIKA')}\n\n"
        f"👥 <b>Jami:</b> {format_number(total)}\n"
        f"✅ <b>Tasdiqlangan:</b> {format_number(ver)}\n"
        f"🚫 <b>Ban:</b> {format_number(ban)}\n"
        f"💸 <b>Pending:</b> {format_number(pend)}\n\n"
        f"{DIV}\n"
        f"🎁 <b>Gift OK:</b> {format_number(gifts_ok)}\n"
        f"⚠️ <b>Gift fail:</b> {format_number(gifts_fail)}\n"
        f"⭐ <b>Jami stars:</b> {format_number(total_stars)}\n"
        f"💝 <b>Jami donat:</b> {format_number(total_don)}\n\n"
        f"{DIV}\n"
        f"💬 <b>Suhbatlar:</b> {format_number(open_chats)}\n"
        f"🏆 <b>Konkurslar:</b> {format_number(active_contests)}\n"
        f"📢 <b>Reklama so'rovlari:</b> {format_number(ad_reqs)}"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


# ─────────── Donatlar ───────────
@dp.callback_query(F.data == "a_donations")
async def a_donations(cb):
    if not is_admin(cb.from_user.id):
        return
    total = bot_donate_balance()
    rows = db_exec("""SELECT d.user_id, d.stars, d.created_at, u.first_name, u.username
        FROM donations d LEFT JOIN users u ON d.user_id = u.user_id
        ORDER BY d.id DESC LIMIT 15""", fetchall=True) or []
    text = f"{box_title('💝 BOT DONAT BALANSI')}\n\n💰 <b>Jami:</b> <b>{format_number(total)} ⭐</b>\n\n"
    if rows:
        text += f"{DIV}\n\n"
        for r in rows:
            uname = f"@{esc(r['username'])}" if r["username"] else "—"
            date = (r["created_at"] or "")[:16].replace("T", " ")
            text += f"• {esc(r['first_name'] or 'User')} ({uname})\n  ⭐ {format_number(r['stars'])} — {date}\n"
    else:
        text += "<i>Hozircha donat yo'q</i>\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_donations")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1, 1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ─────────── Broadcast ───────────
@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(f"📨 <b>BROADCAST</b>\n{DIV}\nXabar yuboring:", parse_mode="HTML")
    await state.set_state(AS.broadcast)
    await cb.answer()


@dp.message(AS.broadcast)
async def broadcast_do(message, state):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users = db_exec("SELECT user_id FROM users WHERE is_banned=0", fetchall=True) or []
    if not users:
        await message.answer("❌ Foydalanuvchilar yo'q!")
        return
    total = len(users)
    status = await message.answer(f"📨 Yuborilmoqda... 0/{total}")
    okk = fail = blocked = 0
    for i, u in enumerate(users, 1):
        try:
            await message.copy_to(chat_id=u["user_id"])
            okk += 1
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
    result = (f"{box_title('📨 BROADCAST TUGADI')}\n\n"
              f"✅ <b>Yuborildi:</b> {format_number(okk)}\n"
              f"❌ <b>Xato:</b> {format_number(fail)}\n"
              f"🚫 <b>Bloklagan:</b> {format_number(blocked)}\n"
              f"👥 <b>Jami:</b> {format_number(total)}")
    try:
        await status.edit_text(result, parse_mode="HTML")
    except Exception:
        await message.answer(result, parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


# ─────────── Yechib olish ───────────
@dp.callback_query(F.data == "a_withdrawals")
async def a_withdrawals(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("""SELECT w.*, u.first_name, u.username FROM withdrawals w
        JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.id DESC LIMIT 10""", fetchall=True) or []
    if not rows:
        await cb.answer("— Pending yo'q", show_alert=True)
        return
    text = f"{box_title('💸 PENDING SO\'ROVLAR')}\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        if r["reward_type"] == "gift":
            g = get_gift(r["gift_key"]) or {}
            info = f"{esc(g.get('emoji', '🎁'))} {esc(g.get('name', 'Gift'))}"
        else:
            info = f"{format_number(r['stars'])} ⭐"
        uname = f"@{esc(r['username'])}" if r["username"] else "—"
        text += f"• <b>#{r['id']}</b> {esc(r['first_name'] or 'User')} ({uname})\n   {info}\n\n"
        b.button(text=f"✅ #{r['id']}", callback_data=f"appr_{r['id']}")
        b.button(text=f"❌ #{r['id']}", callback_data=f"rej_{r['id']}")
    text += BOX_BOTTOM
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("appr_"))
async def approve_w(cb):
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
    claimed = db_exec("UPDATE withdrawals SET status='approved' WHERE id=%s AND status='pending' RETURNING id",
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
            await bot.send_message(w["user_id"], T(u_lang, "stars_will_send", n=format_number(w["stars"])), parse_mode="HTML")
            await notify_admins(f"⚠️ <b>Stars yuborish kerak!</b>\n\n👤 {esc(user['first_name'])}\n🔗 {uname}\n🆔 <code>{user['user_id']}</code>\n⭐ <b>{format_number(w['stars'])} ⭐</b>\n\n<b>Fragment.com</b> orqali qo'lda yuboring!")
            post_text = build_gift_post(user=user, amount=w["stars"], is_stars=True)
            await send_gift_post(w["user_id"], post_text, is_anon=False)
        else:
            okk, err2 = await deliver_gift(w["user_id"], g or {}, anon=bool(w.get("is_anon")), comment=w.get("comment"))
            label = f"{esc((g or {}).get('emoji', '🎁'))} <b>{esc((g or {}).get('name', 'Gift'))}</b>"
            if okk:
                await bot.send_message(w["user_id"], T(u_lang, "gift_done", gift=label, n=format_number(w["stars"])), parse_mode="HTML")
                post_text = build_gift_post(user=user, amount=w["stars"],
                    gift_emoji=(g or {}).get("emoji", "🎁"), gift_name=(g or {}).get("name", "Gift"),
                    is_anon=bool(w.get("is_anon")), is_stars=False)
                await send_gift_post(w["user_id"], post_text, is_anon=bool(w.get("is_anon")))
            else:
                add_stars(w["user_id"], w["stars"])
                db_exec("UPDATE withdrawals SET status='failed', error=%s WHERE id=%s", ((err2 or "")[:500], w_id))
                await bot.send_message(w["user_id"], T(u_lang, "gift_failed", gift=label, n=format_number(w["stars"])), parse_mode="HTML")
                await notify_admins(f"⚠️ <b>Gift yuborilmadi</b> #{w_id}\n❗ {esc(err2)}")
    except Exception as e:
        logger.warning(f"Userga xabar: {e}")
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("rej_"))
async def reject_w(cb):
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


# ─────────── Suhbatlar ───────────
@dp.callback_query(F.data == "a_chats")
async def a_chats(cb):
    if not is_admin(cb.from_user.id):
        return
    chats = get_chat_users()
    if not chats:
        await cb.answer("— Suhbatlar yo'q", show_alert=True)
        return
    text = f"{box_title('💬 SUHBATLAR')}\n\n"
    b = InlineKeyboardBuilder()
    for c in chats[:20]:
        uname = f"@{esc(c['username'])}" if c["username"] else "—"
        icon = "🟢" if c["status"] == "open" else "🔴"
        text += f"{icon} {esc(c['first_name'] or 'User')} ({uname})\n   <code>{c['user_id']}</code>\n\n"
        b.button(text=f"💬 {c['first_name'] or 'User'}", callback_data=f"chat_open_{c['user_id']}")
        b.button(text="🗑", callback_data=f"chat_del_{c['user_id']}")
    text += BOX_BOTTOM
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(*([2] * min(len(chats[:20]), 10)), 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("chat_open_"))
async def chat_open(cb):
    if not is_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("chat_open_", ""))
    user = get_user(uid)
    if not user:
        await cb.answer("❌", show_alert=True)
        return
    if not is_chat_open(uid):
        open_chat(uid)
    rows = db_exec("SELECT * FROM support_tickets WHERE user_id=%s ORDER BY id DESC LIMIT 10", (uid,), fetchall=True) or []
    history = f"{box_title('💬 TARIX')}\n\n👤 <b>{esc(user['first_name'])}</b> (<code>{uid}</code>)\n\n{DIV}\n\n"
    for r in reversed(rows):
        who = "👑" if r["is_from_admin"] else "👤"
        c = r["content"]
        if r["message_type"] != "text":
            c = f"[{r['message_type']}]"
        elif len(c) > 80:
            c = c[:80] + "..."
        history += f"{who} {esc(c)}\n"
    history += f"\n{BOX_BOTTOM}"
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
async def chat_del(cb):
    if not is_admin(cb.from_user.id):
        return
    delete_chat(int(cb.data.replace("chat_del_", "")))
    await cb.answer("✅")
    await a_chats(cb)


# ─────────── Sharhlar ───────────
@dp.callback_query(F.data == "a_reviews")
async def a_reviews(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("""SELECT r.*, u.first_name, u.username FROM reviews r
        LEFT JOIN users u ON r.user_id=u.user_id WHERE r.status='pending' ORDER BY r.id DESC LIMIT 10""", fetchall=True) or []
    if not rows:
        await cb.answer("— Pending yo'q", show_alert=True)
        return
    text = f"{box_title('⭐ PENDING SHARHLAR')}\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        uname = f"@{esc(r['username'])}" if r["username"] else "—"
        text += f"👤 {esc(r['first_name'] or 'User')} ({uname})\n💬 <i>{esc(r['text'][:150])}</i>\n\n"
        b.button(text=f"✅ #{r['id']}", callback_data=f"revappr_{r['id']}")
        b.button(text=f"❌ #{r['id']}", callback_data=f"revrej_{r['id']}")
    text += BOX_BOTTOM
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 2, 2, 2, 2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("revappr_"))
async def review_approve(cb):
    if not is_admin(cb.from_user.id):
        return
    r_id = int(cb.data.replace("revappr_", ""))
    r = db_exec("UPDATE reviews SET status='approved' WHERE id=%s AND status='pending' RETURNING *", (r_id,), fetch=True)
    if not r:
        await cb.answer("—", show_alert=True)
        return
    user = get_user(r["user_id"])
    review_ch = get_setting("review_channel", "")
    if review_ch and user:
        try:
            uname = f"@{user['username']}" if user["username"] else "—"
            post = (f"⭐ <b>YANGI SHARH!</b>\n\n👤 {esc(user['first_name'] or 'User')}\n🔗 {uname}\n"
                    f"🆔 <code>{user['user_id']}</code>\n📅 {now_uz().strftime('%Y-%m-%d %H:%M')}\n\n💬 <i>{esc(r['text'])}</i>")
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
async def review_reject(cb):
    if not is_admin(cb.from_user.id):
        return
    r_id = int(cb.data.replace("revrej_", ""))
    r = db_exec("UPDATE reviews SET status='rejected' WHERE id=%s AND status='pending' RETURNING *", (r_id,), fetch=True)
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


# ─────────── Darajalar ───────────
@dp.callback_query(F.data == "a_levels")
async def a_levels(cb):
    if not is_admin(cb.from_user.id):
        return
    text = f"{box_title('🏅 DARAJALAR')}\n\n"
    for lvl in get_levels():
        text += f"{esc(lvl.get('emoji', ''))} <b>{esc(lvl.get('name', ''))}</b>: {lvl.get('min_stars', 0)}-{lvl.get('max_stars', 0)} ⭐\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi", callback_data="add_level")
    b.button(text="🗑 O'chirish", callback_data="del_level_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_level")
async def add_level_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🏅 <b>Daraja nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.level_name)
    await cb.answer()


@dp.message(AS.level_name)
async def level_name_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(level_name=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>")
    await state.set_state(AS.level_emoji)


@dp.message(AS.level_emoji)
async def level_emoji_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(level_emoji=message.text.strip())
    await message.answer("📉 <b>Min stars:</b>")
    await state.set_state(AS.level_min)


@dp.message(AS.level_min)
async def level_min_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(level_min=val)
    await message.answer("📈 <b>Max stars:</b>")
    await state.set_state(AS.level_max)


@dp.message(AS.level_max)
async def level_max_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    db_exec("INSERT INTO levels (name, emoji, min_stars, max_stars) VALUES (%s, %s, %s, %s)",
            (data["level_name"], data["level_emoji"], data["level_min"], val))
    await state.clear()
    await message.answer("✅ <b>Daraja qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_level_list")
async def del_level_list(cb):
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
async def del_level_do(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM levels WHERE id=%s", (int(cb.data.replace("dellvl_", "")),))
    await cb.answer("✅")
    await a_levels(cb)


# ─────────── User boshqarish ───────────
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
async def a_users(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text(f"👤 <b>USER BOSHQARISH</b>\n{DIV}\nUser ID kiriting:", parse_mode="HTML")
    await state.set_state(AS.user_id)
    await cb.answer()


@dp.message(AS.user_id)
async def user_info(message, state):
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
    text = (f"{box_title('👤 USER INFO')}\n\n"
            f"🆔 <code>{user['user_id']}</code>\n👤 {esc(user['first_name'])}\n🔗 {uname}\n📱 {phone_text}\n\n"
            f"{DIV}\n⭐ <b>Stars:</b> {format_number(user['stars'])}\n"
            f"💝 <b>Donat:</b> {format_number(donated)}\n"
            f"🏅 {esc(lvl.get('emoji', ''))} {esc(lvl.get('name', ''))}\n\n"
            f"{DIV}\n🚫 <b>Ban:</b> {'Ha' if user['is_banned'] else 'Yo`q'}\n"
            f"✅ <b>Ver:</b> {'Ha' if user['is_verified'] else 'Yo`q'}\n"
            f"🌐 <b>Lang:</b> {user.get('language', 'uz')}")
    await message.answer(text, reply_markup=user_manage_kb(uid, user["is_banned"]), parse_mode="HTML")


@dp.callback_query(F.data.startswith("tog_"))
async def toggle_ban(cb):
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
async def add_stars_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await state.update_data(target_uid=int(cb.data.replace("adp_", "")), action="add")
    await cb.message.edit_text("➕ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()


@dp.callback_query(F.data.startswith("rem_"))
async def remove_stars_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await state.update_data(target_uid=int(cb.data.replace("rem_", "")), action="remove")
    await cb.message.edit_text("➖ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()


@dp.message(AS.stars_amount)
async def stars_amount_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int((message.text or "").strip())
    except Exception:
        await message.answer("❌")
        return
    if amount <= 0:
        await message.answer("❌ >0")
        return
    await state.update_data(stars_amount=amount)
    await message.answer("📝 <b>Sabab:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_reason)


@dp.message(AS.stars_reason)
async def stars_reason_input(message, state):
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
        await bot.send_message(uid, T(u_lang, key, n=format_number(amount), reason=reason,
                                      total=format_number(new_stars)), parse_mode="HTML")
    except Exception:
        pass
    if action == "add":
        await check_level_up(uid, old_stars, new_stars)
    sign = "➕" if action == "add" else "➖"
    await message.answer(f"✅ {sign} <b>{format_number(amount)} ⭐</b>\n📝 {reason}\n💰 <b>{format_number(new_stars)} ⭐</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await state.update_data(target_uid=int(cb.data.replace("msg_", "")))
    await cb.message.edit_text("✉️ <b>Xabar:</b>", parse_mode="HTML")
    await state.set_state(AS.user_msg)
    await cb.answer()


@dp.message(AS.user_msg)
async def user_msg_send(message, state):
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


# ─────────── Adminlar ───────────
@dp.callback_query(F.data == "a_admins")
async def a_admins(cb):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True)
        return
    text = f"{box_title('👑 ADMINLAR')}\n\n"
    for a in list_admins():
        u = get_user(a["user_id"])
        tag = " 👑" if a["user_id"] in SUPER_ADMIN_IDS else ""
        text += f"• {esc(u['first_name']) if u else 'N/A'} — <code>{a['user_id']}</code>{tag}\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="➕", callback_data="add_admin")
    b.button(text="➖", callback_data="del_admin_list")
    b.button(text="⬅️", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_admin")
async def add_admin_start(cb, state):
    if not is_super_admin(cb.from_user.id):
        return
    await cb.message.edit_text("👑 <b>Admin ID:</b>", parse_mode="HTML")
    await state.set_state(AS.add_admin_id)
    await cb.answer()


@dp.message(AS.add_admin_id)
async def add_admin_do(message, state):
    if not is_super_admin(message.from_user.id):
        return
    try:
        uid = int((message.text or "").strip())
    except Exception:
        await message.answer("❌")
        return
    user = get_user(uid)
    if not user or uid in SUPER_ADMIN_IDS:
        await message.answer("❌")
        return
    add_admin(uid, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ <b>{esc(user['first_name'])}</b> admin!", parse_mode="HTML")
    try:
        await bot.send_message(uid, "🎉 <b>Siz admin!</b>\n\n/admin", parse_mode="HTML")
    except Exception:
        pass
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_admin_list")
async def del_admin_list(cb):
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
async def del_admin_do(cb):
    if not is_super_admin(cb.from_user.id):
        return
    uid = int(cb.data.replace("deladmin_", ""))
    if uid in SUPER_ADMIN_IDS:
        await cb.answer("❌", show_alert=True)
        return
    remove_admin(uid)
    await cb.answer("✅")
    await a_admins(cb)


# ─────────── Konkurslar ───────────
@dp.callback_query(F.data == "a_contests")
async def a_contests(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM contests ORDER BY id DESC LIMIT 10", fetchall=True) or []
    text = f"{box_title('🏆 KONKURSLAR')}\n\n"
    if rows:
        for c in rows:
            icon = "🟢" if c["status"] == "active" else "🔴"
            text += f"{icon} <b>#{c['id']}</b> {esc(c['title'])}\n   🎁 {esc(c['reward_name'])}\n   📅 {(c['start_at'] or '')[:10]} → {(c['end_at'] or '')[:10]}\n\n"
    else:
        text += "<i>Konkurslar yo'q</i>\n"
    text += BOX_BOTTOM
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi", callback_data="add_contest")
    b.button(text="🏁 Tugatish", callback_data="finish_contest_list")
    b.button(text="🗑 O'chirish", callback_data="del_contest_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_contest")
async def add_contest_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🏆 <b>Konkurs nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.contest_title)
    await cb.answer()


@dp.message(AS.contest_title)
async def contest_title_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_title=message.text.strip())
    await message.answer("📝 <b>Tavsif:</b>")
    await state.set_state(AS.contest_desc)


@dp.message(AS.contest_desc)
async def contest_desc_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_desc=message.text.strip())
    await message.answer("🎁 <b>Sovrin nomi:</b>")
    await state.set_state(AS.contest_reward_name)


@dp.message(AS.contest_reward_name)
async def contest_reward_name_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_reward_name=message.text.strip())
    await message.answer("😀 <b>Sovrin emoji:</b>")
    await state.set_state(AS.contest_reward_emoji)


@dp.message(AS.contest_reward_emoji)
async def contest_reward_emoji_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(c_reward_emoji=message.text.strip())
    await message.answer("📅 <b>Necha kun?</b>")
    await state.set_state(AS.contest_days)


@dp.message(AS.contest_days)
async def contest_days_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int((message.text or "").strip())
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer("❌ 1-365.")
        return
    data = await state.get_data()
    now = now_uz()
    end = now + timedelta(days=days)
    db_exec("""INSERT INTO contests (title, description, reward_emoji, reward_name, start_at, end_at, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'active', %s)""",
        (data["c_title"], data["c_desc"], data["c_reward_emoji"], data["c_reward_name"],
         now.isoformat(), end.isoformat(), now.isoformat()))
    await state.clear()
    await message.answer(f"✅ <b>Konkurs boshlandi!</b>\n\n🏆 {esc(data['c_title'])}\n📅 {days} kun", parse_mode="HTML")
    await notify_admins(f"🏆 <b>YANGI KONKURS!</b>\n\n🎯 {esc(data['c_title'])}\n{esc(data['c_desc'])}\n\n🎁 {esc(data['c_reward_emoji'])} <b>{esc(data['c_reward_name'])}</b>\n📅 {days} kun")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "finish_contest_list")
async def finish_contest_list(cb):
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
async def finish_contest_do(cb):
    if not is_admin(cb.from_user.id):
        return
    cid = int(cb.data.replace("fincontest_", ""))
    c = db_exec("SELECT * FROM contests WHERE id=%s", (cid,), fetch=True)
    if not c:
        await cb.answer("—", show_alert=True)
        return
    winner = db_exec("""SELECT u.user_id, u.first_name, COUNT(r.user_id) AS cnt
        FROM users r JOIN users u ON r.referrer_id = u.user_id
        WHERE r.is_verified=1 AND r.joined_at >= %s
        GROUP BY u.user_id, u.first_name ORDER BY cnt DESC LIMIT 1""",
        (c["start_at"],), fetch=True)
    if not winner:
        await cb.answer("— Qatnashuvchi yo'q", show_alert=True)
        return
    db_exec("UPDATE contests SET status='finished', winner_id=%s, winner_referrals=%s WHERE id=%s",
            (winner["user_id"], winner["cnt"], cid))
    await notify_admins(f"🏁 <b>KONKURS TUGADI!</b>\n\n🏆 {esc(c['title'])}\n\n🥇 <b>G'olib:</b> {esc(winner['first_name'])}\n👥 {winner['cnt']} ta referal")
    try:
        await bot.send_message(winner["user_id"],
            f"🎉 <b>TABRIKLAYMIZ!</b>\n\n<b>{esc(c['title'])}</b> konkursida g'olib bo'ldingiz!\n\n🏆 {winner['cnt']} ta referal\n🎁 {esc(c['reward_emoji'])} {esc(c['reward_name'])}",
            parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("✅")
    await a_contests(cb)


@dp.callback_query(F.data == "del_contest_list")
async def del_contest_list(cb):
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
async def del_contest_do(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM contests WHERE id=%s", (int(cb.data.replace("delcontest_", "")),))
    await cb.answer("✅")
    await a_contests(cb)


# ─────────── Vazifalar (admin) ───────────
@dp.callback_query(F.data == "a_tasks")
async def a_tasks(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM tasks ORDER BY id", fetchall=True) or []
    text = f"{box_title('📌 VAZIFALAR')}\n\n"
    for t in rows:
        icon = "🟢" if t["is_active"] else "🔴"
        text += f"{icon} <b>#{t['id']}</b> {esc(t['emoji'])} {esc(t['title'])}\n   +{t['reward']} ⭐ | {esc(t['action'])}\n\n"
    if not rows:
        text += "<i>Vazifalar yo'q</i>\n"
    text += BOX_BOTTOM
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_task")
    b.button(text="🔄 Toggle", callback_data="toggle_task_list")
    b.button(text="🗑 O'chirish", callback_data="del_task_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "toggle_task_list")
async def toggle_task_list(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM tasks ORDER BY id", fetchall=True) or []
    b = InlineKeyboardBuilder()
    for t in rows:
        icon = "🟢" if t["is_active"] else "🔴"
        b.button(text=f"{icon} #{t['id']} {t['title'][:30]}", callback_data=f"toggletask_{t['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_tasks")
    b.adjust(1)
    await cb.message.edit_text("🔄 <b>Yoqish/O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("toggletask_"))
async def toggle_task_do(cb):
    if not is_admin(cb.from_user.id):
        return
    tid = int(cb.data.replace("toggletask_", ""))
    db_exec("UPDATE tasks SET is_active = 1 - is_active WHERE id=%s", (tid,))
    await cb.answer("✅")
    await toggle_task_list(cb)


@dp.callback_query(F.data == "add_task")
async def add_task_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("📌 <b>Vazifa nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.task_title)
    await cb.answer()


@dp.message(AS.task_title)
async def task_title_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(t_title=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>")
    await state.set_state(AS.task_emoji)


@dp.message(AS.task_emoji)
async def task_emoji_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    await state.update_data(t_emoji=message.text.strip())
    await message.answer("⭐ <b>Mukofot (stars):</b>")
    await state.set_state(AS.task_reward)


@dp.message(AS.task_reward)
async def task_reward_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(t_reward=val)
    await message.answer("🔗 <b>Link</b> (yoki /skip):")
    await state.set_state(AS.task_link)


@dp.message(AS.task_link)
async def task_link_input(message, state):
    if not is_admin(message.from_user.id):
        return
    txt = (message.text or "").strip()
    await state.update_data(t_link=None if txt == "/skip" else txt)
    await message.answer("⚙️ <b>Action:</b>\n\n<code>ref</code> — referal\n<code>sub</code> — obuna\n<code>profile</code> — profil\n<code>manual</code> — qo'lda", parse_mode="HTML")
    await state.set_state(AS.task_action)


@dp.message(AS.task_action)
async def task_action_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    action = message.text.strip().lower()
    if action not in ("ref", "sub", "profile", "manual"):
        await message.answer("❌ Noto'g'ri.")
        return
    data = await state.get_data()
    db_exec("INSERT INTO tasks (title, emoji, reward, link, action, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
            (data["t_title"], data["t_emoji"], data["t_reward"], data["t_link"], action))
    await state.clear()
    await message.answer("✅ <b>Vazifa qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_task_list")
async def del_task_list(cb):
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
async def del_task_do(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM tasks WHERE id=%s", (int(cb.data.replace("deltask_", "")),))
    await cb.answer("✅")
    await a_tasks(cb)


# ─────────── Promokodlar ───────────
@dp.callback_query(F.data == "a_promocodes")
async def a_promocodes(cb):
    if not is_admin(cb.from_user.id):
        return
    rows = db_exec("SELECT * FROM promocodes ORDER BY created_at DESC LIMIT 20", fetchall=True) or []
    text = f"{box_title('🎟 PROMOKODLAR')}\n\n"
    for p in rows:
        text += f"• <code>{esc(p['code'])}</code> — {p['reward']} ⭐ (qoldi: {p['uses_left']})\n"
    if not rows:
        text += "<i>Promokodlar yo'q</i>\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yaratish", callback_data="add_promo")
    b.button(text="🗑 O'chirish", callback_data="del_promo_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_promo")
async def add_promo_start(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🎟 <b>Promokod matni:</b>", parse_mode="HTML")
    await state.set_state(AS.promo_code_admin)
    await cb.answer()


@dp.message(AS.promo_code_admin)
async def promo_code_input(message, state):
    if not is_admin(message.from_user.id) or not message.text:
        return
    code = message.text.strip().upper()
    if db_exec("SELECT 1 FROM promocodes WHERE code=%s", (code,), fetch=True):
        await message.answer("❌ Bu kod bor.")
        return
    await state.update_data(p_code=code)
    await message.answer("⭐ <b>Mukofot:</b>")
    await state.set_state(AS.promo_reward)


@dp.message(AS.promo_reward)
async def promo_reward_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        val = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(p_reward=val)
    await message.answer("👥 <b>Necha kishi?</b>")
    await state.set_state(AS.promo_uses)


@dp.message(AS.promo_uses)
async def promo_uses_input(message, state):
    if not is_admin(message.from_user.id):
        return
    try:
        uses = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    data = await state.get_data()
    db_exec("INSERT INTO promocodes (code, reward, uses_left, created_at) VALUES (%s, %s, %s, %s)",
            (data["p_code"], data["p_reward"], uses, now_uz().isoformat()))
    await state.clear()
    await message.answer(f"✅ <b>Promokod!</b>\n\n🎟 <code>{esc(data['p_code'])}</code>\n⭐ +{data['p_reward']}\n👥 {uses} kishi", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_promo_list")
async def del_promo_list(cb):
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
async def del_promo_do(cb):
    if not is_admin(cb.from_user.id):
        return
    db_exec("DELETE FROM promocodes WHERE code=%s", (cb.data.replace("delpromo_", ""),))
    await cb.answer("✅")
    await a_promocodes(cb)


# ─────────── USERBOT ───────────
@dp.callback_query(F.data == "a_userbot")
async def a_userbot(cb, state):
    if not is_admin(cb.from_user.id):
        return
    await state.clear()
    diag = [f"API_ID: {'✅' if API_ID else '❌'}", f"API_HASH: {'✅' if API_HASH else '❌'}",
            f"SESSION: {'✅' if SESSION_STRING else '❌'}"]
    disabled = get_setting("userbot_disabled", "0") == "1"
    if not tg_client:
        status = "⛔ O'chirilgan" if disabled else "❌ Ulanmagan"
        bal_text = "—"
    else:
        try:
            me = await tg_client.get_me()
            status = f"✅ <b>{esc(me.first_name or '')}</b>"
        except Exception as e:
            status = f"⚠️ {esc(e)}"
        try:
            st = await tg_client(functions.payments.GetStarsStatusRequest(peer=tt.InputPeerSelf()))
            bal = getattr(st.balance, "amount", st.balance)
            bal_text = f"<b>{format_number(bal)} ⭐</b>"
        except Exception:
            bal_text = "<i>o'qib bo'lmadi</i>"
    text = (f"{box_title('🤖 USERBOT')}\n\n📡 <b>Holat:</b> {status}\n💰 <b>Stars:</b> {bal_text}\n\n"
            f"{DIV}\n\n🔍 <b>Diagnostika:</b>\n\n" + "\n".join(diag))
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_userbot")
    if is_super_admin(cb.from_user.id):
        if tg_client or SESSION_STRING:
            b.button(text="🔑 Almashtirish", callback_data="a_userbot_change")
            b.button(text="🗑 O'chirish", callback_data="a_userbot_del")
        else:
            b.button(text="➕ Qo'shish", callback_data="a_userbot_change")
    b.button(text="🧪 Test", callback_data="a_userbot_test")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1)
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_test")
async def a_userbot_test(cb):
    if not is_admin(cb.from_user.id):
        return
    if not tg_client:
        await cb.answer("❌ Userbot ulanmagan!", show_alert=True)
        return
    await cb.answer("⏳...")
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
        await cb.message.answer(f"🧪 <b>USERBOT TEST</b>\n\n👤 {esc(me.first_name or '')}\n🆔 <code>{me.id}</code>\n📞 {esc(me.phone or '—')}\n💰 {bal} ⭐\n🎁 {gift_count}\n\n✅ Userbot ishlayapti!", parse_mode="HTML")
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")


@dp.callback_query(F.data == "a_userbot_change")
async def a_userbot_change(cb, state):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await state.clear()
    title = "🔑 <b>SESSION ALMASHTIRISH</b>" if (tg_client or SESSION_STRING) else "➕ <b>USERBOT QO'SHISH</b>"
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data="a_userbot")
    b.adjust(1)
    await cb.message.edit_text(f"{title}\n\n1️⃣ API_ID ni kiriting\n<i>(my.telegram.org)</i>",
                                reply_markup=b.as_markup(), parse_mode="HTML")
    await state.set_state(AS.userbot_api)
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_del")
async def a_userbot_del(cb, state):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True)
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha", callback_data="a_userbot_del_yes")
    b.button(text="❌ Yo'q", callback_data="a_userbot")
    b.adjust(2)
    await cb.message.edit_text("🗑 <b>USERBOTNI O'CHIRISH</b>\n\nRostdan o'chirasizmi?", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_del_yes")
async def a_userbot_del_yes(cb, state):
    global tg_client, API_ID, API_HASH, SESSION_STRING
    if not is_super_admin(cb.from_user.id):
        return
    await state.clear()
    old = tg_client
    tg_client = None
    if old:
        try:
            await old.disconnect()
        except Exception:
            pass
    API_ID = 0
    API_HASH = ""
    SESSION_STRING = ""
    for k in ("userbot_api_id", "userbot_api_hash", "userbot_session"):
        set_setting(k, "")
    set_setting("userbot_disabled", "1")
    await a_userbot(cb, state)


@dp.message(AS.userbot_api)
async def userbot_api_input(message, state):
    if not is_super_admin(message.from_user.id):
        return
    try:
        api_id = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ Raqam.")
        return
    await state.update_data(new_api_id=api_id)
    await message.answer("2️⃣ API_HASH:")
    await state.set_state(AS.userbot_hash)


@dp.message(AS.userbot_hash)
async def userbot_hash_input(message, state):
    if not is_super_admin(message.from_user.id):
        return
    api_hash = (message.text or "").strip()
    if len(api_hash) < 10:
        await message.answer("❌ Juda qisqa.")
        return
    await state.update_data(new_api_hash=api_hash)
    await message.answer("3️⃣ SESSION_STRING:")
    await state.set_state(AS.userbot_session)


@dp.message(AS.userbot_session)
async def userbot_session_input(message, state):
    if not is_super_admin(message.from_user.id):
        return
    session_str = (message.text or "").strip()
    if len(session_str) < 30:
        await message.answer("❌ Juda qisqa.")
        return
    data = await state.get_data()
    api_id = data.get("new_api_id")
    api_hash = data.get("new_api_hash")
    await message.answer("⏳...")
    try:
        test_client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await test_client.connect()
        if not await test_client.is_user_authorized():
            await test_client.disconnect()
            await message.answer("❌ Yaroqsiz.")
            await state.clear()
            return
        me = await test_client.get_me()
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
        await message.answer(f"✅ <b>USERBOT ULANDI!</b>\n\n👤 {esc(me.first_name or '')}", parse_mode="HTML")
        await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))
    except Exception as e:
        await message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")
        await state.clear()


# ═══════════════════════════════════════════════════════════
# USERBOT INIT
# ═══════════════════════════════════════════════════════════
async def init_userbot():
    global tg_client, API_ID, API_HASH, SESSION_STRING
    if get_setting("userbot_disabled", "0") == "1":
        API_ID = 0
        API_HASH = ""
        SESSION_STRING = ""
        logger.info("Userbot o'chirilgan")
        return
    db_api_id = get_setting("userbot_api_id", "")
    db_api_hash = get_setting("userbot_api_hash", "")
    db_session = get_setting("userbot_session", "")
    if db_api_id and db_api_hash and db_session:
        try:
            API_ID = int(db_api_id)
        except Exception:
            pass
        API_HASH = db_api_hash
        SESSION_STRING = security.dec(db_session)
    if not API_ID or not API_HASH or not SESSION_STRING:
        logger.warning("❌ Userbot sozlamalari to'liq emas")
        return
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return
        tg_client = client
        me = await client.get_me()
        logger.info(f"✅ Userbot: {me.first_name} (id {me.id})")
    except Exception as e:
        logger.error(f"❌ Userbot ulanmadi: {e}")
        tg_client = None


# ═══════════════════════════════════════════════════════════
# WEB API (mini)
# ═══════════════════════════════════════════════════════════
CORS_HEADERS = {"Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}


@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    resp = await handler(request)
    resp.headers.update(CORS_HEADERS)
    return resp


async def health(request):
    return web.Response(text="OK")


async def index(request):
    return web.Response(text=BOT_NAME)


# ═══════════════════════════════════════════════════════════
# ISHGA TUSHIRISH
# ═══════════════════════════════════════════════════════════
async def main():
    init_db()
    await init_userbot()
    security.setup(dp, db_exec=db_exec, now_uz=now_uz, T=T, LANGS=LANGS,
                   is_admin=is_admin, check_subs=check_subs, subs_kb=subs_kb)

    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", index)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Web server {PORT} portda ishga tushdi")

    # Background tasks
    bg_tasks = [
        asyncio.create_task(ad_expiry_loop()),
    ]

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"{BOT_NAME} ishga tushdi")
    try:
        await dp.start_polling(bot)
    finally:
        for t in bg_tasks:
            t.cancel()
        if tg_client:
            await tg_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
