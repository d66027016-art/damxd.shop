from aiogram import Router, BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject, Message, CallbackQuery
import database.db as db
from config import OWNER_IDS

from commands.start  import router as start_router
from commands.gen    import router as gen_router
from commands.co     import router as co_router
from commands.proxy  import router as proxy_router
from commands.admin  import router as admin_router
from commands.fake   import router as fake_router
from commands.rz     import router as rz_router
from commands.payu   import router as payu_router
from commands.cf     import router as cf_router
from commands.epoch  import router as epoch_router
from commands.hit    import router as hit_router
from commands.check  import router as check_router

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        maintenance = await db.get_setting("maintenance_mode", "off")
        if maintenance == "on":
            user = data.get("event_from_user")
            if user:
                uid = user.id
                is_admin_or_owner = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
                if not is_admin_or_owner:
                    plan = await db.get_user_plan(uid)
                    is_premium = plan and plan.get("unlimited", False)
                    if not is_premium:
                        if isinstance(event, Message):
                            await event.answer(
                                "🚧 <b>MAINTENANCE MODE ENABLED</b> 🚧\n\n"
                                "The bot is currently undergoing maintenance.\n"
                                "Only Premium users and Admins can use the bot during this time.\n\n"
                                "We'll notify you once the bot is back for everyone. Sorry for the inconvenience!",
                                parse_mode="HTML"
                            )
                        elif isinstance(event, CallbackQuery):
                            await event.answer(
                                "⚠️ Bot is in Maintenance Mode. Premium and Admins only.",
                                show_alert=True
                            )
                        return None
        return await handler(event, data)


class GroupAuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        chat = None
        if isinstance(event, Message):
            chat = event.chat
            msg_text = event.text or ""
            if msg_text.startswith(("/", ".")):
                chat_id = chat.id
                uid = user.id if user else 0
                chat_title = chat.title or "Private"
                try:
                    with open("commands_log.txt", "a", encoding="utf-8") as f:
                        f.write(f"Chat: {chat_title} ({chat_id}) | Sender: {user.first_name if user else 'None'} ({uid}) | Msg: {msg_text}\n")
                except Exception:
                    pass
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat

        if chat and chat.type in ("group", "supergroup"):
            chat_id = chat.id
            uid = user.id if user else 0
            is_admin_or_owner = uid in OWNER_IDS or await db.is_db_owner(uid) or await db.is_admin(uid)
            
            plan = await db.get_user_plan(uid) if uid else {}
            is_premium = plan and (plan.get("unlimited") or plan.get("type", "free") != "free")
            
            if not is_admin_or_owner and not is_premium:
                is_auth = await db.is_chat_authorized(chat_id)
                if not is_auth:
                    if isinstance(event, Message):
                        text = (event.text or "").strip().lower()
                        # Bypass authorization check for addchat/addgp commands so owners can use them in the group
                        if text.startswith(("/addchat", "/addgp", ".addchat", ".addgp")):
                            return await handler(event, data)
                        if text.startswith(("/", ".")):
                            await event.answer(
                                f"❌ <b>Group Unauthorized</b> ❌\n\n"
                                f"This group (ID: <code>{chat_id}</code>) is not authorized to use this bot.\n"
                                f"Please contact the owner to authorize this group\n"
                                f"and mention @damxd89",
                                parse_mode="HTML"
                            )
                    elif isinstance(event, CallbackQuery):
                        await event.answer(
                            "❌ Group Unauthorized. Contact Owner to authorize by @damxd89.",
                            show_alert=True
                        )
                    return None

        return await handler(event, data)


router = Router()
router.message.outer_middleware(MaintenanceMiddleware())
router.message.outer_middleware(GroupAuthMiddleware())
router.callback_query.outer_middleware(MaintenanceMiddleware())
router.callback_query.outer_middleware(GroupAuthMiddleware())

router.include_router(start_router)
router.include_router(gen_router)
router.include_router(co_router)
router.include_router(proxy_router)
router.include_router(admin_router)
router.include_router(fake_router)
router.include_router(rz_router)
router.include_router(payu_router)
router.include_router(cf_router)
router.include_router(epoch_router)
router.include_router(hit_router)
router.include_router(check_router)

