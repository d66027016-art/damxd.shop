import asyncio
import time
from aiogram import Router, Bot, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode

import os
import database.db as db
from config import OWNER_IDS, BOT_NAME, PLAN_PRICES, UPDATE_PASSWORD
from functions.emojis import EMOJI

router = Router()

# ─── Permanent protected owner — can NEVER be banned, demoted, or removed ───
PROTECTED_OWNER_ID = 8303990517

async def is_owner(uid: int) -> bool:
    """True if the user is a hardcoded super owner OR a DB-promoted owner."""
    return uid in OWNER_IDS or await db.is_db_owner(uid)

async def is_authorized(uid: int) -> bool:
    """True if the user is an owner or an admin."""
    return await is_owner(uid) or await db.is_admin(uid)

@router.message(Command("stats", prefix="/."))
async def cmd_stats(msg: Message):
    if not await is_authorized(msg.from_user.id):
        return

    stats = await db.get_global_stats()
    text = (
        f"「 {EMOJI['stats']} GLOBAL STATS 」\n\n"
        f"Total Users: <code>{stats['users']}</code>\n"
        f"Total Checks: <code>{stats['checks']}</code>\n"
        f"Charged Hits: <code>{stats['charged']}</code>\n"
        f"Live Hits: <code>{stats['live']}</code>\n"
        f"Banned Users: <code>{stats['banned']}</code>\n"
        f"Active Codes: <code>{stats['active_codes']}</code>"
    )
    await msg.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("genkey", prefix="/."))
async def cmd_genkey(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    args = (command.args or "").strip().split()
    if len(args) < 3:
        await msg.answer(
            f"Usage: <code>/genkey &lt;plan&gt; &lt;days&gt; &lt;hpd&gt; [max_uses]</code>\n\n"
            f"Example: <code>/genkey PREMIUM 30 100 1</code>",
            parse_mode=ParseMode.HTML
        )
        return

    plan_type = args[0]
    try:
        days = int(args[1])
        hpd = int(args[2])
        max_uses = int(args[3]) if len(args) > 3 else 1
    except ValueError:
        await msg.answer("Days, HPD and Max Uses must be numbers.")
        return

    code = await db.create_redeem_code(plan_type, days, hpd, max_uses, msg.from_user.id)
    await msg.answer(
        f"「 {EMOJI['charged']} CODE GENERATED 」\n\n"
        f"Code: <code>{code}</code>\n"
        f"Plan: <b>{plan_type}</b>\n"
        f"Days: <code>{days}</code>\n"
        f"HPD: <code>{hpd}</code>\n"
        f"Max Uses: <code>{max_uses}</code>",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("codes", prefix="/."))
async def cmd_codes(msg: Message):
    if not await is_authorized(msg.from_user.id):
        return

    codes = await db.get_active_codes()
    if not codes:
        await msg.answer("No active codes.")
        return

    lines = []
    for c in codes:
        lines.append(f"<code>{c['code']}</code> | {c['plan_type']} | {c['days']}d | {c['used_count']}/{c['max_uses']}")
    
    text = "「 ACTIVE CODES 」\n\n" + "\n".join(lines)
    await msg.answer(text, parse_mode=ParseMode.HTML)

@router.message(Command("revoke", prefix="/."))
async def cmd_revoke(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    code = (command.args or "").strip()
    if not code:
        await msg.answer("Usage: <code>/revoke CODE-HERE</code>", parse_mode=ParseMode.HTML)
        return

    ok = await db.revoke_code(code)
    if ok:
        await msg.answer(f"{EMOJI['charged']} Code <code>{code}</code> revoked.", parse_mode=ParseMode.HTML)
    else:
        await msg.answer(f"{EMOJI['declined']} Code not found.", parse_mode=ParseMode.HTML)

@router.message(Command("users", prefix="/."))
async def cmd_users(msg: Message):
    if not await is_authorized(msg.from_user.id):
        return

    users = await db.get_all_users()
    if not users:
        await msg.answer("No users found.")
        return

    header = f"「 {EMOJI['welcome']} RECENT USERS 」\n\n"
    lines = []
    for u in users[:20]:
        uname = f"@{u['username']}" if u['username'] else u['first_name'] or "User"
        lines.append(f"<code>{u['user_id']}</code> | {uname} | {u['plan_type']}")
    
    await msg.answer(header + "\n".join(lines), parse_mode=ParseMode.HTML)

@router.message(Command("ban", prefix="/."))
async def cmd_ban(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    uid_str = (command.args or "").strip()
    if not uid_str or not uid_str.isdigit():
        await msg.answer("Usage: <code>/ban &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_uid = int(uid_str)

    if target_uid == PROTECTED_OWNER_ID:
        await msg.answer("🛡️ <b>Protected Owner</b> — This user can never be banned.", parse_mode=ParseMode.HTML)
        return
    if target_uid in OWNER_IDS or await db.is_db_owner(target_uid):
        await msg.answer("❌ Cannot ban an Owner.", parse_mode=ParseMode.HTML)
        return

    await db.ban_user(target_uid)
    await msg.answer(f"{EMOJI['ban']} User <code>{target_uid}</code> banned.", parse_mode=ParseMode.HTML)

@router.message(Command("unban", prefix="/."))
async def cmd_unban(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    uid_str = (command.args or "").strip()
    if not uid_str or not uid_str.isdigit():
        await msg.answer("Usage: <code>/unban &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_uid = int(uid_str)
    await db.unban_user(target_uid)
    await msg.answer(f"{EMOJI['welcome']} User <code>{target_uid}</code> unbanned.", parse_mode=ParseMode.HTML)

@router.message(Command("promote", prefix="/."))
async def cmd_promote(msg: Message, command: CommandObject):
    if msg.from_user.id not in OWNER_IDS:
        return

    uid_str = (command.args or "").strip()
    if not uid_str or not uid_str.isdigit():
        await msg.answer("Usage: <code>/promote &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_uid = int(uid_str)
    await db.add_admin(target_uid)
    await msg.answer(f"{EMOJI['charged']} User <code>{target_uid}</code> promoted to Admin.", parse_mode=ParseMode.HTML)

@router.message(Command("demote", prefix="/."))
async def cmd_demote(msg: Message, command: CommandObject):
    if msg.from_user.id not in OWNER_IDS:
        return

    uid_str = (command.args or "").strip()
    if not uid_str or not uid_str.isdigit():
        await msg.answer("Usage: <code>/demote &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_uid = int(uid_str)

    if target_uid == PROTECTED_OWNER_ID:
        await msg.answer("🛡️ <b>Protected Owner</b> — This user can never be demoted.", parse_mode=ParseMode.HTML)
        return

    await db.remove_admin(target_uid)
    await msg.answer(f"{EMOJI['declined']} User <code>{target_uid}</code> demoted from Admin.", parse_mode=ParseMode.HTML)

@router.message(Command("broadcast", prefix="/."))
async def cmd_broadcast(msg: Message, bot: Bot):
    if not await is_authorized(msg.from_user.id):
        return

    is_reply = False
    text = ""
    if msg.reply_to_message:
        is_reply = True
    else:
        # Extract text after command
        parts = msg.text.split(None, 1)
        if len(parts) > 1:
            text = parts[1]

    if not is_reply and not text:
        await msg.answer("Usage: <code>/broadcast &lt;message&gt;</code> or reply to a message (image, text, etc) with <code>/broadcast</code>", parse_mode=ParseMode.HTML)
        return

    uids = await db.get_all_user_ids()
    sent = 0
    failed = 0
    
    status_msg = await msg.answer(f"Starting broadcast to {len(uids)} users...")
    
    for uid in uids:
        try:
            if is_reply:
                await bot.copy_message(chat_id=uid, from_chat_id=msg.chat.id, message_id=msg.reply_to_message.message_id)
            else:
                await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.05) # Small sleep to avoid flood
        except Exception:
            failed += 1
    
    await status_msg.edit_text(f"「 BROADCAST COMPLETE 」\n\nSent: <code>{sent}</code>\nFailed: <code>{failed}</code>", parse_mode=ParseMode.HTML)


@router.message(Command("genapikey", prefix="/."))
async def cmd_genapikey(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    args = (command.args or "").strip().split()
    if len(args) < 3:
        await msg.answer(
            f"Usage: <code>/genapikey &lt;user_id&gt; &lt;hits_per_day&gt; &lt;plan_type&gt;</code>\n\n"
            f"Example: <code>/genapikey 8303990517 5000 BUSINESS</code>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        target_uid = int(args[0])
        hits_per_day = int(args[1])
    except ValueError:
        await msg.answer("User ID and Hits Per Day must be numbers.")
        return

    plan_type = args[2].upper()
    key = await db.create_api_key(target_uid, plan_type, hits_per_day)
    
    await msg.answer(
        f"「 🔑 <b>API KEY GENERATED</b> 」\n\n"
        f"👤 <b>For User ID:</b> <code>{target_uid}</code>\n"
        f"✨ <b>Plan:</b> <code>{plan_type}</code>\n"
        f"📊 <b>Daily Quota:</b> <code>{hits_per_day}</code> hits\n"
        f"🗝️ <b>Key:</b> <code>{key}</code>\n\n"
        f"⚠️ <i>Keep this key secret. Never expose it in client-side code!</i>",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("revokeapikey", prefix="/."))
async def cmd_revokeapikey(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    key = (command.args or "").strip()
    if not key:
        await msg.answer("Usage: <code>/revokeapikey &lt;api_key&gt;</code>", parse_mode=ParseMode.HTML)
        return

    ok = await db.revoke_api_key(key)
    if ok:
        await msg.answer(f"✅ API Key revoked and disabled successfully.", parse_mode=ParseMode.HTML)
    else:
        await msg.answer(f"❌ API Key not found or already inactive.", parse_mode=ParseMode.HTML)


# ─── Owner Management (owner only) ───

@router.message(Command("addowner", prefix="/."))
async def cmd_addowner(msg: Message, command: CommandObject):
    """Only owners can promote someone to Owner."""
    if not await is_owner(msg.from_user.id):
        await msg.answer("❌ <b>Access Denied.</b> Only Owners can use this command.", parse_mode=ParseMode.HTML)
        return

    uid_str = (command.args or "").strip()
    if not uid_str or not uid_str.isdigit():
        await msg.answer("Usage: <code>/addowner &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_uid = int(uid_str)
    if target_uid in OWNER_IDS or await db.is_db_owner(target_uid):
        await msg.answer(f"✔️ User <code>{target_uid}</code> is already an Owner.", parse_mode=ParseMode.HTML)
        return

    username = ""
    try:
        info = await msg.bot.get_chat(target_uid)
        username = info.username or ""
    except Exception:
        pass

    await db.add_owner(target_uid, username=username, added_by=msg.from_user.id)
    await msg.answer(
        f"👑 <b>Owner Promoted!</b>\n"
        f"👤 User ID: <code>{target_uid}</code>"
        + (f"\n@{username}" if username else ""),
        parse_mode=ParseMode.HTML
    )


@router.message(Command("removeowner", prefix="/."))
async def cmd_removeowner(msg: Message, command: CommandObject):
    """Only owners can demote an Owner."""
    if not await is_owner(msg.from_user.id):
        await msg.answer("❌ <b>Access Denied.</b> Only Owners can use this command.", parse_mode=ParseMode.HTML)
        return

    uid_str = (command.args or "").strip()
    if not uid_str or not uid_str.isdigit():
        await msg.answer("Usage: <code>/removeowner &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_uid = int(uid_str)

    if target_uid == PROTECTED_OWNER_ID:
        await msg.answer("🛡️ <b>Protected Owner</b> — This user can never be removed from the owner list.", parse_mode=ParseMode.HTML)
        return
    if target_uid in OWNER_IDS:
        await msg.answer("❌ Cannot remove a <b>super owner</b> (hardcoded in .env).", parse_mode=ParseMode.HTML)
        return

    if not await db.is_db_owner(target_uid):
        await msg.answer(f"❌ User <code>{target_uid}</code> is not a DB Owner.", parse_mode=ParseMode.HTML)
        return

    await db.remove_owner(target_uid)
    await msg.answer(
        f"🔴 <b>Owner Removed.</b>\n"
        f"👤 User ID: <code>{target_uid}</code> has been demoted from Owner.",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("owners", prefix="/."))
async def cmd_owners(msg: Message):
    """List all current owners (super + DB)."""
    if not await is_authorized(msg.from_user.id):
        return

    db_owners = await db.get_all_owners()
    lines = []

    for uid in OWNER_IDS:
        lines.append(f"👑 <b>Super Owner</b> — <code>{uid}</code> <i>(hardcoded)</i>")

    for o in db_owners:
        if o["user_id"] not in OWNER_IDS:
            uname = f"@{o['username']}" if o.get("username") else "No username"
            lines.append(f"👑 <b>Owner</b> — <code>{o['user_id']}</code> ({uname})")

    if not lines:
        await msg.answer("❌ No owners found.", parse_mode=ParseMode.HTML)
        return

    text = (
        f"✦ ━━━━━━━ 👑 ━━━━━━━ ✦\n"
        f"👑 <b>BOT OWNERS</b>\n"
        f"✦ ━━━━━━━ 👑 ━━━━━━━ ✦\n\n"
    ) + "\n".join(lines)
    await msg.answer(text, parse_mode=ParseMode.HTML)


# ─── Gateway Toggle ───

@router.message(Command("on", prefix="/."))
async def cmd_on(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    gw = (command.args or "").strip().lower()
    if not gw:
        await msg.answer("Usage: <code>/on &lt;gateway&gt;</code>\nExample: <code>/on cf</code>", parse_mode=ParseMode.HTML)
        return

    await db.set_setting(f"gateway_{gw}_status", "on")
    await msg.answer(f"✅ Gateway <b>{gw.upper()}</b> is now turned ON.", parse_mode=ParseMode.HTML)

@router.message(Command("off", prefix="/."))
async def cmd_off(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        return

    gw = (command.args or "").strip().lower()
    if not gw:
        await msg.answer("Usage: <code>/off &lt;gateway&gt;</code>\nExample: <code>/off cf</code>", parse_mode=ParseMode.HTML)
        return

    await db.set_setting(f"gateway_{gw}_status", "off")
    await msg.answer(f"❌ Gateway <b>{gw.upper()}</b> is now turned ON FOR OWNER ONLY", parse_mode=ParseMode.HTML)


# ─── Dynamic Remote Code & Command Updates (Password Gated) ───

@router.message(Command("updatecode", prefix="/."))
async def cmd_updatecode(msg: Message, command: CommandObject):
    if not await is_owner(msg.from_user.id):
        await msg.answer("❌ <b>Access Denied.</b> Only Owners can use this command.", parse_mode=ParseMode.HTML)
        return

    args = (command.args or "").strip().split(None, 1)
    if not args:
        await msg.answer("Usage: <code>/updatecode &lt;password&gt; [branch]</code>", parse_mode=ParseMode.HTML)
        return

    password = args[0]
    branch = args[1] if len(args) > 1 else "main"

    if password != UPDATE_PASSWORD:
        await msg.answer("❌ <b>Incorrect Password.</b> You are not authorized to update the code.", parse_mode=ParseMode.HTML)
        return

    status_msg = await msg.answer("⏳ <i>Pulling latest updates from Git...</i>", parse_mode=ParseMode.HTML)
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "pull", "origin", branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode().strip() + "\n" + stderr.decode().strip()
        
        await status_msg.edit_text(
            f"📦 <b>Git Pull Result:</b>\n<pre>{output}</pre>\n\n🔄 <i>Restarting the server...</i>",
            parse_mode=ParseMode.HTML
        )
        
        await asyncio.sleep(2)
        
        # Restart process
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Failed to update:</b> {str(e)}", parse_mode=ParseMode.HTML)


@router.message(Command("exec", prefix="/."))
async def cmd_exec(msg: Message, command: CommandObject):
    if not await is_owner(msg.from_user.id):
        await msg.answer("❌ <b>Access Denied.</b> Only Owners can use this command.", parse_mode=ParseMode.HTML)
        return

    raw_args = (command.args or "").strip()
    parts = raw_args.split(None, 1)
    if len(parts) < 2:
        await msg.answer("Usage: <code>/exec &lt;password&gt; &lt;shell_command&gt;</code>", parse_mode=ParseMode.HTML)
        return

    password = parts[0]
    shell_cmd = parts[1]

    if password != UPDATE_PASSWORD:
        await msg.answer("❌ <b>Incorrect Password.</b> Command execution denied.", parse_mode=ParseMode.HTML)
        return

    status_msg = await msg.answer("⏳ <i>Executing command...</i>", parse_mode=ParseMode.HTML)
    try:
        process = await asyncio.create_subprocess_shell(
            shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = (stdout.decode().strip() or "") + "\n" + (stderr.decode().strip() or "")
        
        if len(output) > 3500:
            output = output[:3500] + "\n...[truncated]"

        await status_msg.edit_text(
            f"💻 <b>Command Output:</b>\n<pre>{output}</pre>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)


@router.message(Command("editcode", prefix="/."))
async def cmd_editcode(msg: Message, command: CommandObject):
    if not await is_owner(msg.from_user.id):
        await msg.answer("❌ <b>Access Denied.</b> Only Owners can use this command.", parse_mode=ParseMode.HTML)
        return

    raw_args = (command.args or "").strip()
    lines = raw_args.split("\n", 2)
    if len(lines) < 3:
        await msg.answer(
            "Usage:\n<code>/editcode &lt;password&gt;\n&lt;filepath&gt;\n&lt;new content&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return

    password = lines[0].strip()
    filepath = lines[1].strip()
    content = lines[2]

    if password != UPDATE_PASSWORD:
        await msg.answer("❌ <b>Incorrect Password.</b> Code modification denied.", parse_mode=ParseMode.HTML)
        return

    abs_path = os.path.abspath(filepath)
    workspace_path = os.path.abspath(os.getcwd())
    if not abs_path.startswith(workspace_path):
        await msg.answer("❌ <b>Security Error:</b> Cannot edit files outside the workspace directory.", parse_mode=ParseMode.HTML)
        return

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        await msg.answer(
            f"✅ File <code>{filepath}</code> updated successfully.\n\n🔄 <i>Restarting the server to apply changes...</i>",
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(2)
        
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await msg.answer(f"❌ <b>Failed to write file:</b> {str(e)}", parse_mode=ParseMode.HTML)


@router.message(Command("addchat", "addgp", prefix="/."))
async def cmd_addchat(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        await msg.answer(
            "❌ <b>Access Denied.</b> Only Owners/Admins can use this command.\n\n"
            "💡 <i>If you are an Owner/Admin, please send this command <b>non-anonymously</b> (disable 'Send Anonymously') or execute it in the bot's <b>private chat</b>.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    chat_id = None
    title = None
    args = (command.args or "").strip()
    if args:
        try:
            raw_id = args.split()[0]
            if not raw_id.startswith("-"):
                if len(raw_id) >= 9:
                    if raw_id.startswith("100"):
                        chat_id = -int(raw_id)
                    else:
                        chat_id = -int(f"100{raw_id}")
                else:
                    chat_id = -int(raw_id)
            else:
                chat_id = int(raw_id)
            title = " ".join(args.split()[1:]) or f"Chat ID {chat_id}"
        except ValueError:
            await msg.answer("❌ Chat ID must be a number.")
            return
    else:
        # Use current chat
        if msg.chat.type == "private":
            await msg.answer("❌ Please provide a chat ID or run this command in a group.")
            return
        chat_id = msg.chat.id
        title = msg.chat.title or "Group Chat"

    await db.add_auth_chat(chat_id, title)
    await msg.answer(f"✅ <b>Group Authorized</b>\n\nTitle: <code>{title}</code>\nID: <code>{chat_id}</code>", parse_mode=ParseMode.HTML)


@router.message(Command("delchat", "delgp", prefix="/."))
async def cmd_delchat(msg: Message, command: CommandObject):
    if not await is_authorized(msg.from_user.id):
        await msg.answer(
            "❌ <b>Access Denied.</b> Only Owners/Admins can use this command.\n\n"
            "💡 <i>If you are an Owner/Admin, please send this command <b>non-anonymously</b> (disable 'Send Anonymously') or execute it in the bot's <b>private chat</b>.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    chat_id = None
    args = (command.args or "").strip()
    if args:
        try:
            raw_id = args.split()[0]
            if not raw_id.startswith("-"):
                if len(raw_id) >= 9:
                    if raw_id.startswith("100"):
                        chat_id = -int(raw_id)
                    else:
                        chat_id = -int(f"100{raw_id}")
                else:
                    chat_id = -int(raw_id)
            else:
                chat_id = int(raw_id)
        except ValueError:
            await msg.answer("❌ Chat ID must be a number.")
            return
    else:
        if msg.chat.type == "private":
            await msg.answer("❌ Please provide a chat ID or run this command in a group.")
            return
        chat_id = msg.chat.id

    removed = await db.remove_auth_chat(chat_id)
    if removed:
        await msg.answer(f"✅ <b>Group Unauthorized</b>\n\nID: <code>{chat_id}</code>", parse_mode=ParseMode.HTML)
    else:
        await msg.answer(f"❌ Chat with ID <code>{chat_id}</code> was not authorized.", parse_mode=ParseMode.HTML)


@router.message(Command("listchats", prefix="/."))
async def cmd_listchats(msg: Message):
    if not await is_authorized(msg.from_user.id):
        return

    chats = await db.get_all_auth_chats()
    if not chats:
        await msg.answer("ℹ️ No group chats are currently authorized.")
        return

    text = f"<b>📋 AUTHORIZED CHATS ({len(chats)}):</b>\n\n"
    for i, chat in enumerate(chats, 1):
        title = chat.get("title") or "Unnamed"
        cid = chat.get("chat_id")
        text += f"{i}. <b>{title}</b> (<code>{cid}</code>)\n"

    await msg.answer(text, parse_mode=ParseMode.HTML)





