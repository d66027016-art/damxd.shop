import time
import re
import random
import string
import json
import asyncio
import tls_client

def get_random_string(length=10):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

async def get_checkout_info(url: str, proxy: str = None) -> dict:
    """Fetches info from a Cashfree link."""
    try:
        session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
            
        res = await asyncio.to_thread(session.get, url, timeout_seconds=15)
        
        if res.status_code != 200:
            return {"error": f"Failed to load URL (Status: {res.status_code})"}
            
        return {
            "key_id": "cf_key",
            "amount": 1.0,
            "currency": "INR",
            "merchant": "Cashfree Merchant",
            "url": url,
            "raw_amount": "100"
        }
    except Exception as e:
        return {"error": f"Error fetching checkout: {str(e)}"}

async def charge_card(card: dict, checkout: dict, proxy: str = None) -> dict:
    """Attempts to charge a card via Cashfree API."""
    start_time = time.perf_counter()
    result = {
        "card": f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}",
        "status": "FAILED",
        "response": "Cashfree placeholder response",
        "time": 0.0
    }
    await asyncio.sleep(1)
    result["time"] = round(time.perf_counter() - start_time, 2)
    return result
