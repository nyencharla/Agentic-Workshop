---
title: 'The eval run and the four code scorers'
type: 'feature'
created: '2026-09-26'
status: 'ready-for-dev'
route: 'dispatch'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing measures the Epic 2 agent. There is no way to run it over the 20 labelled tickets and see how often it gets the schema, category, priority and tool order right.

**Approach:** Add `eval/run_eval.py`, which drives the existing `agent.triage` over every row of `eval/labelled_tickets.csv` through `mlflow.genai.evaluate`, logs exactly one run to the `triage-agent` experiment at `sqlite:///mlflow.db`, and scores each ticket with four local code scorers: `valid_schema`, `category_match`, `priority_match` and `tool_order`.

## Boundaries & Constraints

**Always:**
- Use `mlflow.genai.evaluate` with `@scorer` functions — no hand-rolled scoring loop.
- Call `agent.triage` as-is; never change its decision logic, prompts or policy handling.
- Each ticket's prediction runs inside one MLflow trace, so `tool_order` can see both tool spans.
- The four scorers run locally on schema, label and trace data — no network calls of their own.
- Run tickets one at a time (they share one SQLite file and one MCP subprocess each).

**Never:**
- Edit `eval/labelled_tickets.csv`, `TRIAGE_POLICY.md`, `agent.py`'s decision logic, or anything under `seed/`.
- Build `rationale_judge`, the printed report or `eval/latest_report.json` — that is story 2.
- Add dashboards, CI, hosting, or tune the agent to raise its score.

## Decisions

- Escalation (CAP-8) is out of this story (decided 2026-09-26): Epic 2 story 2 isn't built, so the agent never escalates. Auto-approval and the escalation count are deferred until that gate exists.
- `app.db` comes from `load_seed.py` (Epic 1 story 2), built before this story on its own branch and merged in (decided 2026-09-26).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | 20 labelled rows, `app.db` loaded, provider key set | One MLflow run in `triage-agent` with per-ticket scores and `<scorer>/mean` metrics for all four scorers | N/A |
| Output valid | Agent returns a dict matching `TriageDecision` | `valid_schema` = 1 | N/A |
| Agent fails on a ticket | `triage` raises (e.g. retry-once exhausted, tool error) | That ticket scores 0 on all four; the run still completes the other tickets | Failure recorded on the row, not a crash |
| Category / priority match | Output equals / differs from `expected_category` / `expected_priority` | 1 / 0 | N/A |
| Tool order | Trace has `get_ticket` span starting before `get_customer_history` | `tool_order` = 1; reversed, missing span or no trace = 0 | N/A |

</frozen-after-approval>


## Code Map

- `agent.py` -- `async def triage(ticket_id) -> dict` returning `TriageDecision.model_dump()`. Call it as-is. It opens and closes its own MCP client per call, so a fresh event loop per ticket is safe.
- `run_agent.py` -- the MLflow setup to mirror: `load_dotenv()`, tracking URI `sqlite:///mlflow.db`, experiment `triage-agent`.
- `triage/schema.py` -- `validate_decision(payload)` raises `TriageValidationError`; `valid_schema` uses it.
- `eval/labelled_tickets.csv` -- 20 rows: `ticket_id, expected_category, expected_priority, expected_tools, judge_notes`. Read-only.
- `tests/conftest.py` -- puts the repo root on `sys.path`; `run_eval.py` needs the same so `import agent` works when run as `uv run python eval/run_eval.py`.

**MLflow 3.16.1 facts (checked against installed source):**
- `mlflow.genai.evaluate(data, scorers, predict_fn)`: `data` is a list of dicts with `inputs` (dict) and `expectations` (dict); `predict_fn(**inputs)`. One call = one run, in whatever experiment is active — set tracking URI and experiment first; don't wrap in another `start_run`.
- `predict_fn` may be `async def`; MLflow runs it with `asyncio.run` in a worker thread. Don't call `asyncio.run` yourself.
- Set `MLFLOW_GENAI_EVAL_MAX_WORKERS=1` so tickets run sequentially (default is 10 parallel).
- Decorate `predict_fn` with `@mlflow.trace` and set `MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION=true`; otherwise MLflow makes one extra, paid model call on row 1 to probe for spans.
- `from mlflow.genai.scorers import scorer`; a scorer takes any of `inputs, outputs, expectations, trace` and may return a bool (cast to 0/1). Name = function name. A raising scorer becomes a `SCORER_ERROR` result, not a crash.
- `trace.search_spans(name="get_ticket")` returns spans with `start_time_ns`; `trace` can be `None` when prediction failed. Metrics are keyed `category_match/mean` etc. on the returned result.

## Tasks & Acceptance

**Execution:**
- [ ] `eval/run_eval.py` -- new: load `.env`, set MLflow URI/experiment and the two env settings above, build `data` from the CSV, define an `@mlflow.trace` `async` predict function that awaits `agent.triage`, define the four `@scorer` functions, call `mlflow.genai.evaluate`, and print the run ID and the four means -- the story's deliverable.
- [ ] `tests/test_eval_scorers.py` -- new: unit-test each scorer on hand-built outputs, expectations and fake traces (valid/invalid schema, match/mismatch, correct/reversed/missing spans, `None` trace) -- no live model call.

**Acceptance Criteria:**
- Given `app.db` is loaded and a working provider key, when `uv run python eval/run_eval.py` runs, then exactly one new run appears in the `triage-agent` experiment with `valid_schema/mean`, `category_match/mean`, `priority_match/mean` and `tool_order/mean` computed over 20 tickets.
- Given the run completes, when its traces are listed, then there is one trace per ticket and each contains that ticket's `get_ticket` and `get_customer_history` spans.

## Implementation Notes

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest` -- expected: all tests pass, including `tests/test_eval_scorers.py`.
- `uv run python eval/run_eval.py` -- expected: completes over 20 tickets and prints one run ID plus four scorer means.
