"""
Browser connector — controls Chromium via Playwright.
Provides fill_form() which takes an approval object and fills a local HTML form.
"""

from playwright.sync_api import sync_playwright


def fill_form(approval, headless=False):
    fields = approval["fields"]
    form_path = approval["form_path"]
    url = f"file://{__import__('os').path.abspath(form_path)}"

    filled = 0
    skipped = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url)

        for field in fields:
            fid = field["id"]
            value = field["value"]

            if not value:
                skipped += 1
                continue

            locator = page.locator(f"#{fid}")

            if locator.count() == 0:
                print(f"  [WARN] Field #{fid} not found on page")
                skipped += 1
                continue

            field_type = field["type"]
            if field_type in ("text", "textarea"):
                locator.fill(value)

            print(f"  [FILLED] {(field['label'] or fid)[:40]} → {value[:60]}")
            filled += 1

        print(f"\n{filled} fields filled, {skipped} skipped.")
        input("\nPress Enter to close the browser...")
        browser.close()
