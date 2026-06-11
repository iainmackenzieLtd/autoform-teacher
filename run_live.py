"""
End-to-end live pipeline for the First Class Supply teaching CV form.

Opens a real browser, reads the live form, maps fields to your profile,
asks for confirmation, then fills the form — all in one session.

Usage: python3 run_live.py
"""

import json
import sys
from playwright.sync_api import sync_playwright

PROFILE_PATH = "profile/user_profile.json"
URL = "https://www.firstclasssupply.co.uk/create-cv-secondary/"

IGNORE_IDS = {"wt-cli-checkbox-necessary", "wt-cli-checkbox-analytics"}


def load_profile():
    with open(PROFILE_PATH) as f:
        return json.load(f)


def clean_label(label):
    if not label:
        return ""
    return label.replace("*", "").strip().lower()


def join_bullets(items):
    return "; ".join(items) if items else None


def fetch_fields(page):
    return page.evaluate("""() => {
        const results = [];
        const elements = document.querySelectorAll('input, textarea, select');
        elements.forEach(el => {
            if (['hidden','submit','button','checkbox'].includes(el.type)) return;
            if (el.id && el.id.startsWith('wt-cli')) return;
            if ((el.name || '').includes('recaptcha')) return;

            let label = null;
            if (el.id) {
                const labelEl = document.querySelector(`label[for="${el.id}"]`);
                if (labelEl) label = labelEl.innerText.trim();
            }
            if (!label) {
                const parent = el.closest('label');
                if (parent) label = parent.innerText.trim();
            }

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


def map_fields(fields, profile):
    personal = profile.get("personal", {})
    work = profile.get("work_history", [])
    education = profile.get("education", [])
    cpd = profile.get("cpd", [])

    results = []
    qual_index = 0
    train_index = 0
    job_index = 0

    for i, field in enumerate(fields):
        label = clean_label(field["label"])
        value = None

        # Personal
        if label == "full name":
            value = personal.get("full_name")

        # Qualifications — detect by looking ahead for "qualification name"
        elif label == "year":
            ahead = [clean_label(fields[j]["label"]) for j in range(i+1, min(i+3, len(fields)))]
            if "qualification name" in ahead:
                if qual_index < len(education):
                    value = education[qual_index].get("end")
            elif "course name" in ahead:
                if train_index < len(cpd):
                    value = cpd[train_index].get("date")

        elif label == "place of study/awarding body":
            ahead = [clean_label(fields[j]["label"]) for j in range(i+1, min(i+2, len(fields)))]
            if "qualification name" in ahead:
                if qual_index < len(education):
                    value = education[qual_index].get("institution")
            elif "course name" in ahead:
                if train_index < len(cpd):
                    value = cpd[train_index].get("provider")

        elif label == "qualification name":
            if qual_index < len(education):
                q = education[qual_index].get("qualification", "")
                s = education[qual_index].get("subject", "")
                value = f"{q} {s}".strip() or None
            qual_index += 1

        elif label == "course name":
            if train_index < len(cpd):
                value = cpd[train_index].get("title")
            train_index += 1

        # Work history
        elif label == "from":
            if job_index < len(work):
                value = work[job_index].get("start")

        elif label == "to":
            if job_index < len(work):
                value = work[job_index].get("end") or "Present"

        elif label == "school name":
            if job_index < len(work):
                value = work[job_index].get("employer")

        elif label == "job title":
            if job_index < len(work):
                value = work[job_index].get("title")

        elif label == "duties and responsibilities":
            if job_index < len(work):
                value = join_bullets(work[job_index].get("responsibilities", []))
            job_index += 1

        results.append({**field, "value": value, "status": "mapped" if value else "NEEDS USER INPUT"})

    return results


def review(mapped_fields):
    matched = [f for f in mapped_fields if f["status"] == "mapped"]
    gaps = [f for f in mapped_fields if f["status"] == "NEEDS USER INPUT"]

    print("\n" + "=" * 60)
    print("LIVE FORM FILLER — REVIEW BEFORE ANYTHING IS SUBMITTED")
    print("=" * 60)

    print(f"\n✓ {len(matched)} fields matched from your profile:\n")
    for f in matched:
        label = (f["label"] or f["id"])[:40].ljust(40)
        print(f"  {label} → {str(f['value'])[:60]}")

    print(f"\n⚠️  {len(gaps)} fields need your input:\n")
    for f in gaps:
        if f["required"]:
            prompt = f"  [REQUIRED] {f['label']}: "
        else:
            prompt = f"  [optional] {f['label']} (Enter to skip): "
        val = input(prompt).strip()
        f["value"] = val if val else None
        f["status"] = "mapped" if f["value"] else "NEEDS USER INPUT"

    print("\n" + "=" * 60)
    confirm = input("\nType YES (or y) to fill the form, anything else to cancel: ").strip().lower()
    return confirm in ("yes", "y")


def fill(page, mapped_fields):
    print("\nFilling form...\n")
    filled = 0
    skipped = 0

    for field in mapped_fields:
        fid = field["id"]
        value = field["value"]

        if not value:
            skipped += 1
            continue

        locator = page.locator(f"#{fid}")
        if locator.count() == 0:
            skipped += 1
            continue

        locator.fill(str(value))
        label = (field["label"] or fid)[:40].ljust(40)
        print(f"  [FILLED] {label} → {str(value)[:60]}")
        filled += 1

    print(f"\n{filled} fields filled, {skipped} skipped.")


def run():
    profile = load_profile()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print(f"Opening: {URL}")
        page.goto(URL, wait_until="networkidle")
        print("Page loaded. Reading fields...\n")

        fields = fetch_fields(page)
        mapped = map_fields(fields, profile)

        approved = review(mapped)

        if not approved:
            print("\nCancelled. Nothing has been submitted or changed.")
            input("Press Enter to close the browser...")
            browser.close()
            sys.exit(0)

        fill(page, mapped)
        input("\nForm filled. Review it in the browser, then press Enter to close...")
        browser.close()


if __name__ == "__main__":
    run()
