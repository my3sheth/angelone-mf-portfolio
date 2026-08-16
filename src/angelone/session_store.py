import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SESSIONS_FILE = ROOT / "sessions.json"
LEGACY_ACCOUNT_NAMES = {"Maitri", "Maitri Sheth"}


def _clean_store(store):
    sessions = store.get("sessions", {})
    kept = {}
    for name, session in sessions.items():
        if name in LEGACY_ACCOUNT_NAMES:
            continue
        kept[name] = session
    return {
        "sessions": kept,
        "active_account": store.get("active_account") if store.get("active_account") not in LEGACY_ACCOUNT_NAMES else None,
    }


def _load_store():
    if not SESSIONS_FILE.exists():
        return {"sessions": {}, "active_account": None}

    try:
        data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sessions": {}, "active_account": None}

    if isinstance(data, dict):
        cleaned = _clean_store(data)
        return cleaned

    return {"sessions": {}, "active_account": None}


def _save_store(store):
    cleaned = _clean_store(store)
    SESSIONS_FILE.write_text(
        json.dumps({
            "sessions": cleaned.get("sessions", {}),
            "active_account": cleaned.get("active_account"),
        }, indent=2),
        encoding="utf-8",
    )


def set_active_account_name(account_name):
    name = (account_name or "default").strip() or "default"
    if name in LEGACY_ACCOUNT_NAMES:
        name = "default"
    store = _load_store()
    store["active_account"] = name
    _save_store(store)
    return name


def get_active_account_name():
    store = _load_store()
    active = store.get("active_account")
    if active in LEGACY_ACCOUNT_NAMES:
        return None
    return active


def save_account_session(account_name, session_payload):
    name = (account_name or "default").strip()
    if not name or name in LEGACY_ACCOUNT_NAMES:
        name = "default"

    store = _load_store()
    store["sessions"][name] = {
        "account_name": name,
        **session_payload,
    }
    store["active_account"] = name
    _save_store(store)
    return store["sessions"][name]


def get_default_account_name():
    sessions = list_account_sessions()
    if not sessions:
        return "default"
    return sessions[0]["account_name"]


def get_account_session(account_name):
    name = (account_name or "default").strip() or "default"
    store = _load_store()
    return store.get("sessions", {}).get(name)


def list_account_sessions():
    store = _load_store()
    sessions = store.get("sessions", {})
    return [
        {
            "account_name": name,
            **session,
        }
        for name, session in sorted(sessions.items())
    ]


def remove_account_session(account_name):
    name = (account_name or "default").strip() or "default"
    store = _load_store()
    sessions = store.get("sessions", {})
    sessions.pop(name, None)
    store["sessions"] = sessions
    _save_store(store)
