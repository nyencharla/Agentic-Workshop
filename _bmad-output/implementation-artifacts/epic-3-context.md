# Epic 3 Context: Measure the Agent

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 2 produces a triage agent that decides; Epic 3 measures how well it decides and what it costs. It adds an MLflow eval that runs the agent over the 20 hand-labelled tickets, scores every run with four code scorers plus one independent LLM judge, and reports the scorer means, the agent's token spend and how often it needed a human. Attendees leave with a measured baseline, not just a working agent.

Note: this project is spec-first and has no planning-artifacts directory (no PRD, architecture or UX docs). This context comes from the epic's own spec (`_bmad-output/specs/spec-epic-3/SPEC.md` and `stories.yaml`), its companions (`INTENT.md`, the Epic 2 spec, `eval/labelled_tickets.csv`, `mcp/triage_server.py`) and the current state of the branch.

## Stories

- Story 3.1: The eval run and the four code scorers
- Story 3.2: The rationale judge and the report

## Requirements & Constraints

- `uv run python eval/run_eval.py` evaluates the agent over all 20 rows of `eval/labelled_tickets.csv` (columns: `ticket_id`, `expected_category`, `expected_priority`, `expected_tools`, `judge_notes`) in one pass. It logs exactly one MLflow run to `sqlite:///mlflow.db` under the `triage-agent` experiment.
- Five scorers, each applied to all 20 tickets:
  - `valid_schema`: 1 if the output validates against the Epic 1 triage-decision schema, else 0.
  - `category_match`: 1 if the category equals `expected_category`, else 0.
  - `priority_match`: 1 if the priority equals `expected_priority`, else 0.
  - `tool_order`: 1 if the ticket's trace shows a `get_ticket` span starting before the `get_customer_history` span, else 0.
  - `rationale_judge`: `pass`/`fail` plus a one-line reason, judged against the ticket's `judge_notes`. Its reported mean is the pass rate (pass = 1, fail = 0).
- After the run, the script prints the mean of each of the five scorers, the agent's total tokens (read from the MLflow traces) and the number of auto-approved escalations. It writes the same numbers to `eval/latest_report.json`.
- The run completes with no person present. Every escalation raised during the eval (e.g. T-1044, T-1048, T-1057) is approved automatically and nothing blocks on terminal input. Auto-approval applies only inside the eval: a normal `run_agent.py` run still pauses for a human yes/no.
- Read-only: `eval/labelled_tickets.csv`, `TRIAGE_POLICY.md` and the Epic 2 agent's behaviour. The eval calls the agent as-is and never changes its decision logic, prompts, policy handling or escalation logic.
- `eval/latest_report.json` is the only new file this epic writes outside MLflow's own store.
- Non-goals: dashboards, CI, hosting, and tuning the agent to raise its score.

## Technical Decisions

- Build the harness with `mlflow.genai.evaluate`, not a hand-rolled scoring loop.
- Wrap each ticket's prediction in a single MLflow trace (e.g. `mlflow.trace` on the predict function). When an approved escalation resumes the agent in a second call, that call must land in the same trace. Otherwise it autologs as a separate trace and `tool_order` cannot see it.
- `rationale_judge` always uses `ChatGroq` with the model from `JUDGE_MODEL` (default `openai/gpt-oss-120b`) and the key from `GROQ_API_KEY`, whatever the agent's `PROVIDER` is set to. It never reads `GEMINI_API_KEY`, so it never uses up the agent's Gemini quota.
- Only the agent's model calls and the judge's Groq calls go over the network. `valid_schema`, `category_match`, `priority_match` and `tool_order` run locally on schema, label and trace data.
- MLflow uses `sqlite:///mlflow.db` only. No LangSmith, no Databricks.

## Cross-Story Dependencies

- Current state of the branch:
  - Built: Epic 1's triage-decision schema (`triage/schema.py`) and Epic 2 story 1's agent (`agent.py`, exposing `async def triage(ticket_id) -> dict`). The eval calls this agent directly.
  - Not built yet: Epic 2 story 2 (the `escalate_to_human` tool and the human-in-the-loop approval gate). CAP-8's auto-approval has no gate to intercept until that story lands.
  - Not built yet: Epic 1's `load_seed.py`. `app.db` must be loaded before the MCP tools (`get_ticket`, `get_customer_history`) can serve data, so no real eval run can succeed until the loader exists.
- Story 3.2 builds on Story 3.1. The judge is a fifth scorer inside the same `mlflow.genai.evaluate` run, and the report aggregates scores and trace token counts from that run. The escalation count comes from Story 3.1's auto-approval.
