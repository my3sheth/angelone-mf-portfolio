import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "angelone.sqlite3"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_details (
            account_name TEXT PRIMARY KEY,
            inferred_name TEXT,
            headers TEXT NOT NULL,
            cookies TEXT NOT NULL,
            url TEXT,
            saved_at TEXT NOT NULL,
            expires_at TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            validated_at TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _normalize_account_name(account_name):
    value = (account_name or "").strip()
    if not value:
        raise ValueError("Account name cannot be empty")
    return value


def _row_to_auth_details(row):
    return {
        "account_name": row["account_name"],
        "inferred_name": row["inferred_name"],
        "saved_at": row["saved_at"],
        "expires_at": row["expires_at"],
        "status": row["status"],
        "headers": json.loads(row["headers"] or "{}"),
        "cookies": json.loads(row["cookies"] or "[]"),
        "url": row["url"],
        "validated_at": row["validated_at"],
        "updated_at": row["updated_at"],
    }


def save_auth_details(account_name, headers, cookies, url, inferred_name=None, expires_at=None):
    """Save/refresh per-account authentication details in SQLite."""
    name = _normalize_account_name(account_name)
    now = datetime.utcnow().isoformat()
    payload = {
        "account_name": name,
        "inferred_name": inferred_name or name,
        "headers": json.dumps(headers or {}, ensure_ascii=False),
        "cookies": json.dumps(cookies or [], ensure_ascii=False),
        "url": url,
        "saved_at": now,
        "expires_at": expires_at,
        "status": "active",
        "validated_at": now,
        "updated_at": now,
    }

    with _connect() as conn:
        payload["saved_at"] = now
        payload["updated_at"] = now
        payload["validated_at"] = now
        payload["status"] = "active"
        payload["expires_at"] = expires_at

        conn.execute(
            """
            INSERT INTO auth_details (
                account_name, inferred_name, headers, cookies, url,
                saved_at, expires_at, status, validated_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                inferred_name = excluded.inferred_name,
                headers = excluded.headers,
                cookies = excluded.cookies,
                url = excluded.url,
                saved_at = excluded.saved_at,
                expires_at = excluded.expires_at,
                status = excluded.status,
                validated_at = excluded.validated_at,
                updated_at = excluded.updated_at
            """,
            (
                payload["account_name"],
                payload["inferred_name"],
                payload["headers"],
                payload["cookies"],
                payload["url"],
                payload["saved_at"],
                payload["expires_at"],
                payload["status"],
                payload["validated_at"],
                payload["updated_at"],
            ),
        )
        conn.execute(
            "INSERT INTO auth_history (account_name, event_type, status, message, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                name,
                "save",
                "active",
                "Authentication details saved",
                json.dumps({"inferred_name": inferred_name or name, "url": url}, ensure_ascii=False),
                now,
            ),
        )
        conn.commit()

    return load_auth_details(name)


def load_auth_details(account_name):
    name = _normalize_account_name(account_name)
    with _connect() as conn:
        row = conn.execute(
            "SELECT account_name, inferred_name, headers, cookies, url, saved_at, expires_at, status, validated_at, updated_at FROM auth_details WHERE account_name = ?",
            (name,),
        ).fetchone()
    if not row:
        return None
    return _row_to_auth_details(row)


def list_all_auth_details():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT account_name, inferred_name, saved_at, expires_at, status, updated_at FROM auth_details ORDER BY account_name"
        ).fetchall()
    return [
        {
            "account_name": row["account_name"],
            "inferred_name": row["inferred_name"],
            "saved_at": row["saved_at"],
            "expires_at": row["expires_at"],
            "status": row["status"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_auth_details(account_name):
    name = _normalize_account_name(account_name)
    with _connect() as conn:
        conn.execute("DELETE FROM auth_details WHERE account_name = ?", (name,))
        conn.execute("DELETE FROM auth_history WHERE account_name = ?", (name,))
        conn.commit()


def clear_all_auth_details():
    with _connect() as conn:
        conn.execute("DELETE FROM auth_details")
        conn.execute("DELETE FROM auth_history")
        conn.commit()


def mark_auth_expired(account_name):
    name = _normalize_account_name(account_name)
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE auth_details SET status = 'expired', updated_at = ?, expires_at = COALESCE(expires_at, ?) WHERE account_name = ?",
            (now, now, name),
        )
        conn.execute(
            "INSERT INTO auth_history (account_name, event_type, status, message, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, "expire", "expired", "Authentication expired", json.dumps({"expired_at": now}, ensure_ascii=False), now),
        )
        conn.commit()


def is_auth_valid(account_name):
    auth_details = load_auth_details(account_name)
    if not auth_details:
        return False, None

    status = (auth_details.get("status") or "").lower()
    if status == "expired":
        return False, auth_details
    if status != "active":
        return False, auth_details

    expires_at = auth_details.get("expires_at")
    if expires_at:
        try:
            exp_time = datetime.fromisoformat(expires_at)
            if exp_time < datetime.utcnow():
                mark_auth_expired(account_name)
                return False, load_auth_details(account_name)
        except ValueError:
            pass

    return True, auth_details


def get_auth_status(account_name):
    is_valid, auth_details = is_auth_valid(account_name)
    if not auth_details:
        return {
            "status_code": "no_auth",
            "message": "No authentication found for this account.",
            "valid": False,
        }

    if is_valid:
        return {
            "status_code": "valid",
            "message": "Authentication is valid and ready to use.",
            "valid": True,
            "inferred_name": auth_details.get("inferred_name"),
            "saved_at": auth_details.get("saved_at"),
            "expires_at": auth_details.get("expires_at"),
            "validated_at": auth_details.get("validated_at"),
        }

    status = auth_details.get("status", "unknown")
    return {
        "status_code": status,
        "message": f"Authentication is {status}.",
        "valid": False,
        "inferred_name": auth_details.get("inferred_name"),
        "saved_at": auth_details.get("saved_at"),
        "expires_at": auth_details.get("expires_at"),
        "expired_at": auth_details.get("expires_at"),
    }


def clear_all_auth_details():
    with _connect() as conn:
        conn.execute("DELETE FROM auth_details")
        conn.execute("DELETE FROM auth_history")
        conn.commit()

