---
title: 'Seed loader'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing puts the seed data into `app.db`, so `mcp/triage_server.py` has nothing to serve and neither the agent nor the eval can run.

**Approach:** Add `load_seed.py`: `uv run python load_seed.py` builds `app.db` at the repo root with tables `tickets` and `customers` whose columns match the headers of `seed/tickets.csv` and `seed/customers.csv` (24 tickets, 20 customers). `open_tickets` loads as an integer, everything else as text. Running it again leaves identical contents with no duplicate rows. `seed/` is only read; no network, no API keys.

</frozen-after-approval>

## Implementation Notes

- New files: `load_seed.py` (`load(db_path, seed_dir)` + CLI), `tests/test_load_seed.py` (3 cases: counts and column names match the CSV headers, `open_tickets` is an integer and T-1042 → C-77 / Enterprise / 2, a second run leaves identical contents).
- Idempotency: each table is dropped and recreated inside one explicit `BEGIN`…`COMMIT` transaction (both CSVs are read before the database is touched), so a rerun replaces rather than appends. `ticket_id` and `customer_id` are primary keys, so duplicate rows can't exist even within one load.
- Column names come from each CSV's header, so they match `mcp/triage_server.py`'s queries; types are declared (`open_tickets INTEGER`, rest `TEXT`) and SQLite's type affinity converts the CSV text.
- `uv run pytest` — 30 passed after the review fix. `uv run python load_seed.py` run twice: 24 tickets, 20 customers both times. `mcp/triage_server.py`'s `get_ticket("T-1042")` returns `C-77`, and `get_customer_history("C-77")` returns Northwind, Enterprise, `open_tickets` 2 — Epic 1's success signal.

## Review Triage Log

- **medium (patched):** the reload wasn't one transaction. Python's `sqlite3` only opens implicit transactions before DML, so the first table's `DROP`/`CREATE` autocommitted; a rerun failing mid-way left `tickets` empty while `customers` kept 20 rows (reproduced). Fixed with an explicit `BEGIN`…`COMMIT` (rollback on any error, connection closed in `finally`) and by reading both CSVs before touching the database; locked in with `test_failed_rerun_leaves_previous_contents_intact`.
- **low (rejected):** CSV headers aren't checked against the schema, and header names go into SQL unquoted. `seed/` is read-only, so drift is not something anyone meets in normal use, and the fix adds a guard.
- **low (rejected):** a non-numeric `open_tickets` would be stored as text. Same reasoning: read-only seed, and the fix adds validation.
- **low (rejected):** malformed CSV rows (empty file, short/long rows) aren't reported. Read-only seed; fix adds guards.
- **false:** no `encoding=` on `open()`. Both seed files are plain ASCII (checked), so decoding is identical under every locale.
- **false:** the integer test checks only one row. It asserts `open_tickets` comes back as the Python int `2`, which SQLite only returns for an INTEGER-typed value; the column is declared `INTEGER` for all rows.
- **low (rejected):** no test for the CLI entry point or the MCP lookup. Not a defect; both were checked by hand (see Implementation Notes).
- **false:** tests hardcode 24/20 and use the real seed. That is the spec's own success criterion, and the seed is read-only.
