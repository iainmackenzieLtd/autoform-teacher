# UI Ideas

## Profile onboarding — transparency and trust

When a user first sets up their profile, show them exactly what is about to be stored before saving it:

> "Here is what I will be storing safely... anything to add or change?"

This mirrors the process of building the profile from a CV in conversation — visible, confirmable, reassuring.

### Monthly check-in
Send the user a prompt (email or in-app) once a month asking if their profile needs updating — new job, new qualification, change of address etc.

### Why this matters
Users are handing over sensitive personal data. Showing them what is stored, and checking in regularly, builds trust and keeps the profile accurate. Good data governance by design, not as an afterthought.

---

## Decision agent — checking before submitting

Before anything is submitted, a decision agent should sit between the mapper and the filler:

- Show the user what the mapper has matched: "I'm about to fill these fields with this data — is that right?"
- Flag anything uncertain: "I wasn't sure what to put for Key Skill 1 — can you confirm?"
- Require explicit user approval before the filler runs

This is the safety layer. Nothing gets submitted without the user seeing and confirming the full mapping first.

### Field explanations — don't just show the field name

When asking the user to fill in a gap, the decision agent should explain what the form is actually asking for — not just relay the raw field label.

Bad: `Profile *:`
Good: `The form is asking for a short professional summary — who you are, your experience, and what you're looking for. A paragraph is fine.`

This requires a Claude API call to interpret the field in context. It's the difference between a confusing prompt and a helpful one. Essential for non-technical users.

---

## Architecture principle: code over instructions for safety

**Key insight:** There is a fundamental difference between a rule written in a markdown file (or a prompt) and a rule enforced in code.

- **Instructions** (CLAUDE.md, prompts) — shape behaviour but cannot guarantee it. An LLM may drift, especially under pace. Unpredictable by nature.
- **Code** — structural. If the filler requires a confirmed approval object from the decision agent as a literal input, it cannot run without it. No drift possible.

**How to apply this to the form filler:**
- The decision agent must not be optional — make it a required step in the pipeline, enforced in code
- The filler receives a signed/structured approval object, not just a verbal "yes"
- Log every approval with a timestamp — not just "it was checked" but a record of exactly what was confirmed
- Write tests that verify the filler cannot bypass the decision agent

**The principle:** Don't trust an agent to remember the rules. Make the rules structural so they cannot be bypassed even if the agent drifts.

This distinction — instruction vs code — is one of the most important concepts in building trustworthy AI systems.
