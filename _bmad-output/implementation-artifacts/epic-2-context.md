# Epic 2 Context: The Triage Agent

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 2 turns the schema and loader built in Epic 1 into a working decision-maker: a LangChain agent that looks up a ticket and its customer through MCP tools, applies `TRIAGE_POLICY.md` to decide a category, priority and route, and pauses for a human before the riskiest action (escalation). This is the vision the workshop builds live, and it must work end to end — real tool calls, policy-driven reasoning, schema-valid structured output, visible as an MLflow trace — before Epic 3's eval has anything to measure.

Note: this project is spec-first with no separate PRD/architecture/UX planning-artifacts directory. This context is compiled entirely from the epic's own spec (`_bmad-output/specs/spec-epic-2/SPEC.md` and `stories.yaml`) plus the two files it names as its canonical contract (`TRIAGE_POLICY.md`, `mcp/triage_server.py`). No separate planning docs exist to pull UX or cross-system architecture detail from.

## Stories

- Story 2.1: The triage agent — provider switch, MCP-grounded lookups, policy-driven structured output with retry-once-then-error, and ignoring instructions embedded in ticket text.
- Story 2.2: Human-gated escalation — the `escalate_to_human` tool and LangChain human-in-the-loop approval gate.

## Requirements & Constraints

- Running the agent on one ticket must print a triage decision in the Epic 1 schema (category, priority, route, rationale).
- The model provider must switch between Gemini (default) and Groq by environment variable alone (`PROVIDER=groq`), with no code change; model name and API key are also read from environment variables, with documented defaults.
- The agent must call the ticket lookup before the customer lookup, and must pass the customer ID the ticket lookup returned — not one it infers or invents.
- The agent decides using `TRIAGE_POLICY.md` as its instructions; the policy's Enterprise-bump rule (raise priority one level when the customer is Enterprise with 3+ open tickets) must be applied correctly.
- The returned decision must validate against the Epic 1 schema. On a validation failure the agent retries structured output generation once; a second failure stops the run with a clear error rather than returning invalid output.
- When the policy's escalation rule fires (final priority P1 and an Enterprise customer), the agent must call `escalate_to_human` and pause for an explicit human yes/no at the terminal — answering "yes" completes the run as escalated, "no" completes it without escalating, and nothing escalates without an explicit "yes".
- Ticket text is untrusted customer input. The agent must never follow instructions embedded inside it (e.g. a ticket asking to be marked P1), per the policy's Safety section — it must triage on the ticket's actual content only.
- Out of scope for this epic: the eval harness and LLM judge, any UI beyond the terminal, and hosting/deployment.

## Technical Decisions

- Build the agent with LangChain's `create_agent` — not a hand-rolled tool loop.
- Tool grounding comes only from the two MCP tools in `mcp/triage_server.py` (`get_ticket`, `get_customer_history`), served over stdio via `langchain-mcp-adapters`; no other tool server is introduced.
- `mcp/triage_server.py` reads `app.db` directly via sqlite3; it raises if the ticket or customer isn't found, and `get_customer_history` needs the `customer_id` `get_ticket` returned.
- The Epic 1 triage-decision schema and its loader, `mcp/triage_server.py`, `TRIAGE_POLICY.md`, and everything under `seed/` are read-only for this epic — build around them, don't modify them.
- `escalate_to_human` cannot be added to `mcp/triage_server.py` since that file is read-only; it is instead a separate, locally-exposed tool, gated end-to-end by LangChain's human-in-the-loop middleware so a pause is guaranteed rather than left to the agent's own judgment.
- `run_agent.py` already exists as a stub (imports `triage` from an `agent` module, invokes it via `asyncio.run`, prints the decision as indented JSON) — this is the integration point for the new agent code. Its MLflow setup lines (tracking URI `sqlite:///mlflow.db`, experiment `triage-agent`, `mlflow.langchain.autolog()`) are protected and must stay in place so every run produces a trace.

## UX & Interaction Patterns

- The only interaction surface is the terminal. When escalation fires, the run pauses and presents a yes/no prompt at the terminal via LangChain's human-in-the-loop middleware; the run does not proceed past that point until the person answers.

## Cross-Story Dependencies

- Story 2.2 (human-gated escalation) builds directly on Story 2.1's agent: the escalation gate only has something to intercept once the agent can already reach a policy-driven P1 decision through tool calls and structured output.
- Both stories depend on Epic 1's triage-decision schema and loader (read-only inputs) and on `app.db` being loaded via `load_seed.py` before the MCP tools have data to serve.
- Epic 3's eval harness depends on this epic's agent and traces existing first; nothing in Epic 2 should anticipate or build eval-specific behavior.
