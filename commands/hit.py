import time
import re
import asyncio
import random
from aiogram import Router, Bot
from aiogram.types import Message, LinkPreviewOptions
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode

import database.db as db
from functions.bin_lookup import lookup_bin
from functions.card_utils import parse_card, generate_cards, format_card, parse_cards
from functions.force_join import check_force_join, force_join_keyboard, FORCE_JOIN_MSG
from functions.emojis import EMOJI
from config import OWNER_IDS

router = Router()
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

def extract_checkout_url(text: str) -> str:
    m = re.search(r"https?://[^\s\"\'<>)]+", text, re.IGNORECASE)
    if m:
        return m.group(0).rstrip(".,;:")
    return None

async def _notify_public(bot: Bot, card_str: str, uid: int, username: str, amount_display: str, gateway: str):
    """Masked public notification with bank and country info."""
    public_ch = await db.get_setting("public_channel", "")
    if not public_ch:
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

    cc = card_str.split("|")[0]
    masked_card = cc[:6] + "x" * (len(cc) - 10) + cc[-4:]

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

# ─── /hit (Real Hitter) ────────────────────────────────────────────────────────
@router.message(Command("hit", prefix="/."))
async def cmd_hit_real(msg: Message, command: CommandObject, bot: Bot):
    uid = msg.from_user.id
    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)

    if await db.is_banned(uid):
        return

    if not await check_force_join(bot, uid):
        kb = await force_join_keyboard()
        await msg.answer(FORCE_JOIN_MSG, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    args = (command.args or "").strip().lstrip(".").strip()
    
    # 1. Extract URL
    url = extract_checkout_url(args)
    if not url and msg.reply_to_message:
        reply_text = (msg.reply_to_message.text or "") + " " + (msg.reply_to_message.caption or "")
        url = extract_checkout_url(reply_text)
        
    if not url:
        await msg.answer(
            f"❌ <b>Usage:</b>\n<code>/hit &lt;url&gt; &lt;bin/cc&gt; &lt;amount&gt; [merchant name]</code>\n\n"
            f"<b>Example:</b>\n<code>/hit https://payments.cashfree.com/checkout/1234 453201 100 Stripe Checkout</code>",
            parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW
        )
        return

    # Extract remaining text to find card/bin, amount and merchant name
    remaining = args.replace(url, "", 1).strip()
    parts = remaining.split()

    bin_cc = None
    amount = None
    merchant_custom = None

    def looks_like_card(s: str) -> bool:
        digits = "".join(c for c in s if c.isdigit())
        return len(digits) >= 6 or "|" in s

    if len(parts) >= 2:
        part1 = parts[0]
        part2 = parts[1]
        
        if looks_like_card(part1) and not looks_like_card(part2):
            bin_cc = part1
            amount = part2
            if len(parts) > 2:
                merchant_custom = " ".join(parts[2:]).strip()
        elif looks_like_card(part2) and not looks_like_card(part1):
            bin_cc = part2
            amount = part1
            if len(parts) > 2:
                merchant_custom = " ".join(parts[2:]).strip()
        else:
            bin_cc = part1
            amount = part2
            if len(parts) > 2:
                merchant_custom = " ".join(parts[2:]).strip()
    elif len(parts) == 1:
        if looks_like_card(parts[0]):
            bin_cc = parts[0]
            amount = "1.00 USD"
        else:
            bin_cc = "453201"
            amount = parts[0]
    else:
        # Check if there is a card in reply message
        if msg.reply_to_message:
            reply = msg.reply_to_message
            reply_cards = []
            if reply.document and reply.document.file_name and reply.document.file_name.endswith(".txt"):
                try:
                    file = await bot.get_file(reply.document.file_id)
                    content = await bot.download_file(file.file_path)
                    reply_cards = parse_cards(content.read().decode("utf-8", errors="ignore"))
                except Exception:
                    pass
            elif reply.text:
                reply_card_text = re.sub(r'https?://\S+', '', reply.text).strip()
                if reply_card_text:
                    reply_cards = parse_cards(reply_card_text)
                    
            if reply_cards:
                bin_cc = f"{reply_cards[0]['cc']}|{reply_cards[0]['month']}|{reply_cards[0]['year']}|{reply_cards[0]['cvv']}"
                amount = "1.00 USD"
            else:
                bin_cc = "453201"
                amount = "1.00 USD"
        else:
            await msg.answer(
                f"❌ <b>Usage:</b>\n<code>/hit &lt;url&gt; &lt;bin/cc&gt; &lt;amount&gt; [merchant name]</code>\n\n"
                f"<b>Example:</b>\n<code>/hit https://payments.cashfree.com/checkout/1234 453201 100 Stripe Checkout</code>",
                parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW
            )
            return

    # Check quotas/plans
    plan = await db.get_user_plan(uid)
    is_privileged = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    if not is_privileged:
        can, reason = await db.can_hit(uid)
        if not can:
            await msg.answer(f"{EMOJI['error']} {reason}", parse_mode=ParseMode.HTML)
            return

    # 2. Parse or Generate the card
    card_str = None
    if "|" in bin_cc or len(bin_cc) >= 15:
        parsed = parse_card(bin_cc)
        if parsed:
            card_str = format_card(parsed)
            
    if not card_str:
        prefix = "".join(c for c in bin_cc if c.isdigit())
        if len(prefix) >= 6:
            cards = generate_cards(prefix, "xx", "xx", "xxx", 1)
            if cards:
                card_str = cards[0]
                
    if not card_str:
        cards = generate_cards("453201", "xx", "xx", "xxx", 1)
        card_str = cards[0]

    # Import modules dynamically
    import functions.stripe_tls as stripe_tls
    import functions.razorpay_tls as razorpay_tls
    import functions.cashfree_tls as cashfree_tls
    import functions.payu_tls as payu_tls
    import functions.epoch_tls as epoch_tls

    # Determine gateway module
    url_lower = url.lower()
    if "stripe" in url_lower:
        gw_mod = stripe_tls
        default_merchant = "Stripe Checkout"
    elif "razorpay" in url_lower or "rzp.io" in url_lower or "pages.razorpay.com" in url_lower:
        gw_mod = razorpay_tls
        default_merchant = "Razorpay Checkout"
    elif "cashfree" in url_lower:
        gw_mod = cashfree_tls
        default_merchant = "Cashfree Checkout"
    elif "payu" in url_lower:
        gw_mod = payu_tls
        default_merchant = "PayU Checkout"
    elif "epoch" in url_lower:
        gw_mod = epoch_tls
        default_merchant = "Epoch Checkout"
    else:
        gw_mod = stripe_tls
        default_merchant = "Stripe Checkout"

    status_msg = await msg.answer("Fetching checkout info...", parse_mode=ParseMode.HTML)
    
    from functions.proxy_utils import pick_proxy
    proxy = await pick_proxy(user_id=uid)
    
    checkout = await gw_mod.get_checkout_info(url, proxy)
    if checkout.get("error"):
        await status_msg.edit_text(f"❌ <b>Error:</b>\n<code>{checkout['error']}</code>", parse_mode=ParseMode.HTML)
        return

    # Extract info
    merchant = merchant_custom or checkout.get("merchant") or default_merchant
    
    # Currency symbol & Price
    from functions.stripe_tls import CURRENCY_SYMBOLS
    sym = CURRENCY_SYMBOLS.get((checkout.get("currency") or "").lower(), "")
    price_val = checkout.get("price") or checkout.get("amount")
    if price_val is not None:
        try:
            amount_display = f"{sym}{float(price_val):.2f} {(checkout.get('currency') or '').upper()}"
        except Exception:
            amount_display = f"{price_val} {(checkout.get('currency') or '').upper()}"
    else:
        # Fallback to user specified amount
        amount_clean = amount.strip()
        has_currency = any(not (c.isdigit() or c in "., ") for c in amount_clean)
        if not has_currency:
            try:
                val = float(amount_clean)
                amount_display = f"${val:.2f} USD"
            except ValueError:
                amount_display = f"{amount_clean} USD"
        else:
            amount_display = amount_clean

    # Simulate processing text
    hitting_text = (
        f"<blockquote>⚡ <b>Real Hitter</b> ⚡ ❞</blockquote>\n\n"
        f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
        f"💰 <b>[•] Amount</b> → <code>{amount_display}</code>\n"
        f"🌀 <b>[•] Processed</b> → <code>1/1</code> (Processing...)</blockquote>\n\n"
        f"<blockquote>💳 <code>{card_str}</code> ❞\n"
        f"↳ <b>Result:</b> Processing...</blockquote>"
    )
    await status_msg.edit_text(hitting_text, parse_mode=ParseMode.HTML)

    # Perform card charge
    card_dict = parse_card(card_str)
    start_time = time.perf_counter()
    try:
        result = await asyncio.wait_for(gw_mod.charge_card(card_dict, checkout, proxy), timeout=45)
    except asyncio.TimeoutError:
        result = {"card": card_str, "status": "FAILED", "response": "Timeout", "decline_code": "", "time": 45.0}
    except Exception as e:
        result = {"card": card_str, "status": "FAILED", "response": str(e)[:50], "decline_code": "", "time": 0.0}

    time_taken = round(time.perf_counter() - start_time, 2)
    result_status = result.get("status", "FAILED")
    response_msg = result.get("response", "Declined")

    # Perform BIN lookup
    bin6 = card_str.split("|")[0][:6]
    bin_info = await lookup_bin(bin6)
    country_display = f"{bin_info['flag']} {bin_info['country_name']}" if bin_info['country_code'] else bin_info['country_name']

    # Log in database
    await db.log_check(
        user_id=uid,
        card=card_str,
        url=url,
        merchant=merchant,
        amount=amount_display,
        status=result_status,
        response=response_msg,
        time_taken=time_taken
    )
    if uid not in OWNER_IDS and result_status == "CHARGED":
        await db.increment_daily_hits(uid)

    status_label = "CHARGED ✅" if result_status == "CHARGED" else "DECLINED ❌"
    if result_status == "3DS":
        status_label = "3DS 🟡"

    # Build response text
    response_text = (
        f"<blockquote>🎯 <b>Hit Result!</b> 🎯 ❞</blockquote>\n\n"
        f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
        f"🟢 <b>[•] Status</b> → <b>{status_label}</b>\n"
        f"💬 <b>[•] Response</b> → <code>{response_msg}</code></blockquote>\n\n"
        f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
        f"💰 <b>[•] Amount</b> → <code>{amount_display}</code></blockquote>\n\n"
        f"<blockquote>🏛️ <b>[•] Bank</b> → <code>{bin_info['bank']}</code> ❞\n"
        f"💳 <b>[•] Type</b> → <code>{bin_info['brand']} / {bin_info['type']} ({bin_info['category']})</code>\n"
        f"🌍 <b>[•] Country</b> → <code>{country_display}</code></blockquote>\n\n"
        f"<blockquote>⏱️ <b>Time Taken</b> → <code>{time_taken}s</code> ❞</blockquote>"
    )
    await status_msg.edit_text(response_text, parse_mode=ParseMode.HTML)

    # Notify public channel if charged
    if result_status == "CHARGED":
        gateway_name = merchant.replace(" Checkout", "")
        username_to_pass = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name
        await _notify_public(bot, card_str, uid, username_to_pass, amount_display, gateway_name)


# ─── /hit. (Fake Hitter) ────────────────────────────────────────────────────────
@router.message(Command("hit.", "fakehit", prefix="/."))
async def cmd_hit_fake(msg: Message, command: CommandObject, bot: Bot):
    uid = msg.from_user.id
    
    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)
    if not is_owner:
        await msg.answer("❌ <b>Access Denied.</b> Only Owners can use this command.", parse_mode=ParseMode.HTML)
        return

    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)

    if await db.is_banned(uid):
        return

    if not await check_force_join(bot, uid):
        kb = await force_join_keyboard()
        await msg.answer(FORCE_JOIN_MSG, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    args = (command.args or "").strip().lstrip(".").strip()
    
    # 1. Extract URL
    url = extract_checkout_url(args)
    if not url and msg.reply_to_message:
        reply_text = (msg.reply_to_message.text or "") + " " + (msg.reply_to_message.caption or "")
        url = extract_checkout_url(reply_text)
        
    if not url:
        await msg.answer(
            f"❌ <b>Usage:</b>\n<code>/hit. &lt;url&gt; &lt;bin/cc&gt; &lt;amount&gt; [merchant name]</code>\n\n"
            f"<b>Example:</b>\n<code>/hit. https://payments.cashfree.com/checkout/1234 453201 100 Stripe Checkout</code>",
            parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW
        )
        return

    # Extract remaining text to find card/bin, amount and merchant name
    remaining = args.replace(url, "", 1).strip()
    parts = remaining.split()

    bin_cc = None
    amount = None
    merchant_custom = None

    def looks_like_card(s: str) -> bool:
        digits = "".join(c for c in s if c.isdigit())
        return len(digits) >= 6 or "|" in s

    if len(parts) >= 2:
        part1 = parts[0]
        part2 = parts[1]
        
        if looks_like_card(part1) and not looks_like_card(part2):
            bin_cc = part1
            amount = part2
            if len(parts) > 2:
                merchant_custom = " ".join(parts[2:]).strip()
        elif looks_like_card(part2) and not looks_like_card(part1):
            bin_cc = part2
            amount = part1
            if len(parts) > 2:
                merchant_custom = " ".join(parts[2:]).strip()
        else:
            bin_cc = part1
            amount = part2
            if len(parts) > 2:
                merchant_custom = " ".join(parts[2:]).strip()
    elif len(parts) == 1:
        if looks_like_card(parts[0]):
            bin_cc = parts[0]
            amount = "1.00 USD"
        else:
            bin_cc = "453201"
            amount = parts[0]
    else:
        # Check if there is a card in reply message
        if msg.reply_to_message:
            reply = msg.reply_to_message
            reply_cards = []
            if reply.document and reply.document.file_name and reply.document.file_name.endswith(".txt"):
                try:
                    file = await bot.get_file(reply.document.file_id)
                    content = await bot.download_file(file.file_path)
                    reply_cards = parse_cards(content.read().decode("utf-8", errors="ignore"))
                except Exception:
                    pass
            elif reply.text:
                reply_card_text = re.sub(r'https?://\S+', '', reply.text).strip()
                if reply_card_text:
                    reply_cards = parse_cards(reply_card_text)
                    
            if reply_cards:
                bin_cc = f"{reply_cards[0]['cc']}|{reply_cards[0]['month']}|{reply_cards[0]['year']}|{reply_cards[0]['cvv']}"
                amount = "1.00 USD"
            else:
                bin_cc = "453201"
                amount = "1.00 USD"
        else:
            await msg.answer(
                f"❌ <b>Usage:</b>\n<code>/hit. &lt;url&gt; &lt;bin/cc&gt; &lt;amount&gt; [merchant name]</code>\n\n"
                f"<b>Example:</b>\n<code>/hit. https://payments.cashfree.com/checkout/1234 453201 100 Stripe Checkout</code>",
                parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW
            )
            return

    # Check quotas/plans
    plan = await db.get_user_plan(uid)
    is_privileged = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    if not is_privileged:
        can, reason = await db.can_hit(uid)
        if not can:
            await msg.answer(f"{EMOJI['error']} {reason}", parse_mode=ParseMode.HTML)
            return

    # 2. Parse or Generate the card
    card_str = None
    if "|" in bin_cc or len(bin_cc) >= 15:
        parsed = parse_card(bin_cc)
        if parsed:
            card_str = format_card(parsed)
            
    if not card_str:
        prefix = "".join(c for c in bin_cc if c.isdigit())
        if len(prefix) >= 6:
            cards = generate_cards(prefix, "xx", "xx", "xxx", 1)
            if cards:
                card_str = cards[0]
                
    if not card_str:
        cards = generate_cards("453201", "xx", "xx", "xxx", 1)
        card_str = cards[0]

    # Format the amount
    amount_clean = amount.strip()
    has_currency = any(not (c.isdigit() or c in "., ") for c in amount_clean)
    if not has_currency:
        try:
            val = float(amount_clean)
            amount_display = f"${val:.2f} USD"
        except ValueError:
            amount_display = f"{amount_clean} USD"
    else:
        amount_display = amount_clean

    # Determine merchant
    if merchant_custom:
        merchant = merchant_custom
    else:
        merchant = "Premium Gateway"
        for domain in ["stripe", "cashfree", "razorpay", "payu", "epoch", "shopify"]:
            if domain in url.lower():
                merchant = domain.capitalize() + " Checkout"
                break

    # Send processing status message
    status_msg = await msg.answer("Fetching checkout info...", parse_mode=ParseMode.HTML)
    
    # Simulate processing
    fake_time = round(random.uniform(20.0, 45.0), 1)
    c_str = card_str
    hitting_text = (
        f"<blockquote>⚡ <b>USE OWNER'S STORED CC FOR HITTING</b> ⚡ ❞</blockquote>\n\n"
        f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
        f"💰 <b>[•] Amount</b> → <code>{amount_display}</code>\n"
        f"🌀 <b>[•] Processed</b> → <code>1/1</code> (Processing...)</blockquote>\n\n"
        f"<blockquote>💳 <code>{c_str}</code> ❞\n"
        f"↳ <b>Result:</b> Processing...</blockquote>"
    )
    await status_msg.edit_text(hitting_text, parse_mode=ParseMode.HTML)
    await asyncio.sleep(fake_time)

    # Perform BIN lookup
    bin6 = card_str.split("|")[0][:6]
    bin_info = await lookup_bin(bin6)
    country_display = f"{bin_info['flag']} {bin_info['country_name']}" if bin_info['country_code'] else bin_info['country_name']

    # Determine success or decline based on random chance (1 in 4 to 10 attempts)
    success_denom = random.randint(4, 10)
    is_success = (random.randint(1, success_denom) == 1)

    if is_success:
        status_val = "CHARGED"
        response_msg = "Charge Done / Success"
    else:
        status_val = "DECLINED"
        decline_responses = [
            "Card Declined",
            "Insufficient Funds",
            "Incorrect CVC",
            "Expired Card",
            "Do Not Honor",
            "Stolen Card",
            "Restricted Card",
            "Transaction Not Allowed"
        ]
        response_msg = random.choice(decline_responses)

    # Log fake hit in database
    await db.log_check(
        user_id=uid,
        card=card_str,
        url=url,
        merchant=merchant,
        amount=amount_display,
        status=status_val,
        response=response_msg,
        time_taken=fake_time
    )
    if uid not in OWNER_IDS and status_val == "CHARGED":
        await db.increment_daily_hits(uid)

    if status_val == "CHARGED":
        # Build success response text
        success_text = (
            f"<blockquote>🎯 <b>Hit Found!</b> 🎯 ❞</blockquote>\n\n"
            f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
            f"🟢 <b>[•] Status</b> → <b>CHARGED ✅</b>\n"
            f"💬 <b>[•] Response</b> → <code>{response_msg}</code></blockquote>\n\n"
            f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
            f"💰 <b>[•] Amount</b> → <code>{amount_display}</code></blockquote>\n\n"
            f"<blockquote>🏛️ <b>[•] Bank</b> → <code>{bin_info['bank']}</code> ❞\n"
            f"💳 <b>[•] Type</b> → <code>{bin_info['brand']} / {bin_info['type']} ({bin_info['category']})</code>\n"
            f"🌍 <b>[•] Country</b> → <code>{country_display}</code></blockquote>\n\n"
            f"<blockquote>⏱️ <b>Time Taken</b> → <code>{fake_time}s</code> ❞</blockquote>"
        )
        await status_msg.edit_text(success_text, parse_mode=ParseMode.HTML)

        # Notify public channel
        gateway_name = merchant.replace(" Checkout", "")
        username_to_pass = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name
        await _notify_public(bot, card_str, uid, username_to_pass, amount_display, gateway_name)
    else:
        # Build decline response text
        decline_text = (
            f"<blockquote>🎯 <b>Hit Result!</b> 🎯 ❞</blockquote>\n\n"
            f"<blockquote>💳 <b>[•] Card</b> → <code>{card_str}</code> ❞\n"
            f"🔴 <b>[•] Status</b> → <b>DECLINED ❌</b>\n"
            f"💬 <b>[•] Response</b> → <code>{response_msg}</code></blockquote>\n\n"
            f"<blockquote>🏪 <b>[•] Merchant</b> → <code>{merchant}</code> ❞\n"
            f"💰 <b>[•] Amount</b> → <code>{amount_display}</code></blockquote>\n\n"
            f"<blockquote>🏛️ <b>[•] Bank</b> → <code>{bin_info['bank']}</code> ❞\n"
            f"💳 <b>[•] Type</b> → <code>{bin_info['brand']} / {bin_info['type']} ({bin_info['category']})</code>\n"
            f"🌍 <b>[•] Country</b> → <code>{country_display}</code></blockquote>\n\n"
            f"<blockquote>⏱️ <b>Time Taken</b> → <code>{fake_time}s</code> ❞</blockquote>"
        )
        await status_msg.edit_text(decline_text, parse_mode=ParseMode.HTML)
