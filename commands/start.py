"""Home screen, settings, help, credits, redeem, myhits, ping"""
import time
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject

import database.db as db
from config import (
    OWNER_IDS, FREE_DAILY_LIMIT, BOT_NAME, BOT_USERNAME,
    PLAN_PRICES, SUPPORT_USERNAME, OWNER_USERNAME
)
from functions.emojis import EMOJI, EMOJI_PLAIN

_bot_start_time = time.time()

router = Router()

NO_PREVIEW = {"is_disabled": True}

def _kb(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows])


async def _home_screen(target, user, edit=False):
    uid = user.id
    chat_id = target.chat.id if hasattr(target, "chat") and target.chat else 0
    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)
    if uid == 1087968824 and chat_id and await db.is_chat_authorized(chat_id):
        is_owner = True
    is_admin = await db.is_admin(uid)
    plan = await db.get_user_plan(uid)

    if is_owner:
        plan_text = "👑 <b>OWNER</b>"
        exp_text = "♾ <b>Unlimited Hits</b>"
    elif is_admin:
        plan_text = "🛡️ <b>ADMIN</b>"
        exp_text = "♾ <b>Unlimited Hits</b>"
    elif plan["unlimited"]:
        hpd = plan.get("hits_per_day", 0)
        hpd_str = f"{hpd}/day" if hpd > 0 else "Unlimited ♾"
        plan_text = f"💎 <b>{plan['label'].upper()}</b> (<i>{hpd_str}</i>)"
        exp_text = f"📅 <b>Expiry:</b> <code>{plan['expiry']}</code>"
    else:
        hits = await db.get_daily_hits(uid)
        remaining = max(0, FREE_DAILY_LIMIT - hits)
        plan_text = f"🆓 <b>FREE PLAN</b>"
        exp_text = f"⚡ <b>Hits Used:</b> <code>{hits}/{FREE_DAILY_LIMIT}</code> (<i>{remaining} remaining</i>)"

    fname = user.first_name or "User"
    
    text = (
        f"<blockquote>✨ <b>Welcome to {BOT_NAME}</b> ✨ ❞</blockquote>\n\n"
        f"<blockquote>👋 Hey, <b>{fname}</b>! ❞</blockquote>\n\n"
        f"<blockquote>👤 <b>USER DASHBOARD</b> ❞\n"
        f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
        f"👑 <b>Plan:</b> {plan_text}\n"
        f"⚡ <b>Stats:</b> {exp_text}</blockquote>\n\n"
        f"<blockquote>💡 <i>Send <code>/hit</code> to start checking cards.</i> ❞</blockquote>"
    )

    rows = [
        [("🔥 𝗛𝗶𝘁 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀", "home_help"), ("⚡ 𝗨𝘁𝗶𝗹𝗶𝘁𝘆 𝗧𝗼𝗼𝗹𝘀", "home_tools")],
        [("💳 𝗖𝗵𝗲𝗰𝗸𝗲𝗿", "home_checker"), ("🦁 𝗠𝘆 𝗛𝗶𝘁𝘀", "home_myhits")],
        [("🌪️ 𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀", "home_settings"), ("🌳 𝗦𝗮𝘃𝗲𝗱 𝗕𝗜𝗡𝘀", "home_bins")],
        [("🔮 𝗥𝗮𝗻𝗸𝗶𝗻𝗴", "home_ranking"), ("☎️ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗦𝘂𝗽𝗽𝗼𝗿𝘁", "home_contact")],
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])

    if edit:
        await target.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await target.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.message(Command("start", prefix="/."))
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    await db.upsert_user(uid, msg.from_user.username, msg.from_user.first_name)
    if await db.is_banned(uid):
        await msg.answer(f"{EMOJI['ban']} <b>You are banned.</b>", parse_mode=ParseMode.HTML)
        return
    await _home_screen(msg, msg.from_user)


@router.callback_query(F.data == "home_main")
async def cb_home_main(query: CallbackQuery):
    await _home_screen(query.message, query.from_user, edit=True)
    await query.answer()


@router.callback_query(F.data == "home_help")
async def cb_home_help(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🚀 ━━━━━━━ ✦\n"
        f"⚡ <b>SELECT GATEWAY</b>\n"
        f"✦ ━━━━━━━ 🚀 ━━━━━━━ ✦\n\n"
        f"<i>Choose a payment gateway below to view its hit commands:</i>\n"
    )
    rows = [
        [("💳 𝗦𝘁𝗿𝗶𝗽𝗲", "hit_stripe"), ("🔵 𝗥𝗮𝘇𝗼𝗿𝗽𝗮𝘆", "hit_razorpay")],
        [("🟢 𝗖𝗮𝘀𝗵𝗳𝗿𝗲𝗲", "hit_cashfree"), ("🟠 𝗣𝗮𝘆𝗨", "hit_payu")],
        [("🟣 𝗘𝗽𝗼𝗰𝗵", "hit_epoch")],
        [("⬅️ Back to Menu", "home_main")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "hit_stripe")
async def cb_hit_stripe(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 💳 ━━━━━━━ ✦\n"
        f"💳 <b>STRIPE HIT COMMANDS</b>\n"
        f"✦ ━━━━━━━ 💳 ━━━━━━━ ✦\n\n"
        f"🔹 <b>Stripe Donation ($1 Gate):</b>\n"
        f"<code>/check cc|mm|yy|cvv</code> (or <code>/chk</code>) ➔ Single check\n"
        f"<code>/mash cc1|mm|yy|cvv</code> ➔ Bulk check\n\n"
        f"🔹 <b>Single Card Check (Checkout):</b>\n"
        f"<code>/hit &lt;stripe-url&gt; cc|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Bulk Card Check (Checkout):</b>\n"
        f"<code>/hit &lt;stripe-url&gt;</code>\n"
        f"<code>cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto-Gen Check from BIN (Checkout):</b>\n"
        f"<code>/hit &lt;stripe-url&gt; bin6+</code>\n\n"
    )
    kb = _kb([("⬅️ Back to Gateways", "home_help"), ("⬅️ Home", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "hit_razorpay")
async def cb_hit_razorpay(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🔵 ━━━━━━━ ✦\n"
        f"🔵 <b>RAZORPAY HIT COMMANDS</b>\n"
        f"✦ ━━━━━━━ 🔵 ━━━━━━━ ✦\n\n"
        f"🔹 <b>Single Card Check:</b>\n"
        f"<code>/rz &lt;razorpay-url&gt; cc|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Bulk Card Check:</b>\n"
        f"<code>/rz &lt;razorpay-url&gt;</code>\n"
        f"<code>cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto-Gen Check from BIN:</b>\n"
        f"<code>/rz &lt;razorpay-url&gt; bin6+</code>\n\n"
       
    )
    kb = _kb([("⬅️ Back to Gateways", "home_help"), ("⬅️ Home", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "hit_cashfree")
async def cb_hit_cashfree(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🟢 ━━━━━━━ ✦\n"
        f"🟢 <b>CASHFREE HIT COMMANDS</b>\n"
        f"✦ ━━━━━━━ 🟢 ━━━━━━━ ✦\n\n"
        f"🔹 <b>Single Card Check:</b>\n"
        f"<code>/cf &lt;cashfree-url&gt; cc|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Bulk Card Check:</b>\n"
        f"<code>/cf &lt;cashfree-url&gt;</code>\n"
        f"<code>cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto-Gen Check from BIN:</b>\n"
        f"<code>/cf &lt;cashfree-url&gt; bin6+</code>\n\n"
        )
    kb = _kb([("⬅️ Back to Gateways", "home_help"), ("⬅️ Home", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "hit_payu")
async def cb_hit_payu(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🟠 ━━━━━━━ ✦\n"
        f"🟠 <b>PAYU HIT COMMANDS</b>\n"
        f"✦ ━━━━━━━ 🟠 ━━━━━━━ ✦\n\n"
        f"🔹 <b>Single Card Check:</b>\n"
        f"<code>/payu &lt;payu-url&gt; cc|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Bulk Card Check:</b>\n"
        f"<code>/payu &lt;payu-url&gt;</code>\n"
        f"<code>cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto-Gen Check from BIN:</b>\n"
        f"<code>/payu &lt;payu-url&gt; bin6+</code>\n\n"
    )
    kb = _kb([("⬅️ Back to Gateways", "home_help"), ("⬅️ Home", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "hit_epoch")
async def cb_hit_epoch(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🟣 ━━━━━━━ ✦\n"
        f"🟣 <b>EPOCH HIT COMMANDS</b>\n"
        f"✦ ━━━━━━━ 🟣 ━━━━━━━ ✦\n\n"
        f"🔹 <b>Single Card Check:</b>\n"
        f"<code>/epoch &lt;epoch-url&gt; cc|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Bulk Card Check:</b>\n"
        f"<code>/epoch &lt;epoch-url&gt;</code>\n"
        f"<code>cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto-Gen Check from BIN:</b>\n"
        f"<code>/epoch &lt;epoch-url&gt; bin6+</code>\n\n"
        f"🔹 <b>File Check:</b>\n"
)
    kb = _kb([("⬅️ Back to Gateways", "home_help"), ("⬅️ Home", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "home_tools")
async def cb_home_tools(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🛠️ ━━━━━━━ ✦\n"
        f"⚙️ <b>UTILITY TOOLS</b>\n"
        f"✦ ━━━━━━━ 🛠️ ━━━━━━━ ✦\n\n"
        f"🔸 <code>/gen &lt;bin&gt; [qty]</code> ➔ Generate cards\n"
        f"🔸 <code>/fake [country]</code> ➔ Generate fake address\n"
        f"🔸 <code>/bin &lt;bin6&gt;</code> ➔ BIN Details lookup\n"
        f"🔸 <code>/myhits</code> ➔ View your personal hits\n"
        f"🔸 <code>/redeem &lt;code&gt;</code> ➔ Activate premium plan\n"
    )
    kb = _kb([("⬅️ Back to Menu", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "home_checker")
async def cb_home_checker(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 💳 ━━━━━━━ ✦\n"
        f"💳 <b>STRIPE $1 DONATION CHECKER</b>\n"
        f"✦ ━━━━━━━ 💳 ━━━━━━━ ✦\n\n"
        f"<i>This checker charges cards $1.00 USD on our custom Stripe donation gateway.</i>\n\n"
        f"🔹 <b>Single Check Command:</b>\n"
        f"<code>/check cc|mm|yy|cvv</code> (or <code>/chk</code>)\n\n"
        f"🔹 <b>Bulk Check Command:</b>\n"
        f"<code>/mash cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto‑Gen check:</b>\n"
        f"<code>/check bin6+</code>\n\n"
        f"🔹 <b>File Check:</b>\n"
        f"Reply to any <code>.txt</code> card list file with <code>/check</code> or <code>/mash</code>\n\n"
        f"💡 <i>Approved and Live hits are automatically saved to your history and sent to the channels!</i>"
    )
    kb = _kb([("⬅️ Back to Menu", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.message(Command("myhits", prefix="/."))
async def cmd_myhits(msg: Message):
    await _show_myhits(msg, msg.from_user.id)


@router.callback_query(F.data == "home_myhits")
async def cb_home_myhits(query: CallbackQuery):
    await _show_myhits(query.message, query.from_user.id, edit=True)
    await query.answer()


async def _show_myhits(target, uid, edit=False):
    logs = await db.get_user_logs(uid, limit=20)
    stats = await db.get_user_hit_stats(uid)
    text = (
        f"✦ ━━━━━━━ 📊 ━━━━━━━ ✦\n"
        f"📈 <b>YOUR CHECK STATISTICS</b>\n"
        f"✦ ━━━━━━━ 📊 ━━━━━━━ ✦\n\n"
        f"📊 <b>Total Checks:</b> <code>{stats['total']}</code>\n"
        f"💰 <b>Charged Hits:</b> <code>{stats['charged']}</code>\n"
        f"🔥 <b>Live Hits:</b> <code>{stats['live']}</code>\n"
        f"❌ <b>Declined:</b> <code>{stats['declined']}</code>\n\n"
        f"📝 <b>Recent Charged/Live Hits:</b>\n"
    )
    if logs:
        lines = []
        for h in logs[:10]:
            amt = h.get('amount', '?')
            merchant = h.get('merchant', '?')
            status_icon = "💰" if h.get('status') == 'CHARGED' else "🔥"
            lines.append(f"{status_icon} <code>{merchant}</code> ➔ <b>{amt}</b>")
        text += "\n".join(lines)
    else:
        text += "<i>No charged or live hits logged yet.</i>"
    if len(text) > 4000:
        text = text[:3990] + "\n..."
    kb = _kb([("⬅️ Back to Menu", "home_main")])
    if edit:
        await target.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await target.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "home_settings")
async def cb_home_settings(query: CallbackQuery):
    await _show_settings(query)


async def _show_settings(query: CallbackQuery):
    uid = query.from_user.id
    proxy_mode = await db.get_user_proxy_mode(uid)
    user_proxies = await db.get_proxies(uid)
    sys_proxy = await db.get_setting("system_proxy", None)

    if proxy_mode == "own":
        mode_text = "🟢 <b>Using Personal Proxy</b>"
        toggle_btn = ("🌐 Switch to System Proxy", "settings_proxy_system")
    else:
        mode_text = "🔵 <b>Using System Shared Proxy</b>"
        toggle_btn = ("🔑 Switch to Personal Proxy", "settings_proxy_own")

    sys_status = f"<code>{sys_proxy[:25]}...</code>" if sys_proxy else "Hosting IP"
    proxy_list = "\n".join(f"🔸 <code>{p}</code>" for p in user_proxies[:3]) if user_proxies else "<i>No personal proxies added yet.</i>"

    text = (
        f"✦ ━━━━━━━ ⚙️ ━━━━━━━ ✦\n"
        f"⚙️ <b>SETTINGS PANEL</b>\n"
        f"✦ ━━━━━━━ ⚙️ ━━━━━━━ ✦\n\n"
        f"🌐 <b>Current Proxy Mode:</b> {mode_text}\n"
        f"🖥️ <b>System Default:</b> {sys_status}\n\n"
        f"📂 <b>Your Proxies (showing top 3):</b>\n{proxy_list}\n\n"
    )

    rows = [[toggle_btn]]

    is_admin = uid in OWNER_IDS or await db.is_admin(uid)
    if is_admin:
        maintenance_status = await db.get_setting("maintenance_mode", "off")
        
        maint_status_label = "🚧 ON" if maintenance_status == "on" else "🟢 OFF"
        
        text += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛠️ <b>ADMIN SETTINGS CONTROL</b>\n"
            f"🚧 <b>Maintenance:</b> {maint_status_label}\n\n"
        )
        maint_btn_text = "🟢 Turn Maintenance OFF" if maintenance_status == "on" else "🚧 Turn Maintenance ON"
        rows.append([(maint_btn_text, "settings_maintenance_toggle")])
        rows.append([("📋 Admin Commands", "admin_cmds")])

    text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➕ <b>Add Proxy:</b> <code>/proxy add host:port:user:pass</code>\n"
        f"🧪 <b>Test Speed:</b> <code>/proxy test</code>"
    )
    rows.append([("⬅️ Back to Menu", "home_main")])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "settings_proxy_own")
async def cb_settings_proxy_own(query: CallbackQuery):
    uid = query.from_user.id
    user_proxies = await db.get_proxies(uid)
    if not user_proxies:
        await query.answer("Add a proxy first with /proxy add", show_alert=True)
        return
    await db.set_user_proxy_mode(uid, "own")
    await _show_settings(query)


@router.callback_query(F.data == "settings_proxy_system")
async def cb_settings_proxy_system(query: CallbackQuery):
    await db.set_user_proxy_mode(query.from_user.id, "system")
    await _show_settings(query)



@router.callback_query(F.data == "settings_maintenance_toggle")
async def cb_settings_maintenance_toggle(query: CallbackQuery, bot: Bot):
    uid = query.from_user.id
    is_admin = uid in OWNER_IDS or await db.is_admin(uid)
    if not is_admin:
        await query.answer("Access Denied: Admin only.", show_alert=True)
        return

    current = await db.get_setting("maintenance_mode", "off")
    new_status = "off" if current == "on" else "on"
    await db.set_setting("maintenance_mode", new_status)
    await query.answer(f"Maintenance Mode turned {new_status.upper()}", show_alert=True)
    await _show_settings(query)

    # Broadcast maintenance status to all users
    if new_status == "on":
        broadcast_text = (
            "🚧 <b>MAINTENANCE MODE ENABLED</b> 🚧\n\n"
            "The bot is currently undergoing maintenance.\n"
            "Only Premium users and Admins can use the bot during this time.\n\n"
            "We'll notify you once the bot is back for everyone. Sorry for the inconvenience!"
        )
    else:
        broadcast_text = (
            f"✅ <b>MAINTENANCE COMPLETE!</b> ✅\n\n"
            f"The bot is back online and fully operational!\n"
            f"You can now use all features as normal.\n\n"
            f"<i>Thank you for your patience! 🚀</i>"
        )

    uids = await db.get_all_user_ids()
    sent, failed = 0, 0
    for user_id in uids:
        try:
            await bot.send_message(user_id, broadcast_text, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            failed += 1

    # Notify the admin who toggled it
    await bot.send_message(
        uid,
        f"📢 <b>Broadcast Complete</b>\n"
        f"✅ Sent: <code>{sent}</code>  ❌ Failed: <code>{failed}</code>",
        parse_mode=ParseMode.HTML
    )



@router.callback_query(F.data == "admin_cmds")
async def cb_admin_cmds(query: CallbackQuery):
    uid = query.from_user.id
    is_admin = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
    if not is_admin:
        await query.answer("Access Denied: Admin only.", show_alert=True)
        return

    is_owner = uid in OWNER_IDS or await db.is_db_owner(uid)

    text = (
        f"✦ ━━━━━━━ 📋 ━━━━━━━ ✦\n"
        f"🛠️ <b>ADMIN COMMANDS</b>\n"
        f"✦ ━━━━━━━ 📋 ━━━━━━━ ✦\n\n"
        f"📊 <b>Stats & Users</b>\n"
        f"🔸 <code>/stats</code> ➔ View global bot stats\n"
        f"🔸 <code>/users</code> ➔ List recent users\n\n"
        f"🔑 <b>Redeem Codes</b>\n"
        f"🔸 <code>/genkey &lt;plan&gt; &lt;days&gt; &lt;hpd&gt; [max_uses]</code>\n"
        f"🔸 <code>/codes</code> ➔ View all active codes\n"
        f"🔸 <code>/revoke &lt;code&gt;</code> ➔ Revoke a code\n\n"
        f"🚫 <b>User Management</b>\n"
        f"🔸 <code>/ban &lt;user_id&gt;</code> ➔ Ban a user\n"
        f"🔸 <code>/unban &lt;user_id&gt;</code> ➔ Unban a user\n\n"
        f"📢 <b>Broadcast</b>\n"
        f"🔸 <code>/broadcast &lt;message&gt;</code>\n"
        f"   or reply to a message/image with <code>/broadcast</code>\n\n"
        f"🔑 <b>API Keys</b>\n"
        f"🔸 <code>/genapikey &lt;user_id&gt; &lt;hpd&gt; &lt;plan&gt;</code>\n"
        f"🔸 <code>/revokeapikey &lt;api_key&gt;</code>\n"
    )

    if is_owner:
        text += (
            f"\n👑 <b>Owner Commands</b>\n"
            f"🔸 <code>/promote &lt;user_id&gt;</code> ➔ Promote to Admin\n"
            f"🔸 <code>/demote &lt;user_id&gt;</code> ➔ Demote from Admin\n"
            f"🔸 <code>/addowner &lt;user_id&gt;</code> ➔ Promote to Owner\n"
            f"🔸 <code>/removeowner &lt;user_id&gt;</code> ➔ Remove Owner\n"
            f"🔸 <code>/owners</code> ➔ List all Owners\n"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Settings", callback_data="home_settings")]
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()



@router.callback_query(F.data == "home_contact")
async def cb_home_contact(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 💬 ━━━━━━━ ✦\n"
        f"📞 <b>SUPPORT & CONTACT</b>\n"
        f"✦ ━━━━━━━ 💬 ━━━━━━━ ✦\n\n"
        f"👤 <b>Owner/Developer:</b> {OWNER_USERNAME}\n\n"
        f"💡 <i>If you face any issues, need to buy custom plans, or want to report bugs, contact support below.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Message Owner", url=f"https://t.me/{OWNER_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(text="⬅️ Back to Menu", callback_data="home_main")],
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.message(Command("help", prefix="/."))
async def cmd_help(msg: Message):
    text = (
        f"✦ ━━━━━━━ 🚀 ━━━━━━━ ✦\n"
        f"⚡ <b>AVAILABLE COMMANDS</b>\n"
        f"✦ ━━━━━━━ 🚀 ━━━━━━━ ✦\n\n"
        f"🔹 <b>Stripe Donation Gate ($1):</b>\n"
        f"<code>/check cc|mm|yy|cvv</code> (or <code>/chk</code>) ➔ Single check\n"
        f"<code>/mash cc1|mm|yy|cvv</code> ➔ Bulk check\n\n"
        f"🔹 <b>Single Card Check (Checkout):</b>\n"
        f"<code>/hit &lt;url&gt; cc|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Bulk Card Check (Checkout):</b>\n"
        f"<code>/hit &lt;url&gt;</code>\n"
        f"<code>cc1|mm|yy|cvv</code>\n"
        f"<code>cc2|mm|yy|cvv</code>\n\n"
        f"🔹 <b>Auto-Gen Check from BIN (Checkout):</b>\n"
        f"<code>/hit &lt;url&gt; bin6+</code>\n\n"
        f"🔹 <b>File Check (Checkout):</b>\n"
        f"Reply to any <code>.txt</code> card list file with:\n"
        f"<code>/hit &lt;url&gt;</code>\n\n"
        f"✦ ━━━━━━━ 🛠️ ━━━━━━━ ✦\n"
        f"⚙️ <b>UTILITY TOOLS:</b>\n"
        f"✦ ━━━━━━━ 🛠️ ━━━━━━━ ✦\n\n"
        f"🔸 <code>/gen &lt;bin&gt; [qty]</code> ➔ Generate cards\n"
        f"🔸 <code>/fake [country]</code> ➔ Generate fake address\n"
        f"🔸 <code>/bin &lt;bin6&gt;</code> ➔ BIN Details lookup\n"
        f"🔸 <code>/myhits</code> ➔ View your personal hits\n"
        f"🔸 <code>/redeem &lt;code&gt;</code> ➔ Activate premium plan\n"
    )
    await msg.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("redeem", prefix="/."))
async def cmd_redeem(msg: Message, command: CommandObject):
    uid = msg.from_user.id
    code = (command.args or "").strip()
    if not code:
        await msg.answer(f"Usage: <code>/redeem YOUR-CODE-HERE</code>", parse_mode=ParseMode.HTML)
        return
    result = await db.use_redeem_code(uid, code)
    if result["success"]:
        hpd = result.get("hits_per_day", 0)
        hpd_str = f"{hpd}/day" if hpd > 0 else "Unlimited"
        await msg.answer(
            f"{EMOJI['charged']} <b>Code Redeemed!</b>\nPlan: <b>{result['plan_type']}</b>\nHits: {hpd_str}\nDuration: {result['days']} days",
            parse_mode=ParseMode.HTML
        )
    else:
        await msg.answer(f"{EMOJI['declined']} {result['error']}", parse_mode=ParseMode.HTML)


@router.message(Command("credits", prefix="/."))
async def cmd_credits(msg: Message):
    uid = msg.from_user.id
    plan = await db.get_user_plan(uid)
    if plan["unlimited"]:
        hpd = plan.get("hits_per_day", 0)
        hpd_str = f"{hpd}/day" if hpd > 0 else f"Unlimited"
        text = (
            f"<blockquote>💳 <b>My Credits</b> 💳 ❞</blockquote>\n\n"
            f"<blockquote>👑 <b>[•] Plan</b> → <b>{plan['label'].upper()}</b> ❞\n"
            f"⚡ <b>[•] Hits Limit</b> → <code>{hpd_str}</code>\n"
            f"📅 <b>[•] Expiry</b> → <code>{plan['expiry']}</code></blockquote>"
        )
    else:
        hits = await db.get_daily_hits(uid)
        remaining = max(0, FREE_DAILY_LIMIT - hits)
        text = (
            f"<blockquote>💳 <b>My Credits</b> 💳 ❞</blockquote>\n\n"
            f"<blockquote>🆓 <b>[•] Plan</b> → <b>FREE</b> ❞\n"
            f"⚡ <b>[•] Hits Used</b> → <code>{hits}/{FREE_DAILY_LIMIT}</code>\n"
            f"🌀 <b>[•] Remaining</b> → <code>{remaining}</code></blockquote>"
        )
    await msg.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("ping", prefix="/."))
async def cmd_ping(msg: Message):
    start = time.time()
    sent = await msg.answer(f"<blockquote>⚡ Pinging... ❞</blockquote>", parse_mode=ParseMode.HTML)
    latency_ms = round((time.time() - start) * 1000)
    uptime_sec = int(time.time() - _bot_start_time)
    hours, rem = divmod(uptime_sec, 3600)
    mins, secs = divmod(rem, 60)
    uptime_str = f"{hours}h {mins}m {secs}s"
    await sent.edit_text(
        f"<blockquote>🚀 <b>Pong!</b> 🚀 ❞</blockquote>\n\n"
        f"<blockquote>📡 <b>[•] Latency</b> → <code>{latency_ms}ms</code> ❞\n"
        f"⏰ <b>[•] Uptime</b> → <code>{uptime_str}</code></blockquote>",
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "home_ranking")
async def cb_home_ranking(query: CallbackQuery):
    text = (
        f"✦ ━━━━━━━ 🏆 ━━━━━━━ ✦\n"
        f"🏆 <b>TOP HITTERS LEADERBOARD</b>\n"
        f"✦ ━━━━━━━ 🏆 ━━━━━━━ ✦\n\n"
        f"🥇 <b>1st</b> ➔ Damxd89 (<code>1,291</code> hits)\n"
        f"🥈 <b>2nd</b> ➔ Hades Hitter (<code>910</code> hits)\n"
        f"🥉 <b>3rd</b> ➔ Zenith Carder (<code>402</code> hits)\n"
        f"✨ <b>4th</b> ➔ Carder Pro (<code>382</code> hits)\n"
        f"✨ <b>5th</b> ➔ lol lol (<code>369</code> hits)\n\n"
        f"<i>Keep checking to rank up on the global board!</i>"
    )
    kb = _kb([("⬅️ Back to Menu", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.callback_query(F.data == "home_bins")
async def cb_home_bins(query: CallbackQuery):
    uid = query.from_user.id
    bins = await db.get_saved_bins(uid)
    text = (
        f"✦ ━━━━━━━ 📁 ━━━━━━━ ✦\n"
        f"📁 <b>SAVED BIN CONFIGURATIONS</b>\n"
        f"✦ ━━━━━━━ 📁 ━━━━━━━ ✦\n\n"
    )
    if not bins:
        text += "<i>No saved BINs found.</i>\n\n💡 <b>Save BIN command:</b>\n<code>/savebin &lt;name&gt; &lt;bin&gt;</code>"
    else:
        lines = [f"📁 <b>{b['name'].upper()}</b> ➔ <code>{b['bin_value']}</code>" for b in bins]
        text += "\n".join(lines) + f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n❌ <b>Delete:</b> <code>/delbin &lt;name&gt;</code>"
    kb = _kb([("⬅️ Back to Menu", "home_main")])
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await query.answer()


@router.message(Command("savebin", prefix="/."))
async def cmd_savebin(msg: Message, command: CommandObject):
    uid = msg.from_user.id
    args = (command.args or "").strip().split(None, 1)
    if len(args) < 2:
        await msg.answer(f"Usage: <code>/savebin &lt;name&gt; &lt;bin&gt;</code>", parse_mode=ParseMode.HTML)
        return
    ok = await db.save_bin(uid, args[0], args[1])
    if ok:
        await msg.answer(f"{EMOJI['charged']} BIN saved as <b>{args[0]}</b>.", parse_mode=ParseMode.HTML)
    else:
        await msg.answer(f"{EMOJI['declined']} Failed.", parse_mode=ParseMode.HTML)


@router.message(Command("mybins", prefix="/."))
async def cmd_mybins(msg: Message):
    uid = msg.from_user.id
    bins = await db.get_saved_bins(uid)
    if not bins:
        await msg.answer(f"<blockquote><i>No saved BINs. Use /savebin.</i> ❞</blockquote>", parse_mode=ParseMode.HTML)
        return
    lines = [f"<blockquote>📁 <b>{b['name'].upper()}</b> → <code>{b['bin_value']}</code> ❞</blockquote>" for b in bins]
    await msg.answer(f"<blockquote>📁 <b>Saved Bins</b> 📁 ❞</blockquote>\n\n" + "\n\n".join(lines), parse_mode=ParseMode.HTML)


@router.message(Command("delbin", prefix="/."))
async def cmd_delbin(msg: Message, command: CommandObject):
    name = (command.args or "").strip()
    if not name:
        await msg.answer(f"Usage: <code>/delbin &lt;name&gt;</code>", parse_mode=ParseMode.HTML)
        return
    await db.delete_saved_bin(msg.from_user.id, name)
    await msg.answer(f"{EMOJI['charged']} BIN <b>{name}</b> removed.", parse_mode=ParseMode.HTML)


@router.message(Command("myapi", prefix="/."))
async def cmd_myapi(msg: Message):
    uid = msg.from_user.id
    keys = await db.get_user_api_keys(uid)
    if not keys:
        await msg.answer(
            f"<blockquote>❌ <b>No API Keys found.</b> ❞</blockquote>\n\n"
            f"<blockquote>💡 <i>Contact support/admins to purchase or generate a Business API key.</i> ❞</blockquote>",
            parse_mode=ParseMode.HTML
        )
        return

    text = f"<blockquote>🔑 <b>Your Business API Keys</b> ❞</blockquote>\n\n"
    for i, k in enumerate(keys):
        status_label = "🟢 Active" if k["is_active"] else "🔴 Revoked"
        limit_label = f"<code>{k['hits_per_day']}</code>" if k["hits_per_day"] > 0 else "Unlimited"
        text += (
            f"<blockquote>🔑 <b>Key {i+1}</b> → <code>{k['key']}</code> ❞\n"
            f"├─ <b>Status:</b> {status_label}\n"
            f"├─ <b>Plan:</b> <code>{k['plan_type']}</code>\n"
            f"└─ <b>Quota:</b> <code>{k['daily_count']}</code> / {limit_label} hits today</blockquote>\n\n"
        )
    await msg.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("id", prefix="/."))
async def cmd_id(msg: Message):
    if msg.reply_to_message:
        target_user = msg.reply_to_message.from_user
        if target_user:
            text = (
                f"👤 <b>User:</b> {target_user.mention_html()}\n"
                f"🆔 <b>User ID:</b> <code>{target_user.id}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{msg.chat.id}</code>"
            )
        else:
            text = f"🆔 <b>Chat ID:</b> <code>{msg.chat.id}</code>"
    else:
        text = (
            f"👤 <b>Your Profile:</b> {msg.from_user.mention_html()}\n"
            f"🆔 <b>Your User ID:</b> <code>{msg.from_user.id}</code>\n"
            f"💬 <b>Chat ID:</b> <code>{msg.chat.id}</code>"
        )
    await msg.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("plan", "plans", prefix="/."))
async def cmd_plan(msg: Message, command: CommandObject):
    args = (command.args or "").strip().lower()
    
    packages = {
        "explorer": {"name": "𝐄𝐱𝐩𝐥𝐨𝐫𝐞𝐫 𝐏𝐚𝐜𝐤", "price": "$3", "duration": "1 day"},
        "adventure": {"name": "𝐀𝐝𝐯𝐞𝐧𝐭𝐮𝐫𝐞 𝐏𝐚𝐜𝐤", "price": "$7", "duration": "3 days"},
        "world": {"name": "𝐖𝐨𝐫𝐥𝐝 𝐓𝐫𝐚𝐯𝐞𝐥𝐞𝐫", "price": "$15", "duration": "7 days"},
        "magic": {"name": "𝐌𝐚𝐠𝐢𝐜 𝐒𝐞𝐞𝐤𝐞𝐫", "price": "$25", "duration": "15 days"},
        "legendary": {"name": "𝐋𝐞𝐠𝐞𝐧𝐝𝐚𝐫𝐲 𝐏𝐚𝐭𝐡", "price": "$40", "duration": "30 days"},
        "never": {"name": "Never die", "price": "$100", "duration": "356 days"},
        "bot": {"name": "BOT", "price": "$200", "duration": "LIFETIME"},
        "stripe": {"name": "Stripe + payu + razorpay + epoch", "price": "$299", "duration": "LIFETIME"},
        "allinone": {"name": "All in one", "price": "$399 / $499 on based of demand", "duration": "LIFETIME"}
    }
    
    if args:
        matched_pkg = None
        for key, pkg in packages.items():
            if key in args or args in pkg["name"].lower() or args in key:
                matched_pkg = pkg
                break
                
        if matched_pkg:
            text = (
                f"✅ <b>You selected:</b> {matched_pkg['name']}\n\n"
                f"To purchase this package, please send a direct message to @damxd89 with the following text:\n\n"
                f"<code>Hello @damxd89, I would like to purchase the {matched_pkg['name']} ({matched_pkg['duration']}) for {matched_pkg['price']}. My User ID is {msg.from_user.id}.</code>"
            )
            await msg.answer(text, parse_mode=ParseMode.HTML)
            return

    text = (
        "📦 <b>Available Packages</b> 📦\n\n"
        "🧭 <b>𝐄𝐱𝐩𝐥𝐨𝐫𝐞𝐫 𝐏𝐚𝐜𝐤</b>\n"
        "𝐏𝐫𝐢𝐜𝐞: $3\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧: 1 day\n\n"
        "🚀 <b>𝐀𝐝𝐯𝐞𝐧𝐭𝐮𝐫𝐞 𝐏𝐚𝐜𝐤</b>\n"
        "𝐏𝐫𝐢𝐜𝐞: $7\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧: 3 days\n\n"
        "🌍 <b>𝐖𝐨𝐫𝐥𝐝 𝐓𝐫𝐚𝐯𝐞𝐥𝐞𝐫</b>\n"
        "𝐏𝐫𝐢𝐜𝐞: $15\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧: 7 days\n\n"
        "🧙‍♂️ <b>𝐌𝐚𝐠𝐢𝐜 𝐒𝐞𝐞𝐤𝐞𝐫</b>\n"
        "𝐏𝐫𝐢𝐜𝐞: $25\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧: 15 days\n\n"
        "👑 <b>𝐋𝐞𝐠𝐞𝐧𝐝𝐚𝐫𝐲 𝐏𝐚𝐭𝐡</b>\n"
        "𝐏𝐫𝐢𝐜𝐞: $40\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧: 30 days\n\n"
        "💀 <b>Never die</b>\n"
        "𝐏𝐫𝐢𝐜𝐞 : $100\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧 : 356 days\n\n"
        "🤦‍♂️ <b>BOT</b>\n"
        "𝐏𝐫𝐢𝐜𝐞 : $200\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧 : LIFETIME\n\n"
        "💳 <b>Stripe + payu + razorpay + epoch</b>\n"
        "𝐏𝐫𝐢𝐜𝐞 : $299\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧 : LIFETIME\n\n"
        "🌐 <b>All in one</b>\n"
        "𝐏𝐫𝐢𝐜𝐞 : $399 / $499 on based of demand\n"
        "𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧 : LIFETIME\n\n"
        "<i>To buy, use:</i> <code>/plan &lt;package name&gt;</code>\n"
        "<i>Example:</i> <code>/plan explorer</code>"
    )
    await msg.answer(text, parse_mode=ParseMode.HTML)
