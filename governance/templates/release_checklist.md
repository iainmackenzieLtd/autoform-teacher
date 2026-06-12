# Release / Deployment Checklist

Complete this before moving to any new deployment phase. Do not skip items.

---

## Security

- [ ] Verify `.env` was never committed: `git log --all -- .env`
- [ ] Verify no hardcoded API keys: `grep -rn "sk-ant\|ANTHROPIC_API_KEY" --include="*.py" .`
- [ ] Verify sensitive profile files are gitignored: `git status`
- [ ] Rotate API key if there is any doubt it was exposed
- [ ] Confirm server environment variables are set correctly (not in code)

## Governance controls

- [ ] `TEST_MODE` setting reviewed — is it correct for this phase?
- [ ] `ALLOWED_DOMAINS` list reviewed — does it match this phase's scope?
- [ ] Submit blocking tested: attempt a submit-labelled click and confirm `⛔ BLOCKED` appears in the run log
- [ ] Run report verified: confirm fields_filled and fields_skipped appear after a test run
- [ ] Confirm no profile data appears in logs after a test run

## Data handling

- [ ] Confirm screenshots are not written to disk during or after a run
- [ ] Confirm no API request/response bodies are logged
- [ ] If real user data is involved: confirm DPIA has been conducted

## Profile data

- [ ] Confirm only synthetic (mock) profiles are loaded in test phase deployments
- [ ] Confirm real profile files (`user_profile.json`, CV) are gitignored and not on the server

## Risk register

- [ ] Review `07_risk_register.md` — close or formally accept any risks relevant to this phase
- [ ] Add any new risks identified during this deployment

## Decision log

- [ ] Add a decision log entry (`08_decision_log.md`) for any significant choices made during this deployment

## Final check

- [ ] At least one full test run completed on a synthetic form and reviewed
- [ ] Run report reviewed for correctness
- [ ] `governance/README.md` updated to reflect new current stage
