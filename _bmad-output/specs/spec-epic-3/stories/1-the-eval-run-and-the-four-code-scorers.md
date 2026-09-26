---
title: 'The eval run and the four code scorers'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: []
baseline_commit: '8ff79cc1d0e4abd7ddda8b4106c2442df9d216d8'
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
- [x] `eval/run_eval.py` -- new: load `.env`, set MLflow URI/experiment and the two env settings above, build `data` from the CSV, define an `@mlflow.trace` `async` predict function that awaits `agent.triage`, define the four `@scorer` functions, call `mlflow.genai.evaluate`, and print the run ID and the four means -- the story's deliverable.
- [x] `tests/test_eval_scorers.py` -- new: unit-test each scorer on hand-built outputs, expectations and fake traces (valid/invalid schema, match/mismatch, correct/reversed/missing spans, `None` trace) -- no live model call.

**Acceptance Criteria:**
- Given `app.db` is loaded and a working provider key, when `uv run python eval/run_eval.py` runs, then exactly one new run appears in the `triage-agent` experiment with `valid_schema/mean`, `category_match/mean`, `priority_match/mean` and `tool_order/mean` computed over 20 tickets.
- Given the run completes, when each ticket's scored trace is inspected, then it is a single trace holding that ticket's `get_ticket` and `get_customer_history` spans. (A prediction MLflow retries after a transient error, e.g. a rate limit, may leave one extra error trace in the run; it is not scored.)

## Implementation Notes

- New files: `eval/run_eval.py` (CSV → `evaluate` data, `@mlflow.trace` async `predict` awaiting `agent.triage`, four `@scorer` functions, prints run ID and the four means), `tests/test_eval_scorers.py` (17 cases on fake traces/outputs, no model calls). `run_eval.py` also `chdir`s to the repo root so `sqlite:///mlflow.db` and the MCP server path always resolve there, and passes `expected_tools` through as an unscored expectation.
- `uv run pytest` — 61 passed. Live run on Groq (run `90104aada8b54f46a0df6f0dd97a12e0`): exactly one run in `triage-agent`; `valid_schema`, `category_match`, `priority_match`, `tool_order` each 0.9 over 20 tickets — every ticket that completed matched its labels.
- T-1044 and T-1048 failed and scored 0 on all four (the matrix's failure row): the model called `escalate_to_human`, which `TRIAGE_POLICY.md` tells it to use but which doesn't exist until Epic 2 story 2, and Groq rejected the undefined tool call with a 400. Pre-existing in the agent; deferred.
- The run holds 21 traces: T-1047 hit Groq's tokens-per-minute limit, MLflow retried it successfully, and the failed attempt stayed as an extra error trace. Retries kept on (turning them off would score rate-limited tickets 0); the second acceptance criterion was reworded to what its intent required — see Spec Change Log.

- After review fixes: `uv run pytest` — 63 passed (19 in `tests/test_eval_scorers.py`, incl. a real-trace `tool_order` test and an end-to-end `evaluate` wiring test with one failing ticket, both on a `tmp_path` store). Missing `app.db` now exits at once with the loader hint. Live re-run on Groq (run `3945b9fa045944328b3683e1d5163cdf`): `valid_schema` 0.9, `category_match` 0.9, `priority_match` 0.85, `tool_order` 0.9 — one priority differed from the previous run (model variance; tuning is a non-goal).

## Spec Change Log

- 2026-09-26, found at step 3 verification: the second acceptance criterion said "one trace per ticket", but MLflow's retry after a Groq 429 leaves the failed attempt as an extra error trace. Amended to require that each ticket's *scored* trace is a single trace holding both tool spans — the property `tool_order` actually depends on. Avoids the known-bad alternative of disabling retries, which would score rate-limited tickets 0. KEEP: default MLflow retries; `@mlflow.trace` on `predict`.

## Review Triage Log

- **low (patched):** no preflight: without `app.db` every ticket still makes a paid model call (the agent calls the model before its first tool), plus MLflow's retries, then scores 0 — a fresh clone that skipped `load_seed.py` gets a misleading all-zero run. Fix: exit with a clear message if `app.db` is missing.
- **low (patched):** `from agent import triage` inside `predict` turns a missing agent into 20 failed rows instead of one clear error. Fix: import at startup with a clear `SystemExit`, as `run_agent.py` does.
- **low (patched):** `SCORER_NAMES` repeats the scorer function names; renaming a scorer silently prints `n/a`. Fix: derive names from `SCORERS`.
- **medium (patched):** `tool_order` is only tested against a hand-built `FakeTrace` keyed on the same literal names it searches for; a change in how autolog names MCP tool spans would drop `tool_order` to 0 with every test passing. Fix: a test that produces a real MLflow trace from two stub LangChain tools named `get_ticket` and `get_customer_history` under autolog, against a `tmp_path` tracking store, and scores it.
- **medium (patched):** nothing tests the `evaluate` wiring (`load_data` → `predict` → `SCORERS` → `<name>/mean` metrics) or the matrix's "agent fails on a ticket" row end to end; a renamed `predict` parameter would fail every row with all tests green. Fix: run `mlflow.genai.evaluate` with a fake `agent.triage` (one success, one raise) against a `tmp_path` store and assert all four means and the failing row's zeros.
- **low (defer):** the script never says how many tickets failed (T-1044/T-1048 were invisible behind the 0.9 means) and always exits 0. The printed report is story 2's (CAP-7); recorded in `deferred-work.md` for it.
- **false:** `valid_schema` accepts a JSON string that the match scorers reject. `predict` returns `agent.triage`'s output, which is always a dict (`TriageDecision.model_dump()`), so a string never reaches the scorers.
- **false:** equal `get_ticket`/`get_customer_history` start times. The second tool needs the first's `customer_id`, so it can't start until the first returns; nanosecond timestamps can't tie.
- **false:** `expected_tools` loaded but unused by `tool_order`. The spec defines `tool_order` as `get_ticket` before `get_customer_history`; `expected_tools` is passed through unscored by design.
- **false:** `main` overrides `MLFLOW_GENAI_EVAL_*` env vars the user may have set. Both values are required by the spec's Code Map.
- **false:** CSV encoding. `eval/labelled_tickets.csv` is plain ASCII (checked).
- **false:** a row without expectations crashes the match scorers. `load_data` builds expectations for every row.
- **low (rejected):** short CSV rows, whitespace/case in labels, the live-CSV-dependent data test. `eval/labelled_tickets.csv` is read-only and clean; the fixes add guards for input that never occurs.
- **low (rejected):** `tool_order` when the agent's internal retry re-runs tools in the same trace — the first attempt's order is used. Only reachable after a structured-output failure, and both attempts use the same tool order; not worth extra per-attempt logic.

## Verification

**Commands:**
- `uv run pytest` -- expected: all tests pass, including `tests/test_eval_scorers.py`.
- `uv run python eval/run_eval.py` -- expected: completes over 20 tickets and prints one run ID plus four scorer means.
