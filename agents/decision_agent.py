"""
Decision agent — the safety layer between mapper and filler.

Shows the user the full field mapping, asks them to confirm or fill in
gaps, and produces a signed approval object that the filler requires.

Usage: python3 agents/decision_agent.py tests/sample_form.html profile/user_profile.json
"""

import json
import sys
from datetime import datetime
from agents.mapper import map_fields


APPROVAL_PATH = "profile/approval.json"


def review_and_approve(form_path, profile_path):
    results = map_fields(form_path, profile_path)

    mapped = [r for r in results if r["status"] == "mapped"]
    gaps = [r for r in results if r["status"] == "NEEDS USER INPUT"]

    print("\n" + "=" * 60)
    print("FORM FILLER — REVIEW BEFORE ANYTHING IS SUBMITTED")
    print("=" * 60)

    print(f"\n✓ {len(mapped)} fields matched from your profile:\n")
    for r in mapped:
        label = r["label"][:40].ljust(40)
        print(f"  {label} → {r['value']}")

    print(f"\n⚠️  {len(gaps)} fields need your input:\n")
    user_values = {}
    for r in gaps:
        if r["required"]:
            prompt = f"  [REQUIRED] {r['label']}: "
        else:
            prompt = f"  [optional] {r['label']} (press Enter to skip): "
        value = input(prompt).strip()
        user_values[r["id"]] = value if value else None

    print("\n" + "=" * 60)
    print("SUMMARY — please confirm this is correct before proceeding")
    print("=" * 60)

    final = []
    for r in results:
        value = r["value"] if r["status"] == "mapped" else user_values.get(r["id"])
        final.append({**r, "value": value})
        label = r["label"][:40].ljust(40)
        display = value if value else "(blank)"
        print(f"  {label} → {display}")

    print("\n" + "=" * 60)
    confirm = input("\nType YES (or y) to approve and proceed, or anything else to cancel: ").strip().lower()

    if confirm not in ("yes", "y"):
        print("\nCancelled. Nothing has been submitted or changed.")
        sys.exit(0)

    approval = {
        "approved": True,
        "approved_at": datetime.now().isoformat(),
        "form_path": form_path,
        "fields": final
    }

    with open(APPROVAL_PATH, "w") as f:
        json.dump(approval, f, indent=2)

    print(f"\nApproval saved to {APPROVAL_PATH}")
    print("The filler agent can now proceed.\n")
    return approval


if __name__ == "__main__":
    form_path = sys.argv[1] if len(sys.argv) > 1 else "tests/sample_form.html"
    profile_path = sys.argv[2] if len(sys.argv) > 2 else "profile/user_profile.json"
    review_and_approve(form_path, profile_path)
