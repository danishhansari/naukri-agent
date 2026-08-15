from pathlib import Path

from playwright.sync_api import sync_playwright


AUTH_FILE = Path("data/naukri_auth.json")


def main() -> None:
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        page = context.new_page()

        page.goto(
            "https://www.naukri.com/",
            wait_until="domcontentloaded",
        )

        print()
        print("Log in to Naukri in the browser.")
        print("Complete OTP/CAPTCHA manually if requested.")
        print()

        input("Press ENTER after you are logged in... ")

        context.storage_state(path=str(AUTH_FILE))

        print(f"Session saved to: {AUTH_FILE}")

        browser.close()


if __name__ == "__main__":
    main()
