# Addendum — how the MVP is built

Implementation choices carried from the brief; the PRD states capabilities only.

| Concern | Choice |
|---|---|
| Data | A loader puts `seed/*.csv` into the case's own SQLite file, plus a `decisions` table keyed on `line_id` (upsert), with decision, clause, explanation and payout status. |
| Tools | A FastMCP stdio server with the case's four tools. `get_claim` returns the claim's submission date and each line item with the FR-3 facts already computed. `record_decision` also takes the explanation. |
| Agent | LangChain `create_agent` on Groq, `POLICY.md` as the system prompt. The agent records each item through `record_decision`; that write is the only record. Any structured output is for tracing, never a second copy of the decisions. |
| Gate | No human-in-the-loop middleware. `record_decision` sets payout status (*waiting* for approved items over $500, *released* for the rest); the page's Release/Decline buttons update it. |
| Page | A Streamlit app (`uv add streamlit`): claims list, a Run agent button per claim that calls the agent directly (`asyncio.run`) behind a spinner, and Release/Decline buttons for waiting payouts. |
| Eval | An `mlflow.genai.evaluate` script with three code scorers, tracing to `sqlite:///mlflow.db`. |
| Commands | `uv run python cases/expense/load_data.py` (once), `uv run streamlit run cases/expense/app.py` (the page), `uv run python cases/expense/review_claim.py CL-2001` (fallback), `uv run python cases/expense/run_eval.py` (scores). `[ASSUMPTION]` |

## Build order and cut line

1. Loader and tools with the FR-3 facts.
2. Agent and recording.
3. The run command for any claim.
4. The eval.
5. The page: claims list and Run agent button first, then Release/Decline.
6. If time runs short, cut the page back to read-only and demo with the terminal command.
