"""Unit tests for the four eval code scorers (Epic 3, story 1). No model calls."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_RUN_EVAL = Path(__file__).resolve().parent.parent / "eval" / "run_eval.py"
_spec = importlib.util.spec_from_file_location("run_eval", _RUN_EVAL)
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

VALID = {
    "category": "billing",
    "priority": "P2",
    "route": "billing-team",
    "rationale": "Rule 2 applies because the customer was double charged.",
}
EXPECTED = {"expected_category": "billing", "expected_priority": "P2"}


class FakeTrace:
    def __init__(self, spans: dict[str, list[int]]):
        self._spans = spans

    def search_spans(self, name=None):
        return [SimpleNamespace(name=name, start_time_ns=t) for t in self._spans.get(name, [])]


# valid_schema

def test_valid_schema_accepts_valid_decision():
    assert run_eval.valid_schema(outputs=VALID) is True


@pytest.mark.parametrize(
    "outputs",
    [
        None,
        "not a dict",
        {**VALID, "category": "sales"},
        {**VALID, "extra": 1},
        {k: v for k, v in VALID.items() if k != "route"},
        {**VALID, "rationale": "One. Two."},
    ],
)
def test_valid_schema_rejects_invalid(outputs):
    assert run_eval.valid_schema(outputs=outputs) is False


# category_match / priority_match

def test_category_match():
    assert run_eval.category_match(outputs=VALID, expectations=EXPECTED) is True
    assert run_eval.category_match(outputs={**VALID, "category": "bug"}, expectations=EXPECTED) is False
    assert run_eval.category_match(outputs=None, expectations=EXPECTED) is False


def test_priority_match():
    assert run_eval.priority_match(outputs=VALID, expectations=EXPECTED) is True
    assert run_eval.priority_match(outputs={**VALID, "priority": "P1"}, expectations=EXPECTED) is False
    assert run_eval.priority_match(outputs=None, expectations=EXPECTED) is False


# tool_order

def test_tool_order_correct():
    trace = FakeTrace({"get_ticket": [100], "get_customer_history": [200]})
    assert run_eval.tool_order(outputs=VALID, trace=trace) is True


def test_tool_order_reversed():
    trace = FakeTrace({"get_ticket": [300], "get_customer_history": [200]})
    assert run_eval.tool_order(outputs=VALID, trace=trace) is False


@pytest.mark.parametrize(
    "spans",
    [{"get_ticket": [100]}, {"get_customer_history": [200]}, {}],
)
def test_tool_order_missing_span(spans):
    assert run_eval.tool_order(outputs=VALID, trace=FakeTrace(spans)) is False


def test_tool_order_no_trace():
    assert run_eval.tool_order(outputs=VALID, trace=None) is False


def test_tool_order_failed_prediction_scores_zero():
    trace = FakeTrace({"get_ticket": [100], "get_customer_history": [200]})
    assert run_eval.tool_order(outputs=None, trace=trace) is False


# data

def test_load_data_reads_all_labelled_rows():
    data = run_eval.load_data()
    assert len(data) == 20
    first = data[0]
    assert set(first) == {"inputs", "expectations"}
    assert first["inputs"] == {"ticket_id": "T-1042"}
    assert first["expectations"]["expected_category"] == "billing"
    assert first["expectations"]["expected_tools"] == ["get_ticket", "get_customer_history"]


# Real MLflow traces (no model call)

@pytest.fixture
def tracking_store(tmp_path, monkeypatch):
    import mlflow

    monkeypatch.setenv("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    monkeypatch.setenv("MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION", "true")
    previous_uri = mlflow.get_tracking_uri()
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    mlflow.set_experiment("triage-agent-test")
    mlflow.langchain.autolog()
    yield mlflow
    mlflow.langchain.autolog(disable=True)
    mlflow.set_tracking_uri(previous_uri)


def _stub_tools():
    from langchain_core.tools import tool

    @tool
    def get_ticket(ticket_id: str) -> dict:
        """Stub ticket lookup."""
        return {"ticket_id": ticket_id, "customer_id": "C-1"}

    @tool
    def get_customer_history(customer_id: str) -> dict:
        """Stub customer lookup."""
        return {"customer_id": customer_id, "open_tickets": 0}

    return get_ticket, get_customer_history


def test_tool_order_on_real_langchain_trace(tracking_store):
    mlflow = tracking_store
    get_ticket, get_customer_history = _stub_tools()

    @mlflow.trace
    def fake_run():
        ticket = get_ticket.invoke({"ticket_id": "T-1"})
        get_customer_history.invoke({"customer_id": ticket["customer_id"]})
        return VALID

    fake_run()
    trace = mlflow.get_trace(mlflow.get_last_active_trace_id(), flush=True)
    assert trace is not None
    assert run_eval.tool_order(outputs=VALID, trace=trace) is True


def test_evaluate_wiring_with_one_failing_ticket(tracking_store, monkeypatch):
    import agent

    mlflow = tracking_store
    get_ticket, get_customer_history = _stub_tools()

    async def fake_triage(ticket_id):
        if ticket_id == "T-BAD":
            raise RuntimeError("agent failed")
        ticket = await get_ticket.ainvoke({"ticket_id": ticket_id})
        await get_customer_history.ainvoke({"customer_id": ticket["customer_id"]})
        return VALID

    monkeypatch.setattr(agent, "triage", fake_triage)
    monkeypatch.setattr(run_eval, "_agent", agent)

    expectations = {**EXPECTED, "expected_tools": ["get_ticket", "get_customer_history"]}
    data = [
        {"inputs": {"ticket_id": "T-GOOD"}, "expectations": expectations},
        {"inputs": {"ticket_id": "T-BAD"}, "expectations": expectations},
    ]
    result = mlflow.genai.evaluate(data=data, scorers=run_eval.SCORERS, predict_fn=run_eval.predict)

    for s in run_eval.SCORERS:
        assert result.metrics[f"{s.name}/mean"] == pytest.approx(0.5), s.name
