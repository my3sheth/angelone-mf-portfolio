import json
from pathlib import Path

from dotenv import set_key
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = ROOT / ".env"
PROFILE_DIR = ROOT / "browser_profile"

LOGIN_URL = "https://www.angelone.in/login/"
MF_URL = "https://www.angelone.in/mutual-funds/investments/"

MF_API_HOST = "nbu-mf-portfolio.angelone.in"


class AngelOneAuthenticator:

    def login(self):

        captured = None

        with sync_playwright() as p:

            context = p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=False,
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