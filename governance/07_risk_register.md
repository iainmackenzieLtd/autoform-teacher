# Risk Register

**Version:** 0.1
**Last reviewed:** 2026-06-13

Severity: High / Medium / Low
Likelihood: High / Medium / Low
Status: Open / Mitigated / Accepted / Closed

---

| ID | Risk | Severity | Likelihood | Mitigation | Status |
|---|---|---|---|---|---|
| R001 | Agent clicks Submit on a real application without user review | High | Low | Submit blocking enforced in `_execute_actions` code; test-mode URL allowlist prevents real portal access | Mitigated |
| R002 | Agent invents factual applicant data (NI, DOB, referee contacts, safeguarding declarations) | High | Medium | System prompt prohibits invention; missing fields left blank and reported in run report | Open — prompt-only control; code enforcement pending |
| R003 | Personal data (NI, DOB, address) appears in application logs | High | Low | Logs record only step metadata; no profile JSON or API payloads logged by design | Open — not formally tested; verify before droplet deploy |
| R004 | Screenshots containing personal data are stored locally | High | Low | Screenshots held in memory only; not written to disk after run ends | Open — not formally audited; verify before droplet deploy |
| R005 | Anthropic API key is exposed in git history or logs | High | Low | `.env` gitignored; key never committed; verified clean in git history 2026-06-13 | Mitigated — rotate key if any doubt arises |
| R006 | User misunderstands what data is sent to Anthropic | Medium | Medium | Anthropic data handling disclosure drafted in `policy.md`; not yet shown in app UI | Open — disclosure not yet in app |
| R007 | App deployed to Droplet before synthetic-only controls are verified | High | Low | URL allowlist active; TEST_MODE=True; deployment checklist required before any server deploy | Open — awaiting headless mode build |
| R008 | App used on real job portal before external-site mode is implemented | High | Low | TEST_MODE blocks non-allowlisted URLs with clear error message | Mitigated for current build |
| R009 | Agent fails to navigate multi-page or dynamic forms correctly | Medium | Medium | Tested on 7 synthetic form types; real portals not yet tested | Open — by design; accepted for current phase |
| R010 | User submits a real application with agent-filled errors | Medium | Medium | UI explicitly instructs user to review every field; agent never submits | Accepted — responsibility disclosure required in UI |
| R011 | Once hosted, the Droplet processes real personal data without UK GDPR review | High | Low | Synthetic profiles only in test phase; DPIA required before Phase 0.3 | Open — future phase obligation |
| R012 | User loads another person's details into their profile and uses the app to fill applications on their behalf (identity fraud / impersonation) | High | Low | No technical control currently — profile is trusted as the user's own data. Requires: terms of service requiring users confirm the data is their own; future: account-level profile binding | Open — governance response required before public launch |

| R013 | Full CV extraction sends complete sensitive applicant document to Anthropic API — including NI, DOB, DBS, TRN, referee details, and potentially health/disability/gap information | High | Medium | Add pre-upload disclosure (see app.py profile tab); synthetic CVs only in test mode; Anthropic API data not used for training by default and deleted within 30 days by default (subject to exceptions — see Anthropic Privacy Center); DPIA required before real-user deployment | Open |
| R014 | On hosted deployment (Droplet), user_profile.json would be stored on server disk, not just local machine — changes the risk profile materially | High | Medium | Synthetic profiles only during droplet testing; no real CVs or applicant data on server; review file permissions and logging before Phase 0.2; consider per-session-only storage model | Open |
| R015 | Teacher job applications may involve special category data (health, disability, criminal records, DBS, vetting declarations) under UK GDPR Articles 9 and 10 — higher bar than ordinary personal data | High | Low | No real sensitive/special category data in current phase; mock profiles only; legal/privacy review and DPIA required before processing real applicant data; do not extend form-filling to vetting forms without separate review | Open |

---

## Next review

Before Phase 0.2 (Droplet deployment): close or formally accept R003, R004, R006, R007, R013, R014.

Before any real-user deployment: R011, R012, R015, and a full DPIA.

## Submit-blocking — code-level confirmation

The submit action is blocked in `agents/form_agent.py` in `_execute_actions()`. The check occurs at action execution time (not prompt level only) — any action whose type resolves to a submit/send/apply button is skipped and logged. This should be formally regression-tested against button labels: Submit, Send, Apply, Finish Application, Complete, Finalise, Confirm before Phase 0.2.
