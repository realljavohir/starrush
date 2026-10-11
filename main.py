# ═══════════ ADMIN PANEL ═══════════
ADMIN_TITLE = f"<b>🛠 ADMIN PANEL</b>\n{DIV}\nKerakli bo'limni tanlang 👇"


@dp.message(Command("admin"))
async def admin_panel_cmd(message, state):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!"); return
    await state.clear()
    await message.answer(ADMIN_TITLE, reply_markup=admin_menu(message.from_user.id), parse_mode="HTML")


@dp.callback_query(F.data == "m_admin")
async def cb_admin(cb, state):
    if not is_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True); return
    await state.clear()
    try: await cb.message.edit_text(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    except Exception: await cb.message.answer(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "a_back")
async def a_back(cb, state):
    if not is_admin(cb.from_user.id): return
    await state.clear()
    try: await cb.message.edit_text(ADMIN_TITLE, reply_markup=admin_menu(cb.from_user.id), parse_mode="HTML")
    except: pass
    await cb.answer()

# ─────────── REKLAMA TARIFLARI ───────────
@dp.callback_query(F.data == "a_ads")
async def a_ads(cb, state):
    if not is_admin(cb.from_user.id): return
    services = get_ad_services(active_only=False)
    text = box_title("📢 REKLAMA TARIFLAR") + "\n\n"
    if services:
        for s in services:
            status = "🟢" if s["is_active"] else "🔴"
            text += f"{status} <b>#{s['id']}</b> {esc(s['title'])}\n"
            text += f"   💰 {format_number(s['price_uzs'])} so'm\n"
            if s["hours"]: text += f"   ⏰ {s['hours']} soat\n"
            if s["bonus_subs"]: text += f"   🎁 +{s['bonus_subs']} garant\n"
            text += "\n"
    else:
        text += "<i>Tariflar yo'q</i>\n"
    text += BOX_BOTTOM
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi tarif", callback_data="add_ad")
    b.button(text="🗑 O'chirish", callback_data="del_ad_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    try: await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except: pass
    await cb.answer()


@dp.callback_query(F.data == "add_ad")
async def add_ad_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("📢 <b>Tarif nomi:</b>\n<i>Masalan: 12 soat reklama</i>", parse_mode="HTML")
    await state.set_state(AS.ad_title)
    await cb.answer()


@dp.message(AS.ad_title)
async def ad_title_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(ad_title=message.text.strip())
    await message.answer("📝 <b>Tavsif:</b>")
    await state.set_state(AS.ad_desc)


@dp.message(AS.ad_desc)
async def ad_desc_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(ad_desc=message.text.strip())
    await message.answer("⏰ <b>Necha soat?</b> (0 = yo'q)")
    await state.set_state(AS.ad_hours)


@dp.message(AS.ad_hours)
async def ad_hours_input(message, state):
    if not is_admin(message.from_user.id): return
    try: h = int((message.text or "0").strip())
    except: await message.answer("❌ Raqam."); return
    await state.update_data(ad_hours=h)
    await message.answer("💰 <b>Narx (so'm):</b>")
    await state.set_state(AS.ad_price)


@dp.message(AS.ad_price)
async def ad_price_input(message, state):
    if not is_admin(message.from_user.id): return
    try: p = int((message.text or "").strip().replace(" ", ""))
    except: await message.answer("❌ Raqam."); return
    await state.update_data(ad_price=p)
    await message.answer("🎁 <b>Garant obunachi soni:</b> (0 = yo'q)")
    await state.set_state(AS.ad_subs)


@dp.message(AS.ad_subs)
async def ad_subs_input(message, state):
    if not is_admin(message.from_user.id): return
    try: s = int((message.text or "0").strip())
    except: await message.answer("❌ Raqam."); return
    data = await state.get_data()
    db_exec("""INSERT INTO ad_services (title, description, hours, price_uzs, bonus_subs, is_active, created_at)
               VALUES (%s, %s, %s, %s, %s, 1, %s)""",
            (data["ad_title"], data["ad_desc"], data["ad_hours"], data["ad_price"], s, now_uz().isoformat()))
    await state.clear()
    await message.answer(f"✅ Tarif qo'shildi!\n\n<b>{esc(data['ad_title'])}</b>\n💰 {format_number(data['ad_price'])} so'm", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_ad_list")
async def del_ad_list(cb):
    if not is_admin(cb.from_user.id): return
    services = get_ad_services(active_only=False)
    if not services:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for s in services:
        b.button(text=f"❌ #{s['id']} {s['title'][:30]}", callback_data=f"delad_{s['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_ads")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delad_"))
async def del_ad_do(cb):
    if not is_admin(cb.from_user.id): return
    db_exec("DELETE FROM ad_services WHERE id=%s", (int(cb.data.replace("delad_", "")),))
    await cb.answer("✅")
    await a_ads(cb, None)

# ─────────── BONUS CONFIG ───────────
@dp.callback_query(F.data == "a_bonus")
async def a_bonus(cb, state):
    if not is_admin(cb.from_user.id): return
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
    try: await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except: pass
    await cb.answer()


@dp.callback_query(F.data == "reset_bonus")
async def reset_bonus(cb):
    if not is_admin(cb.from_user.id): return
    db_exec("DELETE FROM bonus_config")
    for i, r in enumerate(BONUS_REWARDS, 1):
        db_exec("INSERT INTO bonus_config (day_num, reward, is_active) VALUES (%s, %s, 1)", (i, r))
    await cb.answer("✅ Reset qilindi!")
    await a_bonus(cb, None)


@dp.callback_query(F.data == "edit_bonus")
async def edit_bonus_start(cb, state):
    if not is_admin(cb.from_user.id): return
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
    if not is_admin(message.from_user.id) or not message.text: return
    txt = message.text.strip()
    try:
        if "," in txt:
            for pair in txt.split(","):
                d, r = pair.split(":")
                db_exec("""INSERT INTO bonus_config (day_num, reward, is_active) VALUES (%s, %s, 1)
                           ON CONFLICT DO NOTHING""", (int(d), int(r)))
        else:
            d, r = txt.split(":")
            db_exec("UPDATE bonus_config SET reward=%s WHERE day_num=%s", (int(r), int(d)))
    except Exception as e:
        await message.answer(f"❌ Xato format: {e}"); return
    await state.clear()
    await message.answer("✅ Yangilandi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ─────────── PREMIUM EMOJI ───────────
PREMIUM_KEYS = ["star", "gift", "flame", "crown", "rank", "trophy", "rocket", "contest"]


@dp.callback_query(F.data == "a_pe")
async def a_pe(cb, state):
    if not is_admin(cb.from_user.id): return
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
    try: await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except: pass
    await cb.answer()


@dp.callback_query(F.data == "add_pe")
async def add_pe_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text(
        "✨ <b>PREMIUM EMOJI QO'SHISH</b>\n\n"
        "1️⃣ Kalit nomini yuboring (masalan: <code>star</code>)\n\n"
        f"Mavjud: {', '.join(PREMIUM_KEYS)}",
        parse_mode="HTML")
    await state.set_state(AS.pe_key)
    await cb.answer()


@dp.message(AS.pe_key)
async def pe_key_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(pe_key=message.text.strip().lower())
    await message.answer("2️⃣ <b>Emoji ID</b> ni yuboring:\n<i>(Premium emoji ID raqami)</i>", parse_mode="HTML")
    await state.set_state(AS.pe_id)


@dp.message(AS.pe_id)
async def pe_id_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(pe_id=message.text.strip())
    await message.answer("3️⃣ <b>Fallback emoji</b> (oddiy emoji, masalan ⭐):")
    await state.set_state(AS.pe_fallback)


@dp.message(AS.pe_fallback)
async def pe_fallback_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    data = await state.get_data()
    set_premium_emoji(data["pe_key"], data["pe_id"], message.text.strip())
    await state.clear()
    await message.answer(f"✅ <b>{esc(data['pe_key'])}</b> saqlandi!")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_pe_list")
async def del_pe_list(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM premium_emojis", fetchall=True) or []
    if not rows:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"❌ {r['key']}", callback_data=f"delpe_{r['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_pe")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delpe_"))
async def del_pe_do(cb):
    if not is_admin(cb.from_user.id): return
    db_exec("DELETE FROM premium_emojis WHERE key=%s", (cb.data.replace("delpe_", ""),))
    await cb.answer("✅")
    await a_pe(cb, None)

# ─────────── Kanallar ───────────
@dp.callback_query(F.data == "a_channels")
async def a_channels(cb):
    if not is_admin(cb.from_user.id): return
    channels = get_channels()
    text = box_title("📢 KANALLAR") + "\n\n"
    if channels:
        for ch in channels: text += f"• {esc(ch)}\n"
    else: text += "<i>Kanallar yo'q</i>\n"
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
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("📢 <b>KANAL USERNAME KIRITING</b>\n\nMisol: <code>@mychannel</code>\n\n⚠️ Bot admin qilingan bo'lishi shart!", parse_mode="HTML")
    await state.set_state(AS.channel)
    await cb.answer()


@dp.message(AS.channel)
async def add_ch_process(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    ch = message.text.strip()
    if not ch.startswith("@"): ch = "@" + ch
    try:
        chat = await bot.get_chat(ch)
        member = await bot.get_chat_member(ch, (await bot.get_me()).id)
        if member.status not in ("administrator", "creator"):
            await message.answer(f"⚠️ Bot <b>{esc(ch)}</b> kanalida admin emas!", parse_mode="HTML"); return
    except Exception as e:
        await message.answer(f"❌ Kanal tekshirilmadi:\n<code>{esc(e)}</code>", parse_mode="HTML"); return
    add_channel(ch)
    await state.clear()
    await message.answer(f"✅ <b>{esc(ch)}</b> qo'shildi!", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_ch_list")
async def del_ch_list(cb):
    if not is_admin(cb.from_user.id): return
    channels = get_channels()
    if not channels:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for ch in channels: b.button(text=f"❌ {ch}", callback_data=f"delch_{ch}")
    b.button(text="⬅️ Orqaga", callback_data="a_channels")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delch_"))
async def del_ch_do(cb):
    if not is_admin(cb.from_user.id): return
    remove_channel(cb.data.replace("delch_", ""))
    await cb.answer("✅")
    await a_channels(cb)

# ─────────── Savollar ───────────
@dp.callback_query(F.data == "a_questions")
async def a_questions(cb):
    if not is_admin(cb.from_user.id): return
    qs = get_questions()
    text = box_title("❓ SAVOLLAR") + "\n\n"
    if qs:
        for q in qs:
            text += f"📝 {esc(q['question'])}\n✅ {esc(q['correct_answer'])}\n❌ {esc(q['wrong1'])} | {esc(q['wrong2'])}\n\n"
    else: text += "<i>Savollar yo'q</i>\n"
    text += BOX_BOTTOM
    if len(text) > 4000: text = text[:3990] + "…"
    b = InlineKeyboardBuilder()
    b.button(text="➕ Qo'shish", callback_data="add_q")
    b.button(text="➖ O'chirish", callback_data="del_q_list")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(2, 1)
    await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "add_q")
async def add_q_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("❓ <b>Savolni kiriting:</b>", parse_mode="HTML")
    await state.set_state(AS.q_text)
    await cb.answer()


@dp.message(AS.q_text)
async def add_q_text(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(q_text=message.text.strip())
    await message.answer("✅ <b>To'g'ri javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_correct)


@dp.message(AS.q_correct)
async def add_q_correct(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(q_correct=message.text.strip())
    await message.answer("❌ <b>1-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong1)


@dp.message(AS.q_wrong1)
async def add_q_wrong1(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(q_wrong1=message.text.strip())
    await message.answer("❌ <b>2-xato javob:</b>", parse_mode="HTML")
    await state.set_state(AS.q_wrong2)


@dp.message(AS.q_wrong2)
async def add_q_wrong2(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    data = await state.get_data()
    add_question(data["q_text"], data["q_correct"], data["q_wrong1"], message.text.strip())
    await state.clear()
    await message.answer("✅ <b>Savol qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_q_list")
async def del_q_list(cb):
    if not is_admin(cb.from_user.id): return
    qs = get_questions()
    if not qs:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for q in qs: b.button(text=f"❌ {q['question'][:40]}", callback_data=f"delq_{q['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_questions")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delq_"))
async def del_q_do(cb):
    if not is_admin(cb.from_user.id): return
    remove_question(int(cb.data.replace("delq_", "")))
    await cb.answer("✅")
    await a_questions(cb)

# ─────────── Giftlar ───────────
@dp.callback_query(F.data == "a_gifts")
async def a_gifts(cb):
    if not is_admin(cb.from_user.id): return
    gifts = get_all_gifts()
    text = box_title("🎁 GIFTLAR") + "\n\n"
    for g in gifts:
        gid = g.get("gift_id")
        gid_text = f" [ID:{gid}]" if gid else " [ID yo'q]"
        pe_id = g.get("premium_emoji_id")
        pe_text = f" [PE:{pe_id[:8]}...]" if pe_id else ""
        text += f"{esc(g['emoji'])} <b>{esc(g['name'])}</b> — {g['stars']} ⭐{gid_text}{pe_text}\n"
    if not gifts: text += "<i>Giftlar yo'q</i>\n"
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
    if not is_admin(cb.from_user.id): return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True); return
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
    if not is_admin(cb.from_user.id): return
    key = cb.data.replace("editgid_", "")
    g = get_gift(key)
    if not g:
        await cb.answer("—", show_alert=True); return
    await state.update_data(edit_gift_key=key, edit_mode="gift_id")
    await cb.message.edit_text(
        f"✏️ <b>{esc(g['emoji'])} {esc(g['name'])}</b>\n\n"
        f"Hozirgi ID: <code>{g.get('gift_id') or 'yo`q'}</code>\n\n"
        f"Yangi <b>Telegram Gift ID</b> raqamini yuboring:",
        parse_mode="HTML")
    await state.set_state(AS.gift_id_input)
    await cb.answer()


@dp.callback_query(F.data == "edit_gift_pe")
async def edit_gift_pe_list(cb):
    if not is_admin(cb.from_user.id): return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for g in gifts:
        pe_id = g.get("premium_emoji_id") or "yo'q"
        b.button(text=f"🎨 {g['emoji']} {g['name']}", callback_data=f"editgpe_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("🎨 <b>Premium emoji tahrirlash:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("editgpe_"))
async def edit_gift_pe_start(cb, state):
    if not is_admin(cb.from_user.id): return
    key = cb.data.replace("editgpe_", "")
    g = get_gift(key)
    if not g:
        await cb.answer("—", show_alert=True); return
    await state.update_data(edit_gift_key=key, edit_mode="pe")
    await cb.message.edit_text(
        f"🎨 <b>{esc(g['emoji'])} {esc(g['name'])}</b>\n\n"
        f"Hozirgi PE ID: <code>{g.get('premium_emoji_id') or 'yo`q'}</code>\n\n"
        f"Yangi <b>Premium emoji ID</b> raqamini yuboring:\n"
        f"<i>(yoki /skip — o'chirish uchun)</i>",
        parse_mode="HTML")
    await state.set_state(AS.gift_premium_id)
    await cb.answer()


@dp.message(AS.gift_premium_id)
async def gift_pe_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
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
    """Generic gift_id input (ham yangi qo'shish, ham tahrirlash uchun)."""
    if not is_admin(message.from_user.id) or not message.text: return
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

    # Yangi gift qo'shish oqimi
    gift_id = None
    if txt != "/skip":
        try: gift_id = int(txt)
        except ValueError:
            await message.answer("❌ Raqam kiriting yoki /skip"); return
    await state.update_data(gift_id=gift_id)
    await message.answer("⭐ <b>Narx (Stars):</b>", parse_mode="HTML")
    await state.set_state(AS.gift_stars)


@dp.callback_query(F.data == "sync_gifts")
async def sync_gifts(cb):
    if not is_admin(cb.from_user.id): return
    if not tg_client:
        await cb.answer("❌ Userbot ulanmagan!", show_alert=True); return
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
        if len(text) > 4000: text = text[:3990] + "…"
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Orqaga", callback_data="a_gifts")
        b.adjust(1)
        await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")


@dp.callback_query(F.data == "add_gift")
async def add_gift_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("🎁 <b>Kalit so'z:</b>", parse_mode="HTML")
    await state.set_state(AS.gift_key)
    await cb.answer()


@dp.message(AS.gift_key)
async def gift_key_process(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    key = message.text.strip().lower().replace(" ", "_")
    if not key or not key.replace("_", "").isalnum():
        await message.answer("❌ Faqat harflar va raqamlar."); return
    if get_gift(key):
        await message.answer("❌ Allaqachon bor."); return
    await state.update_data(gift_key=key)
    await message.answer("😀 <b>Emoji</b>:", parse_mode="HTML")
    await state.set_state(AS.gift_emoji)


@dp.message(AS.gift_emoji)
async def gift_emoji_process(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
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
    if not is_admin(message.from_user.id) or not message.text: return
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
    if not is_admin(message.from_user.id) or not message.text: return
    data = await state.get_data()
    if data.get("edit_gift_key"):
        if message.text.strip() != "/skip":
            try: db_exec("UPDATE gifts SET stars=%s WHERE key=%s", (int(message.text.strip()), data["edit_gift_key"]))
            except ValueError:
                await message.answer("❌ Raqam."); return
        await state.clear()
        await message.answer("✅ <b>Tahrirlandi!</b>", parse_mode="HTML")
    else:
        try: stars = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Raqam."); return
        if stars < 1:
            await message.answer("❌ Kamida 1."); return
        add_gift(data["gift_key"], data["gift_emoji"], data["gift_name"], stars, data.get("gift_id"))
        await state.clear()
        await message.answer("✅ <b>Gift qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_gift_list")
async def del_gift_list(cb):
    if not is_admin(cb.from_user.id): return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for g in gifts: b.button(text=f"❌ {g['emoji']} {g['name']}", callback_data=f"delgift_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delgift_"))
async def del_gift_do(cb):
    if not is_admin(cb.from_user.id): return
    remove_gift(cb.data.replace("delgift_", ""))
    await cb.answer("✅")
    await a_gifts(cb)


@dp.callback_query(F.data == "edit_gift_list")
async def edit_gift_list(cb):
    if not is_admin(cb.from_user.id): return
    gifts = get_all_gifts()
    if not gifts:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for g in gifts: b.button(text=f"✏️ {g['emoji']} {g['name']}", callback_data=f"editgift_{g['key']}")
    b.button(text="⬅️ Orqaga", callback_data="a_gifts")
    b.adjust(1)
    await cb.message.edit_text("✏️ <b>Tahrirlash:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("editgift_"))
async def edit_gift_start(cb, state):
    if not is_admin(cb.from_user.id): return
    key = cb.data.replace("editgift_", "")
    gift = get_gift(key)
    if not gift:
        await cb.answer("—", show_alert=True); return
    await state.update_data(edit_gift_key=key, edit_mode="basic")
    await cb.message.edit_text(
        f"✏️ <b>{esc(gift['emoji'])} {esc(gift['name'])}</b> ({gift['stars']}⭐)\n\nYangi emoji (yoki /skip):",
        parse_mode="HTML")
    await state.set_state(AS.gift_emoji)
    await cb.answer()

# ─────────── Sozlamalar ───────────
@dp.callback_query(F.data == "a_settings")
async def a_settings(cb):
    if not is_admin(cb.from_user.id): return
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
    try: await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except: pass
    await cb.answer()


@dp.callback_query(F.data.in_({"set_ref", "set_minw", "set_maxw", "set_dlim", "set_age", "set_hold"}))
async def set_val_start(cb, state):
    if not is_admin(cb.from_user.id): return
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
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("📢 <b>Sharh kanali username:</b>\nMisol: <code>@my_reviews</code>", parse_mode="HTML")
    await state.set_state(AS.review_channel)
    await cb.answer()


@dp.message(AS.review_channel)
async def set_rev_ch_process(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    ch = message.text.strip()
    if not ch.startswith("@"): ch = "@" + ch
    set_setting("review_channel", ch)
    await state.clear()
    await message.answer(f"✅ Sharh kanali: <b>{esc(ch)}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "set_gift_ch")
async def set_gift_ch_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("🎁 <b>Gift kanali username:</b>\nMisol: <code>@starrush_gifts</code>", parse_mode="HTML")
    await state.set_state(AS.gift_channel)
    await cb.answer()


@dp.message(AS.gift_channel)
async def set_gift_ch_process(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    ch = message.text.strip()
    if not ch.startswith("@"): ch = "@" + ch
    try:
        await bot.get_chat(ch)
        me = await bot.get_me()
        member = await bot.get_chat_member(ch, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(f"⚠️ Bot <b>{esc(ch)}</b> kanalida admin emas!", parse_mode="HTML"); return
    except Exception as e:
        await message.answer(f"❌ {esc(e)}", parse_mode="HTML"); return
    set_setting("gift_channel", ch)
    await state.clear()
    await message.answer(f"✅ Gift kanali: <b>{esc(ch)}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.message(AS.setting_val)
async def set_val_do(message, state):
    if not is_admin(message.from_user.id): return
    try: val = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Raqam."); return
    data = await state.get_data()
    set_setting(data["setting_key"], val)
    await state.clear()
    await message.answer(f"✅ <b>{data['setting_key']} = {val}</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ─────────── Statistika ───────────
@dp.callback_query(F.data == "a_stats")
async def a_stats(cb):
    if not is_admin(cb.from_user.id): return
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
    ad_reqs = q("SELECT COUNT(*) AS c FROM ad_requests WHERE status='pending'")
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
    if not is_admin(cb.from_user.id): return
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
    else: text += "<i>Hozircha donat yo'q</i>\n"
    text += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangilash", callback_data="a_donations")
    b.button(text="⬅️ Orqaga", callback_data="a_back")
    b.adjust(1, 1)
    try: await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except: pass
    await cb.answer()

# ─────────── Broadcast ───────────
@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text(f"📨 <b>BROADCAST</b>\n{DIV}\nXabar yuboring:", parse_mode="HTML")
    await state.set_state(AS.broadcast)
    await cb.answer()


@dp.message(AS.broadcast)
async def broadcast_do(message, state):
    if not is_admin(message.from_user.id): return
    await state.clear()
    users = db_exec("SELECT user_id FROM users WHERE is_banned=0", fetchall=True) or []
    if not users:
        await message.answer("❌ Foydalanuvchilar yo'q!"); return
    total = len(users)
    status = await message.answer(f"📨 Yuborilmoqda... 0/{total}")
    okk = fail = blocked = 0
    for i, u in enumerate(users, 1):
        try:
            await message.copy_to(chat_id=u["user_id"])
            okk += 1
        except TelegramForbiddenError:
            blocked += 1; fail += 1
        except: fail += 1
        if i % 25 == 0:
            try: await status.edit_text(f"📨 Yuborilmoqda... {i}/{total}")
            except: pass
        await asyncio.sleep(0.05)
    result = (f"{box_title('📨 BROADCAST TUGADI')}\n\n"
              f"✅ <b>Yuborildi:</b> {format_number(okk)}\n"
              f"❌ <b>Xato:</b> {format_number(fail)}\n"
              f"🚫 <b>Bloklagan:</b> {format_number(blocked)}\n"
              f"👥 <b>Jami:</b> {format_number(total)}")
    try: await status.edit_text(result, parse_mode="HTML")
    except: await message.answer(result, parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ─────────── Yechib olish ───────────
@dp.callback_query(F.data == "a_withdrawals")
async def a_withdrawals(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("""SELECT w.*, u.first_name, u.username FROM withdrawals w
        JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.id DESC LIMIT 10""", fetchall=True) or []
    if not rows:
        await cb.answer("— Pending yo'q", show_alert=True); return
    text = f"{box_title('💸 PENDING SO\'ROVLAR')}\n\n"
    b = InlineKeyboardBuilder()
    for r in rows:
        if r["reward_type"] == "gift":
            g = get_gift(r["gift_key"]) or {}
            info = f"{esc(g.get('emoji', '🎁'))} {esc(g.get('name', 'Gift'))}"
        else: info = f"{format_number(r['stars'])} ⭐"
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
    if not is_admin(cb.from_user.id): return
    w_id = int(cb.data.replace("appr_", ""))
    w = db_exec("SELECT * FROM withdrawals WHERE id=%s", (w_id,), fetch=True)
    if not w or w["status"] != "pending":
        await cb.answer("—", show_alert=True); return
    user = get_user(w["user_id"])
    if not user:
        await cb.answer("—", show_alert=True); return
    claimed = db_exec("UPDATE withdrawals SET status='approved' WHERE id=%s AND status='pending' RETURNING id",
                      (w_id,), fetch=True)
    if not claimed:
        await cb.answer("—", show_alert=True); return
    if spend_stars(w["user_id"], w["stars"]) is None:
        db_exec("UPDATE withdrawals SET status='pending' WHERE id=%s", (w_id,))
        await cb.answer(f"❌ Kerak: {w['stars']}, bor: {user['stars']}", show_alert=True); return
    try: await cb.message.edit_text(cb.message.html_text + "\n\n✅ <b>TASDIQLANGAN</b>", parse_mode="HTML")
    except: pass
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
    except Exception as e: logger.warning(f"Userga xabar: {e}")
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("rej_"))
async def reject_w(cb):
    if not is_admin(cb.from_user.id): return
    w_id = int(cb.data.replace("rej_", ""))
    w = db_exec("UPDATE withdrawals SET status='rejected' WHERE id=%s AND status='pending' RETURNING *",
                (w_id,), fetch=True)
    if not w:
        await cb.answer("—", show_alert=True); return
    try: await cb.message.edit_text(cb.message.html_text + "\n\n❌ <b>RAD ETILGAN</b>", parse_mode="HTML")
    except: pass
    await cb.answer("❌")
    try: await bot.send_message(w["user_id"], T(get_user_lang(w["user_id"]), "rejected"), parse_mode="HTML")
    except: pass

# ─────────── Suhbatlar ───────────
@dp.callback_query(F.data == "a_chats")
async def a_chats(cb):
    if not is_admin(cb.from_user.id): return
    chats = get_chat_users()
    if not chats:
        await cb.answer("— Suhbatlar yo'q", show_alert=True); return
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
    if not is_admin(cb.from_user.id): return
    uid = int(cb.data.replace("chat_open_", ""))
    user = get_user(uid)
    if not user:
        await cb.answer("❌", show_alert=True); return
    if not is_chat_open(uid): open_chat(uid)
    rows = db_exec("SELECT * FROM support_tickets WHERE user_id=%s ORDER BY id DESC LIMIT 10", (uid,), fetchall=True) or []
    history = f"{box_title('💬 TARIX')}\n\n👤 <b>{esc(user['first_name'])}</b> (<code>{uid}</code>)\n\n{DIV}\n\n"
    for r in reversed(rows):
        who = "👑" if r["is_from_admin"] else "👤"
        c = r["content"]
        if r["message_type"] != "text": c = f"[{r['message_type']}]"
        elif len(c) > 80: c = c[:80] + "..."
        history += f"{who} {esc(c)}\n"
    history += f"\n{BOX_BOTTOM}"
    b = InlineKeyboardBuilder()
    b.button(text="✉️ Javob", callback_data=f"reply_{uid}")
    b.button(text="🔚 Tugatish", callback_data=f"chat_close_admin_{uid}")
    b.button(text="🗑 O'chirish", callback_data=f"chat_del_{uid}")
    b.button(text="⬅️", callback_data="a_chats")
    b.adjust(1)
    try: await cb.message.edit_text(history, reply_markup=b.as_markup(), parse_mode="HTML")
    except Exception: await cb.message.answer(history, reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("chat_del_"))
async def chat_del(cb):
    if not is_admin(cb.from_user.id): return
    delete_chat(int(cb.data.replace("chat_del_", "")))
    await cb.answer("✅")
    await a_chats(cb)

# ─────────── Sharhlar ───────────
@dp.callback_query(F.data == "a_reviews")
async def a_reviews(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("""SELECT r.*, u.first_name, u.username FROM reviews r
        LEFT JOIN users u ON r.user_id=u.user_id WHERE r.status='pending' ORDER BY r.id DESC LIMIT 10""", fetchall=True) or []
    if not rows:
        await cb.answer("— Pending yo'q", show_alert=True); return
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
    if not is_admin(cb.from_user.id): return
    r_id = int(cb.data.replace("revappr_", ""))
    r = db_exec("UPDATE reviews SET status='approved' WHERE id=%s AND status='pending' RETURNING *", (r_id,), fetch=True)
    if not r:
        await cb.answer("—", show_alert=True); return
    user = get_user(r["user_id"])
    review_ch = get_setting("review_channel", "")
    if review_ch and user:
        try:
            uname = f"@{user['username']}" if user["username"] else "—"
            post = (f"⭐ <b>YANGI SHARH!</b>\n\n👤 {esc(user['first_name'] or 'User')}\n🔗 {uname}\n"
                    f"🆔 <code>{user['user_id']}</code>\n📅 {now_uz().strftime('%Y-%m-%d %H:%M')}\n\n💬 <i>{esc(r['text'])}</i>")
            await bot.send_message(review_ch, post, parse_mode="HTML")
        except Exception as e: logger.warning(f"Sharh kanali: {e}")
    try: await bot.send_message(r["user_id"], T(get_user_lang(r["user_id"]), "review_approved"), parse_mode="HTML")
    except: pass
    try: await cb.message.edit_text(cb.message.html_text + f"\n\n✅ <b>#{r_id} TASDIQLANDI</b>", parse_mode="HTML")
    except: pass
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("revrej_"))
async def review_reject(cb):
    if not is_admin(cb.from_user.id): return
    r_id = int(cb.data.replace("revrej_", ""))
    r = db_exec("UPDATE reviews SET status='rejected' WHERE id=%s AND status='pending' RETURNING *", (r_id,), fetch=True)
    if not r:
        await cb.answer("—", show_alert=True); return
    try: await bot.send_message(r["user_id"], T(get_user_lang(r["user_id"]), "review_rejected"), parse_mode="HTML")
    except: pass
    try: await cb.message.edit_text(cb.message.html_text + f"\n\n❌ <b>#{r_id} RAD ETILDI</b>", parse_mode="HTML")
    except: pass
    await cb.answer("❌")

# ─────────── Darajalar ───────────
@dp.callback_query(F.data == "a_levels")
async def a_levels(cb):
    if not is_admin(cb.from_user.id): return
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
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("🏅 <b>Daraja nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.level_name)
    await cb.answer()


@dp.message(AS.level_name)
async def level_name_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(level_name=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>")
    await state.set_state(AS.level_emoji)


@dp.message(AS.level_emoji)
async def level_emoji_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(level_emoji=message.text.strip())
    await message.answer("📉 <b>Min stars:</b>")
    await state.set_state(AS.level_min)


@dp.message(AS.level_min)
async def level_min_input(message, state):
    if not is_admin(message.from_user.id): return
    try: val = int((message.text or "").strip())
    except: await message.answer("❌ Raqam."); return
    await state.update_data(level_min=val)
    await message.answer("📈 <b>Max stars:</b>")
    await state.set_state(AS.level_max)


@dp.message(AS.level_max)
async def level_max_input(message, state):
    if not is_admin(message.from_user.id): return
    try: val = int((message.text or "").strip())
    except: await message.answer("❌ Raqam."); return
    data = await state.get_data()
    db_exec("INSERT INTO levels (name, emoji, min_stars, max_stars) VALUES (%s, %s, %s, %s)",
            (data["level_name"], data["level_emoji"], data["level_min"], val))
    await state.clear()
    await message.answer("✅ <b>Daraja qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_level_list")
async def del_level_list(cb):
    if not is_admin(cb.from_user.id): return
    b = InlineKeyboardBuilder()
    for lvl in get_levels():
        if "id" not in lvl: continue
        b.button(text=f"❌ {lvl.get('emoji', '')} {lvl.get('name', '')}", callback_data=f"dellvl_{lvl['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_levels")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("dellvl_"))
async def del_level_do(cb):
    if not is_admin(cb.from_user.id): return
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
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text(f"👤 <b>USER BOSHQARISH</b>\n{DIV}\nUser ID kiriting:", parse_mode="HTML")
    await state.set_state(AS.user_id)
    await cb.answer()


@dp.message(AS.user_id)
async def user_info(message, state):
    if not is_admin(message.from_user.id): return
    try: uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌"); return
    user = get_user(uid)
    if not user:
        await message.answer("❌ Topilmadi."); return
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
    if not is_admin(cb.from_user.id): return
    uid = int(cb.data.replace("tog_", ""))
    user = get_user(uid)
    if not user: return
    new_val = 0 if user["is_banned"] else 1
    update_user(uid, is_banned=new_val)
    try: await cb.message.edit_reply_markup(reply_markup=user_manage_kb(uid, new_val))
    except: pass
    await cb.answer("✅")


@dp.callback_query(F.data.startswith("adp_"))
async def add_stars_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await state.update_data(target_uid=int(cb.data.replace("adp_", "")), action="add")
    await cb.message.edit_text("➕ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()


@dp.callback_query(F.data.startswith("rem_"))
async def remove_stars_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await state.update_data(target_uid=int(cb.data.replace("rem_", "")), action="remove")
    await cb.message.edit_text("➖ <b>Miqdor:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_amount)
    await cb.answer()


@dp.message(AS.stars_amount)
async def stars_amount_input(message, state):
    if not is_admin(message.from_user.id): return
    try: amount = int((message.text or "").strip())
    except: await message.answer("❌"); return
    if amount <= 0:
        await message.answer("❌ >0"); return
    await state.update_data(stars_amount=amount)
    await message.answer("📝 <b>Sabab:</b>", parse_mode="HTML")
    await state.set_state(AS.stars_reason)


@dp.message(AS.stars_reason)
async def stars_reason_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    reason = html.escape(message.text.strip())
    data = await state.get_data()
    uid = data["target_uid"]
    amount = data["stars_amount"]
    action = data.get("action", "add")
    user = get_user(uid)
    if not user:
        await message.answer("❌"); await state.clear(); return
    if action == "add":
        new_stars = add_stars(uid, amount)
        old_stars = new_stars - amount
    else:
        new_stars = spend_stars(uid, amount)
        if new_stars is None:
            await message.answer(f"❌ Faqat {user['stars']} ⭐"); return
        old_stars = new_stars + amount
    await state.clear()
    u_lang = get_user_lang(uid)
    try:
        key = "stars_added" if action == "add" else "stars_removed"
        await bot.send_message(uid, T(u_lang, key, n=format_number(amount), reason=reason,
                                      total=format_number(new_stars)), parse_mode="HTML")
    except: pass
    if action == "add": await check_level_up(uid, old_stars, new_stars)
    sign = "➕" if action == "add" else "➖"
    await message.answer(f"✅ {sign} <b>{format_number(amount)} ⭐</b>\n📝 {reason}\n💰 <b>{format_number(new_stars)} ⭐</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data.startswith("msg_"))
async def user_msg_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await state.update_data(target_uid=int(cb.data.replace("msg_", "")))
    await cb.message.edit_text("✉️ <b>Xabar:</b>", parse_mode="HTML")
    await state.set_state(AS.user_msg)
    await cb.answer()


@dp.message(AS.user_msg)
async def user_msg_send(message, state):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    try:
        await message.copy_to(chat_id=data["target_uid"])
        await message.answer("✅")
    except Exception as e: await message.answer(f"❌ {esc(e)}", parse_mode="HTML")
    await state.clear()
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))

# ─────────── Adminlar ───────────
@dp.callback_query(F.data == "a_admins")
async def a_admins(cb):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌", show_alert=True); return
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
    if not is_super_admin(cb.from_user.id): return
    await cb.message.edit_text("👑 <b>Admin ID:</b>", parse_mode="HTML")
    await state.set_state(AS.add_admin_id)
    await cb.answer()


@dp.message(AS.add_admin_id)
async def add_admin_do(message, state):
    if not is_super_admin(message.from_user.id): return
    try: uid = int((message.text or "").strip())
    except: await message.answer("❌"); return
    user = get_user(uid)
    if not user or uid in SUPER_ADMIN_IDS:
        await message.answer("❌"); return
    add_admin(uid, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ <b>{esc(user['first_name'])}</b> admin!", parse_mode="HTML")
    try: await bot.send_message(uid, "🎉 <b>Siz admin!</b>\n\n/admin", parse_mode="HTML")
    except: pass
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_admin_list")
async def del_admin_list(cb):
    if not is_super_admin(cb.from_user.id): return
    b = InlineKeyboardBuilder()
    for a in list_admins():
        if a["user_id"] in SUPER_ADMIN_IDS: continue
        u = get_user(a["user_id"])
        name = u["first_name"] if u else "N/A"
        b.button(text=f"❌ {html.unescape(name)}", callback_data=f"deladmin_{a['user_id']}")
    b.button(text="⬅️", callback_data="a_admins")
    b.adjust(1)
    await cb.message.edit_text("🗑", reply_markup=b.as_markup())
    await cb.answer()


@dp.callback_query(F.data.startswith("deladmin_"))
async def del_admin_do(cb):
    if not is_super_admin(cb.from_user.id): return
    uid = int(cb.data.replace("deladmin_", ""))
    if uid in SUPER_ADMIN_IDS:
        await cb.answer("❌", show_alert=True); return
    remove_admin(uid)
    await cb.answer("✅")
    await a_admins(cb)

# ─────────── Konkurslar ───────────
@dp.callback_query(F.data == "a_contests")
async def a_contests(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM contests ORDER BY id DESC LIMIT 10", fetchall=True) or []
    text = f"{box_title('🏆 KONKURSLAR')}\n\n"
    if rows:
        for c in rows:
            icon = "🟢" if c["status"] == "active" else "🔴"
            text += f"{icon} <b>#{c['id']}</b> {esc(c['title'])}\n   🎁 {esc(c['reward_name'])}\n   📅 {(c['start_at'] or '')[:10]} → {(c['end_at'] or '')[:10]}\n\n"
    else: text += "<i>Konkurslar yo'q</i>\n"
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
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("🏆 <b>Konkurs nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.contest_title)
    await cb.answer()


@dp.message(AS.contest_title)
async def contest_title_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(c_title=message.text.strip())
    await message.answer("📝 <b>Tavsif:</b>")
    await state.set_state(AS.contest_desc)


@dp.message(AS.contest_desc)
async def contest_desc_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(c_desc=message.text.strip())
    await message.answer("🎁 <b>Sovrin nomi:</b>")
    await state.set_state(AS.contest_reward_name)


@dp.message(AS.contest_reward_name)
async def contest_reward_name_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(c_reward_name=message.text.strip())
    await message.answer("😀 <b>Sovrin emoji:</b>")
    await state.set_state(AS.contest_reward_emoji)


@dp.message(AS.contest_reward_emoji)
async def contest_reward_emoji_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(c_reward_emoji=message.text.strip())
    await message.answer("📅 <b>Necha kun?</b>")
    await state.set_state(AS.contest_days)


@dp.message(AS.contest_days)
async def contest_days_input(message, state):
    if not is_admin(message.from_user.id): return
    try:
        days = int((message.text or "").strip())
        if days < 1 or days > 365: raise ValueError
    except ValueError:
        await message.answer("❌ 1-365."); return
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
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM contests WHERE status='active'", fetchall=True) or []
    if not rows:
        await cb.answer("— Faol konkurs yo'q", show_alert=True); return
    b = InlineKeyboardBuilder()
    for c in rows: b.button(text=f"🏁 #{c['id']} {c['title']}", callback_data=f"fincontest_{c['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_contests")
    b.adjust(1)
    await cb.message.edit_text("🏁 <b>Tugatish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("fincontest_"))
async def finish_contest_do(cb):
    if not is_admin(cb.from_user.id): return
    cid = int(cb.data.replace("fincontest_", ""))
    c = db_exec("SELECT * FROM contests WHERE id=%s", (cid,), fetch=True)
    if not c:
        await cb.answer("—", show_alert=True); return
    winner = db_exec("""SELECT u.user_id, u.first_name, COUNT(r.user_id) AS cnt
        FROM users r JOIN users u ON r.referrer_id = u.user_id
        WHERE r.is_verified=1 AND r.joined_at >= %s
        GROUP BY u.user_id, u.first_name ORDER BY cnt DESC LIMIT 1""",
        (c["start_at"],), fetch=True)
    if not winner:
        await cb.answer("— Qatnashuvchi yo'q", show_alert=True); return
    db_exec("UPDATE contests SET status='finished', winner_id=%s, winner_referrals=%s WHERE id=%s",
            (winner["user_id"], winner["cnt"], cid))
    await notify_admins(f"🏁 <b>KONKURS TUGADI!</b>\n\n🏆 {esc(c['title'])}\n\n🥇 <b>G'olib:</b> {esc(winner['first_name'])}\n👥 {winner['cnt']} ta referal")
    try:
        await bot.send_message(winner["user_id"],
            f"🎉 <b>TABRIKLAYMIZ!</b>\n\n<b>{esc(c['title'])}</b> konkursida g'olib bo'ldingiz!\n\n🏆 {winner['cnt']} ta referal\n🎁 {esc(c['reward_emoji'])} {esc(c['reward_name'])}",
            parse_mode="HTML")
    except: pass
    await cb.answer("✅")
    await a_contests(cb)


@dp.callback_query(F.data == "del_contest_list")
async def del_contest_list(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM contests ORDER BY id DESC LIMIT 20", fetchall=True) or []
    if not rows:
        await cb.answer("—", show_alert=True); return
    b = InlineKeyboardBuilder()
    for c in rows: b.button(text=f"❌ #{c['id']} {c['title'][:30]}", callback_data=f"delcontest_{c['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_contests")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delcontest_"))
async def del_contest_do(cb):
    if not is_admin(cb.from_user.id): return
    db_exec("DELETE FROM contests WHERE id=%s", (int(cb.data.replace("delcontest_", "")),))
    await cb.answer("✅")
    await a_contests(cb)

# ─────────── Vazifalar (admin) ───────────
@dp.callback_query(F.data == "a_tasks")
async def a_tasks(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM tasks ORDER BY id", fetchall=True) or []
    text = f"{box_title('📌 VAZIFALAR')}\n\n"
    for t in rows:
        icon = "🟢" if t["is_active"] else "🔴"
        text += f"{icon} <b>#{t['id']}</b> {esc(t['emoji'])} {esc(t['title'])}\n   +{t['reward']} ⭐ | {esc(t['action'])}\n\n"
    if not rows: text += "<i>Vazifalar yo'q</i>\n"
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
    if not is_admin(cb.from_user.id): return
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
    if not is_admin(cb.from_user.id): return
    tid = int(cb.data.replace("toggletask_", ""))
    db_exec("UPDATE tasks SET is_active = 1 - is_active WHERE id=%s", (tid,))
    await cb.answer("✅")
    await toggle_task_list(cb)


@dp.callback_query(F.data == "add_task")
async def add_task_start(cb, state):
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("📌 <b>Vazifa nomi:</b>", parse_mode="HTML")
    await state.set_state(AS.task_title)
    await cb.answer()


@dp.message(AS.task_title)
async def task_title_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(t_title=message.text.strip())
    await message.answer("😀 <b>Emoji:</b>")
    await state.set_state(AS.task_emoji)


@dp.message(AS.task_emoji)
async def task_emoji_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    await state.update_data(t_emoji=message.text.strip())
    await message.answer("⭐ <b>Mukofot (stars):</b>")
    await state.set_state(AS.task_reward)


@dp.message(AS.task_reward)
async def task_reward_input(message, state):
    if not is_admin(message.from_user.id): return
    try: val = int((message.text or "").strip())
    except: await message.answer("❌ Raqam."); return
    await state.update_data(t_reward=val)
    await message.answer("🔗 <b>Link</b> (yoki /skip):")
    await state.set_state(AS.task_link)


@dp.message(AS.task_link)
async def task_link_input(message, state):
    if not is_admin(message.from_user.id): return
    txt = (message.text or "").strip()
    await state.update_data(t_link=None if txt == "/skip" else txt)
    await message.answer("⚙️ <b>Action:</b>\n\n<code>ref</code> — referal\n<code>sub</code> — obuna\n<code>webapp</code> — Mini App\n<code>profile</code> — profil\n<code>manual</code> — qo'lda", parse_mode="HTML")
    await state.set_state(AS.task_action)


@dp.message(AS.task_action)
async def task_action_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    action = message.text.strip().lower()
    if action not in ("ref", "sub", "webapp", "profile", "manual"):
        await message.answer("❌ Noto'g'ri."); return
    data = await state.get_data()
    db_exec("INSERT INTO tasks (title, emoji, reward, link, action, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
            (data["t_title"], data["t_emoji"], data["t_reward"], data["t_link"], action))
    await state.clear()
    await message.answer("✅ <b>Vazifa qo'shildi!</b>", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_task_list")
async def del_task_list(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM tasks ORDER BY id", fetchall=True) or []
    b = InlineKeyboardBuilder()
    for t in rows: b.button(text=f"❌ #{t['id']} {t['title'][:30]}", callback_data=f"deltask_{t['id']}")
    b.button(text="⬅️ Orqaga", callback_data="a_tasks")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("deltask_"))
async def del_task_do(cb):
    if not is_admin(cb.from_user.id): return
    db_exec("DELETE FROM tasks WHERE id=%s", (int(cb.data.replace("deltask_", "")),))
    await cb.answer("✅")
    await a_tasks(cb)

# ─────────── Promokodlar ───────────
@dp.callback_query(F.data == "a_promocodes")
async def a_promocodes(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM promocodes ORDER BY created_at DESC LIMIT 20", fetchall=True) or []
    text = f"{box_title('🎟 PROMOKODLAR')}\n\n"
    for p in rows: text += f"• <code>{esc(p['code'])}</code> — {p['reward']} ⭐ (qoldi: {p['uses_left']})\n"
    if not rows: text += "<i>Promokodlar yo'q</i>\n"
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
    if not is_admin(cb.from_user.id): return
    await cb.message.edit_text("🎟 <b>Promokod matni:</b>", parse_mode="HTML")
    await state.set_state(AS.promo_code_admin)
    await cb.answer()


@dp.message(AS.promo_code_admin)
async def promo_code_input(message, state):
    if not is_admin(message.from_user.id) or not message.text: return
    code = message.text.strip().upper()
    if db_exec("SELECT 1 FROM promocodes WHERE code=%s", (code,), fetch=True):
        await message.answer("❌ Bu kod bor."); return
    await state.update_data(p_code=code)
    await message.answer("⭐ <b>Mukofot:</b>")
    await state.set_state(AS.promo_reward)


@dp.message(AS.promo_reward)
async def promo_reward_input(message, state):
    if not is_admin(message.from_user.id): return
    try: val = int((message.text or "").strip())
    except: await message.answer("❌ Raqam."); return
    await state.update_data(p_reward=val)
    await message.answer("👥 <b>Necha kishi?</b>")
    await state.set_state(AS.promo_uses)


@dp.message(AS.promo_uses)
async def promo_uses_input(message, state):
    if not is_admin(message.from_user.id): return
    try: uses = int((message.text or "").strip())
    except: await message.answer("❌ Raqam."); return
    data = await state.get_data()
    db_exec("INSERT INTO promocodes (code, reward, uses_left, created_at) VALUES (%s, %s, %s, %s)",
            (data["p_code"], data["p_reward"], uses, now_uz().isoformat()))
    await state.clear()
    await message.answer(f"✅ <b>Promokod!</b>\n\n🎟 <code>{esc(data['p_code'])}</code>\n⭐ +{data['p_reward']}\n👥 {uses} kishi", parse_mode="HTML")
    await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))


@dp.callback_query(F.data == "del_promo_list")
async def del_promo_list(cb):
    if not is_admin(cb.from_user.id): return
    rows = db_exec("SELECT * FROM promocodes ORDER BY created_at DESC LIMIT 20", fetchall=True) or []
    b = InlineKeyboardBuilder()
    for p in rows: b.button(text=f"❌ {p['code']}", callback_data=f"delpromo_{p['code']}")
    b.button(text="⬅️ Orqaga", callback_data="a_promocodes")
    b.adjust(1)
    await cb.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=b.as_markup(), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("delpromo_"))
async def del_promo_do(cb):
    if not is_admin(cb.from_user.id): return
    db_exec("DELETE FROM promocodes WHERE code=%s", (cb.data.replace("delpromo_", ""),))
    await cb.answer("✅")
    await a_promocodes(cb)

# ─────────── USERBOT ───────────
@dp.callback_query(F.data == "a_userbot")
async def a_userbot(cb, state):
    if not is_admin(cb.from_user.id): return
    await state.clear()
    diag = [f"API_ID: {'✅' if API_ID else '❌'}", f"API_HASH: {'✅' if API_HASH else '❌'}",
            f"SESSION: {'✅' if SESSION_STRING else '❌'}"]
    disabled = get_setting("userbot_disabled", "0") == "1"
    if not tg_client:
        status = "⛔ O'chirilgan" if disabled else "❌ Ulanmagan"
        bal_text = "—"
    else:
        try: me = await tg_client.get_me(); status = f"✅ <b>{esc(me.first_name or '')}</b>"
        except Exception as e: status = f"⚠️ {esc(e)}"
        try:
            st = await tg_client(functions.payments.GetStarsStatusRequest(peer=tt.InputPeerSelf()))
            bal = getattr(st.balance, "amount", st.balance)
            bal_text = f"<b>{format_number(bal)} ⭐</b>"
        except: bal_text = "<i>o'qib bo'lmadi</i>"
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
    try: await cb.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    except: pass
    await cb.answer()


@dp.callback_query(F.data == "a_userbot_test")
async def a_userbot_test(cb):
    if not is_admin(cb.from_user.id): return
    if not tg_client:
        await cb.answer("❌ Userbot ulanmagan!", show_alert=True); return
    await cb.answer("⏳...")
    try:
        me = await tg_client.get_me()
        try:
            st = await tg_client(functions.payments.GetStarsStatusRequest(peer=tt.InputPeerSelf()))
            bal = getattr(st.balance, "amount", st.balance)
        except Exception as e: bal = f"xato: {e}"
        try:
            res = await tg_client(functions.payments.GetStarGiftsRequest(hash=0))
            gift_count = len(getattr(res, "gifts", []))
        except Exception as e: gift_count = f"xato: {e}"
        await cb.message.answer(f"🧪 <b>USERBOT TEST</b>\n\n👤 {esc(me.first_name or '')}\n🆔 <code>{me.id}</code>\n📞 {esc(me.phone or '—')}\n💰 {bal} ⭐\n🎁 {gift_count}\n\n✅ Userbot ishlayapti!", parse_mode="HTML")
    except Exception as e:
        await cb.message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")


@dp.callback_query(F.data == "a_userbot_change")
async def a_userbot_change(cb, state):
    if not is_super_admin(cb.from_user.id):
        await cb.answer("❌ Faqat bosh admin!", show_alert=True); return
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
        await cb.answer("❌ Faqat bosh admin!", show_alert=True); return
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
    if not is_super_admin(cb.from_user.id): return
    await state.clear()
    old = tg_client; tg_client = None
    if old:
        try: await old.disconnect()
        except: pass
    API_ID = 0; API_HASH = ""; SESSION_STRING = ""
    for k in ("userbot_api_id", "userbot_api_hash", "userbot_session"):
        set_setting(k, "")
    set_setting("userbot_disabled", "1")
    await a_userbot(cb, state)


@dp.message(AS.userbot_api)
async def userbot_api_input(message, state):
    if not is_super_admin(message.from_user.id): return
    try: api_id = int((message.text or "").strip())
    except: await message.answer("❌ Raqam."); return
    await state.update_data(new_api_id=api_id)
    await message.answer("2️⃣ API_HASH:")
    await state.set_state(AS.userbot_hash)


@dp.message(AS.userbot_hash)
async def userbot_hash_input(message, state):
    if not is_super_admin(message.from_user.id): return
    api_hash = (message.text or "").strip()
    if len(api_hash) < 10:
        await message.answer("❌ Juda qisqa."); return
    await state.update_data(new_api_hash=api_hash)
    await message.answer("3️⃣ SESSION_STRING:")
    await state.set_state(AS.userbot_session)


@dp.message(AS.userbot_session)
async def userbot_session_input(message, state):
    if not is_super_admin(message.from_user.id): return
    session_str = (message.text or "").strip()
    if len(session_str) < 30:
        await message.answer("❌ Juda qisqa."); return
    data = await state.get_data()
    api_id, api_hash = data.get("new_api_id"), data.get("new_api_hash")
    await message.answer("⏳...")
    try:
        test_client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await test_client.connect()
        if not await test_client.is_user_authorized():
            await test_client.disconnect()
            await message.answer("❌ Yaroqsiz."); await state.clear(); return
        me = await test_client.get_me()
        global tg_client, API_ID, API_HASH, SESSION_STRING
        if tg_client:
            try: await tg_client.disconnect()
            except: pass
        tg_client = test_client
        API_ID = api_id; API_HASH = api_hash; SESSION_STRING = session_str
        set_setting("userbot_api_id", str(api_id))
        set_setting("userbot_api_hash", api_hash)
        set_setting("userbot_session", security.enc(session_str))
        set_setting("userbot_disabled", "0")
        await state.clear()
        try: await message.delete()
        except: pass
        await message.answer(f"✅ <b>USERBOT ULANDI!</b>\n\n👤 {esc(me.first_name or '')}", parse_mode="HTML")
        await message.answer("🛠 Admin Panel", reply_markup=admin_menu(message.from_user.id))
    except Exception as e:
        await message.answer(f"❌ Xato: {esc(e)}", parse_mode="HTML")
        await state.clear()

# ═══════════ WEB APP API ═══════════
def validate_init_data(init_data, max_age=86400):
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = pairs.pop("hash", None)
        if not recv_hash: return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash): return None
        if time.time() - int(pairs.get("auth_date", "0")) > max_age: return None
        return json.loads(pairs["user"])
    except Exception:
        return None


def _count_refs(uid, since=None):
    if since:
        r = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1 AND joined_at >= %s", (uid, since), fetch=True)
    else:
        r = db_exec("SELECT COUNT(*) AS c FROM users WHERE referrer_id=%s AND is_verified=1", (uid,), fetch=True)
    return r["c"] if r else 0


def build_profile(uid):
    u = db_exec("SELECT * FROM users WHERE user_id=%s", (uid,), fetch=True)
    if not u: return {"error": "Foydalanuvchi topilmadi. Botda /start bosing."}
    rank = db_exec("SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0", (u["stars"],), fetch=True)
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    lvl = get_user_level(u["stars"])
    return {
        "user_id": u["user_id"], "first_name": u["first_name"] or "User",
        "username": u["username"], "stars": u["stars"], "donated": total_donated(uid),
        "level_name": lvl.get("name", "Bronza"), "level_emoji": lvl.get("emoji", "🥉"),
        "level_min": lvl.get("min_stars", 0), "level_max": lvl.get("max_stars", 10),
        "referrals": _count_refs(uid), "week_referrals": _count_refs(uid, week_ago),
        "rank": rank["rank"] if rank else 0,
    }


def build_rating(uid):
    me_stars = db_exec("SELECT first_name, stars FROM users WHERE user_id=%s", (uid,), fetch=True)
    if not me_stars: return {"error": "Foydalanuvchi topilmadi."}
    rows = db_exec("SELECT user_id, first_name, stars FROM users WHERE is_verified=1 AND is_banned=0 ORDER BY stars DESC, user_id ASC LIMIT 10", fetchall=True) or []
    stars_top = [{"rank": i, "name": r["first_name"] or "User", "stars": r["stars"],
                  "level_emoji": get_user_level(r["stars"]).get("emoji", ""),
                  "is_me": r["user_id"] == uid} for i, r in enumerate(rows, 1)]
    stars_rank = db_exec("SELECT COUNT(*) + 1 AS rank FROM users WHERE stars > %s AND is_verified=1 AND is_banned=0", (me_stars["stars"],), fetch=True)
    d_rows = db_exec("""SELECT u.user_id, u.first_name, COALESCE(SUM(d.stars),0) AS total, COUNT(d.id) AS count
        FROM donations d JOIN users u ON d.user_id=u.user_id GROUP BY u.user_id, u.first_name ORDER BY total DESC LIMIT 10""", fetchall=True) or []
    donate_top = [{"rank": i, "name": r["first_name"] or "User", "total": int(r["total"]),
                   "count": int(r["count"]), "is_me": r["user_id"] == uid} for i, r in enumerate(d_rows, 1)]
    me_d = db_exec("SELECT COALESCE(SUM(stars),0) AS total, COUNT(id) AS count FROM donations WHERE user_id=%s", (uid,), fetch=True) or {"total": 0, "count": 0}
    my_don_total = int(me_d["total"]); my_don_count = int(me_d["count"])
    don_rank = db_exec("SELECT COUNT(*) + 1 AS rank FROM (SELECT user_id, SUM(stars) AS total FROM donations GROUP BY user_id HAVING SUM(stars) > %s) t", (my_don_total,), fetch=True)
    r_rows = db_exec("""SELECT u.user_id, u.first_name, COUNT(r.user_id) AS cnt FROM users r
        JOIN users u ON r.referrer_id=u.user_id WHERE r.is_verified=1
        GROUP BY u.user_id, u.first_name ORDER BY cnt DESC LIMIT 10""", fetchall=True) or []
    ref_top = [{"rank": i, "name": r["first_name"] or "User", "count": int(r["cnt"]),
                "is_me": r["user_id"] == uid} for i, r in enumerate(r_rows, 1)]
    my_ref = _count_refs(uid)
    ref_rank = db_exec("""SELECT COUNT(*) + 1 AS rank FROM (SELECT referrer_id, COUNT(*) AS cnt FROM users
        WHERE is_verified=1 AND referrer_id<>0 GROUP BY referrer_id HAVING COUNT(*) > %s) t""", (my_ref,), fetch=True)
    return {
        "stars": {"top": stars_top, "me": {"rank": stars_rank["rank"] if stars_rank else 0, "name": me_stars["first_name"] or "User", "stars": me_stars["stars"]}},
        "donate": {"top": donate_top, "me": {"rank": don_rank["rank"] if don_rank else 0, "name": me_stars["first_name"] or "User", "total": my_don_total, "count": my_don_count}},
        "ref": {"top": ref_top, "me": {"rank": ref_rank["rank"] if ref_rank else 0, "name": me_stars["first_name"] or "User", "count": my_ref}},
    }


def build_levels(uid):
    u = db_exec("SELECT stars FROM users WHERE user_id=%s", (uid,), fetch=True)
    return {"stars": u["stars"] if u else 0,
            "levels": [{"name": l.get("name", ""), "emoji": l.get("emoji", ""),
                        "min": l.get("min_stars", 0), "max": l.get("max_stars", 0)} for l in get_levels()]}


def build_contest_api(uid):
    active_row = get_active_contest()
    active = None
    if active_row:
        lb = get_contest_leaderboard(active_row, uid)
        active = {"title": active_row["title"], "description": active_row["description"],
                  "reward_emoji": active_row["reward_emoji"], "reward_name": active_row["reward_name"],
                  "target": active_row["target"], "end_at": active_row["end_at"],
                  "leaders": lb["leaders"], "me": lb["me"]}
    finished_rows = db_exec("""SELECT c.*, u.first_name AS winner_name FROM contests c
        LEFT JOIN users u ON c.winner_id = u.user_id WHERE c.status='finished' ORDER BY c.id DESC LIMIT 5""", fetchall=True) or []
    finished = [{"title": r["title"], "reward_emoji": r["reward_emoji"], "reward_name": r["reward_name"],
                 "winner_name": r["winner_name"], "winner_referrals": r["winner_referrals"]} for r in finished_rows]
    return {"active": active, "finished": finished}


def build_bonus_api(uid):
    return {"daily": check_daily_bonus(uid), "tasks": get_user_tasks(uid)}


def build_referrals(uid):
    week_ago = (now_uz() - timedelta(days=7)).isoformat()
    rows = db_exec("SELECT first_name, joined_at FROM users WHERE referrer_id=%s AND is_verified=1 ORDER BY joined_at DESC LIMIT 50", (uid,), fetchall=True) or []
    return {"total": _count_refs(uid), "week": _count_refs(uid, week_ago),
            "reward": int(get_setting("stars_per_referral", "2")),
            "items": [{"name": r["first_name"] or "User", "joined_at": r["joined_at"]} for r in rows]}


def build_advertise(uid):
    services = get_ad_services(active_only=True)
    return {"services": [{"id": s["id"], "title": s["title"], "description": s["description"],
                          "hours": s["hours"], "price_uzs": s["price_uzs"], "bonus_subs": s["bonus_subs"]} for s in services]}


CORS_HEADERS = {"Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}


@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS": return web.Response(headers=CORS_HEADERS)
    resp = await handler(request)
    resp.headers.update(CORS_HEADERS)
    return resp


def make_api(builder):
    async def handler(request):
        tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
        if not tg_user or "id" not in tg_user:
            return web.json_response({"error": "Ruxsat yo'q"}, status=401)
        uid = int(tg_user["id"])
        if not get_user(uid):
            return web.json_response({"error": "Botda /start bosing"}, status=403)
        try: data = await asyncio.to_thread(builder, uid)
        except Exception as e:
            logger.error(f"API xato: {e}")
            return web.json_response({"error": "Server xatosi"}, status=500)
        return web.json_response(data)
    return handler


async def health(request): return web.Response(text="OK")


async def index(request):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(p): return web.FileResponse(p)
    return web.Response(text=BOT_NAME)


async def api_claim(request):
    tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not tg_user or "id" not in tg_user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=401)
    uid = int(tg_user["id"])
    try: body = await request.json()
    except: return web.json_response({"error": "Xato"}, status=400)
    cid = str(body.get("id", ""))
    lang = get_user_lang(uid)
    if cid == "daily":
        res = await asyncio.to_thread(claim_daily_bonus, uid)
        if res is None:
            return web.json_response({"error": T(lang, "bonus_already")}, status=400)
        try:
            await bot.send_message(uid, T(lang, "stars_added", n=res["reward"], reason="Kunlik bonus",
                                          total=(get_user(uid) or {}).get("stars", 0)), parse_mode="HTML")
        except: pass
        return web.json_response({"reward": res["reward"], "streak": res["streak"]})
    if cid.isdigit():
        reward = await asyncio.to_thread(claim_task_reward, uid, int(cid))
        if reward is None:
            return web.json_response({"error": "Mukofot olish mumkin emas"}, status=400)
        try:
            await bot.send_message(uid, T(lang, "stars_added", n=reward, reason="Vazifa mukofoti",
                                          total=(get_user(uid) or {}).get("stars", 0)), parse_mode="HTML")
        except: pass
        return web.json_response({"reward": reward})
    return web.json_response({"error": "Noma'lum amal"}, status=400)


async def api_promo(request):
    tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not tg_user or "id" not in tg_user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=401)
    uid = int(tg_user["id"])
    try: body = await request.json()
    except: return web.json_response({"error": "Xato"}, status=400)
    code = str(body.get("code", "")).strip().upper()
    lang = get_user_lang(uid)
    reward, err2 = await asyncio.to_thread(use_promocode, uid, code)
    if err2: return web.json_response({"error": T(lang, err2)}, status=400)
    try:
        await bot.send_message(uid, T(lang, "stars_added", n=reward, reason=f"Promokod: {code}",
                                      total=(get_user(uid) or {}).get("stars", 0)), parse_mode="HTML")
    except: pass
    return web.json_response({"reward": reward})


async def api_ad_buy(request):
    tg_user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not tg_user or "id" not in tg_user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=401)
    uid = int(tg_user["id"])
    try: body = await request.json()
    except: return web.json_response({"error": "Xato"}, status=400)
    sid = int(body.get("service_id", 0))
    s = await asyncio.to_thread(get_ad_service, sid)
    if not s or not s["is_active"]:
        return web.json_response({"error": "Tarif topilmadi"}, status=400)
    await asyncio.to_thread(add_ad_request, uid, s)
    user = get_user(uid)
    uname = f"@{user['username']}" if user and user.get("username") else "—"
    await notify_admins(f"📢 <b>YANGI REKLAMA SO'ROVI!</b>\n\n👤 {user['first_name'] if user else 'User'} ({uname})\n"
                       f"🆔 <code>{uid}</code>\n\n📋 <b>{esc(s['title'])}</b>\n💰 {format_number(s['price_uzs'])} so'm")
    return web.json_response({"ok": True})

# ═══════════ USERBOT ULANISH ═══════════
async def init_userbot():
    global tg_client, API_ID, API_HASH, SESSION_STRING
    if get_setting("userbot_disabled", "0") == "1":
        API_ID = 0; API_HASH = ""; SESSION_STRING = ""
        logger.info("Userbot o'chirilgan")
        return
    db_api_id = get_setting("userbot_api_id", "")
    db_api_hash = get_setting("userbot_api_hash", "")
    db_session = get_setting("userbot_session", "")
    if db_api_id and db_api_hash and db_session:
        try: API_ID = int(db_api_id)
        except: pass
        API_HASH = db_api_hash
        SESSION_STRING = security.dec(db_session)
    if not API_ID or not API_HASH or not SESSION_STRING:
        logger.warning("❌ Userbot sozlamalari to'liq emas")
        return
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect(); return
        tg_client = client
        me = await client.get_me()
        logger.info(f"✅ Userbot: {me.first_name} (id {me.id})")
    except Exception as e:
        logger.error(f"❌ Userbot ulanmadi: {e}")
        tg_client = None

# ═══════════ ISHGA TUSHIRISH ═══════════
async def main():
    init_db()
    await init_userbot()
    security.setup(dp, db_exec=db_exec, now_uz=now_uz, T=T, LANGS=LANGS,
                   is_admin=is_admin, check_subs=check_subs, subs_kb=subs_kb)

    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    for path, builder in (
        ("/api/profile", build_profile), ("/api/rating", build_rating),
        ("/api/levels", build_levels), ("/api/contest", build_contest_api),
        ("/api/bonus", build_bonus_api), ("/api/referrals", build_referrals),
        ("/api/advertise", build_advertise),
    ):
        app.router.add_get(path, make_api(builder))
    app.router.add_post("/api/claim", api_claim)
    app.router.add_post("/api/promo", api_promo)
    app.router.add_post("/api/ad_buy", api_ad_buy)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Web server {PORT} portda ishga tushdi")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"{BOT_NAME} ishga tushdi")
    try: await dp.start_polling(bot)
    finally:
        if tg_client: await tg_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
