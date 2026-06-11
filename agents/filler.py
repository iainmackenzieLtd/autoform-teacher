"""
Filler agent — executes form filling based on an approved mapping.

REQUIRES a valid approval.json produced by the decision agent.
Will refuse to run without it — this is enforced in code, not instruction.

Usage: python3 agents/filler.py
"""

import json
import sys
import os
from connectors.browser import fill_form as browser_fill

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


if __name__ == "__main__":
    approval = load_approval()
    print(f"\nApproval confirmed ({approval['approved_at']})")
    print(f"Opening form: {approval['form_path']}\n")
    browser_fill(approval, headless=False)
