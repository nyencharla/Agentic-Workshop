"""Unit tests for the triage agent's non-model logic (Epic 2, story 1).

These cover provider selection from env vars and the retry-once-then-raise
wrapper. Live-model behavior (an actual Gemini/Groq call, MCP tool ordering)
is verified manually per the story's Verification section, not here — the
schema and MCP tool behavior are already covered by Epic 1's tests.
"""

import asyncio

import pytest

import agent
from agent import _get_tools, _invoke_with_retry, _read_policy, build_model
from langchain.agents.structured_output import StructuredOutputValidationError
from triage.schema import TriageDecision

VALID_DECISION = TriageDecision(
    category="billing",
    priority="P2",
    route="billing-team",
    rationale="A double charge is money at stake for one customer.",
)


def _validation_error() -> StructuredOutputValidationError:
    from langchain_core.messages import AIMessage

    return StructuredOutputValidationError(
        tool_name="TriageDecision",
        source=ValueError("bad payload"),
        ai_message=AIMessage(content=""),
    )


class _FakeAgent:
    """Stands in for the compiled `create_agent` graph: `ainvoke` either
    succeeds, or raises `StructuredOutputValidationError` a fixed number of
    times before succeeding (or forever)."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls <= self.failures:
            raise _validation_error()
        return {"structured_response": VALID_DECISION}


class TestProviderSelection:
    def test_defaults_to_gemini_with_default_model(self, monkeypatch):
        monkeypatch.delenv("PROVIDER", raising=False)
        monkeypatch.delenv("MODEL", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        model = build_model()

        assert type(model).__name__ == "ChatGoogleGenerativeAI"
        assert model.model == "gemini-3.8-flash"

    def test_gemini_honors_model_env_var(self, monkeypatch):
        monkeypatch.delenv("PROVIDER", raising=False)
        monkeypatch.setenv("MODEL", "gemini-custom")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        model = build_model()

        assert type(model).__name__ == "ChatGoogleGenerativeAI"
        assert model.model == "gemini-custom"

    def test_provider_groq_switches_to_chatgroq_with_default_model(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "groq")
        monkeypatch.delenv("MODEL", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        model = build_model()

        assert type(model).__name__ == "ChatGroq"
        assert model.model_name == "openai/gpt-oss-120b"

    def test_groq_honors_model_env_var(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "groq")
        monkeypatch.setenv("MODEL", "groq-custom")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        model = build_model()

        assert type(model).__name__ == "ChatGroq"
        assert model.model_name == "groq-custom"

    def test_provider_match_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "GROQ")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        model = build_model()

        assert type(model).__name__ == "ChatGroq"


class TestRetryOnceThenRaise:
    """No live model call is involved: `_invoke_with_retry` is exercised
    directly against a fake agent, driven with `asyncio.run` since this
    project has no pytest-asyncio dependency to add for it."""

    def test_succeeds_on_first_try(self):
        agent = _FakeAgent(failures=0)

        decision = asyncio.run(_invoke_with_retry(agent, {"messages": []}, "T-1042"))

        assert decision == VALID_DECISION
        assert agent.calls == 1

    def test_retries_once_then_succeeds(self):
        agent = _FakeAgent(failures=1)

        decision = asyncio.run(_invoke_with_retry(agent, {"messages": []}, "T-1042"))

        assert decision == VALID_DECISION
        assert agent.calls == 2

    def test_raises_a_clear_error_after_second_failure(self):
        agent = _FakeAgent(failures=2)

        with pytest.raises(RuntimeError, match="T-1042"):
            asyncio.run(_invoke_with_retry(agent, {"messages": []}, "T-1042"))

        assert agent.calls == 2


def test_read_policy_returns_non_empty_text():
    assert _read_policy().strip() != ""


class TestStructuredOutputHandleErrorsFalse:
    """`handle_errors` must stay `False` on the `ToolStrategy` `triage()` passes
    to `create_agent`, so a validation failure raises instead of being
    silently retried inside a single `ainvoke` call by the library default
    (`True`) -- which would break `_invoke_with_retry`'s retry-once contract
    with no test failing. Captures what `triage()` actually passes."""

    def test_triage_passes_handle_errors_false(self, monkeypatch):
        captured_kwargs = {}

        class _FakeMcpClient:
            def __init__(self, *args, **kwargs):
                pass

            async def get_tools(self):
                return []

        class _FakeCompiledAgent:
            async def ainvoke(self, messages):
                return {"structured_response": VALID_DECISION}

        def _fake_create_agent(model, **kwargs):
            captured_kwargs.update(kwargs)
            return _FakeCompiledAgent()

        monkeypatch.setattr(agent, "MultiServerMCPClient", _FakeMcpClient)
        monkeypatch.setattr(agent, "build_model", lambda: object())
        monkeypatch.setattr(agent, "create_agent", _fake_create_agent)

        asyncio.run(agent.triage("T-1042"))

        assert captured_kwargs["response_format"].handle_errors is False


class TestMcpToolErrorsPropagate:
    """A tool error (e.g. an unknown ticket ID) must stop the run and propagate
    the tool's message, per the I/O matrix -- not be swallowed into a soft
    self-correction message for the model. `MultiServerMCPClient` only does
    that when constructed with `handle_tool_errors=False`; its default is
    `True`, which lets the agent see the failure as an ordinary tool result
    and potentially proceed anyway. This locks in that config without needing
    a live model call or a real `app.db`."""

    def test_get_tools_disables_soft_tool_error_handling(self, monkeypatch):
        captured_kwargs = {}
        captured_connections = {}

        class _FakeClient:
            def __init__(self, connections, **kwargs):
                captured_connections.update(connections)
                captured_kwargs.update(kwargs)

            async def get_tools(self):
                return []

        monkeypatch.setattr(agent, "MultiServerMCPClient", _FakeClient)

        asyncio.run(_get_tools())

        assert captured_kwargs.get("handle_tool_errors") is False

        connection = captured_connections["triage"]
        assert connection["command"] == "python"
        assert connection["args"] == [str(agent._MCP_SERVER_PATH)]
        assert connection["transport"] == "stdio"
