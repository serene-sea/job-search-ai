"""不打开本机端口，核对联调用假模型的两种响应格式。"""

import io
import json

from backend.scripts.fake_model_service import FakeModelHandler
from backend.services.chat_stream import model_settings
from backend.services.model_options import completion_options


def fake_request(body: dict) -> FakeModelHandler:
    handler = FakeModelHandler.__new__(FakeModelHandler)
    content = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.path = "/v1/chat/completions"
    handler.request_version = "HTTP/1.1"
    handler.requestline = "POST /v1/chat/completions HTTP/1.1"
    handler.headers = {"Content-Length": str(len(content))}
    handler.rfile = io.BytesIO(content)
    handler.wfile = io.BytesIO()
    handler.do_POST()
    return handler


def test_fake_extract_only_quotes_input():
    handler = fake_request({"messages": [{"content": json.dumps(
        {"requirements_text": "熟悉 Python 后端开发"}, ensure_ascii=False)}]})
    body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)[1]
    result = json.loads(json.loads(body)["choices"][0]["message"]["content"])
    assert result == {"items": [{"quote": "熟悉 Python 后端开发", "priority": "unspecified"}]}


def test_fake_chat_stream_ends(monkeypatch):
    monkeypatch.setattr("backend.scripts.fake_model_service.time.sleep", lambda _: None)
    handler = fake_request({"stream": True})
    output = handler.wfile.getvalue()
    assert b"data: [DONE]\n\n" in output
    assert output.count(b"data: ") == 36


def test_fake_agent_requests_tools_then_cites_tool_records():
    first = fake_request({"stream": True, "messages": [{"role": "user", "content": "问岗位"}],
                          "tools": [{"function": {"name": "read_current_job"}},
                                    {"function": {"name": "read_skills"}}]})
    assert b"read_current_job" in first.wfile.getvalue()
    assert b"read_skills" in first.wfile.getvalue()
    second = fake_request({"stream": True, "messages": [
        {"role": "tool", "content": json.dumps({"records": [{"id": "job:7"}]})}],
        "tools": [{"function": {"name": "read_current_job"}}]})
    assert b"[job:7]" in second.wfile.getvalue()


def test_only_deepseek_receives_thinking_option():
    assert completion_options("https://api.deepseek.com") == {"thinking": {"type": "disabled"}}
    assert completion_options("https://example.com/v1") == {}
    assert completion_options("http://127.0.0.1:8765/v1") == {}


def test_one_key_uses_deepseek_defaults(monkeypatch):
    monkeypatch.setattr("backend.services.chat_stream.load_local_env", lambda: None)
    monkeypatch.setenv("JOB_AI_API_KEY", "fake-key")
    monkeypatch.delenv("JOB_AI_BASE_URL", raising=False)
    monkeypatch.delenv("JOB_AI_MODEL", raising=False)
    assert model_settings() == ("https://api.deepseek.com", "deepseek-flash", "fake-key")
