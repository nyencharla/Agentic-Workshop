- source_spec: `_bmad-output/specs/spec-epic-1/stories/1-triage-decision-schema.md`
  summary: An untracked `.env.swp` sits at the repo root holding a raw copy of `.env` (API keys included) and is not covered by `.gitignore` (only `.env` itself is ignored), so a broad `git add` would commit secrets.
  evidence: Confirmed present (`ls -la .env.swp`, 12288 bytes) and confirmed absent from `.gitignore` (`grep env .gitignore` shows only `.env`). Predates this story — not caused by it. Fix is outside this story: delete the file and add `*.swp` to `.gitignore`.
- source_spec: `_bmad-output/specs/spec-epic-1/stories/1-triage-decision-schema.md`
  summary: `testAgent.py` is an unrelated scratch script at the repo root that makes a live Gemini network call on import and uses config surface AGENTS.md doesn't sanction (`google.genai` directly, `GEMINI_MODEL`, `gemini-2.5-flash`).
  evidence: File predates this story (present in git status before this branch started) and is untouched by it. Violates Epic 1's "no network calls" constraint and AGENTS.md's Models section if ever run or copied from. Fix is outside this story: remove it or move it to whichever story actually needs it.

## Deferred from: code review of 1-triage-decision-schema.md (2026-09-26)

- `SPEC.md` (Epic 1) still lists as Open Questions the category/route pairing, extra-field rejection and one-sentence enforcement, all of which story 1 settled in code and tests. Must be reconciled through `/bmad-spec`, not by hand.
- source_spec: `_bmad-output/specs/spec-epic-3/stories/1-the-eval-run-and-the-four-code-scorers.md`
  summary: Epic 3 CAP-8 — auto-approve every escalation during the eval and report the escalation count — was left out of Epic 3 story 1.
  evidence: Epic 2 story 2 (`escalate_to_human` and its human-in-the-loop gate) isn't built, so the agent never escalates and there is no gate to approve. Once it lands, `eval/run_eval.py` will block on the first escalating ticket (e.g. T-1044) until CAP-8 is added.
