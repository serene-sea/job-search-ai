"""用脚本模型测试真正的“模型选工具→查本人资料→核对引用”，不花 API 费用。"""

import asyncio
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.base import Base
from backend.db.models import ChatMessage, GenerationRun, Job, JobStatus, Resume, Skill, User
from backend.routers import chat
from backend.scripts.fake_model_service import FakeModelHandler
from backend.services import personal_agent as agent


class ScriptedModel(FakeMessagesListChatModel):
    """测试专用模型：按顺序返回“调用工具”和“最终回答”，从不请求外网。"""

    def bind_tools(self, tools, **kwargs):
        return self


def _database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'agent.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=1, username="one", password_hash="h"),
                    User(id=2, username="two", password_hash="h")])
        db.flush()
        db.add(JobStatus(id=1, user_id=1, name="想投", sort_order=1))
        db.flush()
        db.add(Job(id=7, user_id=1, status_id=1, company_name="甲公司", title="后端",
                   requirements_text="熟悉 Python 后端开发"))
        db.add_all([
            Skill(id=11, user_id=1, name="Python", proficiency=2, importance=5,
                  description="做过简单接口", updated_at=datetime(2026, 11, 3)),
            Skill(id=12, user_id=2, name="OTHER_PRIVATE_SKILL", proficiency=4, importance=5,
                  updated_at=datetime(2026, 11, 3)),
            Resume(user_id=1, raw_extracted_text="PRIVATE_UNCONFIRMED_RESUME",
                   reviewed_text="PRIVATE_UNCONFIRMED_RESUME", confirmed_at=None,
                   updated_at=datetime(2026, 11, 3)),
        ])
        db.commit()
    return engine


def _context(engine, *, user_id=1, sources=("skills",), job_id=7):
    return agent.AgentContext(user_id=user_id, allowed_sources=sources, job_id=job_id,
                              report=None, db_factory=sessionmaker(bind=engine))


def _run(context, model, monkeypatch):
    monkeypatch.setattr(agent, "_make_model", lambda _settings: model)

    async def collect():
        return [event async for event in agent.run_personal_agent(
            [{"role": "user", "content": "这个岗位我缺什么？"}],
            ("http://127.0.0.1:8765/v1", "local-fake", "fake"), context,
        )]

    return asyncio.run(collect())


def test_agent_calls_two_tools_and_checks_sources(tmp_path, monkeypatch):
    engine = _database(tmp_path)
    try:
        scripted = ScriptedModel(responses=[
            AIMessage(content="", tool_calls=[
                {"name": "read_current_job", "args": {}, "id": "job-call"},
                {"name": "read_skills", "args": {}, "id": "skill-call"},
            ]),
            AIMessage(content="岗位要求 Python [job:7]；你自评掌握 Python [skill:11]，可补接口实践。"),
        ])
        events = _run(_context(engine), scripted, monkeypatch)
        assert ("progress", "已查看当前岗位") in events
        assert ("progress", "已查看技能") in events
        assert events[-1][0] == "answer"
        assert "【当前岗位】" in events[-1][1]
        assert "【技能：Python】" in events[-1][1]
        assert "[skill:11]" not in events[-1][1]
        assert "OTHER_PRIVATE_SKILL" not in str(events)
        assert "PRIVATE_UNCONFIRMED_RESUME" not in str(events)
        assert scripted.i == 0  # 已经过两次模型决策，脚本模型循环回第一条。
    finally:
        engine.dispose()


def test_scope_and_owner_cannot_be_selected_by_model(tmp_path):
    engine = _database(tmp_path)
    try:
        own = _context(engine)
        assert [tool.name for tool in agent._allowed_tools(own)] == ["read_current_job", "read_skills"]
        with pytest.raises(ValueError, match="未允许"):
            agent._read("resume", type("Runtime", (), {"context": own})())
        foreign = _context(engine, user_id=2)
        with pytest.raises(Exception) as error:
            agent._read("job", type("Runtime", (), {"context": foreign})())
        assert "熟悉 Python" not in str(error.value)
        # 就算勾选了简历，未确认的文字也不会进入工具结果。
        resume = agent._read("resume", type("Runtime", (), {"context":
            _context(engine, sources=("resume",), job_id=None)})())
        assert "PRIVATE_UNCONFIRMED_RESUME" not in resume
    finally:
        engine.dispose()


def test_agent_rejects_fake_reference(tmp_path, monkeypatch):
    engine = _database(tmp_path)
    try:
        scripted = ScriptedModel(responses=[
            AIMessage(content="", tool_calls=[{"name": "read_skills", "args": {}, "id": "skill-call"}]),
            AIMessage(content="你掌握了数据库 [skill:999]。"),
        ])
        with pytest.raises(ValueError, match="没有读取"):
            _run(_context(engine, sources=("skills",), job_id=None), scripted, monkeypatch)
    finally:
        engine.dispose()


def test_personal_chat_uses_agent_and_saves_answer(tmp_path, monkeypatch):
    engine = _database(tmp_path)
    seen = {}

    async def fake_agent(messages, settings, context):
        # 接口只交给 Agent 问题和服务端身份，个人资料没有提前拼进 prompt。
        seen["messages"] = messages
        seen["context"] = context
        yield "progress", "已查看当前岗位"
        yield "answer", "岗位要求见 [job:7]，还需要更多真实项目证据。"

    monkeypatch.setattr(chat, "model_settings", lambda: ("http://127.0.0.1:8765/v1", "fake", "fake"))
    monkeypatch.setattr(chat, "run_personal_agent", fake_agent)

    async def ask_and_read():
        with Session(engine, expire_on_commit=False) as db:
            owner = db.get(User, 1)
            row = chat.create_session(chat.SessionCreate(job_id=7), owner, db)
            response = await chat.ask(row.id, chat.AskRequest(
                question="我缺什么？", mode="personal", sources=["skills"],
                request_key="abcdef0123456789",
            ), owner, db)
        return row.id, "".join([chunk async for chunk in response.body_iterator])

    try:
        session_id, events = asyncio.run(ask_and_read())
        assert "event: progress" in events and "event: delta" in events
        assert seen["context"].user_id == 1
        assert seen["context"].allowed_sources == ("skills",)
        assert "熟悉 Python" not in str(seen["messages"])
        assert "PRIVATE_UNCONFIRMED_RESUME" not in str(seen["messages"])
        with Session(engine) as db:
            run = db.query(GenerationRun).filter_by(session_id=session_id).one()
            answer = db.get(ChatMessage, run.assistant_message_id)
            assert run.status == "completed" and run.source_scope == ["skills"]
            assert answer.content.startswith("岗位要求见")
    finally:
        engine.dispose()


def test_agent_reaches_local_fake_model_without_real_key(tmp_path, monkeypatch):
    """真实走一次 HTTP 工具调用协议；服务只监听本机，资料都是本测试写的假数据。"""
    engine = _database(tmp_path)
    # 用户机器可能设置了系统代理；本机假服务必须直连 127.0.0.1。
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeModelHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    async def collect():
        return [event async for event in agent.run_personal_agent(
            [{"role": "user", "content": "这条模拟岗位呢？"}],
            (f"http://127.0.0.1:{server.server_port}/v1", "local-fake", "fake-key"),
            _context(engine),
        )]

    try:
        events = asyncio.run(collect())
        assert ("progress", "已查看当前岗位") in events
        assert ("progress", "已查看技能") in events
        assert "【当前岗位】" in events[-1][1]
        assert "PRIVATE_UNCONFIRMED_RESUME" not in str(events)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
        engine.dispose()


def test_stop_cancels_personal_agent_and_marks_interrupted(tmp_path, monkeypatch):
    engine = _database(tmp_path)
    ready = asyncio.Event()

    async def waiting_agent(_messages, _settings, _context):
        yield "progress", "已查看当前岗位"
        ready.set()
        await asyncio.Event().wait()  # 模拟模型仍在生成；只由停止按钮结束。

    monkeypatch.setattr(chat, "model_settings", lambda: ("http://127.0.0.1:8765/v1", "fake", "fake"))
    monkeypatch.setattr(chat, "run_personal_agent", waiting_agent)

    async def scenario():
        with Session(engine, expire_on_commit=False) as db:
            owner = db.get(User, 1)
            row = chat.create_session(chat.SessionCreate(job_id=7), owner, db)
            response = await chat.ask(row.id, chat.AskRequest(
                question="我该准备什么？", mode="personal", sources=["skills"],
                request_key="abcdef0123456790",
            ), owner, db)

        async def consume():
            return [part async for part in response.body_iterator]

        task = asyncio.create_task(consume())
        await asyncio.wait_for(ready.wait(), timeout=3)
        with Session(engine) as db:
            run = db.query(GenerationRun).filter_by(session_id=row.id).one()
            result = await chat.stop(run.id, db.get(User, 1), db)
            assert result["status"] == "cancel_requested"
        with pytest.raises(asyncio.CancelledError):
            await task
        with Session(engine) as db:
            saved = db.query(GenerationRun).filter_by(session_id=row.id).one()
            answer = db.get(ChatMessage, saved.assistant_message_id)
            assert saved.status == "interrupted"
            assert answer.status == "interrupted" and answer.content == ""

    try:
        asyncio.run(scenario())
    finally:
        engine.dispose()
