import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "angelone.sqlite3"
INVALID_PLACEHOLDER_NAMES = {
    "default",
    "user",
    "placeholder",
    "undefined",
    "null",
    "none",
    "temp",
    "temporary",
    "new-account",
}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            account_name TEXT PRIMARY KEY,
            session_data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT,
            expires_at TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    return conn


def _is_generated_account_name(value):
    value = (value or "").strip()
    if not value:
        return False

    lower = value.lower()
    if lower in INVALID_PLACEHOLDER_NAMES:
        return True

    if ":" in value:  # IPv6 address or port
        return True

    if bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", value)):  # IPv4 address
        return True

    if lower.startswith("account_") or lower.startswith("profile_"):
        prefix_len = len("account_") if lower.startswith("account_") else len("profile_")
        suffix = value[prefix_len:]
        return bool(suffix) and (
            suffix.isdigit()
            or bool(re.fullmatch(r"\d{8,}.*", suffix))
            or bool(re.fullmatch(r"\d{4,}[-_\d]*", suffix))
            or suffix.lower() in {"default", "temp", "new", "placeholder"}
        )

    if value.lower().endswith("-p") and bool(re.fullmatch(r"[0-9a-fA-F-]+", value[:-2])):
        return True

    if bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:-[A-Za-z0-9]+)?", value)):
        return True

    if len(value) >= 12 and not (" " in value) and all(c in "0123456789abcdefABCDEF" for c in value):
        return True

    if len(value) >= 30 and bool(re.fullmatch(r"[A-Za-z0-9_+=/.-]+", value)) and not (" " in value):
        return True

    return False


def _normalize_account_name(account_name):
    value = (account_name or "").strip()
    if not value:
        return None
    if value.lower() in INVALID_PLACEHOLDER_NAMES:
        return None
    if _is_generated_account_name(value):
        return None
    if len(value) < 2:
        return None
    if not any(ch.isalnum() for ch in value):
        return None
    if len(value) >= 40 and not (" " in value):
        return None
    return value


def cleanup_generated_accounts():
    with _connect() as conn:
        rows = conn.execute("SELECT account_name FROM sessions").fetchall()
        for row in rows:
            name = (row["account_name"] or "").strip()
            if _is_generated_account_name(name):
                conn.execute("DELETE FROM sessions WHERE account_name = ?", (name,))
        active = conn.execute("SELECT value FROM app_state WHERE key = 'active_account'").fetchone()
        if active and _is_generated_account_name(active["value"]):
            conn.execute("DELETE FROM app_state WHERE key = 'active_account'")
        conn.commit()


def _session_payload_to_row(session_payload, account_name, now):
    payload = {
        "account_name": account_name,
        **session_payload,
    }
    expires_at = session_payload.get("expires_at")
    status = "active" if not expires_at else "active"
    return {
        "account_name": account_name,
        "session_data": json.dumps(payload, ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
        "last_used_at": now,
        "expires_at": expires_at,
        "status": status,
    }


def _row_to_session(row):
    payload = json.loads(row["session_data"])
    return {
        "account_name": row["account_name"],
        **payload,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_used_at": row["last_used_at"],
        "expires_at": row["expires_at"],
        "status": row["status"],
    }


def _load_store():
    cleanup_generated_accounts()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT account_name, session_data, created_at, updated_at, last_used_at, expires_at, status FROM sessions ORDER BY account_name"
        ).fetchall()
        active_row = conn.execute(
            "SELECT value FROM app_state WHERE key = 'active_account'"
        ).fetchone()
        sessions = {
            row["account_name"]: _row_to_session(row)
            for row in rows
            if _normalize_account_name(row["account_name"]) is not None
        }
        active_account = active_row["value"] if active_row else None
        if active_account is not None and _normalize_account_name(active_account) is None:
            active_account = None
        return {"sessions": sessions, "active_account": active_account}


def _save_store(store):
    with _connect() as conn:
        for name, session in store.get("sessions", {}).items():
            payload = {
                "account_name": name,
                **session,
            }
            payload.pop("created_at", None)
            payload.pop("updated_at", None)
            payload.pop("last_used_at", None)
            payload.pop("expires_at", None)
            payload.pop("status", None)
            session_data = json.dumps({"account_name": name, **payload}, ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO sessions (account_name, session_data, created_at, updated_at, last_used_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_name) DO UPDATE SET
                    session_data = excluded.session_data,
                    updated_at = excluded.updated_at,
                    last_used_at = excluded.last_used_at,
                    expires_at = excluded.expires_at,
                    status = excluded.status
                """,
                (
                    name,
                    session_data,
                    session.get("created_at", datetime.utcnow().isoformat()),
                    session.get("updated_at", datetime.utcnow().isoformat()),
                    session.get("last_used_at", datetime.utcnow().isoformat()),
                    session.get("expires_at"),
                    session.get("status", "active"),
                ),
            )
        active = store.get("active_account")
        if active is None:
            conn.execute("DELETE FROM app_state WHERE key = 'active_account'")
        else:
            conn.execute(
                "INSERT INTO app_state(key, value) VALUES('active_account', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (active,),
            )
        conn.commit()


def set_active_account_name(account_name):
    name = _normalize_account_name(account_name)
    store = _load_store()
    store["active_account"] = name
    _save_store(store)
    return name


def get_active_account_name():
    store = _load_store()
    active = _normalize_account_name(store.get("active_account"))
    return active


def save_account_session(account_name, session_payload):
    name = _normalize_account_name(account_name)
    if name is None:
        raise ValueError("Account name must be a real user identifier and cannot be a timestamp placeholder.")
    cleanup_generated_accounts()

    now = datetime.utcnow().isoformat()
    payload = {
        "account_name": name,
        **session_payload,
        "updated_at": now,
        "last_used_at": now,
        "created_at": now,
        "status": "active",
    }

    with _connect() as conn:
        row = {
            "account_name": name,
            "session_data": json.dumps(payload, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
            "last_used_at": now,
            "expires_at": session_payload.get("expires_at"),
            "status": "active",
        }
        conn.execute(
            """
            INSERT INTO sessions (account_name, session_data, created_at, updated_at, last_used_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                session_data = excluded.session_data,
                updated_at = excluded.updated_at,
                last_used_at = excluded.last_used_at,
                expires_at = excluded.expires_at,
                status = excluded.status
            """,
            (
                row["account_name"],
                row["session_data"],
                row["created_at"],
                row["updated_at"],
                row["last_used_at"],
                row["expires_at"],
                row["status"],
            ),
        )
        conn.execute(
            "INSERT INTO app_state(key, value) VALUES('active_account', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (name,),
        )
        conn.commit()

    return get_account_session(name)


def get_default_account_name():
    sessions = list_account_sessions()
    if not sessions:
        return None
    return sessions[0]["account_name"]


def get_account_session(account_name):
    name = _normalize_account_name(account_name)
    if name is None:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT account_name, session_data, created_at, updated_at, last_used_at, expires_at, status FROM sessions WHERE account_name = ?",
            (name,),
        ).fetchone()
    if not row:
        return None
    return _row_to_session(row)


def list_account_sessions():
    cleanup_generated_accounts()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT account_name, session_data, created_at, updated_at, last_used_at, expires_at, status FROM sessions ORDER BY account_name"
        ).fetchall()
    filtered = []
    for row in rows:
        name = (row["account_name"] or "").strip()
        if _normalize_account_name(name) is None:
            continue
        filtered.append(_row_to_session(row))
    return filtered


def remove_account_session(account_name):
    name = _normalize_account_name(account_name)
    if name is None:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE account_name = ?", (name,))
        active = conn.execute("SELECT value FROM app_state WHERE key = 'active_account'").fetchone()
        if active and active["value"] == name:
            conn.execute("DELETE FROM app_state WHERE key = 'active_account'")
        conn.commit()


def clear_all_sessions():
    with _connect() as conn:
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM app_state")
        conn.commit()
