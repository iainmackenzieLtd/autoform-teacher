# AutoForm Governance

**Current stage:** 0.1 — Test Phase (synthetic forms only, local machine)
**Not yet:** hosted, multi-user, or running against real job portals

This folder is a living evidence trail, not a compliance museum. It documents what the system does, what risks are known, and why key decisions were made. It grows as the product grows.

## Files

| File | Purpose |
|---|---|
| `policy.md` | Combined policy reference — all tiers in one document |
| `07_risk_register.md` | Known risks, severity, mitigation, and current status |
| `08_decision_log.md` | Key decisions made during the build and why |
| `templates/release_checklist.md` | Steps to complete before any new deployment phase |

## One rule

**Governance documentation must not outrun actual controls.**

If this folder says "screenshots are not stored," the code must prove it. If the code changes, the relevant document must be updated in the same commit.
