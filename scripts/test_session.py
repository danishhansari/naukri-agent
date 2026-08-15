from pathlib import Path

from playwright.sync_api import sync_playwright


AUTH_FILE = Path("data/naukri_auth.json")


def main() -> None:
    if not AUTH_FILE.exists():
        raise FileNotFoundError(
            "No Naukri session found. Run: "
            "uv run python scripts/login.py"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            storage_state=str(AUTH_FILE),
        )

        page = context.new_page()

        page.goto(
            "https://www.naukri.com/",
            wait_until="domcontentloaded",
        )

        print("Naukri opened using saved session.")
        print("Check the browser to confirm you're logged in.")

        input("Press ENTER to close... ")

        browser.close()


if __name__ == "__main__":
    main()
