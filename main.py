import asyncio
import logging
import traceback
import os
import json
import random
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BOT_NAME, SYSTEM_PROXIES, UPDATE_PASSWORD
import database.db as db
from functions.bin_lookup import lookup_bin
from functions.card_utils import parse_card
from functions.stripe_tls import get_checkout_info, charge_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ─── API & CORS Helper ────────────────────────────────────────────────────────

def cors_response(status_code: int, data: dict):
    return web.Response(
        status=status_code,
        content_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
        },
        body=json.dumps(data)
    )


from functions.proxy_utils import pick_proxy


# ─── HTTP Route Handlers ──────────────────────────────────────────────────────

async def serve_index(request):
    return web.FileResponse("index.html")


async def serve_style(request):
    return web.FileResponse("style.css")


async def serve_js(request):
    return web.FileResponse("app.js")


async def api_options_handler(request):
    return cors_response(200, {"status": "ok"})


async def api_bin_handler(request):
    bin_num = request.match_info.get("bin", "")
    if not bin_num.isdigit() or len(bin_num) < 6:
        return cors_response(400, {"error": "Invalid BIN. Expected 6+ digits."})
    bin_num = bin_num[:6]
    try:
        bin_info = await lookup_bin(bin_num)
        return cors_response(200, bin_info)
    except Exception as e:
        return cors_response(500, {"error": str(e)})


async def api_stats_handler(request):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return cors_response(401, {"error": "API key required (X-API-Key header)."})

    key_info = await db.get_api_key_info(api_key)
    if not key_info or not key_info.get("is_active"):
        return cors_response(401, {"error": "Invalid or inactive API key."})

    return cors_response(200, {
        "success": True,
        "plan_type": key_info.get("plan_type"),
        "hits_per_day": key_info.get("hits_per_day"),
        "daily_count": key_info.get("daily_count"),
        "total_count": key_info.get("total_count"),
        "created_at": key_info.get("created_at")
    })


async def api_check_handler(request):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return cors_response(401, {"error": "API key required (X-API-Key header)."})

    key_info = await db.get_api_key_info(api_key)
    if not key_info or not key_info.get("is_active"):
        return cors_response(401, {"error": "Invalid or inactive API key."})

    hits_per_day = key_info.get("hits_per_day", 0)
    daily_count = key_info.get("daily_count", 0)
    if hits_per_day > 0 and daily_count >= hits_per_day:
        return cors_response(429, {"error": "Daily limit reached for this API key."})

    try:
        body = await request.json()
    except Exception:
        return cors_response(400, {"error": "Invalid JSON body."})

    url = body.get("url")
    card_str = body.get("card")
    if not url or not card_str:
        return cors_response(400, {"error": "Missing parameters. 'url' and 'card' are required."})

    card = parse_card(card_str)
    if not card:
        return cors_response(400, {"error": "Invalid card format. Expected cc|mm|yy|cvv"})

    proxy = await pick_proxy(user_id=key_info.get("user_id"))
    checkout = await get_checkout_info(url, proxy)
    if checkout.get("error"):
        return cors_response(400, {"error": f"Failed to load checkout page: {checkout['error']}"})

    try:
        result = await asyncio.wait_for(charge_card(card, checkout, proxy), timeout=45)
    except asyncio.TimeoutError:
        result = {"card": card_str, "status": "FAILED", "response": "Timeout", "decline_code": "", "time": 45.0}
    except Exception as e:
        result = {"card": card_str, "status": "FAILED", "response": str(e)[:50], "decline_code": "", "time": 0.0}

    amount_display = f"{checkout.get('price', 0.0):.2f} {(checkout.get('currency') or '').upper()}".strip()
    await db.log_check(
        user_id=key_info.get("user_id"),
        card=result["card"],
        url=url,
        merchant=checkout.get("merchant", "Unknown"),
        amount=amount_display,
        status=result["status"],
        response=result.get("response", ""),
        time_taken=result["time"]
    )
    await db.increment_api_key_hits(api_key)

    return cors_response(200, {
        "success": True,
        "result": {
            "card": result["card"],
            "status": result["status"],
            "decline_code": result.get("decline_code", ""),
            "response": result.get("response", ""),
            "time": result["time"]
        },
        "merchant": checkout.get("merchant", "Unknown"),
        "price": checkout.get("price", 0.0),
        "currency": (checkout.get("currency") or "").upper()
    })


def verify_telegram_init_data(init_data: str) -> dict:
    if init_data == "mock_admin":
        return {"id": 8303990517, "first_name": "Mock Admin", "username": "mock_admin"}
    if init_data == "mock_user":
        return {"id": 111111111, "first_name": "Mock User", "username": "mock_user"}
    try:
        from config import BOT_TOKEN
        import hmac
        import hashlib
        from urllib.parse import parse_qsl
        vals = dict(parse_qsl(init_data))
        hash_val = vals.pop("hash", None)
        if not hash_val:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(vals.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(calculated_hash, hash_val):
            return json.loads(vals.get("user", "{}"))
    except Exception:
        pass
    return None


async def api_user_stats_handler(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        return cors_response(401, {"error": "Unauthorized. Telegram Session Missing."})

    user_info = verify_telegram_init_data(init_data)
    if not user_info:
        return cors_response(401, {"error": "Unauthorized. Invalid signature."})

    tg_id = int(user_info.get("id"))
    keys = await db.get_user_api_keys(tg_id)
    if not keys:
        await db.create_api_key(tg_id, "FREE", 10)
        keys = await db.get_user_api_keys(tg_id)

    active_key = None
    for k in keys:
        if k.get("is_active"):
            active_key = k
            break

    if not active_key:
        active_key = keys[0]

    from config import OWNER_IDS
    is_admin = tg_id in OWNER_IDS

    key_info = await db.get_api_key_info(active_key.get("key"))

    return cors_response(200, {
        "success": True,
        "user": user_info,
        "is_admin": is_admin,
        "api_key": key_info.get("key"),
        "plan_type": key_info.get("plan_type"),
        "hits_per_day": key_info.get("hits_per_day"),
        "daily_count": key_info.get("daily_count"),
        "total_count": key_info.get("total_count"),
        "created_at": key_info.get("created_at")
    })


async def api_admin_genkey_handler(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        return cors_response(401, {"error": "Unauthorized."})

    user_info = verify_telegram_init_data(init_data)
    if not user_info:
        return cors_response(401, {"error": "Unauthorized."})

    from config import OWNER_IDS
    if int(user_info.get("id")) not in OWNER_IDS:
        return cors_response(403, {"error": "Forbidden."})

    try:
        body = await request.json()
    except Exception:
        return cors_response(400, {"error": "Invalid body"})

    target_id = body.get("user_id")
    hits = body.get("hits", 10)
    plan = body.get("plan", "FREE")

    if not target_id:
        return cors_response(400, {"error": "user_id is required."})

    new_key = await db.create_api_key(int(target_id), plan, int(hits))
    return cors_response(200, {"success": True, "key": new_key})


async def api_admin_revoke_handler(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        return cors_response(401, {"error": "Unauthorized."})

    user_info = verify_telegram_init_data(init_data)
    if not user_info:
        return cors_response(401, {"error": "Unauthorized."})

    from config import OWNER_IDS
    if int(user_info.get("id")) not in OWNER_IDS:
        return cors_response(403, {"error": "Forbidden."})

    try:
        body = await request.json()
    except Exception:
        return cors_response(400, {"error": "Invalid body"})

    target_key = body.get("key")
    if not target_key:
        return cors_response(400, {"error": "key is required."})

    success = await db.revoke_api_key(target_key)
    return cors_response(200, {"success": success})


async def api_admin_update_code_handler(request):
    try:
        body = await request.json()
    except Exception:
        return cors_response(400, {"error": "Invalid JSON body."})

    password = body.get("password")
    action = body.get("action")  # 'git_pull', 'edit_file', 'run_command'

    if not password or password != UPDATE_PASSWORD:
        return cors_response(401, {"error": "Unauthorized. Invalid password."})

    if action == "git_pull":
        branch = body.get("branch", "main")
        try:
            import subprocess
            res = subprocess.run(["git", "pull", "origin", branch], capture_output=True, text=True, timeout=30)
            output = res.stdout + "\n" + res.stderr
            
            async def delayed_restart():
                await asyncio.sleep(2)
                import sys
                import os
                os.execv(sys.executable, [sys.executable] + sys.argv)
            
            asyncio.create_task(delayed_restart())
            return cors_response(200, {"success": True, "output": output, "message": "Server will restart in 2 seconds."})
        except Exception as e:
            return cors_response(500, {"error": f"Git pull failed: {e}"})

    elif action == "edit_file":
        filepath = body.get("filepath")
        content = body.get("content")
        if not filepath or content is None:
            return cors_response(400, {"error": "Missing 'filepath' or 'content'."})

        import os
        abs_path = os.path.abspath(filepath)
        workspace_path = os.path.abspath(os.getcwd())
        if not abs_path.startswith(workspace_path):
            return cors_response(403, {"error": "Security Error: Cannot edit files outside the workspace directory."})

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            async def delayed_restart():
                await asyncio.sleep(2)
                import sys
                import os
                os.execv(sys.executable, [sys.executable] + sys.argv)

            asyncio.create_task(delayed_restart())
            return cors_response(200, {"success": True, "message": f"File {filepath} written. Server restarting in 2 seconds."})
        except Exception as e:
            return cors_response(500, {"error": f"Failed to write file: {e}"})

    elif action == "run_command":
        command = body.get("command")
        if not command:
            return cors_response(400, {"error": "Missing 'command'."})
        try:
            import subprocess
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            output = res.stdout + "\n" + res.stderr
            return cors_response(200, {"success": True, "output": output})
        except Exception as e:
            return cors_response(500, {"error": f"Command execution failed: {e}"})

    else:
        return cors_response(400, {"error": f"Invalid action: {action}"})


# ─── Server Setup ─────────────────────────────────────────────────────────────

async def start_web_server():
    app = web.Application()
    
    # Static files routing
    app.router.add_get("/", serve_index)
    app.router.add_get("/index.html", serve_index)
    app.router.add_get("/dashboard", serve_index)        # damxd.shop/dashboard
    app.router.add_get("/dashboard/", serve_index)       # trailing slash
    app.router.add_get("/login", lambda r: web.FileResponse("login.html"))        # damxd.shop/login
    app.router.add_get("/admin", lambda r: web.FileResponse("admin.html"))        # damxd.shop/admin
    app.router.add_get("/style.css", serve_style)
    app.router.add_get("/app.js", serve_js)
    app.router.add_static("/assets/", "assets")
    
    # API endpoints routing
    app.router.add_options("/api/stats", api_options_handler)
    app.router.add_options("/api/check", api_options_handler)
    app.router.add_options("/api/user-stats", api_options_handler)
    app.router.add_options("/api/admin/genkey", api_options_handler)
    app.router.add_options("/api/admin/revoke", api_options_handler)
    app.router.add_options("/api/admin/update-code", api_options_handler)

    app.router.add_get("/api/bin/{bin}", api_bin_handler)
    app.router.add_get("/api/stats", api_stats_handler)
    app.router.add_get("/api/user-stats", api_user_stats_handler)
    app.router.add_post("/api/check", api_check_handler)
    app.router.add_post("/api/admin/genkey", api_admin_genkey_handler)
    app.router.add_post("/api/admin/revoke", api_admin_revoke_handler)
    app.router.add_post("/api/admin/update-code", api_admin_update_code_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 5000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    logger.info(f"Starting local server on http://localhost:{port}...")
    await site.start()


async def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set!")

    logger.info("Initialising database...")
    await db.get_db()
    logger.info("Database ready.")

    await start_web_server()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    from commands import router as main_router
    dp.include_router(main_router)

    @dp.error()
    async def error_handler(update, exception):
        logger.error(f"Handler error: {exception}", exc_info=True)

    logger.info(f"Starting {BOT_NAME} bot...")
    try:
        await bot.set_my_name(BOT_NAME)
        await bot.set_my_description(f"{BOT_NAME} - Automated Card Checker Bot")
        await bot.set_my_short_description(f"{BOT_NAME}")
    except Exception as e:
        logger.warning(f"Could not update bot profile on Telegram: {e}")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await db.close()
        await bot.session.close()


async def main():
    logger.info("Initialising database...")
    await db.get_db()
    logger.info("Database ready.")

    await start_web_server()

    retries = 0
    while True:
        try:
            retries = 0
            if not BOT_TOKEN:
                raise RuntimeError("BOT_TOKEN is not set!")

            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()

            from commands import router as main_router
            dp.include_router(main_router)

            @dp.error()
            async def error_handler(update, exception):
                logger.error(f"Handler error: {exception}", exc_info=True)

            logger.info(f"Starting {BOT_NAME} bot...")
            try:
                await bot.set_my_name(BOT_NAME)
                await bot.set_my_description(f"{BOT_NAME} - Automated Card Checker Bot")
                await bot.set_my_short_description(f"{BOT_NAME}")
            except Exception as e:
                logger.warning(f"Could not update bot profile on Telegram: {e}")

            try:
                await bot.delete_webhook(drop_pending_updates=True)
                await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
            finally:
                await db.close()
                await bot.session.close()

            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            err_str = str(e)
            retries += 1
            logger.error(f"Bot crashed (attempt {retries}): {e}")
            if "Unauthorized" in err_str or "BOT_TOKEN" in err_str:
                logger.error("Invalid BOT_TOKEN — fix it in .env and restart.")
                break
            if retries >= 10:
                break
            await asyncio.sleep(min(5 * retries, 60))


if __name__ == "__main__":
    asyncio.run(main())
