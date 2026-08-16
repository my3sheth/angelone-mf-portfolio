import json
import re
from pathlib import Path

from dotenv import set_key
from playwright.sync_api import sync_playwright

from angelone.session_store import save_account_session


ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = ROOT / ".env"
PROFILE_ROOT = ROOT / "browser_profile"

LOGIN_URL = "https://www.angelone.in/login/"
MF_URL = "https://www.angelone.in/mutual-funds/investments/"

MF_API_HOST = "nbu-mf-portfolio.angelone.in"


class AngelOneAuthenticator:

    @staticmethod
    def _profile_dir_for(account_name="default"):
        safe_name = (account_name or "default").strip() or "default"
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe_name).strip("_")
        if not safe_name:
            safe_name = "default"
        PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        return PROFILE_ROOT / safe_name

    def _infer_logged_in_name(self, page):
        try:
            body_text = page.locator("body").inner_text(timeout=15000)
            text = " ".join(body_text.split())
            patterns = [
                r"(?i)\b(?:hi|hello|welcome)\s*,?\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})",
                r"(?i)\bmy\s+name\s+is\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})",
                r"(?i)\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})\s*\|\s*.*?",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    inferred = match.group(1).strip()
                    if inferred and inferred.lower() not in {"maitri", "maitri sheth", "user", "welcome", "hello"}:
                        return inferred
        except Exception:
            pass

        return None

    def login(self, account_name="default", headless=False):

        captured = None

        profile_dir = self._profile_dir_for(account_name)

        with sync_playwright() as p:

            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                channel="chrome",
            )

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
                            "headers": dict(
                                request.headers
                            ),
                            "cookies": context.cookies(),
                        }

                        print()
                        print(
                            "Captured authenticated "
                            "MF holdings request."
                        )
                        print(request.url)

            page.on(
                "request",
                capture_request,
            )

            print(
                f"Opening: {LOGIN_URL}"
            )

            page.goto(
                LOGIN_URL,
                wait_until="domcontentloaded",
            )

            print()
            print(
                "Complete Angel One login "
                "in the browser."
            )
            print(
                "Waiting for successful login..."
            )
            print()

            # Wait indefinitely until Angel One
            # redirects to the authenticated area.
            while True:
                if "/trade/home" in page.url:
                    break

                if "/trade/tradeone/chart" in page.url:
                    break

                page.wait_for_timeout(1000)

            print()
            print("Login successful.")
            print(
                "Opening Mutual Fund "
                "investments automatically..."
            )

            try:
                page.goto(
                    MF_URL,
                    wait_until="domcontentloaded",
                    timeout=0,
                )
            except Exception as exc:

                # Angel One can continue loading
                # after the navigation timeout.
                print(
                    f"MF navigation notice: {exc}"
                )

            print()
            print(
                "Waiting indefinitely for "
                "MF holdings API request..."
            )

            # Wait indefinitely.
            while captured is None:

                # Keep the browser alive while
                # network requests are captured.
                page.wait_for_timeout(1000)

            # Save authentication information.
            session_payload = {
                "headers": captured["headers"],
                "cookies": captured["cookies"],
                "url": captured["url"],
            }

            inferred_name = self._infer_logged_in_name(page) or account_name
            if inferred_name in {"Maitri", "Maitri Sheth"}:
                inferred_name = account_name or "default"
            save_account_session(inferred_name, session_payload)

            set_key(
                str(ENV_FILE),
                "ANGELONE_MF_HEADERS",
                json.dumps(
                    captured["headers"]
                ),
            )

            set_key(
                str(ENV_FILE),
                "ANGELONE_MF_COOKIES",
                json.dumps(
                    captured["cookies"]
                ),
            )

            set_key(
                str(ENV_FILE),
                "ANGELONE_MF_URL",
                captured["url"],
            )

            context.close()

        print()
        print(
            f"Authentication data saved to "
            f"{ENV_FILE}"
        )
        print("Browser closed.")