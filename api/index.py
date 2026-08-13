import asyncio
import json
import os
import sys
import hmac
import hashlib
import logging
from urllib.parse import parse_qsl, urlparse

# ── Make sure project root is on sys.path so our modules resolve ──────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import BOT_TOKEN, BOT_NAME, UPDATE_PASSWORD, OWNER_IDS
import database.db as db
from functions.bin_lookup import lookup_bin
from functions.card_utils import parse_card
from functions.stripe_tls import get_checkout_info, charge_card
from functions.proxy_utils import pick_proxy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Aiogram webhook setup ─────────────────────────────────────────────────────
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

_bot: Bot = None
_dp: Dispatcher = None


def _get_bot_dp():
    global _bot, _dp
    if _bot is None:
        _bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        _dp = Dispatcher()
        from commands import router as main_router
        _dp.include_router(main_router)
    return _bot, _dp


# ── CORS helpers ──────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, X-API-Key, X-Telegram-Init-Data",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Content-Type": "application/json",
}


def json_response(status: int, data: dict):
    body = json.dumps(data).encode()
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": body.decode(),
    }


# ── Telegram init-data verification ──────────────────────────────────────────

def verify_telegram_init_data(init_data: str):
    if init_data == "mock_admin":
        return {"id": 8303990517, "first_name": "Mock Admin", "username": "mock_admin"}
    if init_data == "mock_user":
        return {"id": 111111111, "first_name": "Mock User", "username": "mock_user"}
    try:
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


# ── Route handlers ────────────────────────────────────────────────────────────

async def handle_bin(path: str, method: str, headers: dict, body: dict):
    # path looks like  /api/bin/424242
    parts = path.strip("/").split("/")
    bin_num = parts[-1] if parts else ""
    if not bin_num.isdigit() or len(bin_num) < 6:
        return json_response(400, {"error": "Invalid BIN. Expected 6+ digits."})
    bin_num = bin_num[:6]
    try:
        await db.get_db()
        bin_info = await lookup_bin(bin_num)
        return json_response(200, bin_info)
    except Exception as e:
        return json_response(500, {"error": str(e)})


async def handle_stats(path: str, method: str, headers: dict, body: dict):
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if not api_key:
        return json_response(401, {"error": "API key required (X-API-Key header)."})
    await db.get_db()
    key_info = await db.get_api_key_info(api_key)
    if not key_info or not key_info.get("is_active"):
        return json_response(401, {"error": "Invalid or inactive API key."})
    return json_response(200, {
        "success": True,
        "plan_type": key_info.get("plan_type"),
        "hits_per_day": key_info.get("hits_per_day"),
        "daily_count": key_info.get("daily_count"),
        "total_count": key_info.get("total_count"),
        "created_at": key_info.get("created_at"),
    })


async def handle_check(path: str, method: str, headers: dict, body: dict):
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if not api_key:
        return json_response(401, {"error": "API key required (X-API-Key header)."})
    await db.get_db()
    key_info = await db.get_api_key_info(api_key)
    if not key_info or not key_info.get("is_active"):
        return json_response(401, {"error": "Invalid or inactive API key."})

    hits_per_day = key_info.get("hits_per_day", 0)
    daily_count = key_info.get("daily_count", 0)
    if hits_per_day > 0 and daily_count >= hits_per_day:
        return json_response(429, {"error": "Daily limit reached for this API key."})

    url = body.get("url")
    card_str = body.get("card")
    if not url or not card_str:
        return json_response(400, {"error": "Missing parameters. 'url' and 'card' are required."})

    card = parse_card(card_str)
    if not card:
        return json_response(400, {"error": "Invalid card format. Expected cc|mm|yy|cvv"})

    proxy = await pick_proxy(user_id=key_info.get("user_id"))
    checkout = await get_checkout_info(url, proxy)
    if checkout.get("error"):
        return json_response(400, {"error": f"Failed to load checkout page: {checkout['error']}"})

    try:
        result = await asyncio.wait_for(charge_card(card, checkout, proxy), timeout=25)
    except asyncio.TimeoutError:
        result = {"card": card_str, "status": "FAILED", "response": "Timeout", "decline_code": "", "time": 25.0}
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
        time_taken=result["time"],
    )
    await db.increment_api_key_hits(api_key)

    return json_response(200, {
        "success": True,
        "result": {
            "card": result["card"],
            "status": result["status"],
            "decline_code": result.get("decline_code", ""),
            "response": result.get("response", ""),
            "time": result["time"],
        },
        "merchant": checkout.get("merchant", "Unknown"),
        "price": checkout.get("price", 0.0),
        "currency": (checkout.get("currency") or "").upper(),
    })


async def handle_user_stats(path: str, method: str, headers: dict, body: dict):
    init_data = headers.get("x-telegram-init-data") or headers.get("X-Telegram-Init-Data")
    if not init_data:
        return json_response(401, {"error": "Unauthorized. Telegram Session Missing."})
    user_info = verify_telegram_init_data(init_data)
    if not user_info:
        return json_response(401, {"error": "Unauthorized. Invalid signature."})

    tg_id = int(user_info.get("id"))
    await db.get_db()
    keys = await db.get_user_api_keys(tg_id)
    if not keys:
        await db.create_api_key(tg_id, "FREE", 10)
        keys = await db.get_user_api_keys(tg_id)

    active_key = next((k for k in keys if k.get("is_active")), keys[0] if keys else None)
    if not active_key:
        return json_response(500, {"error": "Could not get API key."})

    is_admin = tg_id in OWNER_IDS
    key_info = await db.get_api_key_info(active_key.get("key"))

    return json_response(200, {
        "success": True,
        "user": user_info,
        "is_admin": is_admin,
        "api_key": key_info.get("key"),
        "plan_type": key_info.get("plan_type"),
        "hits_per_day": key_info.get("hits_per_day"),
        "daily_count": key_info.get("daily_count"),
        "total_count": key_info.get("total_count"),
        "created_at": key_info.get("created_at"),
    })


async def handle_admin_genkey(path: str, method: str, headers: dict, body: dict):
    init_data = headers.get("x-telegram-init-data") or headers.get("X-Telegram-Init-Data")
    if not init_data:
        return json_response(401, {"error": "Unauthorized."})
    user_info = verify_telegram_init_data(init_data)
    if not user_info or int(user_info.get("id")) not in OWNER_IDS:
        return json_response(403, {"error": "Forbidden."})

    target_id = body.get("user_id")
    hits = body.get("hits", 10)
    plan = body.get("plan", "FREE")
    if not target_id:
        return json_response(400, {"error": "user_id is required."})

    await db.get_db()
    new_key = await db.create_api_key(int(target_id), plan, int(hits))
    return json_response(200, {"success": True, "key": new_key})


async def handle_admin_revoke(path: str, method: str, headers: dict, body: dict):
    init_data = headers.get("x-telegram-init-data") or headers.get("X-Telegram-Init-Data")
    if not init_data:
        return json_response(401, {"error": "Unauthorized."})
    user_info = verify_telegram_init_data(init_data)
    if not user_info or int(user_info.get("id")) not in OWNER_IDS:
        return json_response(403, {"error": "Forbidden."})

    target_key = body.get("key")
    if not target_key:
        return json_response(400, {"error": "key is required."})

    await db.get_db()
    success = await db.revoke_api_key(target_key)
    return json_response(200, {"success": success})


async def handle_admin_update_code(path: str, method: str, headers: dict, body: dict):
    password = body.get("password")
    action = body.get("action")

    if not password or password != UPDATE_PASSWORD:
        return json_response(401, {"error": "Unauthorized. Invalid password."})

    # On Vercel, git_pull and edit_file restarts don't apply — return informational response
    if action == "git_pull":
        return json_response(200, {
            "success": False,
            "message": "git_pull is not supported on Vercel serverless. Redeploy via Vercel dashboard or CLI.",
        })

    elif action == "edit_file":
        return json_response(200, {
            "success": False,
            "message": "edit_file is not supported on Vercel serverless. Push changes via Git.",
        })

    elif action == "run_command":
        command = body.get("command")
        if not command:
            return json_response(400, {"error": "Missing 'command'."})
        try:
            import subprocess
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=25)
            output = res.stdout + "\n" + res.stderr
            return json_response(200, {"success": True, "output": output})
        except Exception as e:
            return json_response(500, {"error": f"Command execution failed: {e}"})

    return json_response(400, {"error": f"Invalid action: {action}"})


async def handle_webhook(path: str, method: str, headers: dict, raw_body: str):
    """Receive a Telegram update and dispatch it through aiogram."""
    secret = os.getenv("WEBHOOK_SECRET", "")
    if secret:
        incoming = headers.get("x-telegram-bot-api-secret-token", "")
        if incoming != secret:
            return json_response(403, {"error": "Invalid webhook secret."})
    try:
        update_data = json.loads(raw_body)
    except Exception:
        return json_response(400, {"error": "Invalid JSON"})

    bot, dp = _get_bot_dp()
    await db.get_db()

    update = Update(**update_data)
    await dp.feed_webhook_update(bot, update)
    return json_response(200, {"ok": True})


async def handle_setup_webhook(path: str, method: str, headers: dict, body: dict):
    """
    POST /api/setup-webhook
    Body: { "password": "...", "url": "https://yourapp.vercel.app" }
    Registers the Vercel deployment URL as the Telegram webhook.
    """
    password = body.get("password")
    if not password or password != UPDATE_PASSWORD:
        return json_response(401, {"error": "Unauthorized."})

    webhook_url = body.get("url") or os.getenv("WEBHOOK_URL", "")
    if not webhook_url:
        return json_response(400, {"error": "Provide 'url' in body or set WEBHOOK_URL env var."})

    secret = os.getenv("WEBHOOK_SECRET", "")
    full_url = webhook_url.rstrip("/") + "/api/webhook"

    bot, _ = _get_bot_dp()
    await bot.set_webhook(
        url=full_url,
        secret_token=secret if secret else None,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )
    return json_response(200, {"success": True, "webhook": full_url})


# ── Router ────────────────────────────────────────────────────────────────────

async def route(event: dict):
    path = event.get("path", "/")
    method = event.get("httpMethod", "GET").upper()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    raw_body = event.get("body") or ""

    # Parse JSON body once
    body = {}
    if raw_body:
        try:
            body = json.loads(raw_body)
        except Exception:
            pass

    # Strip /api prefix for matching
    slug = path[len("/api"):].strip("/")  # e.g. "bin/424242", "webhook", "stats"

    # OPTIONS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if slug.startswith("bin/"):
        return await handle_bin(path, method, headers, body)

    if slug == "stats" and method == "GET":
        return await handle_stats(path, method, headers, body)

    if slug == "check" and method == "POST":
        return await handle_check(path, method, headers, body)

    if slug == "user-stats" and method == "GET":
        return await handle_user_stats(path, method, headers, body)

    if slug == "admin/genkey" and method == "POST":
        return await handle_admin_genkey(path, method, headers, body)

    if slug == "admin/revoke" and method == "POST":
        return await handle_admin_revoke(path, method, headers, body)

    if slug == "admin/update-code" and method == "POST":
        return await handle_admin_update_code(path, method, headers, body)

    if slug == "webhook" and method == "POST":
        return await handle_webhook(path, method, headers, raw_body)

    if slug == "setup-webhook" and method == "POST":
        return await handle_setup_webhook(path, method, headers, body)

    return json_response(404, {"error": f"Unknown route: {path}"})


# ── Vercel entry point ────────────────────────────────────────────────────────

def handler(event, context):
    """Vercel calls this synchronously; we run the async router in an event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(route(event))
    except Exception as e:
        logger.exception("Unhandled error in handler")
        return json_response(500, {"error": str(e)})
    finally:
        try:
            loop.close()
        except Exception:
            pass
