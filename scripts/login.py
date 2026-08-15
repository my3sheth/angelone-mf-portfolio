from pathlib import Path

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
PROFILE_DIR = BASE_DIR / "browser_profile"
ENV_FILE = BASE_DIR / ".env"

LOGIN_URL = "https://www.angelone.in/login/"

TOKEN_NAMES = {
    "prod_non_trade_access_token": "ANGELONE_NON_TRADE_ACCESS_TOKEN",
    "prod_trade_access_token": "ANGELONE_TRADE_ACCESS_TOKEN",
}


def save_tokens(cookies: list[dict]) -> None:
    tokens = {}

    for cookie in cookies:
        env_name = TOKEN_NAMES.get(cookie["name"])

        if env_name:
            tokens[env_name] = cookie["value"]

    missing = set(TOKEN_NAMES.values()) - set(tokens)

    if missing:
        raise RuntimeError(
            f"Authentication tokens not found: {', '.join(sorted(missing))}"
        )

    existing = {}

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)

        for env_name in TOKEN_NAMES.values():
            value = __import__("os").getenv(env_name)

            if value:
                existing[env_name] = value

    existing.update(tokens)

    lines = [
        f"{name}={value}"
        for name, value in existing.items()
    ]

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"Saved authentication tokens to {ENV_FILE}")


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

        cookies = context.cookies()

        save_tokens(cookies)

        print(f"Final URL: {page.url}")
        print(f"Final title: {page.title()}")

        context.close()


if __name__ == "__main__":
    main()