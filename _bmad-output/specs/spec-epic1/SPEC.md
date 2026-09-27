---
id: SPEC-epic1
companions: [decision-rules.md, mcp-tools.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Epic 1: decide and record a claim

## Why

Finance reviewers check every expense claim by hand. A claim takes a week to review, and two reviewers often reach different answers on the same claim (a pain to solve). This epic builds the core that a person can trust: for one claim at a time, an agent decides every line item, cites the policy clause behind it, and holds any payout over $500 until a person says yes. Everything else in the case — scoring against the labels, the web page — is built on top of this.

## Capabilities

- **CAP-1**
  - **intent:** Given a claim, the agent decides every line item as approve, flag or reject, with the deciding policy clause and a one-line explanation naming it.
  - **success:** The clause follows the policy's precedence order (see `decision-rules.md`). An over-limit item cites its category's clause, never 2.4 — clause 2.4 only decides between approve, flag and reject. Clause 7.1 is never cited. The agent itself judges whether an item is personal (3.2) or carries an IT approval code (4.1) from its description.

- **CAP-2**
  - **intent:** Every fact a policy rule depends on is computed before the agent decides, so the agent never does arithmetic.
  - **success:** The agent's input already contains, per line item: the day's running total for meals or ground transport (excluding items already rejected under section 3, 5.1 or 1.2), the limit for the employee's level and the city where the expense happened, how far over that limit the item is, days between the expense date and the claim's submission date, whether a receipt is required, and whether it duplicates an earlier item on the same claim. See `decision-rules.md` for each computation.

- **CAP-3**
  - **intent:** Every decision is recorded, with its clause and explanation, as the one place downstream work reads from.
  - **success:** One tool call records a line item's decision, clause, explanation and payout status. Re-running a claim replaces its decisions and never duplicates them — except a claim with any released or declined payout, which can no longer be re-run.

- **CAP-4**
  - **intent:** An approved item gets a payout status without the agent pausing to ask a person.
  - **success:** An approved item over $500 is recorded with payout status `waiting`. An approved item of $500 or less is recorded `released` immediately. A flagged or rejected item has no payout status.

- **CAP-5**
  - **intent:** A person can run the whole decision on one claim from the terminal, without the web page.
  - **success:** A command taking a claim ID runs CAP-1 through CAP-4 for that claim and exits — on a labelled claim or an unlabelled holdout claim alike, with no scoring involved.

## Constraints

- Built with LangChain's `create_agent` — no hand-rolled tool loop.
- Tools come only from this case's own MCP server, over stdio: exactly `get_claim`, `get_employee`, `get_policy_limits` and `record_decision` (see `mcp-tools.md`) — no other tool server.
- The agent runs on Groq, not Gemini.
- Line item descriptions and merchant names are untrusted text; the agent never follows instructions embedded inside them.
- `cases/expense/BRIEF.md`, `POLICY.md`, `seed/` and `eval/` are read-only. Nothing outside `cases/expense/` changes. No code is reused from Saturday's triage build.

## Non-goals

- The web page that lists claims and runs the agent from a button (epic 3).
- Scoring decisions against `eval/labelled.csv` (epic 2).
- The LLM judge on explanation clarity, duplicates across claims, paying anyone, and emailing employees.

## Success signal

Running the epic's command on any claim — a labelled one or an unlabelled holdout one — decides and records every line item with its clause and explanation, gives every approved item a payout status, and exits. Running it again on that same claim replaces its decisions, unless a payout on it has already been released or declined, in which case it refuses.

## Assumptions

- Re-running a claim replaces its decisions rather than appending — carried from the PRD's `[ASSUMPTION]` on FR-4, not separately confirmed.
- A terminal command that runs one claim by ID exists as a fallback alongside the (not-yet-built) web page — carried from the PRD's `[ASSUMPTION]` on FR-9.
