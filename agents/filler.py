"""
Filler agent — executes form filling based on an approved mapping.

REQUIRES a valid approval.json produced by the decision agent.
Will refuse to run without it — this is enforced in code, not instruction.

Currently runs as a dry run (prints what it would fill).
TODO: replace dry run with Playwright browser calls when browser connector is added.

Usage: python3 agents/filler.py
"""

import json
import sys
import os

APPROVAL_PATH = "profile/approval.json"


def load_approval():
    if not os.path.exists(APPROVAL_PATH):
        print("\nERROR: No approval file found.")
        print("You must run the decision agent first and confirm the mapping.")
        print("  python3 -m agents.decision_agent\n")
        sys.exit(1)

    with open(APPROVAL_PATH, "r") as f:
        approval = json.load(f)

    if not approval.get("approved"):
        print("\nERROR: Approval file exists but was not approved.")
        print("Please re-run the decision agent.\n")
        sys.exit(1)

    return approval


def fill_form(approval):
    fields = approval["fields"]
    approved_at = approval["approved_at"]
    form_path = approval["form_path"]

    print("\n" + "=" * 60)
    print("FORM FILLER — DRY RUN")
    print(f"Form:     {form_path}")
    print(f"Approved: {approved_at}")
    print("=" * 60)
    print("\nThe following actions would be taken:\n")

    filled = 0
    skipped = 0

    for field in fields:
        fid = field["id"]
        label = (field["label"] or fid)[:40].ljust(40)
        value = field["value"]

        if value:
            print(f"  [FILL] {label} → {value[:60]}")
            filled += 1
        else:
            print(f"  [SKIP] {label} → (no value provided)")
            skipped += 1

    print(f"\n{filled} fields would be filled, {skipped} skipped.")
    print("\nDRY RUN COMPLETE — nothing was submitted.")
    print("TODO: connect Playwright browser to fill a real form.\n")


if __name__ == "__main__":
    approval = load_approval()
    fill_form(approval)
