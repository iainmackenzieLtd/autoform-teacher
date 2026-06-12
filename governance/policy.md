# AutoForm Governance Policy

**Version:** 0.1 — Test Phase
**Last updated:** 2026-06-13
**Status:** Internal — not yet user-facing

---

## What AutoForm is

AutoForm is a form-filling assistant. It uses AI vision to read a job application form and fill fields from a user-provided profile. The user reviews every field before submitting. AutoForm never submits on the user's behalf.

---

## Tier 1 — Hard Technical Controls

These are enforced in code. They cannot be overridden by the AI agent or by user configuration.

### 1. Agent never submits

Submit-type clicks are blocked at the browser-action level, not only in the system prompt. The `_execute_actions` function refuses to execute any click whose label matches a submit pattern (`submit`, `apply`, `send application`, `finish application`, etc.). This is logged as a `⛔ BLOCKED` event in the run report.

### 2. URL access is phase-controlled

In test mode, AutoForm may only access approved synthetic test URLs. External-site access is disabled by default.

**Current approved domains:**
- `localhost`
- `127.0.0.1`
- `file:///`
- `iainmackenzieltd.github.io`

If external-site access is added in a future phase, it must require:
- explicit user confirmation before each run
- a prominent warning about third-party portal terms
- preserved submit blocking
- a full run report

### 3. No local storage of screenshots or form data

Screenshots taken during a run are held in memory only and discarded when the run ends. They are not written to disk, logged, or retained locally.

### 4. API key in environment variables only

The Anthropic API key must live in `.env` only. It must never appear in source code, logs, or be committed to any git repository. The `.gitignore` enforces this. If there is any doubt the key has been exposed, rotate it immediately at console.anthropic.com.

---

## Tier 2 — Runtime Behaviour Rules

These govern what the agent is instructed to do. They are enforced via the system prompt and verified by code where possible.

### 5. No invented factual data

The agent must not invent or infer the following fields. If the data is absent from the profile, the field must be left blank and reported as "needs user input":

- National Insurance number
- Date of birth
- Address and postcode
- Employment dates
- Qualification dates and grades
- Referee names, titles, and contact details
- Right-to-work status
- Visa / work permit status
- Safeguarding declarations
- Disability or health disclosures
- Criminal record declarations

The agent may compose prose (supporting statements, personal statements) by drawing on profile facts, but must not fabricate structured data.

### 6. Missing fields reported, not smoothed over

If a required factual field cannot be filled from the profile, the agent marks it as skipped in the run report with the reason. It does not guess or leave the field silently blank.

### 7. Run report after every completion

Every completed run produces a report containing:
- Fields filled (field name and value summary)
- Fields skipped (field name and reason)
- Any submit-blocked events

The run report must not contain raw profile data, screenshots, or API payloads.

### 8. No sensitive data in logs

Application logs may record:
- Form name or URL domain
- Timestamp
- Step count
- Success / failure category
- Blocked-submit events

Logs must not contain profile JSON, NI numbers, dates of birth, addresses, screenshots, or API request/response bodies.

---

## Tier 3 — User-Facing Disclosures

These will be shown to users in the application UI. They are honest, not liability shields.

### 9. Data sent to Anthropic

Screenshots of the form and the user's profile data are sent to Anthropic's Claude API in order to fill the form. Anthropic processes this data on its servers.

### 10. Anthropic data retention

Anthropic states that commercial API data is not used to train models by default. API inputs and outputs are normally deleted from Anthropic's systems within 30 days, subject to exceptions (legal requirements, policy enforcement, or specific service agreements). Source: [Anthropic Privacy Center](https://privacy.anthropic.com).

### 11. AutoForm is an assistant, not a guarantor

AutoForm may make mistakes. The user must review every field before submitting any real application. The system is designed not to submit automatically. Any errors in a submitted application are the responsibility of the user.

### 12. Third-party portal terms

Some job portals may restrict or prohibit automated form-filling tools. AutoForm operates similarly to a browser autofill extension, but is more capable. Users are responsible for checking whether the portal they are using permits automated assistance before using AutoForm on real sites.

---

## Phase Roadmap

| Phase | URL access | Profile data | Submit blocking | Run report |
|---|---|---|---|---|
| **0.1 — Test (now)** | Allowlisted synthetic forms only | Synthetic (mock profile) | Enforced in code | Yes |
| **0.2 — Droplet test** | Allowlisted synthetic forms only | Synthetic only | Enforced in code | Yes |
| **0.3 — Real portal pilot** | External sites, explicit confirmation per run | Real profile, user consent | Enforced in code | Yes, no data in logs |
| **1.0 — Multi-user** | External sites | Per-user isolated profiles | Enforced in code | Per-user, retained N days |

---

## UK GDPR / ICO Note

Once AutoForm is hosted on a server and processes real user data, it becomes a personal data processor under UK GDPR. At that point, a Data Protection Impact Assessment (DPIA) should be conducted. The ICO's AI and data protection guidance applies. Data minimisation, purpose limitation, and security controls must be formally reviewed before Phase 0.3.

---

## Security checks before any deployment

Run these before deploying to any server:

```bash
# Verify .env was never committed
git log --all -- .env

# Verify no hardcoded secrets in Python files
grep -rn "sk-ant\|ANTHROPIC_API_KEY" --include="*.py" .

# Verify sensitive profile files are gitignored
git status
```

If any of these return unexpected results, stop and investigate before proceeding.
