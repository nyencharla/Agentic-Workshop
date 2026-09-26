---
title: 'Triage decision schema'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing in the repo yet defines what a valid triage decision looks like. Epic 2's agent has to produce one and Epic 3's eval has to check one, and both need the same authoritative shape rather than each inventing their own.

**Approach:** Add an importable schema for a triage decision — category, priority, route and a one-sentence rationale, each restricted to the fixed sets in `TRIAGE_POLICY.md` — that accepts only that shape and rejects everything else (an invalid value, a missing field, an extra field, or a rationale that isn't a single sentence), naming the offending field in every rejection. No network calls, no database, no dependency on `seed/`, `mcp/triage_server.py`, or the not-yet-built loader.

</frozen-after-approval>

## Implementation Notes

- Investigation looked at `upstream/stage-2` (the workshop's own "Epic 1 built" checkpoint, fetched from `lutic1/Agentic-Workshop`) to settle three shape questions the input left open: category/route are validated independently, not as a matched pair; extra fields are rejected (`extra="forbid"`); the rationale must be a single sentence, checked by regex, not just non-empty. That checkpoint's own tests confirmed all three, so no Open Questions were needed and this ran as a oneshot.
- New files: `triage/__init__.py` (empty, makes `triage` a package), `triage/schema.py` (the `TriageDecision` pydantic model, `TriageValidationError`, and `validate_decision()` for dict-or-JSON input), `tests/conftest.py` (puts the repo root on `sys.path` so `tests/` can import `triage`), `tests/test_schema.py` (16 cases: valid decision, each field's bad value, each missing field, non-object payloads, extra field, multi-sentence and empty rationale, immutability).
- No new dependencies — `pydantic>=2.8` was already in `pyproject.toml`.
- `uv run pytest` — 16 passed.
- Review (blind-hunter) found a real bug: `_MULTIPLE_SENTENCES` rejected legitimate single-sentence rationales containing an abbreviation or an inline rule reference (e.g. "e.g. this is a refund request." or "Escalate per rule 3. it is Enterprise."), because any `.`/`!`/`?` followed by whitespace and *any* character counted as a second sentence. Fixed by requiring the following character to be uppercase — a real sentence boundary, not an abbreviation or a lowercase continuation — and added tests for both the false positives and the still-correctly-rejected true multi-sentence case.
- Review also flagged that `TRIAGE_POLICY.md`'s category→route pairing is not enforced (each field is checked only against its own allowed set) with no test showing that was deliberate. Confirmed against `upstream/stage-2` (see above) that this is intended for this story — enforcing the pairing is Epic 2/3's concern, not this schema's. Added a test that locks in and documents the current accepted behavior so a future change can't silently tighten or loosen it unnoticed.
- Review also flagged missing coverage for near-miss casing/whitespace on the enum fields (e.g. `"Billing"`, `" P2"`). Pydantic's `Literal` already rejected these correctly; added tests to prove it since this schema exists specifically to gate untrusted/LLM-produced output.
- `uv run pytest` — 22 passed after the fixes.

## Review Triage Log

- **medium (patched):** `_MULTIPLE_SENTENCES` regex rejected valid single-sentence rationales containing an abbreviation or a lowercase continuation after a period. Verified by direct call (`validate_decision` raised on "e.g. this is a refund request." and "Escalate per rule 3. it is Enterprise."). Fixed by requiring an uppercase letter after the break; covered by new tests.
- **low (patched):** category/route pairing is validated independently with no test locking in that this is deliberate. Confirmed the behavior matches `upstream/stage-2`'s reference schema; added a test documenting it.
- **low (patched):** no test proved near-miss casing/whitespace on enum fields (`"Billing"`, `" P2"`, `"Billing-Team"`) is already rejected. Verified pydantic's `Literal` already rejects all three correctly; added tests.
- **low (rejected):** no upper bound on rationale length or content beyond "single sentence." Not asked for by `INTENT.md`, `SPEC.md`, or the `upstream/stage-2` reference (which has the same lack of a bound); adding one now would invent an unrequested constraint rather than fix a defect.
- **false:** frontmatter still showed `status: 'in-progress'` while Implementation Notes described finished work. Disproved: this is the in-progress state expected mid-workflow, before this Finalize Spec step sets `status: 'done'`, which it now has.
- **deferred to `deferred-work.md`:** an untracked `.env.swp` at the repo root holds a raw copy of `.env` (including API keys) and is not covered by `.gitignore`. Confirmed present and confirmed `.gitignore` covers only `.env`. Predates this story, not caused by it — flagged directly to the user as well since it's a live secret-exposure risk, not just filed away.
- **deferred to `deferred-work.md`:** `testAgent.py`, an untracked scratch script unrelated to this story, makes a live network call and uses non-sanctioned model config. Predates this story, not caused by it.

