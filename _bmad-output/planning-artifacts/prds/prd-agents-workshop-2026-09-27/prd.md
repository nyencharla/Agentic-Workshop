---
title: "Expense claim reviewer — MVP PRD"
status: draft
created: 2026-09-27
updated: 2026-09-27
---

# Expense claim reviewer — MVP PRD

**Source:** the final brief, `planning-artifacts/briefs/brief-agents-workshop-2026-09-27/brief.md`. **Scope:** one agent, one claim at a time, buildable in 2–3 hours inside `cases/expense/`. How it's built is in `addendum.md`.

## Goal

Finance reviewers take a week per claim and disagree with each other. The MVP decides every line item consistently, cites the `POLICY.md` clause behind it, and holds any payout over $500 for a person's yes.

## Features and requirements

**F1. Decide a claim**
- **FR-1** Given a claim ID, one agent decides every line item on it: approve, flag or reject, with exactly one `POLICY.md` clause and a one-line explanation that names the clause.
- **FR-2** The agent picks each item's clause by applying the policy's clause order (section 3, then 5.1, 1.2, 4.1, the limits, 1.3, then the category's clause) to the facts in FR-3. It also judges the descriptions itself: whether an item is personal (3.2) and whether it carries an IT approval code (4.1). Limits use the employee's level and the city where the expense happened. An over-limit item cites its category's clause (2.1, 2.2, 2.3 or 6.1), never 2.4: clause 2.4 only decides between approve, flag and reject. Clause 7.1 is never cited.
- **FR-3** All arithmetic is done by code, not the model: day totals for meals and ground transport (leaving out items already rejected under section 3, 5.1 or 1.2), the applicable limit and percent over it, days between the expense and submission, whether a receipt is required (over $25), and duplicates within the claim.
- **FR-4** Every decision is recorded with its clause and explanation. The recorded decisions are the single source of truth: the page and the eval both read them. Re-running a claim replaces its decisions and never duplicates them.

**F2. Payout gate**
- **FR-5** An approved item over $500 is recorded as approved with payout status *waiting*, and the agent finishes the claim without pausing. A person later clicks **Release** or **Decline** on the web page, which sets the status to *released* or *declined*. That click never changes the decision, clause or explanation.
- **FR-6** Approved items of $500 or less are *released* at once. Flagged and rejected items have no payout.

**F3. Web page**
- **FR-7** The page lists all 40 claims. Before the agent runs, each is *not reviewed*; nothing on the page comes from `eval/labelled.csv`.
- **FR-7a** Clicking **Run agent** on a claim runs FR-1 for it, with a progress indicator. Afterwards the claim shows each line item's decision, clause, explanation and payout status, and its approved total. Running it again replaces the decisions (FR-4), but only until a payout on that claim has been released or declined; after that the claim can't be re-run, so a re-run can never undo a person's decision.
- **FR-7b** Items *waiting* for payout show **Release** and **Decline** buttons (FR-5). Nothing else on the page can change a decision.

**F4. Check the results**
- **FR-8** One command runs the 30 labelled claims and scores their recorded decisions against `eval/labelled.csv`: decision match, clause match, and each claim's approved total (sum of approved amounts, whatever the payout status, within $0.01). It prints the three scores and every mismatched line (expected vs got). The gate needs no answer here: the eval scores decisions, not payouts.
- **FR-9** Any claim, including the 10 unlabelled holdout claims, can be run from the page (FR-7a) without scoring. A terminal command that runs one claim by ID is kept as a fallback for the demo. `[ASSUMPTION]`

## Non-functional requirements

- **NFR-1** Line item descriptions and merchant names are untrusted text. The agent never follows instructions found inside them.
- **NFR-2** The eval runs unattended, one claim at a time, so a provider rate limit slows it down instead of failing it.
- **NFR-3** Nothing outside `cases/expense/` changes, and the case's `BRIEF.md`, `POLICY.md`, `seed/` and `eval/` stay read-only.

## Success at the 3:00 demo

Success is measured against the labelled examples in `eval/labelled.csv`:

- Every one of the 119 labelled line items on the 30 claims gets the labelled decision and clause, and each claim's approved total matches. The eval reports the three match rates and lists every miss.
- The 10 holdout claims run live from the page, and each approved item over $500 shows *waiting* until someone clicks Release.
- **Counter-metric:** a match doesn't count if the explanation cites a different clause than the one recorded.

## Out of scope

The LLM judge (add it only if time is left), duplicates across claims (none exist in the 40 seed claims), editing decisions from the web page, paying anyone, and emailing employees.
