"""Model streaming, tool execution, and failure behavior without subscription usage."""

import json
from pathlib import Path
from threading import Event

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent import codex_model
from agent.codex_model import ChatCodex
from agent.json_content_stream import JSONContentStream
from tools.internal.get_customer_profile import get_customer_profile


@pytest.fixture
def fake_cli(monkeypatch):
    calls = []
    response = {
        "answer": {"content": "Checking the customer.", "tool_calls": [
            {"name": "get_customer_profile", "arguments": '{"customer_id":"CUST-UK-004821"}'}
        ]},
        "status": "completed", "account": {"type": "chatgpt"},
    }

    class FakeServer:
        def __init__(self, command, **kwargs):
            self.call = {"command": command, **kwargs, "requests": {}, "completed": False, "closed": False}
            calls.append(self.call)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.call["closed"] = True

        def request(self, method, params):
            self.call["requests"][method] = params
            return {"account": response["account"]} if method == "account/read" else {"thread": {"id": "thread_1"}}

        def send(self, method, params=None, **kwargs):
            self.call["requests"][method] = params
            if method != "turn/start":
                return
            answer = response["answer"]
            if callable(answer):
                answer = answer(params["input"][0]["text"])
            text = answer if isinstance(answer, str) else json.dumps(answer)
            # No private reasoning or commentary should reach the application.
            self.events = [
                {"method": "item/reasoning/textDelta", "params": {"delta": "private reasoning"}},
                {"method": "item/started", "params": {"item": {"id": "comment", "type": "agentMessage", "phase": "commentary"}}},
                {"method": "item/agentMessage/delta", "params": {"itemId": "comment", "delta": "unstructured preamble"}},
                {"method": "item/started", "params": {"item": {"id": "answer", "type": "agentMessage", "phase": "final_answer"}}},
            ]
            self.events += [
                {"method": "item/agentMessage/delta", "params": {"itemId": "answer", "delta": text[i:i + 3]}}
                for i in range(0, len(text), 3)
            ]
            self.events += [
                {"method": "item/completed", "params": {"item": {"id": "answer", "type": "agentMessage", "text": text, "phase": "final_answer"}}},
                {"method": "turn/completed", "params": {"turn": {"status": response["status"]}}},
            ]

        def receive(self):
            if response.get("timeout"):
                raise RuntimeError("Codex did not finish within 1 seconds.")
            if not self.events:
                raise RuntimeError("Codex disconnected before completing the response.")
            event = self.events.pop(0)
            if event["method"] == "turn/completed":
                if response.get("before_completion"):
                    assert response["before_completion"].wait(timeout=5)
                self.call["completed"] = True
            return event

    monkeypatch.setattr(codex_model, "_cli_path", lambda: "codex.exe")
    monkeypatch.setattr(codex_model, "CodexAppServer", FakeServer)
    return calls, response


def test_text_arrives_before_completion_and_tools_wait_for_success(fake_cli):
    calls, response = fake_cli
    stream = ChatCodex().bind_tools([get_customer_profile]).stream([
        SystemMessage(content="Investigate"), HumanMessage(content="Customer alert")
    ])
    first = next(stream)
    assert first.content
    assert not calls[-1]["completed"]
    assert not first.tool_calls
    chunks = [first, *stream]
    assert "".join(c.content for c in chunks) == response["answer"]["content"]
    tool_chunk = next(c for c in chunks if c.tool_calls)
    tool_call = tool_chunk.tool_calls[0]
    assert json.loads(get_customer_profile.invoke(tool_call["args"]))["customer_id"] == "CUST-UK-004821"
    call = calls[-1]
    assert call["completed"] and call["closed"]
    assert call["requests"]["thread/start"]["sandbox"] == "read-only"
    assert call["requests"]["thread/start"]["ephemeral"] is True
    assert "model" not in call["requests"]["thread/start"]
    assert call["command"][1] == "app-server"
    assert "shell_tool" in call["command"]
    assert "Customer alert" not in " ".join(call["command"])
    assert not Path(call["cwd"]).exists()


def test_tool_ids_history_and_model_override(fake_cli):
    calls, _ = fake_cli
    result = ChatCodex(model_name="gpt-6-luna").bind_tools([get_customer_profile]).invoke([
        HumanMessage(content="Investigate"),
        AIMessage(content="", tool_calls=[{"name": "get_customer_profile", "args": {"customer_id": "CUST-UK-004821"}, "id": "previous_call"}]),
        ToolMessage(content='{"customer_id":"CUST-UK-004821"}', tool_call_id="previous_call"),
    ])
    call = calls[-1]
    assert call["requests"]["thread/start"]["model"] == "gpt-6-luna"
    assert '"tool_call_id": "previous_call"' in call["requests"]["turn/start"]["input"][0]["text"]
    assert result.tool_calls[0]["id"].startswith("call_")


def test_plain_sar_stream_has_multiple_real_deltas(fake_cli):
    calls, response = fake_cli
    response["answer"] = "Funds moved between the customer's own accounts."
    stream = ChatCodex().stream("Draft a SAR section")
    first = next(stream)
    assert not calls[-1]["completed"]
    chunks = [first, *stream]
    assert len([chunk for chunk in chunks if chunk.content]) > 2
    assert "".join(chunk.content for chunk in chunks) == response["answer"]
    assert "outputSchema" not in calls[-1]["requests"]["turn/start"]


@pytest.mark.parametrize("bad_call", [
    {"name": "execute_shell", "arguments": "{}"},
    {"name": "get_customer_profile", "arguments": "[]"},
    {"name": "get_customer_profile", "arguments": "not JSON"},
])
def test_rejects_invalid_tool_requests(fake_cli, bad_call):
    _, response = fake_cli
    response["answer"]["tool_calls"] = [bad_call]
    with pytest.raises(RuntimeError, match="invalid application tool response"):
        ChatCodex().bind_tools([get_customer_profile]).invoke("Investigate")


def test_api_key_login_is_rejected(fake_cli):
    calls, response = fake_cli
    response["account"] = {"type": "apiKey"}
    with pytest.raises(RuntimeError, match="requires a Codex ChatGPT login"):
        ChatCodex().invoke("Hello")
    assert "turn/start" not in calls[-1]["requests"]
    assert calls[-1]["closed"]


def test_child_does_not_inherit_api_keys_or_parent_session(monkeypatch):
    names = ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_THREAD_ID", "OPENAI_BASE_URL", "OPENAI_ACCESS_TOKEN")
    for name in names:
        monkeypatch.setenv(name, "must-not-be-forwarded")
    monkeypatch.setenv("CODEX_HOME", "/chosen/auth/home")
    env = codex_model._cli_environment()
    assert env["CODEX_HOME"] == "/chosen/auth/home"
    assert all(name not in env for name in names)


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_failed_partial_turn_never_executes_tools(fake_cli, status):
    calls, response = fake_cli
    response["status"] = status
    stream = ChatCodex().bind_tools([get_customer_profile]).stream("Investigate")
    assert next(stream).content
    chunks = []
    with pytest.raises(RuntimeError, match="could not complete"):
        for chunk in stream:
            chunks.append(chunk)
    assert not any(chunk.tool_calls for chunk in chunks)
    assert calls[-1]["closed"]


def test_timeout_and_cancellation_close_transport(fake_cli):
    calls, response = fake_cli
    response["timeout"] = True
    with pytest.raises(RuntimeError, match="did not finish"):
        ChatCodex().invoke("Hello")
    assert calls[-1]["closed"]
    response["timeout"] = False
    stream = ChatCodex().stream("Hello")
    next(stream)
    stream.close()
    assert calls[-1]["closed"]


@pytest.mark.parametrize("chunk_size", [1, 2, 5, 17])
@pytest.mark.parametrize("content_first", [True, False])
def test_content_decoder_handles_split_escapes_and_unicode(chunk_size, content_first):
    text = 'Line 1\n"quoted" \\ £ café 😀 **bold**'
    envelope = {"content": text, "tool_calls": []} if content_first else {"tool_calls": [], "content": text}
    raw = json.dumps(envelope, ensure_ascii=True)
    decoder = JSONContentStream()
    output = "".join(decoder.feed(raw[i:i + chunk_size]) for i in range(0, len(raw), chunk_size))
    assert output == text
    assert decoder.closed


def test_provider_factory(monkeypatch):
    from agent.llm import get_llm, get_llm_config
    monkeypatch.setenv("LLM_PROVIDER", "codex")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert get_llm_config() == {"provider": "codex", "model": "Codex default"}
    assert isinstance(get_llm(), ChatCodex)


def test_investigation_sse_streams_text_before_verdict(monkeypatch, fake_cli):
    import agent.graph as graph_module
    from api import _stream_investigation
    from schemas.alert import AlertPayload

    calls, response = fake_cli
    first_answer = response["answer"]
    first_answer["content"] = 'Looking up {"customer_id":"CUST-UK-004821"}.'
    verdict = {"verdict": "FALSE_POSITIVE", "confidence": "HIGH", "sar_recommended": False}
    response["answer"] = lambda prompt: (
        {"content": json.dumps(verdict), "tool_calls": []}
        if '"role": "tool"' in prompt else first_answer
    )
    monkeypatch.setenv("LLM_PROVIDER", "codex")
    monkeypatch.setattr(graph_module, "_llm_with_tools", None)
    response["before_completion"] = Event()
    alert_path = Path(__file__).parent / "sample_alerts" / "false_positive.json"
    alert = AlertPayload.model_validate_json(alert_path.read_text(encoding="utf-8"))
    events = _stream_investigation(alert)
    next(events)  # System prompt.
    first = next(events)
    assert first.startswith("event: thinking")
    assert not calls[-1]["completed"]
    response["before_completion"].set()
    parsed = [(event.splitlines()[0], json.loads(event.splitlines()[1][6:])) for event in events]
    assert sum(kind == "event: thinking" for kind, _ in parsed) > 2
    assert any(kind == "event: tool_result" and data["result"]["customer_id"] == "CUST-UK-004821" for kind, data in parsed)
    assert ("event: verdict", verdict) in parsed
    assert not any(kind == "event: error" for kind, _ in parsed)
