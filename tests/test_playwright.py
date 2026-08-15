from playwright.sync_api import sync_playwright


def test_browser_launch():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        page = browser.new_page()
        page.goto("https://example.com")

        assert page.title() == "Example Domain"

        browser.close()