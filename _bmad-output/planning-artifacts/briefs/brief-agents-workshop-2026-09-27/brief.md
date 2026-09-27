---
title: "Expense claim reviewer"
status: final
created: 2026-09-27
updated: 2026-09-27
---

# Expense claim reviewer (MVP)

## Problem

Finance reviewers check every expense claim by hand. A claim takes a week to review, and two reviewers often reach different answers on the same claim.

## What the MVP does

For one claim at a time, an agent decides every line item as **approve**, **flag** or **reject**, cites the `POLICY.md` clause behind it, and records the decision. An approved item over $500 waits for a person's yes before its payout is released.

**Constraints:** built from scratch in `cases/expense/` in 2–3 hours, reusing no code from Saturday's triage build.

## Success at the 3:00 demo

- Running the agent on any claim decides and records every line item, and pauses once for each approved item over $500.
- The Streamlit page lists the claims already run, with every line item's decision and payout status.
- The eval over the 30 labelled claims runs unattended and prints the three scores.
- The 10 holdout claims run through that same command during the demo.

## How it works

| Layer | Simplest option |
|---|---|
| Data | A loader that puts the four seed CSVs into the case's own SQLite file, plus a `decisions` table. |
| Tools | A FastMCP stdio server with the case's four tools. Code does all the arithmetic: meal and ground-transport day totals, the limit for the employee's level and the city where the expense happened, how far over the limit an item is, the days between the expense and the claim's submission, whether a receipt is needed, and duplicates within the claim. |
| Agent | LangChain `create_agent` on Groq, with `POLICY.md` as its instructions. It applies the clause order in `POLICY.md` to the facts the tools return, picks the clause, and writes a one-line explanation. |
| Output | A Pydantic model per line item: decision, clause, explanation. |
| Recording | `record_decision` writes each decision to `decisions`. |
| Gate | Human-in-the-loop yes/no in the terminal for approved items over $500. The answer is saved as a payout status: waiting, then released (yes) or declined (no). |
| View | A read-only Streamlit page over the database: each claim, its line items, decision, clause and payout status. |
| Eval | An MLflow script over `eval/labelled.csv`, with three code checks: decision, clause, and each claim's approved total. The script answers the gate with "yes" every time, so it never waits. |

## Out of scope for the MVP

- **The LLM judge** on explanation clarity. The organisers score this at the demo; add it only if time is left.
- **Duplicates across claims:** an accepted risk, handled later. One in the holdout set would be missed.
- **Anything beyond the terminal, the read-only Streamlit page and the MLflow UI:** no approving or editing decisions from the page.
- **Payouts and employee emails:** the case brief excludes both.

## Risks

- **The model can still pick the wrong clause** when several apply, even with the maths done in code. The clause order in `POLICY.md` is the guard.
- **Groq's free tier limits requests per minute.** An eval over 30 claims may hit it; runs go one claim at a time.
