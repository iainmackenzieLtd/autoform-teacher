# Architecture Principles

## The two layers: instruction vs code

When working with AI systems there are two fundamentally different ways to shape behaviour:

**Instruction** (markdown files, prompts, conversation)
- How the user and Claude interact
- Flexible, human, conversational
- Cannot be guaranteed — an LLM may drift, especially under pace
- Right for: collaboration, exploration, learning

**Code** (agents, harness, pipeline)
- How the system enforces behaviour structurally
- Testable, reliable, predictable
- Cannot be bypassed — a Python function that requires an input will throw an error if it isn't there
- Right for: safety, governance, anything that must not fail

## How this applies to the form filler

```
User ←→ Claude         (instruction — flexible, human, unpredictable)
              ↓
        Agent code      (structure — enforced, testable, reliable)
              ↓
        LLM calls       (intelligence — reasoning, matching, flagging)
              ↓
        Harness         (governance — logging, approvals, audit trail)
```

- The **LLM** is the brain — it reasons, matches fields, flags uncertainty
- The **code** is the skeleton — it enforces the pipeline structure
- The **harness** is the rules of conduct — the skeleton enforces them

## What this means in practice

- Safety rules belong in code, not in CLAUDE.md or prompts
- The filler must structurally require an approval object from the decision agent — not just be "told" to check first
- The decision agent is not optional — it is a required step enforced by the pipeline
- Logs and audit trails are written by code, not trusted to memory

## The principle

Don't trust an agent to remember the rules. Make the rules structural so they cannot be bypassed even if the agent drifts.

This distinction — instruction vs code — is one of the most important concepts in building trustworthy AI systems.
