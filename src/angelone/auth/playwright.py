import base64
import json
import re
from datetime import datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from angelone.auth_store import save_auth_details as save_auth_json
from angelone.session_store import save_account_session


ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = ROOT / ".env"
PROFILE_ROOT = ROOT / "browser_profile"

LOGIN_URL = "https://www.angelone.in/login/"
MF_URL = "https://www.angelone.in/mutual-funds/investments/"

MF_API_HOST = "nbu-mf-portfolio.angelone.in"

import zlib

INVALID_NAMES = {
    "default",
    "user",
    "placeholder",
    "undefined",
    "null",
    "none",
    "temp",
    "temporary",
    "new-account",
    "login",
    "logout",
    "home",
    "dashboard",
    "trade",
    "angel",
    "one",
    "welcome",
    "hello",
    "portfolio",
    "account",
    "profile",
}


def _extract_from_ab_user_cookie(cookie_val):
    """Decompress and parse Angel One ABUserCookie containing UserName and ClientCode."""
    if not cookie_val or not isinstance(cookie_val, str):
        return None
    try:
        raw_b64 = base64.b64decode(cookie_val.strip())
        try:
            decompressed = zlib.decompress(raw_b64)
        except Exception:
            decompressed = zlib.decompress(raw_b64, -zlib.MAX_WBITS)
        data = json.loads(decompressed.decode("utf-8", errors="ignore"))
        if isinstance(data, dict):
            user_name = (data.get("UserName") or "").strip()
            if user_name and _is_valid_user_name(user_name):
                # Clean and title-case for clean display
                cleaned = re.sub(r"\s+", " ", user_name).title()
                return cleaned
            client_code = (data.get("ClientCode") or "").strip()
            if client_code and _is_valid_user_name(client_code):
                return client_code
    except Exception as exc:
        print(f"        ABUserCookie notice: {exc}")
    return None


def _decode_jwt_payload(token_str):
    """Safely decode JWT token payload without signature verification."""
    try:
        if not token_str or not isinstance(token_str, str):
            return None
        token = token_str.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            decoded_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
            return json.loads(decoded_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        pass
    return None


def _is_valid_user_name(name):
    """Check if the name is a real user name and not a placeholder/uuid/ip."""
    if not name:
        return False
    cleaned = re.sub(r"\s+", " ", str(name)).strip()
    if len(cleaned) < 2:
        return False
    lower = cleaned.lower()
    if lower in INVALID_NAMES:
        return False
    if cleaned.isdigit():
        return False
    if ":" in cleaned:  # IPv6 address or port
        return False
    if bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", cleaned)):  # IPv4 address
        return False
    if lower.startswith("account_") or lower.startswith("profile_"):
        return False
    if bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:-[A-Za-z0-9]+)?", cleaned)):
        return False
    if len(cleaned) >= 12 and not (" " in cleaned) and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return False
    if len(cleaned) >= 40 and not (" " in cleaned):
        return False
    return True


def _extract_name_from_dict(d):
    """Search a dict for common user name keys."""
    if not isinstance(d, dict):
        return None
    keys_priority = [
        "UserName", "userName", "user_name",
        "longName", "long_name",
        "clientName", "client_name",
        "fullName", "full_name",
        "displayName", "display_name",
        "name",
        "customerName", "customer_name",
    ]
    for key in keys_priority:
        val = d.get(key)
        if isinstance(val, str) and _is_valid_user_name(val):
            return re.sub(r"\s+", " ", val).title() if val.isupper() else val.strip()

    # Search nested dicts
    for v in d.values():
        if isinstance(v, dict):
            found = _extract_name_from_dict(v)
            if found:
                return found
    return None


def _fetch_profile_via_api(headers, cookies):
    """Fetch user profile directly via HTTP POST with intercepted credentials."""
    try:
        url = "https://kyc2-clcm-critical.angelone.in/v2/client/profile"
        req_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
        }
        for k, v in (headers or {}).items():
            if k.lower() not in {"host", "content-length", "connection", "cookie"}:
                req_headers[k] = v

        cookie_dict = {}
        for c in (cookies or []):
            if isinstance(c, dict) and "name" in c and "value" in c:
                cookie_dict[c["name"]] = c["value"]

        body = {
            "masked": False,
            "fields": [
                "activeSegments",
                "homepageDetails",
                "clientDetails.UserType",
                "clientDetails.Mobile",
                "clientDetails.ClientId",
                "clientDetails.CreateTs",
                "clientDetails.LongName",
                "clientDetails.Pan",
            ],
        }

        resp = requests.post(url, json=body, headers=req_headers, cookies=cookie_dict, timeout=10)
        if resp.ok:
            data = resp.json()
            rows = data.get("data") or []
            if rows and isinstance(rows, list):
                client_details = rows[0].get("clientDetails") or {}
                long_name = client_details.get("longName")
                if long_name and _is_valid_user_name(long_name):
                    return re.sub(r"\s+", " ", str(long_name)).title()
                client_id = client_details.get("ClientId") or client_details.get("clientId")
                if client_id and _is_valid_user_name(client_id):
                    return str(client_id).strip()
    except Exception as exc:
        print(f"        Profile API fetch notice: {exc}")
    return None


def _extract_from_tokens_and_cookies(headers, cookies):
    """Extract user name or client ID from cookies and JWT tokens."""
    # Check ABUserCookie first
    if cookies:
        for c in cookies:
            if isinstance(c, dict) and c.get("name") == "ABUserCookie":
                found = _extract_from_ab_user_cookie(c.get("value"))
                if found:
                    return found

    # Check headers for JWT
    if headers:
        for k, v in headers.items():
            if not isinstance(v, str):
                continue
            payload = _decode_jwt_payload(v)
            if payload:
                found = _extract_name_from_dict(payload)
                if found:
                    return found

    # Check cookies for JWT or names
    if cookies:
        for c in cookies:
            if not isinstance(c, dict):
                continue
            val = c.get("value") or ""
            name = (c.get("name") or "").lower()
            if any(k in name for k in ["name", "user", "client", "customer"]) and _is_valid_user_name(val):
                return re.sub(r"\s+", " ", val).title() if val.isupper() else val.strip()
            payload = _decode_jwt_payload(val)
            if payload:
                found = _extract_name_from_dict(payload)
                if found:
                    return found

    return None


def _extract_expiration(cookies, headers):
    """Extract expiration datetime string from cookies or JWT tokens."""
    if cookies:
        for c in cookies:
            if isinstance(c, dict) and c.get("name") == "ABUserCookie":
                try:
                    raw_b64 = base64.b64decode(c.get("value", "").strip())
                    try:
                        dec = zlib.decompress(raw_b64)
                    except Exception:
                        dec = zlib.decompress(raw_b64, -zlib.MAX_WBITS)
                    data = json.loads(dec.decode("utf-8", errors="ignore"))
                    nt_exp = data.get("NTRefreshExp")
                    if nt_exp:
                        return datetime.utcfromtimestamp(nt_exp / 1000.0).isoformat()
                except Exception:
                    pass
        for c in cookies:
            if isinstance(c, dict):
                jwt = _decode_jwt_payload(c.get("value"))
                if jwt and "exp" in jwt:
                    return datetime.utcfromtimestamp(jwt["exp"]).isoformat()
    if headers:
        for v in headers.values():
            if isinstance(v, str):
                jwt = _decode_jwt_payload(v)
                if jwt and "exp" in jwt:
                    return datetime.utcfromtimestamp(jwt["exp"]).isoformat()
    return None


class AngelOneAuthenticator:

    @staticmethod
    def _profile_dir_for(account_name="default"):
        safe_name = (account_name or "default").strip() or "default"
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe_name).strip("_")
        if not safe_name:
            safe_name = "default"
        PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        return PROFILE_ROOT / safe_name

    def _infer_logged_in_name(self, page, captured=None):
        """
        Extract the real Angel One user name using multi-tiered strategy:
        1. ABUserCookie decompressor (Python-side)
        2. Intercepted JWT Tokens & Cookies (Python-side)
        3. Direct authenticated Profile API request (Python-side)
        4. In-browser evaluate: Profile API, LocalStorage/SessionStorage JSON parsing, DOM elements
        5. In-page text matching
        """
        headers = (captured or {}).get("headers") or {}
        cookies = (captured or {}).get("cookies") or []

        # Tier 1: Check ABUserCookie and JWT tokens
        print("        [1/4] Checking cookies and JWT tokens...")
        name = _extract_from_tokens_and_cookies(headers, cookies)
        if name:
            print(f"        Found profile name via cookie/token: {name}")
            return name

        # Tier 2: Direct HTTP call to Profile API with captured headers
        print("        [2/4] Checking profile API with network credentials...")
        name = _fetch_profile_via_api(headers, cookies)
        if name:
            print(f"        Found profile name via API: {name}")
            return name

        # Tier 3: Browser DOM, Storage & Evaluated API
        print("        [3/4] Checking browser storage and DOM...")
        try:
            browser_candidates = page.evaluate(
                """
                () => {
                    const values = [];
                    const seen = new Set();
                    const add = (value) => {
                        if (!value) return;
                        const text = String(value).trim();
                        if (text && !seen.has(text.toLowerCase()) && text.length >= 2 && !text.includes(':')) {
                            seen.add(text.toLowerCase());
                            values.push(text);
                        }
                    };

                    const searchObj = (obj) => {
                        if (!obj || typeof obj !== 'object') return;
                        const keys = ['longName', 'long_name', 'clientName', 'client_name', 'userName', 'user_name', 'fullName', 'full_name', 'displayName', 'name', 'customerName'];
                        for (const k of keys) {
                            if (obj[k] && typeof obj[k] === 'string' && !obj[k].includes(':')) add(obj[k]);
                        }
                        for (const v of Object.values(obj)) {
                            if (typeof v === 'object') searchObj(v);
                        }
                    };

                    // Search all storage keys
                    const storageKeys = [
                        'userName', 'username', 'user_name',
                        'customerName', 'customer_name',
                        'profileName', 'profile_name',
                        'displayName', 'display_name',
                        'accountName', 'account_name',
                        'name', 'fullName', 'full_name',
                        'clientName', 'client_name',
                        'holderName', 'holder_name',
                        'user_details', 'userDetails', 'userData', 'user', 'profile', 'profileData',
                        'clientDetails', 'client_details', 'auth_user', 'globalState'
                    ];

                    for (const store of [localStorage, sessionStorage]) {
                        try {
                            for (let i = 0; i < store.length; i++) {
                                const key = store.key(i);
                                const val = store.getItem(key);
                                if (!val) continue;
                                add(val);
                                try {
                                    const parsed = JSON.parse(val);
                                    searchObj(parsed);
                                } catch {}
                            }
                        } catch {}
                    }

                    // Check cookies
                    try {
                        const cookiePairs = document.cookie.split(';');
                        for (const pair of cookiePairs) {
                            const [name, value] = pair.split('=');
                            const key = (name || '').trim().toLowerCase();
                            const val = (value || '').trim();
                            if (/name|user|customer|profile|account|client|holder/i.test(key) && val && val.length > 2) {
                                try { add(decodeURIComponent(val)); } catch {}
                            }
                        }
                    } catch {}

                    // Check DOM elements
                    const selectors = [
                        '[data-user-name]', '[data-customer-name]', '[data-profile-name]', '[data-account-name]',
                        '[aria-label*="profile"]', '[aria-label*="name"]', '[aria-label*="user"]',
                        '.user-name', '.profile-name', '.account-name', '.customer-name',
                        '[class*="profile"] [class*="name"]',
                        '[class*="header"] [class*="profile"]',
                        '[class*="user"] [class*="name"]',
                        '.header-profile', '.navbar-profile', '.top-profile',
                        '[id*="profile"]', '[id*="user"]', '[id*="account"]',
                    ];
                    for (const selector of selectors) {
                        try {
                            for (const el of document.querySelectorAll(selector)) {
                                add(el.getAttribute('aria-label') || el.textContent || el.getAttribute('title'));
                            }
                        } catch {}
                    }

                    return values;
                }
                """
            ) or []

            for val in browser_candidates:
                if _is_valid_user_name(val):
                    print(f"        Found valid name from browser state: {val}")
                    return str(val).strip()

        except Exception as exc:
            print(f"        Browser evaluation notice: {exc}")

        # Tier 4: Page visible text regex
        print("        [4/4] Checking page text patterns...")
        try:
            body_text = page.locator("body").inner_text(timeout=5000)
            text = " ".join(body_text.split())

            patterns = [
                r"(?i)\bwelcome\s*,?\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
                r"(?i)\bhi\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
                r"(?i)\bhello\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
                r"(?i)\bnamaste\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
                r"(?i)portfolio\s+of\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
                r"(?i)account.*?:\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
                r"(?i)name\s*:\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,3})\b",
            ]

            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    inferred = match.group(1).strip()
                    if _is_valid_user_name(inferred):
                        print(f"        Found name in text: {inferred}")
                        return inferred
        except Exception as exc:
            print(f"        Page text extraction notice: {exc}")

        return None

    def login(self, account_name="default", headless=False, clear_session=True):
        captured = None
        profile_label = (account_name or "").strip() or f"profile_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        profile_dir = self._profile_dir_for(profile_label)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                channel="chrome",
            )

            if clear_session:
                try:
                    context.clear_cookies()
                except Exception:
                    pass

            page = (
                context.pages[0]
                if context.pages
                else context.new_page()
            )

            # No login timeout.
            page.set_default_timeout(0)
            page.set_default_navigation_timeout(0)

            def capture_request(request):
                nonlocal captured
                if (
                    MF_API_HOST in request.url
                    and "/v2/portfolios/holdings?" in request.url
                ):
                    if captured is None:
                        captured = {
                            "url": request.url,
                            "headers": dict(request.headers),
                            "cookies": context.cookies(),
                        }
                        print()
                        print("Captured authenticated MF holdings request.")
                        print(request.url)

            page.on("request", capture_request)

            print(f"Opening: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            print()
            print("Complete Angel One login in the browser.")
            print("Waiting for successful login...")
            print()

            # Wait until Angel One redirects to the authenticated area.
            while True:
                curr_url = page.url.lower()
                cookies = context.cookies()
                has_auth_cookie = any(
                    c.get("name") in {"ABUserCookie", "prod_non_trade_access_token", "prod_trade_access_token"}
                    for c in cookies
                )

                if (
                    "/trade" in curr_url
                    or "/mutual-funds" in curr_url
                    or "/dashboard" in curr_url
                    or has_auth_cookie
                ) and "/login" not in curr_url:
                    break

                page.wait_for_timeout(1000)

            print()
            print("Login successful.")
            print("Opening Mutual Fund investments automatically...")
            page.wait_for_timeout(2000)

            try:
                page.goto(
                    MF_URL,
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except Exception as exc:
                print(f"MF navigation notice: {exc}")

            print()
            print("Waiting for MF holdings API request...")

            nav_retries = 0
            while captured is None:
                curr_url = page.url.lower()
                # If still on /trade or not yet on mutual-funds, navigate directly
                if captured is None and "/mutual-funds" not in curr_url and nav_retries < 5:
                    page.wait_for_timeout(2000)
                    try:
                        print(f"Navigating to Mutual Funds investments... (attempt {nav_retries + 1})")
                        mf_link = page.locator("a[href*='mutual-funds']").first
                        if mf_link.is_visible(timeout=1000):
                            mf_link.click(timeout=3000)
                        else:
                            page.goto(MF_URL, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        try:
                            page.goto(MF_URL, wait_until="domcontentloaded", timeout=30000)
                        except Exception:
                            pass
                    nav_retries += 1

                page.wait_for_timeout(1000)

            expires_at = _extract_expiration(captured["cookies"], captured["headers"])

            # Save authentication information.
            session_payload = {
                "headers": captured["headers"],
                "cookies": captured["cookies"],
                "url": captured["url"],
                "expires_at": expires_at,
            }

            inferred_name = self._infer_logged_in_name(page, captured=captured)
            if not inferred_name:
                raise RuntimeError("Unable to determine the Angel One user name. Please log in again.")

            cleaned_name = inferred_name.strip()
            if not _is_valid_user_name(cleaned_name):
                raise RuntimeError(f"Extracted name '{cleaned_name}' is not a valid user name. Please log in again.")

            save_account_session(cleaned_name, session_payload)

            # Track auth details in SQLite auth_details table
            save_auth_json(
                cleaned_name,
                headers=captured["headers"],
                cookies=captured["cookies"],
                url=captured["url"],
                inferred_name=cleaned_name,
                expires_at=expires_at,
            )

            context.close()

        print()
        print(f"Authentication data saved for account '{cleaned_name}' (Expires: {expires_at or 'N/A'}).")
        print("Browser closed.")
        return cleaned_name