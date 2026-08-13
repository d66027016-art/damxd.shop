"""
database/db.py  –  Firebase Firestore backend
Drop-in replacement for the previous motor/MongoDB implementation.
All public function signatures are identical.
"""
import asyncio
import json
import os
import secrets
import string
from datetime import datetime, date, timedelta, timezone
import logging

from google.cloud import firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1 import async_transaction
from google.cloud.firestore_v1.transforms import SERVER_TIMESTAMP, Increment
from google.oauth2 import service_account

from config import FREE_DAILY_LIMIT, FIREBASE_CREDENTIALS, FIREBASE_PROJECT_ID
import uuid
from google.auth import exceptions as google_auth_exceptions

# Simple in-memory mock Firestore client used as a fallback when real credentials
# are not available. Implements a tiny subset of the async client API used by
# this project (async methods only).


class _MockSnapshot:
    def __init__(self, ref, data):
        self.reference = ref
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _MockDocumentRef:
    def __init__(self, client, col, doc_id):
        self._client = client
        self._col = col
        self._id = doc_id

    async def get(self, transaction=None):
        col = self._client._store.get(self._col, {})
        data = col.get(self._id)
        return _MockSnapshot(self, data)

    async def set(self, data, merge=False):
        col = self._client._store.setdefault(self._col, {})
        if merge and self._id in col and isinstance(col[self._id], dict):
            col[self._id].update(data)
        else:
            col[self._id] = dict(data)

    async def update(self, data):
        col = self._client._store.setdefault(self._col, {})
        if self._id not in col:
            raise Exception("Document does not exist")
        for k, v in data.items():
            # Support Increment transform
            if hasattr(v, "__class__") and getattr(v.__class__, "__name__", "") == "Increment":
                col[self._id][k] = (col[self._id].get(k) or 0) + int(v._value) if hasattr(v, "_value") else col[self._id].get(k, 0) + 1
            else:
                col[self._id][k] = v

    async def delete(self):
        col = self._client._store.get(self._col, {})
        if self._id in col:
            del col[self._id]


class _MockQuery:
    def __init__(self, client, col, filters=None):
        self._client = client
        self._col = col
        self._filters = filters or []
        self._limit = None
        self._order = None

    def where(self, field, op, value):
        return _MockQuery(self._client, self._col, self._filters + [(field, op, value)])

    def order_by(self, field, direction=None):
        self._order = (field, direction)
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def get(self):
        col = self._client._store.get(self._col, {})
        docs = []
        for doc_id, data in col.items():
            match = True
            for field, op, value in self._filters:
                if op == "==":
                    if data.get(field) != value:
                        match = False
                        break
            if match:
                docs.append(_MockSnapshot(_MockDocumentRef(self._client, self._col, doc_id), data))
        if self._order and self._order[0]:
            key, direction = self._order
            docs.sort(key=lambda s: (s.to_dict() or {}).get(key))
            if direction == firestore.Query.DESCENDING:
                docs.reverse()
        if self._limit is not None:
            docs = docs[: self._limit]
        return docs


class _MockBatch:
    def __init__(self, client):
        self._client = client
        self._deletes = []

    def delete(self, ref):
        self._deletes.append(ref)

    async def commit(self):
        for ref in self._deletes:
            await ref.delete()


class _MockTransaction:
    def __init__(self, client):
        self._client = client

    async def get(self, ref):
        return await ref.get()

    async def update(self, ref, data):
        await ref.update(data)

    async def set(self, ref, data):
        await ref.set(data)


class _MockAsyncClient:
    def __init__(self, project=None, credentials=None):
        self._store = {}
        self._project = project

    def collection(self, name):
        return _MockCollection(self, name)

    def batch(self):
        return _MockBatch(self)

    def transaction(self):
        return _MockTransaction(self)


class _MockCollection:
    def __init__(self, client, name):
        self._client = client
        self._name = name

    def document(self, doc_id):
        return _MockDocumentRef(self._client, self._name, doc_id)

    async def add(self, data):
        doc_id = uuid.uuid4().hex[:20]
        ref = _MockDocumentRef(self._client, self._name, doc_id)
        await ref.set(data)
        return ref, None

    def where(self, *args, **kwargs):
        return _MockQuery(self._client, self._name).where(*args, **kwargs)


# ── Singleton client ──────────────────────────────────────────────────────────

_db: AsyncClient = None


async def get_db() -> AsyncClient:
    global _db
    if _db is None:
        _db = _build_client()
    return _db


def _build_client() -> AsyncClient:
    """Build an AsyncClient from FIREBASE_CREDENTIALS env var (JSON string)
    or fall back to Application Default Credentials."""
    creds_json = FIREBASE_CREDENTIALS.strip()
    project = FIREBASE_PROJECT_ID.strip() or None
    logger = logging.getLogger(__name__)

    if creds_json:
        creds_info = None
        try:
            creds_info = json.loads(creds_json)
        except json.JSONDecodeError:
            # maybe it is a file path (local dev convenience)
            try:
                with open(creds_json) as f:
                    creds_info = json.load(f)
            except Exception as e:
                logger.warning("Failed to read FIREBASE_CREDENTIALS file: %s", e)

        if creds_info:
            project = project or creds_info.get("project_id")
            try:
                creds = service_account.Credentials.from_service_account_info(
                    creds_info,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                return AsyncClient(project=project, credentials=creds)
            except Exception as e:
                # If provided credentials are invalid (corrupt PEM, wrong format, etc.),
                # warn and fall back to application default credentials so import doesn't crash.
                logger.warning("Invalid FIREBASE_CREDENTIALS provided, falling back to ADC: %s", e)

    # Application Default Credentials (e.g. gcloud auth or GOOGLE_APPLICATION_CREDENTIALS)
    try:
        return AsyncClient(project=project)
    except Exception as e:
        # If ADC not configured or client cannot be created, fall back to in-memory mock.
        logger.warning("Could not create real Firestore client, using in-memory mock: %s", e)
        return _MockAsyncClient(project=project)


async def close():
    global _db
    _db = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _col(db: AsyncClient, name: str):
    return db.collection(name)


def _doc_data(snap) -> dict | None:
    if snap is None or not snap.exists:
        return None
    return snap.to_dict()


# ── User CRUD ─────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str = None, first_name: str = None):
    db = await get_db()
    uid = str(user_id)

    user_ref = _col(db, "users").document(uid)
    snap = await user_ref.get()
    if snap.exists:
        await user_ref.update({
            "username": username or "",
            "first_name": first_name or "",
        })
    else:
        await user_ref.set({
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "join_date": date.today().isoformat(),
            "is_banned": 0,
            "proxy_mode": "system",
            "show_site": "ask",
        })

    plan_ref = _col(db, "user_plans").document(uid)
    plan_snap = await plan_ref.get()
    if not plan_snap.exists:
        await plan_ref.set({
            "user_id": user_id,
            "plan_type": "free",
            "expiry_date": None,
            "hits_per_day": 0,
        })


async def is_banned(user_id: int) -> bool:
    db = await get_db()
    snap = await _col(db, "users").document(str(user_id)).get()
    d = _doc_data(snap)
    return bool(d and d.get("is_banned"))


async def ban_user(user_id: int) -> bool:
    PROTECTED_OWNER_ID = 8303990517
    if user_id == PROTECTED_OWNER_ID:
        return False
    db = await get_db()
    await _col(db, "users").document(str(user_id)).update({"is_banned": 1})
    return True


async def unban_user(user_id: int):
    db = await get_db()
    await _col(db, "users").document(str(user_id)).update({"is_banned": 0})


# ── Proxy mode ────────────────────────────────────────────────────────────────

async def get_user_proxy_mode(user_id: int) -> str:
    db = await get_db()
    snap = await _col(db, "users").document(str(user_id)).get()
    d = _doc_data(snap)
    return d.get("proxy_mode", "system") if d else "system"


async def set_user_proxy_mode(user_id: int, mode: str):
    db = await get_db()
    await _col(db, "users").document(str(user_id)).update({"proxy_mode": mode})


async def get_show_site(user_id: int) -> str:
    db = await get_db()
    snap = await _col(db, "users").document(str(user_id)).get()
    d = _doc_data(snap)
    return d.get("show_site", "ask") if d else "ask"


async def set_show_site(user_id: int, mode: str):
    db = await get_db()
    await _col(db, "users").document(str(user_id)).update({"show_site": mode})


# ── Plans ─────────────────────────────────────────────────────────────────────

async def get_user_plan(user_id: int) -> dict:
    db = await get_db()
    snap = await _col(db, "user_plans").document(str(user_id)).get()
    row = _doc_data(snap)

    if not row:
        return {"type": "free", "label": "Free", "unlimited": False,
                "hits_per_day": 0, "expiry": None, "just_expired": False}

    plan_type = row.get("plan_type", "free")
    expiry    = row.get("expiry_date")
    hpd       = row.get("hits_per_day") or 0

    if plan_type != "free" and expiry:
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        if expiry_date < date.today():
            await _col(db, "user_plans").document(str(user_id)).update(
                {"plan_type": "free", "expiry_date": None, "hits_per_day": 0}
            )
            return {"type": "free", "label": "Free", "unlimited": False,
                    "hits_per_day": 0, "expiry": None, "just_expired": True,
                    "expired_plan": plan_type}
        return {"type": plan_type, "label": plan_type, "unlimited": True,
                "hits_per_day": hpd, "expiry": expiry, "just_expired": False}

    return {"type": "free", "label": "Free", "unlimited": False,
            "hits_per_day": 0, "expiry": None, "just_expired": False}


async def set_user_plan(user_id: int, plan_type: str, days: int, hits_per_day: int = 0):
    db = await get_db()
    expiry = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")
    await _col(db, "user_plans").document(str(user_id)).set(
        {"user_id": user_id, "plan_type": plan_type,
         "expiry_date": expiry, "hits_per_day": hits_per_day},
        merge=True,
    )


# ── Daily hits ────────────────────────────────────────────────────────────────

async def get_daily_hits(user_id: int) -> int:
    db = await get_db()
    today = date.today().isoformat()
    snap = await _col(db, "daily_hits").document(f"{user_id}_{today}").get()
    d = _doc_data(snap)
    return d["count"] if d else 0


async def increment_daily_hits(user_id: int) -> int:
    db = await get_db()
    today = date.today().isoformat()
    doc_id = f"{user_id}_{today}"
    ref = _col(db, "daily_hits").document(doc_id)

    @firestore.async_transactional
    async def _txn(transaction):
        snap = await ref.get(transaction=transaction)
        if snap.exists:
            new_count = (snap.to_dict().get("count") or 0) + 1
            transaction.update(ref, {"count": new_count})
        else:
            new_count = 1
            transaction.set(ref, {"user_id": user_id, "hit_date": today, "count": 1})
        return new_count

    transaction = db.transaction()
    return await _txn(transaction)


async def can_hit(user_id: int) -> tuple:
    if await is_admin(user_id) or await is_db_owner(user_id):
        return True, None
    plan = await get_user_plan(user_id)
    if plan["unlimited"]:
        if plan["hits_per_day"] > 0:
            hits = await get_daily_hits(user_id)
            if hits >= plan["hits_per_day"]:
                return False, f"Daily limit reached ({plan['hits_per_day']}/day). Contact owner for upgrade!"
        return True, None
    hits = await get_daily_hits(user_id)
    remaining = FREE_DAILY_LIMIT - hits
    if remaining <= 0:
        return False, f"Daily limit reached ({FREE_DAILY_LIMIT}/day on Free plan). Contact owner for access!"
    return True, None


# ── Logging ───────────────────────────────────────────────────────────────────

async def log_check(user_id: int, card: str, url: str, merchant: str,
                    amount: str, status: str, response: str, time_taken: float):
    db = await get_db()
    await _col(db, "check_logs").add({
        "user_id": user_id,
        "card": card,
        "checkout_url": url[:100],
        "merchant": merchant or "",
        "amount": amount or "",
        "status": status,
        "response": response or "",
        "time_taken": time_taken,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def get_user_logs(user_id: int, limit: int = 20) -> list:
    db = await get_db()
    query = (
        _col(db, "check_logs")
        .where("user_id", "==", user_id)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [snap.to_dict() for snap in (await query.get())]


async def get_recent_charged_hits(limit: int = 20) -> list:
    db = await get_db()
    query = (
        _col(db, "check_logs")
        .where("status", "==", "CHARGED")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    return [snap.to_dict() for snap in (await query.get())]


async def get_user_hit_stats(user_id: int) -> dict:
    db = await get_db()
    snaps = await _col(db, "check_logs").where("user_id", "==", user_id).get()
    docs  = [s.to_dict() for s in snaps]
    total    = len(docs)
    charged  = sum(1 for d in docs if d.get("status") == "CHARGED")
    live     = sum(1 for d in docs if d.get("status") == "LIVE")
    declined = sum(1 for d in docs if d.get("status") == "DECLINED")
    return {"total": total, "charged": charged, "live": live, "declined": declined}


# ── Proxies ───────────────────────────────────────────────────────────────────

async def add_proxy(user_id: int, proxy: str) -> bool:
    db = await get_db()
    import hashlib
    doc_id = f"{user_id}_{hashlib.md5(proxy.encode()).hexdigest()[:8]}"
    try:
        await _col(db, "proxies").document(doc_id).set(
            {"user_id": user_id, "proxy": proxy}, merge=True
        )
        return True
    except Exception:
        return False


async def remove_proxy(user_id: int, proxy: str = None):
    db = await get_db()
    if proxy and proxy.lower() != "all":
        import hashlib
        doc_id = f"{user_id}_{hashlib.md5(proxy.encode()).hexdigest()[:8]}"
        await _col(db, "proxies").document(doc_id).delete()
    else:
        snaps = await _col(db, "proxies").where("user_id", "==", user_id).get()
        for snap in snaps:
            await snap.reference.delete()


async def get_proxies(user_id: int) -> list:
    db = await get_db()
    snaps = await _col(db, "proxies").where("user_id", "==", user_id).get()
    return [s.to_dict()["proxy"] for s in snaps if s.exists]


# ── Ranking ───────────────────────────────────────────────────────────────────

async def get_charged_ranking(limit: int = 10) -> list:
    db = await get_db()
    snaps = await _col(db, "check_logs").where("status", "==", "CHARGED").get()
    counts: dict[int, int] = {}
    for s in snaps:
        uid = s.to_dict().get("user_id")
        if uid:
            counts[uid] = counts.get(uid, 0) + 1
    sorted_uids = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    result = []
    for uid, cnt in sorted_uids:
        user_snap = await _col(db, "users").document(str(uid)).get()
        u = _doc_data(user_snap) or {}
        result.append({
            "user_id": uid,
            "charged_count": cnt,
            "username": u.get("username", ""),
            "first_name": u.get("first_name", ""),
        })
    return result


# ── Saved BINs ────────────────────────────────────────────────────────────────

async def save_bin(user_id: int, name: str, bin_value: str) -> bool:
    db = await get_db()
    doc_id = f"{user_id}_{name.lower()}"
    try:
        await _col(db, "saved_bins").document(doc_id).set({
            "user_id": user_id,
            "name": name.lower(),
            "bin_value": bin_value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return True
    except Exception:
        return False


async def get_saved_bins(user_id: int) -> list:
    db = await get_db()
    snaps = await (
        _col(db, "saved_bins")
        .where("user_id", "==", user_id)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(50)
        .get()
    )
    return [{"name": s.to_dict()["name"], "bin_value": s.to_dict()["bin_value"]}
            for s in snaps if s.exists]


async def delete_saved_bin(user_id: int, name: str) -> bool:
    db = await get_db()
    doc_id = f"{user_id}_{name.lower()}"
    await _col(db, "saved_bins").document(doc_id).delete()
    return True


# ── Redeem codes ──────────────────────────────────────────────────────────────

async def create_redeem_code(plan_type: str, days: int, hits_per_day: int,
                              max_uses: int, created_by: int) -> str:
    db = await get_db()
    chars = string.ascii_uppercase + string.digits
    code  = "-".join("".join(secrets.choice(chars) for _ in range(4)) for _ in range(3))
    await _col(db, "redeem_codes").document(code).set({
        "code": code,
        "plan_type": plan_type,
        "days": days,
        "hits_per_day": hits_per_day,
        "max_uses": max_uses,
        "used_count": 0,
        "created_by": created_by,
        "is_active": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return code


async def use_redeem_code(user_id: int, code: str) -> dict:
    db = await get_db()
    code = code.upper().strip()
    snap = await _col(db, "redeem_codes").document(code).get()
    row  = _doc_data(snap)

    if not row or row.get("is_active") != 1:
        return {"success": False, "error": "Invalid or expired code"}
    if row["used_count"] >= row["max_uses"]:
        return {"success": False, "error": "Code already fully used"}

    use_id   = f"{code}_{user_id}"
    use_snap = await _col(db, "code_uses").document(use_id).get()
    if use_snap.exists:
        return {"success": False, "error": "You already used this code"}

    await _col(db, "code_uses").document(use_id).set({
        "code": code, "user_id": user_id,
        "used_at": datetime.now(timezone.utc).isoformat(),
    })
    new_used = row["used_count"] + 1
    update = {"used_count": new_used}
    if new_used >= row["max_uses"]:
        update["is_active"] = 0
    await _col(db, "redeem_codes").document(code).update(update)

    hpd = row.get("hits_per_day") or 0
    await set_user_plan(user_id, row["plan_type"], row["days"], hpd)
    return {"success": True, "plan_type": row["plan_type"],
            "days": row["days"], "hits_per_day": hpd}


async def revoke_code(code: str) -> bool:
    db = await get_db()
    code = code.upper().strip()
    snap = await _col(db, "redeem_codes").document(code).get()
    if not snap.exists:
        return False
    await _col(db, "redeem_codes").document(code).update({"is_active": 0})
    return True


async def get_active_codes() -> list:
    db = await get_db()
    snaps = await (
        _col(db, "redeem_codes")
        .where("is_active", "==", 1)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(20)
        .get()
    )
    return [s.to_dict() for s in snaps if s.exists]


# ── Stats ─────────────────────────────────────────────────────────────────────

async def get_global_stats() -> dict:
    db = await get_db()
    user_snaps  = await _col(db, "users").get()
    users_docs  = [s.to_dict() for s in user_snaps]
    active_users = sum(1 for d in users_docs if not d.get("is_banned"))
    banned_users = sum(1 for d in users_docs if d.get("is_banned"))

    log_snaps   = await _col(db, "check_logs").get()
    log_docs    = [s.to_dict() for s in log_snaps]
    checks      = len(log_docs)
    charged     = sum(1 for d in log_docs if d.get("status") == "CHARGED")
    live        = sum(1 for d in log_docs if d.get("status") == "LIVE")

    code_snaps  = await _col(db, "redeem_codes").where("is_active", "==", 1).get()
    active_codes = len(list(code_snaps))

    return {"users": active_users, "checks": checks, "charged": charged,
            "live": live, "banned": banned_users, "active_codes": active_codes}


async def get_all_users() -> list:
    db = await get_db()
    user_snaps = await _col(db, "users").order_by("join_date", direction=firestore.Query.DESCENDING).get()
    result = []
    for s in user_snaps:
        u = s.to_dict()
        uid = u.get("user_id")
        plan_snap = await _col(db, "user_plans").document(str(uid)).get()
        plan = _doc_data(plan_snap) or {}
        result.append({
            "user_id":    uid,
            "username":   u.get("username", ""),
            "first_name": u.get("first_name", ""),
            "join_date":  u.get("join_date"),
            "is_banned":  u.get("is_banned", 0),
            "proxy_mode": u.get("proxy_mode", "system"),
            "plan_type":  plan.get("plan_type", "free"),
            "expiry_date":plan.get("expiry_date"),
            "hits_per_day":plan.get("hits_per_day", 0),
        })
    return result


async def get_all_users_with_hits() -> list:
    db = await get_db()
    log_snaps = await _col(db, "check_logs").get()
    hit_map: dict[int, dict] = {}
    for s in log_snaps:
        d   = s.to_dict()
        uid = d.get("user_id")
        if uid is None:
            continue
        if uid not in hit_map:
            hit_map[uid] = {"total": 0, "charged": 0}
        hit_map[uid]["total"] += 1
        if d.get("status") == "CHARGED":
            hit_map[uid]["charged"] += 1

    user_snaps = await _col(db, "users").order_by("join_date", direction=firestore.Query.DESCENDING).get()
    result = []
    for s in user_snaps:
        u   = s.to_dict()
        uid = u.get("user_id")
        plan_snap = await _col(db, "user_plans").document(str(uid)).get()
        plan = _doc_data(plan_snap) or {}
        hits = hit_map.get(uid, {"total": 0, "charged": 0})
        result.append({
            "user_id":     uid,
            "username":    u.get("username", ""),
            "first_name":  u.get("first_name", ""),
            "join_date":   u.get("join_date"),
            "is_banned":   u.get("is_banned", 0),
            "proxy_mode":  u.get("proxy_mode", "system"),
            "plan_type":   plan.get("plan_type", "free"),
            "expiry_date": plan.get("expiry_date"),
            "hits_per_day":plan.get("hits_per_day", 0),
            "total_hits":  hits["total"],
            "charged_hits":hits["charged"],
        })
    return result


async def get_all_user_ids() -> list:
    db = await get_db()
    snaps = await _col(db, "users").where("is_banned", "==", 0).get()
    return [s.to_dict()["user_id"] for s in snaps if s.exists]


async def get_user_info(user_id: int) -> dict:
    db = await get_db()
    snap = await _col(db, "users").document(str(user_id)).get()
    return _doc_data(snap)


async def get_setting(key: str, default=None):
    db = await get_db()
    snap = await _col(db, "bot_settings").document(key).get()
    d = _doc_data(snap)
    return d["value"] if d else default


async def set_setting(key: str, value: str):
    db = await get_db()
    await _col(db, "bot_settings").document(key).set({"key": key, "value": value})


# ── Admin role ────────────────────────────────────────────────────────────────

async def add_admin(user_id: int):
    db = await get_db()
    await _col(db, "admins").document(str(user_id)).set({"user_id": user_id})


async def remove_admin(user_id: int):
    db = await get_db()
    await _col(db, "admins").document(str(user_id)).delete()


async def is_admin(user_id: int) -> bool:
    db = await get_db()
    snap = await _col(db, "admins").document(str(user_id)).get()
    return snap.exists


async def get_all_admins() -> list:
    db = await get_db()
    snaps = await _col(db, "admins").get()
    return [s.to_dict()["user_id"] for s in snaps if s.exists]


# ── Owner role ────────────────────────────────────────────────────────────────

async def add_owner(user_id: int, username: str = None, added_by: int = None):
    db = await get_db()
    await _col(db, "owners").document(str(user_id)).set({
        "user_id": user_id,
        "username": username or "",
        "added_by": added_by,
    })


async def remove_owner(user_id: int):
    db = await get_db()
    await _col(db, "owners").document(str(user_id)).delete()


async def is_db_owner(user_id: int) -> bool:
    db = await get_db()
    snap = await _col(db, "owners").document(str(user_id)).get()
    return snap.exists


async def get_all_owners() -> list:
    db = await get_db()
    snaps = await _col(db, "owners").get()
    return [s.to_dict() for s in snaps if s.exists]


# ── Reset stats ───────────────────────────────────────────────────────────────

async def _delete_collection(db: AsyncClient, col_name: str, batch_size: int = 100):
    col = _col(db, col_name)
    snaps = await col.limit(batch_size).get()
    while snaps:
        batch = db.batch()
        for snap in snaps:
            batch.delete(snap.reference)
        await batch.commit()
        if len(snaps) < batch_size:
            break
        snaps = await col.limit(batch_size).get()


async def reset_global_stats():
    db = await get_db()
    await _delete_collection(db, "check_logs")
    await _delete_collection(db, "daily_hits")


async def clear_daily_cache():
    db = await get_db()
    await _delete_collection(db, "daily_hits")


async def get_total_users_count() -> int:
    db = await get_db()
    snaps = await _col(db, "users").get()
    return len(list(snaps))


# ── API Keys ──────────────────────────────────────────────────────────────────

async def create_api_key(user_id: int, plan_type: str, hits_per_day: int) -> str:
    db = await get_db()
    token = secrets.token_hex(20)
    key   = f"damxd_live_{token}"
    await _col(db, "api_keys").document(key).set({
        "key": key,
        "user_id": user_id,
        "plan_type": plan_type,
        "hits_per_day": hits_per_day,
        "daily_count": 0,
        "total_count": 0,
        "last_reset_date": date.today().isoformat(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return key


async def get_api_key_info(key: str) -> dict:
    db = await get_db()
    snap = await _col(db, "api_keys").document(key).get()
    row  = _doc_data(snap)
    if not row:
        return None

    today = date.today().isoformat()
    if row.get("last_reset_date") != today:
        await _col(db, "api_keys").document(key).update(
            {"daily_count": 0, "last_reset_date": today}
        )
        row["daily_count"]    = 0
        row["last_reset_date"] = today

    return row


async def increment_api_key_hits(key: str):
    db = await get_db()
    await _col(db, "api_keys").document(key).update({
        "daily_count": Increment(1),
        "total_count": Increment(1),
    })


async def revoke_api_key(key: str) -> bool:
    db = await get_db()
    snap = await _col(db, "api_keys").document(key).get()
    if not snap.exists:
        return False
    await _col(db, "api_keys").document(key).update({"is_active": False})
    return True


async def get_user_api_keys(user_id: int) -> list:
    db = await get_db()
    snaps = await (
        _col(db, "api_keys")
        .where("user_id", "==", user_id)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(50)
        .get()
    )
    return [s.to_dict() for s in snaps if s.exists]


# ── Auth Chats ────────────────────────────────────────────────────────────────

async def add_auth_chat(chat_id: int, title: str = None) -> bool:
    db = await get_db()
    await _col(db, "auth_chats").document(str(chat_id)).set({
        "chat_id": chat_id,
        "title": title or "",
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    return True


async def remove_auth_chat(chat_id: int) -> bool:
    db = await get_db()
    snap = await _col(db, "auth_chats").document(str(chat_id)).get()
    if not snap.exists:
        return False
    await _col(db, "auth_chats").document(str(chat_id)).delete()
    return True


async def is_chat_authorized(chat_id: int) -> bool:
    db = await get_db()
    snap = await _col(db, "auth_chats").document(str(chat_id)).get()
    return snap.exists


async def get_all_auth_chats() -> list:
    db = await get_db()
    snaps = await _col(db, "auth_chats").get()
    return [s.to_dict() for s in snaps if s.exists]
