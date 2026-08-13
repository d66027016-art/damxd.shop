import time
import asyncio
from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode

import database.db as db
from config import OWNER_IDS
from functions.card_utils import parse_gen_input, generate_cards
from functions.bin_lookup import lookup_bin
from functions.force_join import check_force_join, force_join_keyboard, FORCE_JOIN_MSG
from functions.emojis import EMOJI, EMOJI_PLAIN

router = Router()


def _build_gen_text(cards, prefix, count, bin_info, elapsed_ms, display_prefix):
    """Build gen result matching screenshot style"""
    brand = bin_info.get("brand", "")
    btype = bin_info.get("type", "")
    level = bin_info.get("category", "")
    bank = bin_info.get("bank", "")
    flag = bin_info.get("flag", "")
    country = bin_info.get("country_name", "")
    iso = bin_info.get("country_code", "")

    cards_text = "\n".join(f"<code>{c}</code>" for c in cards)

    text = (
        f"<blockquote>🐸 <b>CC Generator</b> 🐸 ❞</blockquote>\n\n"
        f"<blockquote>💖 <b>[•] BIN</b> → <code>{prefix[:6]}</code> ❞\n"
        f"⏰ <b>[•] Amount</b> → <code>{len(cards)}</code></blockquote>\n\n"
        f"<blockquote>{cards_text} ❞</blockquote>\n\n"
        f"<blockquote>🐇 <b>[•] Info</b> → <code>{brand} - {btype} ({level})</code> ❞\n"
        f"🔥 <b>[•] Issuer</b> → <code>{bank or '─'}</code>\n"
        f"🌌 <b>[•] Country</b> → <code>{country}</code> {flag}</blockquote>"
    )
    return text


def _regen_keyboard(prefix, mm, yy, cvv_pattern, count):
    """Regenerate + link buttons matching screenshot style"""
    cb_data = f"regen:{prefix}:{mm}:{yy}:{cvv_pattern}:{count}"
    if len(cb_data) > 64:
        cb_data = cb_data[:64]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍪 Regen", callback_data=cb_data),
            InlineKeyboardButton(text="👾 Close", callback_data="close_gen")
        ],
    ])


@router.message(Command("gen", prefix="/."))
async def cmd_gen(msg: Message, command: CommandObject, bot: Bot):
    uid = msg.from_user.id
    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)

    if await db.is_banned(uid):
        return

    if not await check_force_join(bot, uid):
        kb = await force_join_keyboard()
        await msg.answer(FORCE_JOIN_MSG, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    args = (command.args or "").strip()
    if not args:
        await msg.answer(
            "「 CC GENERATOR 」\n\n"
            "Usage: <code>/gen &lt;bin&gt;[|mm|yy|cvv] [count]</code>\n\n"
            "Examples:\n"
            "<code>/gen 415920</code>\n"
            "<code>/gen 415920|xx|26|xxx 20</code>\n"
            "<code>/gen 374155|12|xx|xxxx 5</code>\n\n"
            "<i>x = random. Max 50 cards.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    parsed = parse_gen_input(args)
    if not parsed:
        await msg.answer(
            f"{EMOJI['declined']} Invalid format.\nUsage: <code>/gen &lt;bin6+&gt;[|mm|yy|cvv] [count]</code>",
            parse_mode=ParseMode.HTML
        )
        return

    prefix, mm, yy, cvv_pattern, count = parsed

    # Determine generation limits based on plan
    is_owner_admin = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    plan = await db.get_user_plan(uid)
    
    if is_owner_admin:
        max_limit = 200000
        plan_label = "Admin/Owner"
    elif plan["unlimited"]:
        max_limit = 100
        plan_label = "Premium"
    else:
        max_limit = 50
        plan_label = "Free"

    if count <= 0:
        count = 10
    elif count > max_limit:
        await msg.answer(
            f"{EMOJI['declined']} <b>Limit Exceeded!</b>\n\n"
            f"Your current status ({plan_label}) allows generating a maximum of <code>{max_limit:,}</code> cards at once.\n"
            f"Please specify a lower quantity or contact support to upgrade.",
            parse_mode=ParseMode.HTML
        )
        return

    t0 = time.perf_counter()
    loop = asyncio.get_event_loop()
    cards = await loop.run_in_executor(None, generate_cards, prefix, mm, yy, cvv_pattern, count)
    bin_info = await lookup_bin(prefix)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    if not cards:
        await msg.answer(f"{EMOJI['declined']} Failed to generate cards.", parse_mode=ParseMode.HTML)
        return

    is_amex = prefix.startswith("34") or prefix.startswith("37")
    card_len = 15 if is_amex else 16
    display_prefix = prefix + "x" * (card_len - len(prefix))

    if len(cards) > 40:
        file_data = "\n".join(cards).encode('utf-8')
        input_file = BufferedInputFile(file_data, filename=f"cards_{prefix}_{len(cards)}.txt")
        caption = (
            f"<blockquote>🐸 <b>CC Generator (File)</b> 🐸 ❞</blockquote>\n\n"
            f"<blockquote>💖 <b>[•] BIN</b> → <code>{prefix[:6]}</code> ❞\n"
            f"⏰ <b>[•] Amount</b> → <code>{len(cards):,}</code></blockquote>\n\n"
            f"<blockquote>🐇 <b>[•] Info</b> → <code>{bin_info.get('brand', '─')} - {bin_info.get('type', '─')} ({bin_info.get('category', '─')})</code> ❞\n"
            f"🔥 <b>[•] Issuer</b> → <code>{bin_info.get('bank') or '─'}</code>\n"
            f"🌌 <b>[•] Country</b> → <code>{bin_info.get('country_name', '─')}</code> {bin_info.get('flag', '')}</blockquote>\n\n"
            f"<blockquote>⏱️ <b>Time Taken:</b> <code>{elapsed_ms}ms</code> ❞</blockquote>"
        )
        await msg.answer_document(document=input_file, caption=caption, parse_mode=ParseMode.HTML)
    else:
        text = _build_gen_text(cards, prefix, count, bin_info, elapsed_ms, display_prefix)
        kb = _regen_keyboard(prefix, mm, yy, cvv_pattern, count)
        await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("regen:"))
async def on_regen(callback: CallbackQuery, bot: Bot):
    """Regenerate fresh cards in same message"""
    try:
        parts = callback.data.split(":")
        if len(parts) < 6:
            await callback.answer("❌ Invalid data", show_alert=True)
            return

        prefix, mm, yy, cvv_pattern = parts[1], parts[2], parts[3], parts[4]
        count = int(parts[5])

        t0 = time.perf_counter()
        cards = generate_cards(prefix, mm, yy, cvv_pattern, count)
        bin_info = await lookup_bin(prefix)
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        if not cards:
            await callback.answer("❌ Failed", show_alert=True)
            return

        is_amex = prefix.startswith("34") or prefix.startswith("37")
        card_len = 15 if is_amex else 16
        display_prefix = prefix + "x" * (card_len - len(prefix))

        text = _build_gen_text(cards, prefix, count, bin_info, elapsed_ms, display_prefix)
        kb = _regen_keyboard(prefix, mm, yy, cvv_pattern, count)

        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        await callback.answer("🔄 Regenerated!")
    except Exception as e:
        await callback.answer(f"Error: {str(e)[:40]}", show_alert=True)


@router.callback_query(lambda c: c.data == "close_gen")
async def on_close_gen(callback: CallbackQuery):
    """Delete generator response message"""
    try:
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        await callback.answer(f"Failed to delete: {str(e)[:30]}", show_alert=True)


@router.message(Command("bin", prefix="/."))
async def cmd_bin(msg: Message, command: CommandObject, bot: Bot):
    uid = msg.from_user.id
    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)

    if await db.is_banned(uid):
        return

    if not await check_force_join(bot, uid):
        kb = await force_join_keyboard()
        await msg.answer(FORCE_JOIN_MSG, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    args = (command.args or "").strip()
    if not args or not args.replace(" ", "").isdigit() or len(args.replace(" ", "")) < 6:
        await msg.answer(
            "「 BIN LOOKUP 」\n\n"
            "Usage: <code>/bin &lt;6+ digit BIN&gt;</code>\n"
            "Example: <code>/bin 415920</code>",
            parse_mode=ParseMode.HTML
        )
        return

    t0 = time.perf_counter()
    bin_info = await lookup_bin(args)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    brand = bin_info.get("brand", "")
    btype = bin_info.get("type", "")
    level = bin_info.get("category", "")
    bank = bin_info.get("bank", "")
    flag = bin_info.get("flag", "")
    country = bin_info.get("country_name", "")
    iso = bin_info.get("country_code", "")

    text = (
        f"<blockquote>🔍 <b>BIN Lookup</b> 🔎 ❞</blockquote>\n\n"
        f"<blockquote>💖 <b>[•] BIN</b> → <code>{args[:6]}</code> ❞\n"
        f"💳 <b>[•] Brand/Type</b> → <code>{brand} - {btype} ({level})</code></blockquote>\n\n"
        f"<blockquote>🏛️ <b>[•] Bank</b> → <code>{bank or '─'}</code> ❞\n"
        f"🌍 <b>[•] Country</b> → <code>{country} ({iso})</code> {flag}</blockquote>\n\n"
        f"<blockquote>⏱️ <b>Time Taken</b> → <code>{elapsed_ms}ms</code> ❞</blockquote>"
    )
    await msg.answer(text, parse_mode=ParseMode.HTML)
