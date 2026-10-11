# ═══════════════════════════════════════════════════════════
# main.py — PROFESSIONAL DIZAYN PATCH
# 5 ta qadam. Tepadan pastga bajaring.
# ═══════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────
# QADAM 1. Importga qo'shing (aiogram.types import qatoriga):
#   InlineKeyboardButton, InlineKeyboardMarkup
# Masalan:
# from aiogram.types import (
#     BufferedInputFile, WebAppInfo, LabeledPrice,
#     ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
#     InlineKeyboardButton, InlineKeyboardMarkup,
# )
# ───────────────────────────────────────────────────────────


# ───────────────────────────────────────────────────────────
# QADAM 2. "CHIZIQLAR (dizayn)" bo'limini (box_title, BOX_BOTTOM,
# BOX_MID) TO'LIQ shu blok bilan almashtiring:
# ───────────────────────────────────────────────────────────
DIV = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
BOX_MID = DIV
BOX_BOTTOM = ""          # pastki chiziq endi kerak emas


def box_title(title: str) -> str:
    """Sarlavha: qalin matn + ingichka chiziq."""
    return f"<b>{title}</b>\n{DIV}"


def kv(icon: str, label: str, value) -> str:
    """Bir qatorli 'belgi  Nomi — qiymat' ko'rinishi."""
    return f"{icon} <b>{label}:</b> {value}"


def progress_bar(cur: int, lo: int, hi: int, width: int = 12) -> tuple:
    """(bar, foiz) qaytaradi. Eng yuqori daraja uchun to'liq bar."""
    if hi >= 999_999_999 or hi <= lo:
        return "▰" * width, 100
    pct = max(0, min(100, int((cur - lo) / (hi - lo) * 100)))
    filled = round(pct / 100 * width)
    return "▰" * filled + "▱" * (width - filled), pct


def format_number(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


# ───────────────────────────────────────────────────────────
# QADAM 3. LANGS lug'ati TUGAGANIDAN KEYIN (def T(...) dan oldin)
# shu blokni qo'ying. U barcha 3 tildagi eski chiziqlarni yangisiga
# almashtiradi va "welcome" matnini yangilaydi.
# ───────────────────────────────────────────────────────────
_OLD_DIV = "━" * 19
for _code in LANGS:
    for _k, _v in list(LANGS[_code].items()):
        if isinstance(_v, str) and _OLD_DIV in _v:
            LANGS[_code][_k] = _v.replace(_OLD_DIV, DIV)

LANGS["uz"]["welcome"] = (
    "✨ <b>Xush kelibsiz, {name}!</b>\n"
    f"{DIV}\n"
    "🚀 <b>StarRush</b> — Stars yig'ish platformasi\n\n"
    "👥  Do'stlarni taklif qiling\n"
    "🎁  Stars to'plab, Gift oling\n"
    "🔥  Kunlik bonus va vazifalar\n"
    "🏆  Reytingda birinchi bo'ling\n"
    f"{DIV}\n"
    "Kerakli bo'limni tanlang 👇"
)
LANGS["ru"]["welcome"] = (
    "✨ <b>Добро пожаловать, {name}!</b>\n"
    f"{DIV}\n"
    "🚀 <b>StarRush</b> — платформа для сбора Stars\n\n"
    "👥  Приглашайте друзей\n"
    "🎁  Копите Stars и получайте Gift\n"
    "🔥  Ежедневный бонус и задания\n"
    "🏆  Станьте первым в рейтинге\n"
    f"{DIV}\n"
    "Выберите раздел 👇"
)
LANGS["en"]["welcome"] = (
    "✨ <b>Welcome, {name}!</b>\n"
    f"{DIV}\n"
    "🚀 <b>StarRush</b> — the Stars collecting platform\n\n"
    "👥  Invite friends\n"
    "🎁  Collect Stars and get Gifts\n"
    "🔥  Daily bonus and tasks\n"
    "🏆  Be #1 on the leaderboard\n"
    f"{DIV}\n"
    "Choose a section 👇"
)


# ───────────────────────────────────────────────────────────
# QADAM 4. main_menu(uid) funksiyasini shu bilan almashtiring.
# Guruhlangan, toza tartib: asosiy -> daromad -> pul -> qo'shimcha.
# ───────────────────────────────────────────────────────────
def main_menu(uid):
    lang = get_user_lang(uid)
    cb = lambda text, data: InlineKeyboardButton(text=text, callback_data=data)

    rows = [
        [cb(T(lang, "profile"), "m_profile"), cb(T(lang, "stats"), "m_stats")],
        [cb("🔥 " + T(lang, "bonus_menu"), "m_bonus"), cb("📌 " + T(lang, "tasks_menu"), "m_tasks")],
        [cb("🏆 " + T(lang, "contest_menu"), "m_contest"), cb("🎟 " + T(lang, "promo_menu"), "m_promo")],
        [cb(T(lang, "ref_link"), "m_reflink")],
        [cb(T(lang, "withdraw"), "m_withdraw"), cb(T(lang, "rating"), "m_rating")],
        [cb(T(lang, "gift_stars"), "m_gift"), cb(T(lang, "donate"), "m_donate")],
    ]
    extra = [cb(T(lang, "banner"), "m_banner")]
    if WEBAPP_URL:
        extra.append(InlineKeyboardButton(text=T(lang, "webapp"), web_app=WebAppInfo(url=WEBAPP_URL)))
    rows.append(extra)
    rows.append([cb(T(lang, "review"), "m_review"), cb(T(lang, "support"), "m_support")])
    rows.append([cb("🌐 Til / Язык / Lang", "m_lang")])
    if is_admin(uid):
        rows.append([cb(T(lang, "admin"), "m_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ───────────────────────────────────────────────────────────
# QADAM 5. cb_profile ichidagi `text = (...)` blokini va
# cb_stats ichidagi `text = (...)` blokini quyidagilar bilan
# almashtiring (o'zgaruvchilar o'sha funksiyalarda allaqachon bor).
# ───────────────────────────────────────────────────────────

# ---- cb_profile: eski `text = (f"{box_title('👤 PROFIL')}..." o'rniga ----
#
#     bar, pct = progress_bar(user["stars"], lvl.get("min_stars", 0), lvl.get("max_stars", 10))
#     text = (
#         f"{box_title('👤 PROFIL')}\n"
#         f"<b>{user['first_name'] or 'N/A'}</b>  ·  {uname}\n"
#         f"<code>{user['user_id']}</code>\n\n"
#         f"{lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n"
#         f"{bar}  {pct}%\n"
#         f"⭐ <b>{format_number(user['stars'])}</b> Stars\n"
#         f"⬆️ Keyingi: {next_text}\n\n"
#         f"{DIV}\n"
#         f"{kv('👥', 'Takliflar', format_number(ref_count) + ' ta')}\n"
#         f"{kv('🏆', \"O'rin\", '#' + format_number(rank))}\n"
#         f"{kv('💝', 'Donat', format_number(donated) + ' ⭐')}\n\n"
#         f"{DIV}\n"
#         f"{ver} Tasdiqlangan   {ban} Holat\n"
#         f"📅 Qo'shilgan: {joined}"
#     )

# ---- cb_stats: eski `text = (f"{box_title('📊 STATISTIKA')}..." o'rniga ----
#
#     bar, pct = progress_bar(user["stars"], lvl_min, lvl_max)
#     text = (
#         f"{box_title('📊 STATISTIKA')}\n"
#         f"<b>{user['first_name']}</b>\n\n"
#         f"{lvl.get('emoji', '🥉')} <b>{lvl.get('name', 'Bronza')}</b>\n"
#         f"{bar}  {pct}%\n"
#         f"<b>{format_number(user['stars'])}</b> / {format_number(lvl_max) if lvl_max < 999_999_999 else '∞'} ⭐\n"
#         f"⬆️ Keyingi: {next_text}  (yana <b>{format_number(need)}</b> ⭐)\n\n"
#         f"{DIV}\n"
#         f"{kv('⭐', 'Stars', format_number(user['stars']))}\n"
#         f"{kv('💝', 'Donat', format_number(donated) + ' ⭐')}\n"
#         f"{kv('👥', 'Referallar', format_number(ref_count) + ' ta')}\n"
#         f"{kv('📈', 'Bu hafta', '+' + format_number(week_ref_count))}\n"
#         f"{kv('🏆', \"O'rin\", '#' + format_number(rank))}"
#     )
#
# Eslatma: f-string ichida teskari slash ishlatilmasin. Python 3.12 dan
# past versiyada `\"O'rin\"` xato beradi, shuning uchun uni oldindan
# o'zgaruvchiga oling:  lbl_rank = "O'rin"  va  kv('🏆', lbl_rank, ...)

# ADMIN_TITLE ni ham yangilang:
ADMIN_TITLE = (
    "<b>🛠 ADMIN PANEL</b>\n"
    f"{DIV}\n"
    "Kerakli bo'limni tanlang 👇"
)
