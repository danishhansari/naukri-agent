import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)

from llm import get_answers
from form_parser import (
    extract_form_fields,
    extract_page_text
)
from form_filler import (
    fill_field,
    validate_field
)


load_dotenv()

NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")

SEARCH_KEYWORD = os.getenv(
    "SEARCH_KEYWORD",
    "Java Developer"
)

SEARCH_LOCATION = os.getenv(
    "SEARCH_LOCATION",
    "Mumbai"
)

MIN_EXPERIENCE = os.getenv(
    "MIN_EXPERIENCE",
    "2"
)

MAX_APPLICATIONS = int(
    os.getenv(
        "MAX_APPLICATIONS",
        "1"
    )
)

HEADLESS = (
    os.getenv(
        "HEADLESS",
        "false"
    ).lower() == "true"
)

AUTO_SUBMIT = (
    os.getenv(
        "AUTO_SUBMIT",
        "false"
    ).lower() == "true"
)


BASE_DIR = Path(__file__).resolve().parent

PROFILE_FILE = (
    BASE_DIR / "profile.json"
)

REVIEW_DIR = (
    BASE_DIR / "manual_review"
)


if not NAUKRI_EMAIL or not NAUKRI_PASSWORD:
    print(
        "Missing NAUKRI_EMAIL / "
        "NAUKRI_PASSWORD in .env"
    )

    sys.exit(1)


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def load_profile():
    with open(
        PROFILE_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def ensure_review_dir():
    REVIEW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def save_manual_review(page, reason):
    """
    Save screenshot + page HTML for investigation.
    """

    ensure_review_dir()

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_reason = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        reason
    )

    prefix = (
        REVIEW_DIR /
        f"{timestamp}_{safe_reason}"
    )

    try:
        page.screenshot(
            path=str(prefix) + ".png",
            full_page=True
        )
    except Exception:
        pass

    try:
        html = page.content()

        with open(
            str(prefix) + ".html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(html)

    except Exception:
        pass

    print(
        f"Manual review saved to: {prefix}"
    )


# ---------------------------------------------------------
# Login
# ---------------------------------------------------------

def login(page):

    print(
        "Navigating to Naukri login..."
    )

    page.goto(
        "https://www.naukri.com/nlogin/login",
        wait_until="domcontentloaded"
    )

    page.fill(
        "#usernameField",
        NAUKRI_EMAIL
    )

    page.fill(
        "#passwordField",
        NAUKRI_PASSWORD
    )

    page.click(
        'button[type="submit"]'
    )

    try:

        page.wait_for_url(
            "**/mnjuser/homepage**",
            timeout=20000
        )

        print(
            "Login successful."
        )

    except PlaywrightTimeoutError:

        error_text = None

        try:
            error_text = page.locator(
                ".erLbl, .error-txt"
            ).first.text_content(
                timeout=2000
            )
        except Exception:
            pass

        raise RuntimeError(
            "Login may have failed. "
            +
            (
                f"Naukri error: {error_text}"
                if error_text
                else
                "Check credentials/selectors."
            )
        )


# ---------------------------------------------------------
# Search URL
# ---------------------------------------------------------

def build_search_url():

    keyword = SEARCH_KEYWORD.strip()

    location = SEARCH_LOCATION.strip()

    keyword_slug = (
        keyword.lower()
        .replace(" ", "-")
    )

    location_slug = (
        location.lower()
        .replace(" ", "-")
    )

    return (
        f"https://www.naukri.com/"
        f"{keyword_slug}-jobs-in-{location_slug}"
        f"?k={keyword_slug}"
        f"&l={location_slug}"
        f"&experience={MIN_EXPERIENCE}"
        f"&jobAge=30"
    )


# ---------------------------------------------------------
# Job description
# ---------------------------------------------------------

def extract_job_description(page):

    selectors = [
        ".styles_job-desc-container__tx0Q7",
        ".job-desc",
        ".dang-inner-html",
        "[class*='job-desc']"
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.count():

                text = locator.inner_text(
                    timeout=2000
                )

                if text.strip():
                    return text[:12000]

        except Exception:
            continue

    return extract_page_text(
        page,
        max_length=12000
    )


# ---------------------------------------------------------
# Detect application page
# ---------------------------------------------------------

def get_application_page(job_page, context):
    """
    Click Apply and determine whether the application stays on Naukri.

    If the application goes to an external company/ATS website,
    return None so the caller skips this job.
    """

    before_pages = set(context.pages)

    apply_button = job_page.locator(
        '#apply-button, '
        '.apply-button, '
        'button:has-text("Apply"), '
        'a:has-text("Apply")'
    ).first

    try:
        if not apply_button.is_visible(timeout=3000):
            return None
    except Exception:
        return None

    print("  Clicking Apply...")

    try:
        apply_button.click()
    except Exception as exc:
        print(f"  Could not click Apply: {exc}")
        return None

    # Allow popup/redirect to happen.
    time.sleep(3)

    after_pages = set(context.pages)

    new_pages = list(
        after_pages - before_pages
    )

    # --------------------------------------------------
    # Case 1: New tab/page opened
    # --------------------------------------------------

    if new_pages:

        application_page = new_pages[0]

        try:
            application_page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000
            )
        except Exception:
            pass

        url = application_page.url.lower()

        print(
            f"  Apply opened: {application_page.url}"
        )

        if "naukri.com" not in url:

            print(
                "  External company/ATS application detected."
            )

            print(
                "  Skipping this job."
            )

            try:
                application_page.close()
            except Exception:
                pass

            return None

        return application_page

    # --------------------------------------------------
    # Case 2: Same page was redirected
    # --------------------------------------------------

    current_url = job_page.url.lower()

    print(
        f"  After Apply URL: {job_page.url}"
    )

    if "naukri.com" not in current_url:

        print(
            "  External company/ATS application detected."
        )

        print(
            "  Skipping this job."
        )

        return None

    # Still on Naukri.
    return job_page

    before_pages = set(
        context.pages
    )

    apply_button = job_page.locator(
        '#apply-button, '
        '.apply-button, '
        'button:has-text("Apply"), '
        'a:has-text("Apply")'
    ).first

    if not apply_button.is_visible(
        timeout=3000
    ):
        return None

    print(
        "  Clicking Apply..."
    )

    apply_button.click()

    # Give redirects/popups time to happen.
    time.sleep(3)

    after_pages = set(
        context.pages
    )

    new_pages = list(
        after_pages - before_pages
    )

    if new_pages:

        application_page = new_pages[0]

        try:
            application_page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000
            )
        except Exception:
            pass

        return application_page

    # Application stayed on same page.
    return job_page


# ---------------------------------------------------------
# CAPTCHA / assessment detection
# ---------------------------------------------------------

def detect_manual_intervention(page):

    text = ""

    try:
        text = page.locator(
            "body"
        ).inner_text(
            timeout=3000
        )

    except Exception:
        return None

    lowered = text.lower()

    indicators = [
        "captcha",
        "i'm not a robot",
        "verify you are human",
        "recaptcha",
        "assessment",
        "coding challenge",
        "technical test"
    ]

    for indicator in indicators:

        if indicator in lowered:
            return indicator

    return None


# ---------------------------------------------------------
# Form processing
# ---------------------------------------------------------

def process_application_form(
    page,
    profile,
    job_description
):

    print(
        "\nInspecting application form..."
    )

    fields = extract_form_fields(
        page
    )

    if not fields:

        print(
            "No standard form controls found."
        )

        return False

    print(
        f"Found {len(fields)} "
        f"visible form controls."
    )

    questions = []

    for field in fields:

        questions.append({
            "question_id":
                field["question_id"],

            "label":
                field["label"],

            "type":
                field["type"],

            "required":
                field["required"],

            "options":
                field["options"]
        })

    print(
        "\nSending form questions "
        "to OpenRouter..."
    )

    result = get_answers(
        profile=profile,
        questions=questions,
        job_description=job_description
    )

    answers = result.get(
        "answers",
        []
    )

    answer_map = {
        item["question_id"]: item
        for item in answers
    }

    unknown_required = []

    filled_count = 0

    for field in fields:

        question_id = (
            field["question_id"]
        )

        label = (
            field["label"]
            or field["name"]
            or field["id"]
            or question_id
        )

        answer_data = (
            answer_map.get(question_id)
        )

        if not answer_data:

            print(
                f"  ⚠ No answer: {label}"
            )

            if field["required"]:
                unknown_required.append(
                    label
                )

            continue

        answer = answer_data.get(
            "answer"
        )

        confidence = answer_data.get(
            "confidence",
            "low"
        )

        reason = answer_data.get(
            "reason",
            "unknown"
        )

        print(
            f"\n  {label}"
        )

        print(
            f"    Answer: {answer}"
        )

        print(
            f"    Confidence: {confidence}"
        )

        print(
            f"    Source: {reason}"
        )

        # Never invent low-confidence information.
        if answer is None:

            if field["required"]:
                unknown_required.append(
                    label
                )

            print(
                "    ⚠ Unknown - not filling."
            )

            continue

        if confidence == "low":

            print(
                "    ⚠ Low confidence - "
                "not filling."
            )

            if field["required"]:
                unknown_required.append(
                    label
                )

            continue

        filled = fill_field(
            page,
            field,
            answer
        )

        if not filled:

            print(
                "    ⚠ Could not fill."
            )

            if field["required"]:
                unknown_required.append(
                    label
                )

            continue

        valid = validate_field(
            page,
            field,
            answer
        )

        if valid:

            print(
                "    ✓ Filled and validated."
            )

            filled_count += 1

        else:

            print(
                "    ⚠ Validation failed."
            )

            if field["required"]:
                unknown_required.append(
                    label
                )

    print(
        f"\nFilled fields: {filled_count}"
    )

    if unknown_required:

        print(
            "\n⚠ Required information "
            "could not be safely filled:"
        )

        for item in unknown_required:
            print(
                f"  - {item}"
            )

        save_manual_review(
            page,
            "missing_required_fields"
        )

        return False

    return True


# ---------------------------------------------------------
# Submit
# ---------------------------------------------------------

def submit_application(page):

    if not AUTO_SUBMIT:

        print(
            "\nAUTO_SUBMIT=false"
        )

        print(
            "Form was filled successfully."
        )

        print(
            "Stopping before final submission."
        )

        save_manual_review(
            page,
            "ready_for_submission"
        )

        return False

    print(
        "\nLooking for final submit button..."
    )

    submit = page.locator(
        'button[type="submit"], '
        'input[type="submit"], '
        'button:has-text("Submit"), '
        'button:has-text("Apply")'
    ).first

    try:

        if not submit.is_visible(
            timeout=3000
        ):

            print(
                "No final submit button found."
            )

            save_manual_review(
                page,
                "no_submit_button"
            )

            return False

        submit.click()

        time.sleep(3)

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

        lowered = body_text.lower()

        success_words = [
            "application submitted",
            "application sent",
            "applied successfully",
            "thank you for applying",
            "application received"
        ]

        for word in success_words:

            if word in lowered:

                print(
                    "✓ Application submitted."
                )

                return True

        print(
            "Submit clicked but success "
            "could not be confirmed."
        )

        save_manual_review(
            page,
            "submission_uncertain"
        )

        return False

    except Exception as exc:

        print(
            f"Submission error: {exc}"
        )

        save_manual_review(
            page,
            "submission_error"
        )

        return False


# ---------------------------------------------------------
# Process jobs
# ---------------------------------------------------------

def apply_to_listings(
    page,
    context,
    profile
):

    search_url = build_search_url()

    print(
        f"\nSearching:\n{search_url}"
    )

    page.goto(
        search_url,
        wait_until="domcontentloaded"
    )

    time.sleep(2)

    job_card_selector = (
        ".srp-jobtuple-wrapper, "
        ".jobTuple"
    )

    try:

        page.wait_for_selector(
            job_card_selector,
            timeout=20000
        )

    except PlaywrightTimeoutError:

        print(
            "No job cards found. "
            "Naukri layout may have changed."
        )

        return

    job_cards = page.locator(
        job_card_selector
    ).all()

    print(
        f"Found {len(job_cards)} "
        f"job listings."
    )

    applied_count = 0
    skipped_count = 0

    for i, card in enumerate(
        job_cards
    ):

        if applied_count >= MAX_APPLICATIONS:
            break

        job_title = "Unknown title"

        try:

            job_title = card.locator(
                ".title, a.title"
            ).first.text_content(
                timeout=2000
            ).strip()

        except Exception:
            pass

        print(
            f"\n[{i + 1}/{len(job_cards)}] "
            f"{job_title}"
        )

        # Open job in new tab.
        job_page = None

        try:

            with context.expect_page(
                timeout=5000
            ) as new_page_info:

                card.locator(
                    ".title, a.title"
                ).first.click(
                    modifiers=["Control"]
                )

            job_page = (
                new_page_info.value
            )

        except Exception:

            print(
                "  Could not open job."
            )

            skipped_count += 1
            continue

        try:

            job_page.wait_for_load_state(
                "domcontentloaded"
            )

            time.sleep(1.5)

            # Already applied?
            try:

                already = job_page.locator(
                    "text=Already Applied"
                ).first

                if already.is_visible(
                    timeout=1500
                ):

                    print(
                        "  Already applied."
                    )

                    skipped_count += 1
                    continue

            except Exception:
                pass

            job_description = (
                extract_job_description(
                    job_page
                )
            )

            application_page = (
                get_application_page(
                    job_page,
                    context
                )
            )

            if not application_page:

                print(
                    "  No Apply button."
                )

                skipped_count += 1
                continue

            print(
                "  Application URL:"
            )

            print(
                f"  {application_page.url}"
            )

            # Check for CAPTCHA or assessment.
            manual_reason = (
                detect_manual_intervention(
                    application_page
                )
            )

            if manual_reason:

                print(
                    f"  ⚠ Manual intervention "
                    f"required: {manual_reason}"
                )

                save_manual_review(
                    application_page,
                    manual_reason
                )

                skipped_count += 1
                continue

            # Process form.
            success = (
                process_application_form(
                    application_page,
                    profile,
                    job_description
                )
            )

            if not success:

                print(
                    "  Form could not be "
                    "safely completed."
                )

                skipped_count += 1
                continue

            # Submit if enabled.
            submitted = (
                submit_application(
                    application_page
                )
            )

            if submitted:

                applied_count += 1

            else:

                # With AUTO_SUBMIT=false,
                # don't count it as submitted.
                skipped_count += 1

        except Exception as err:

            print(
                f"  Error: {err}"
            )

            try:
                save_manual_review(
                    job_page,
                    "unexpected_error"
                )
            except Exception:
                pass

            skipped_count += 1

        finally:

            try:
                job_page.close()
            except Exception:
                pass

            time.sleep(2)

    print(
        "\n================================"
    )

    print(
        f"Applied: {applied_count}"
    )

    print(
        f"Skipped/Manual: {skipped_count}"
    )

    print(
        "================================"
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    profile = load_profile()

    print(
        "Starting Naukri automation..."
    )

    print(
        f"Keyword: {SEARCH_KEYWORD}"
    )

    print(
        f"Location: {SEARCH_LOCATION}"
    )

    print(
        f"Max applications: "
        f"{MAX_APPLICATIONS}"
    )

    print(
        f"Auto submit: {AUTO_SUBMIT}"
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS
        )

        context = browser.new_context()

        page = context.new_page()

        try:

            login(page)

            apply_to_listings(
                page,
                context,
                profile
            )

        except Exception as err:

            print(
                f"\nScript failed: {err}"
            )

        finally:

            time.sleep(3)

            browser.close()


if __name__ == "__main__":
    main()