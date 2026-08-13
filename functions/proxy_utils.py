import random
import database.db as db
from config import SYSTEM_PROXIES

def get_proxy_url(proxy_str: str) -> str:
    if not proxy_str:
        return None
    try:
        if "@" in proxy_str:
            auth, hostport = proxy_str.rsplit("@", 1)
            user, password = auth.split(":", 1)
            host, port = hostport.rsplit(":", 1)
            return f"http://{user}:{password}@{host}:{port}"
        parts = proxy_str.split(":")
        if len(parts) == 4:
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        if len(parts) == 2:
            return f"http://{parts[0]}:{parts[1]}"
    except Exception:
        pass
    return None

async def pick_proxy(user_id: int = None) -> str:
    if user_id:
        mode = await db.get_user_proxy_mode(user_id)
        if mode == "own":
            user_proxies = await db.get_proxies(user_id)
            if user_proxies:
                return get_proxy_url(random.choice(user_proxies))
    system_proxy = await db.get_setting("system_proxy", "")
    if system_proxy:
        return get_proxy_url(system_proxy)
    if SYSTEM_PROXIES:
        return get_proxy_url(random.choice(SYSTEM_PROXIES))
    return None
