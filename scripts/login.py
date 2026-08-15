from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).resolve().parents[1]
PROFILE_DIR = BASE_DIR / "browser_profile"
LOGIN_URL = "https://www.angelone.in/login/"


def main() -> None:
    PROFILE_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",
            headless=False,
        )

        page = context.pages[0] if context.pages else context.new_page()

        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print(f"Opening: {page.url}")
        print(f"Title: {page.title()}")

        input(
            "\nComplete Angel One login manually. "
            "After successful login, press Enter here..."
        )

        print(f"\nFinal URL: {page.url}")
        print(f"Final title: {page.title()}")

        context.close()


if __name__ == "__main__":
    main()