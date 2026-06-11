"""
Reads form fields from a live website using Playwright.
Opens a visible browser, waits for the page to fully load,
then extracts all form fields and prints them.

Usage: python3 tests/read_live_form.py
"""

import json
from playwright.sync_api import sync_playwright

URL = "https://www.firstclasssupply.co.uk/create-cv-secondary/"


def read_live_form(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print(f"Opening: {url}")
        page.goto(url, wait_until="networkidle")
        print("Page loaded.\n")

        fields = page.evaluate("""() => {
            const results = [];
            const elements = document.querySelectorAll('input, textarea, select');
            elements.forEach(el => {
                if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return;

                let label = null;
                if (el.id) {
                    const labelEl = document.querySelector(`label[for="${el.id}"]`);
                    if (labelEl) label = labelEl.innerText.trim();
                }
                if (!label) {
                    const parent = el.closest('label');
                    if (parent) label = parent.innerText.trim();
                }
                if (!label && el.placeholder) label = el.placeholder;

                results.push({
                    id: el.id || null,
                    name: el.name || null,
                    type: el.type || el.tagName.toLowerCase(),
                    label: label,
                    required: el.required
                });
            });
            return results;
        }""")

        print(f"Found {len(fields)} fields:\n")
        print(json.dumps(fields, indent=2))

        input("\nPress Enter to close the browser...")
        browser.close()
        return fields


if __name__ == "__main__":
    read_live_form(URL)
