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


def load_profile(path=PROFILE_PATH):
    with open(path) as f:
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


def contains_any(label, keywords):
    """Return True if the label contains any of the given keywords."""
    return any(kw in label for kw in keywords)


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
        overflow = False

        def ahead_str(n=6):
            return " ".join(
                clean_label(fields[j]["label"])
                for j in range(i + 1, min(i + n + 1, len(fields)))
            )

        # ── Personal ──────────────────────────────────────────
        if contains_any(label, ["full name", "your name", "applicant name", "candidate name"]):
            value = personal.get("full_name")

        elif label in ("first name", "forename", "given name", "christian name"):
            name = personal.get("full_name", "")
            value = name.split()[0] if name else None

        elif contains_any(label, ["surname", "last name", "family name"]):
            name = personal.get("full_name", "")
            value = name.split()[-1] if name else None

        elif contains_any(label, ["email"]):
            value = personal.get("email")

        elif contains_any(label, ["phone", "mobile", "telephone", "contact number", "tel"]):
            value = personal.get("phone_uk")

        elif contains_any(label, ["address", "postcode", "location", "town", "city"]):
            value = personal.get("location_current")

        elif contains_any(label, ["nationality", "citizen"]):
            value = personal.get("nationality")

        elif contains_any(label, ["right to work", "work in the uk", "eligible to work"]):
            value = personal.get("right_to_work")

        elif contains_any(label, ["ni number", "national insurance"]):
            value = personal.get("ni_number")

        elif contains_any(label, ["dbs", "disclosure", "barring"]):
            value = personal.get("dbs_status")

        # ── Education: place of study ─────────────────────────
        elif contains_any(label, ["place of study", "awarding body", "institution", "university", "college"]):
            a = ahead_str(3)
            if contains_any(a, ["qualification", "awarding body", "place of study"]):
                if qual_index < len(education):
                    value = education[qual_index].get("institution")
                else:
                    overflow = True
            elif contains_any(a, ["course"]):
                if train_index < len(cpd):
                    value = cpd[train_index].get("provider")
                else:
                    overflow = True

        # ── Education: qualification name ─────────────────────
        elif contains_any(label, ["qualification name", "qualification title", "degree", "certificate", "diploma"]):
            if qual_index < len(education):
                q = education[qual_index].get("qualification", "")
                s = education[qual_index].get("subject", "")
                value = f"{q} {s}".strip() or None
            else:
                overflow = True
            qual_index += 1

        # ── CPD: course name ──────────────────────────────────
        elif contains_any(label, ["course name", "course title"]):
            if train_index < len(cpd):
                value = cpd[train_index].get("title")
            else:
                overflow = True
            train_index += 1

        # ── Year fields — education or CPD context only ───────
        # Note: "from"/"to" are NOT included here — those are work history dates
        elif label in ("year", "year*") or contains_any(label, ["awarded", "completed"]):
            a = ahead_str(6)
            if contains_any(a, ["qualification", "awarding body", "place of study"]):
                if qual_index < len(education):
                    value = education[qual_index].get("end")
                else:
                    overflow = True
            elif contains_any(a, ["course name", "course title"]):
                if train_index < len(cpd):
                    value = cpd[train_index].get("date")
                else:
                    overflow = True
            else:
                overflow = True

        # ── Work history ───────────────────────────────────────
        elif label == "from" or contains_any(label, ["start date", "date from", "employed from"]):
            if job_index < len(work):
                value = work[job_index].get("start")
            else:
                overflow = True

        elif label == "to" or contains_any(label, ["end date", "date to", "employed to", "until"]):
            if job_index < len(work):
                value = work[job_index].get("end") or "Present"
            else:
                overflow = True

        elif contains_any(label, ["school name", "employer", "organisation", "company", "workplace", "name of school"]):
            if job_index < len(work):
                value = work[job_index].get("employer")
            else:
                overflow = True

        elif contains_any(label, ["job title", "position", "role", "post held"]):
            if job_index < len(work):
                value = work[job_index].get("title")
            else:
                overflow = True

        elif contains_any(label, ["duties", "responsibilities", "description of role"]):
            if job_index < len(work):
                value = join_bullets(work[job_index].get("responsibilities", []))
            else:
                overflow = True
            job_index += 1

        # ── Status ────────────────────────────────────────────
        if overflow:
            status = "OVERFLOW"
        elif value is not None:
            status = "mapped"
        else:
            status = "NEEDS USER INPUT"

        results.append({**field, "value": value, "status": status})

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
