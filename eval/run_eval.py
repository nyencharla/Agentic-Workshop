"""Run the triage agent over the labelled tickets and score it (Epic 3, story 1).

Drives `agent.triage` over every row of `eval/labelled_tickets.csv` through
`mlflow.genai.evaluate`, logging one run to the `triage-agent` experiment at
`sqlite:///mlflow.db`, scored by four local code scorers.

Usage: uv run python eval/run_eval.py
"""

import csv
import importlib
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import mlflow  # noqa: E402
from mlflow.genai.scorers import scorer  # noqa: E402

from triage.schema import TriageValidationError, validate_decision  # noqa: E402

LABELLED_TICKETS = _REPO_ROOT / "eval" / "labelled_tickets.csv"
TRACKING_URI = "sqlite:///mlflow.db"
EXPERIMENT = "triage-agent"
APP_DB = _REPO_ROOT / "app.db"

# The `agent` module, imported once by `main` (tests set it directly).
_agent = None


def load_data(path: Path = LABELLED_TICKETS) -> list[dict]:
    """Turn each labelled row into an `inputs` / `expectations` record for `evaluate`."""
    with path.open(newline="") as handle:
        return [
            {
                "inputs": {"ticket_id": row["ticket_id"]},
                "expectations": {
                    "expected_category": row["expected_category"],
                    "expected_priority": row["expected_priority"],
                    "expected_tools": [t.strip() for t in row["expected_tools"].split(",") if t.strip()],
                },
            }
            for row in csv.DictReader(handle)
        ]


@mlflow.trace(name="triage", span_type="AGENT")
async def predict(ticket_id: str) -> dict:
    """Triage one ticket inside a single trace so its tool spans nest under it."""
    return await _agent.triage(ticket_id)


# --- Scorers: local, no network. A failed prediction (outputs is None) scores 0 on all four.


@scorer
def valid_schema(outputs) -> bool:
    if outputs is None:
        return False
    try:
        validate_decision(outputs)
    except TriageValidationError:
        return False
    return True


@scorer
def category_match(outputs, expectations) -> bool:
    if not isinstance(outputs, dict):
        return False
    return outputs.get("category") == expectations.get("expected_category")


@scorer
def priority_match(outputs, expectations) -> bool:
    if not isinstance(outputs, dict):
        return False
    return outputs.get("priority") == expectations.get("expected_priority")


def _first_start(trace, name: str) -> int | None:
    starts = [span.start_time_ns for span in trace.search_spans(name=name)]
    return min(starts) if starts else None


@scorer
def tool_order(outputs, trace) -> bool:
    """1 when a `get_ticket` span starts before the first `get_customer_history` span."""
    if outputs is None or trace is None:
        return False
    ticket_start = _first_start(trace, "get_ticket")
    history_start = _first_start(trace, "get_customer_history")
    if ticket_start is None or history_start is None:
        return False
    return ticket_start < history_start


SCORERS = [valid_schema, category_match, priority_match, tool_order]


def main() -> None:
    global _agent
    from dotenv import load_dotenv

    if not APP_DB.exists():
        raise SystemExit(f"{APP_DB} not found. Load the data first: uv run python load_seed.py")
    try:
        _agent = importlib.import_module("agent")
    except ImportError as error:
        raise SystemExit(
            f"Could not import the agent ({error}). That's Epic 2: _bmad-output/specs/spec-epic-2/SPEC.md"
        )

    load_dotenv(_REPO_ROOT / ".env")
    # Relative sqlite URI and the MCP server both resolve against the repo root.
    os.chdir(_REPO_ROOT)
    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "1"
    os.environ["MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION"] = "true"

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)
    mlflow.langchain.autolog()

    result = mlflow.genai.evaluate(data=load_data(), scorers=SCORERS, predict_fn=predict)

    print(f"Run ID: {result.run_id}")
    for name in (s.name for s in SCORERS):
        value = result.metrics.get(f"{name}/mean")
        print(f"{name}/mean: {value if value is not None else 'n/a'}")


if __name__ == "__main__":
    main()
