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

---

## Next review

Before Phase 0.2 (Droplet deployment): close or formally accept R003, R004, R006, R007.
