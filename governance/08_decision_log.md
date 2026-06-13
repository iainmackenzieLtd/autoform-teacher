# Decision Log

Key decisions made during the AutoForm build, and why. Useful when memory gets fuzzy or when explaining choices to others.

---

## D001 — Vision API over Computer Use tool
**Date:** 2025 (early build)
**Decision:** Use Claude's vision API (base64 screenshots sent to messages endpoint) rather than the deprecated `computer_20241022` beta tool.
**Why:** Computer Use tool was deprecated. Vision API is stable, well-supported, and gives full control over the action loop.
**Trade-off:** Requires our own action execution layer (Playwright). More code, more control.

---

## D002 — Playwright over Selenium
**Date:** 2025 (early build)
**Decision:** Use Playwright for browser automation.
**Why:** Better async support, more reliable selectors, built-in screenshot API, active maintenance. Selenium is older and more brittle for modern JS-heavy forms.

---

## D003 — `select_option` via JavaScript, not native click
**Date:** 2026 (during form testing)
**Decision:** Dropdowns are handled by injecting JavaScript to set the value directly, rather than clicking to open the native OS dropdown.
**Why:** Native OS dropdowns are not visible to Playwright's click system on Linux and cannot be reliably controlled via mouse clicks. The JS approach is reliable and fast.

---

## D004 — Agentic loop capped at 20 steps
**Date:** 2026-06
**Decision:** `MAX_STEPS = 20`, reduced from 35.
**Why:** Harlington conditional form took 30 steps and cost ~$1.24. Shorter forms prove the agent in fewer steps; longer cap encourages inefficiency. 20 steps is sufficient for all current test forms.
**Review:** May need to increase for real multi-section portals (college_portal.html has 7 sections).

---

## D005 — `_agent_done` flag pattern for rerun
**Date:** 2026-06
**Decision:** Use a boolean flag `_agent_done = True` inside the try block, with `if _agent_done: st.rerun()` completely outside the try/except.
**Why:** `st.rerun()` raises `RerunException`, which is a subclass of `Exception`. Placing `st.rerun()` inside a `try/except Exception` block causes it to be silently swallowed. The flag pattern avoids this entirely.

---

## D006 — In-place placeholder updates from `_on_step` callback
**Date:** 2026-06
**Decision:** Light up the "What to do next" panel immediately when the agent signals done, before the browser closes, using Streamlit placeholder `.container()` in-place updates called from the `_on_step` callback.
**Why:** The browser stays open for user review after the agent finishes. `st.rerun()` only fires after the browser closes. Without in-place updates, the completion UI would remain dark until the user closed the browser — poor UX.

---

## D007 — Submit blocking enforced in code, not only in system prompt
**Date:** 2026-06-13
**Decision:** `_execute_actions` in `form_agent.py` checks the label of every click action against a set of submit patterns and refuses to execute matches.
**Why:** A prompt-only control is not sufficient. The agent might misinterpret instructions or a future prompt change might inadvertently remove the restriction. Code-level blocking is a hard control that survives prompt changes.
**Reference:** ChatGPT governance review, 2026-06-13.

---

## D008 — URL allowlist as phase-specific test control
**Date:** 2026-06-13
**Decision:** `TEST_MODE = True` with `ALLOWED_DOMAINS` list restricts the agent to approved synthetic URLs. This is not a permanent product restriction — it will be replaced by an explicit external-site confirmation mode in a later phase.
**Why:** Moving the app to a Droplet changes the risk profile. An allowlist prevents accidental scope creep from "local prototype" to "hosted personal-data processor" while controls are still being verified.
**Reference:** Agreed position between Claude Code and ChatGPT, 2026-06-13.

---

## D009 — GitHub Pages for synthetic test form hosting
**Date:** 2026-06-13
**Decision:** Host the 7 synthetic test forms on GitHub Pages (iainmackenzieltd.github.io/autoform-teacher/).
**Why:** Gives real `https://` URLs for testing without a server. Pure static HTML, no server-side processing, no data transmitted. Lets us test the agent on external URLs before touching real portals.

---

## D010 — DigitalOcean Droplet for production deployment (not Railway)
**Date:** 2026-06-13
**Decision:** Use the existing DigitalOcean Droplet (already running Docker for Hermes) rather than a new Railway or Render account.
**Why:** Iain already pays for the Droplet. Docker is already proven there. No additional cost or new service to manage.

---

## D011 — Two-phase browser pattern for headless fill + visible review
**Date:** 2026-06-13
**Decision:** Phase 1: headless Playwright fills the form while screenshots stream into Streamlit. Before closing, JavaScript harvests all field values into a dict. Phase 2: a visible browser opens the same URL, and JS injects the harvested values back in, firing input/change/blur events. The user reviews the restored form and submits manually.
**Why:** Headless mode gives a clean streaming UI without an OS window cluttering the screen. But the filled data lives in the headless browser's DOM — closing it loses everything. Harvesting values then restoring them in a visible window solves both goals: clean UI during fill, submittable form at the end.
**Trade-off:** Values are injected via JavaScript, not typed by the agent. This works for most forms but may not trigger all JS framework reactivity (e.g. React controlled components). Tested and confirmed working on all 7 synthetic test forms.

---

*Add new entries here as significant decisions are made.*
