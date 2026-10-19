"""不启动服务器、不调用真实模型，检查聊天记录、权限和流式完成状态。"""

import asyncio
import json
import pytest
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import ChatMessage, GenerationRun, Job, JobStatus, Resume, Skill, User
from backend.routers import chat
from backend.services import job_analysis
from backend.services.job_report import JobGuide
from backend.services.personal_context import build_personal_context


def make_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'chat.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=1, username="one", password_hash="h"),
                    User(id=2, username="two", password_hash="h")])
        db.flush()
        db.add(JobStatus(id=1, user_id=1, name="想投", sort_order=1))
        db.flush()
        db.add(Job(id=7, user_id=1, status_id=1, company_name="甲公司", title="后端",
                   requirements_text="熟悉 Python 后端开发"))
        db.commit()
    return engine


def test_chat_session_owner_and_report_persistence(tmp_path, monkeypatch):
    engine = make_db(tmp_path)
    try:
        with Session(engine, expire_on_commit=False) as db:
            owner, other = db.get(User, 1), db.get(User, 2)
            with pytest.raises(HTTPException) as foreign_job:
                chat.create_session(chat.SessionCreate(job_id=7), other, db)
            assert foreign_job.value.status_code == 404
            row = chat.create_session(chat.SessionCreate(job_id=7), owner, db)
            with pytest.raises(HTTPException) as foreign_chat:
                chat.list_messages(row.id, other, db)
            assert foreign_chat.value.status_code == 404

            snapshot = chat.build_snapshot(db, owner.id, 7)
            from backend.services.job_analysis import JobAnalysisResult, AnalysisItem
            fake_result = JobAnalysisResult(job_id=7, company_name="甲公司", title="后端",
                resume_used=False, context_limited=False,
                items=[AnalysisItem(quote="熟悉 Python 后端开发", priority="required",
                    status="no_evidence", evidence=[], reason="本次材料没有证据", next_step="补充真实经历")])
            def fake_align(snapshot_arg, items_arg):
                assert snapshot_arg.job_id == 7
                assert len(items_arg) == 1
                return fake_result
            monkeypatch.setattr(chat, "align_requirements", fake_align)
            monkeypatch.setattr(chat, "build_guide", lambda *_: JobGuide(
                text="测试中不调用真实模型", limited=True))
            # 无关对话即使已保存，也不会传入生成报告的模型调用。
            db.add(ChatMessage(session_id=row.id, user_id=owner.id, role="user", kind="text",
                               content="无关闲聊", status="completed", created_at=datetime(2026, 10, 19)))
            db.commit()
            report = chat.create_report(row.id, chat.ReportRequest(
                snapshot_version=snapshot.version,
                items=[{"quote": "熟悉 Python 后端开发", "priority": "required"}]), owner, db)
            assert report.report_json["items"][0]["status"] == "no_evidence"
            assert report.report_json["guide"]["limited"] is True
            assert report.content == "岗位证据分析报告"
            assert chat.list_messages(row.id, owner, db)[-1].kind == "report"
            assert chat.latest_report(db, owner.id, row.id).snapshot_version == snapshot.version
    finally:
        engine.dispose()


def test_plain_prompt_contains_only_question_and_selected_history(tmp_path):
    engine = make_db(tmp_path)
    try:
        with Session(engine, expire_on_commit=False) as db:
            owner = db.get(User, 1)
            row = chat.create_session(chat.SessionCreate(), owner, db)
            assert chat._prompt_messages(db, owner.id, row, "Python 是什么？", "plain") == [
                {"role": "user", "content": "Python 是什么？"}
            ]
    finally:
        engine.dispose()


def test_report_alignment_receives_only_requirements_and_evidence(tmp_path, monkeypatch):
    engine = make_db(tmp_path)
    try:
        with Session(engine) as db:
            snapshot = job_analysis.build_snapshot(db, 1, 7)
        sent = []

        def fake_model(_system, data):
            sent.append(data)
            return json.dumps({"items": [{"requirement_index": 0, "status": "no_evidence",
                                         "evidence_ids": [], "reason": "没有可引用的个人材料",
                                         "next_step": "补充真实项目经历"}]})

        monkeypatch.setattr(job_analysis, "chat_json", fake_model)
        result = job_analysis.align_requirements(
            snapshot, [job_analysis.RequirementDraft(quote="熟悉 Python 后端开发", priority="required")])
        assert "focus" not in sent[0]
        assert sent[0]["evidence"] == []  # 输入框问题不参与报告对齐。
        assert result.items[0].status == "no_evidence"
    finally:
        engine.dispose()


def test_personal_context_uses_only_selected_sources_and_current_user(tmp_path):
    engine = make_db(tmp_path)
    try:
        with Session(engine) as db:
            now = datetime(2026, 10, 19)
            db.add_all([
                Skill(user_id=1, name="SQL", proficiency=2, importance=5,
                      description="会基础查询", updated_at=now),
                Skill(user_id=2, name="OTHER_PRIVATE_SKILL", proficiency=4,
                      importance=5, updated_at=now),
                Resume(user_id=1, raw_extracted_text="PRIVATE_RESUME", reviewed_text="PRIVATE_RESUME",
                       confirmed_at=None, updated_at=now),
            ])
            db.commit()
            only_skills = build_personal_context(db, 1, ["skills"])
            assert "SQL" in only_skills
            assert "PRIVATE_RESUME" not in only_skills
            assert "OTHER_PRIVATE_SKILL" not in only_skills
            job_context = build_personal_context(db, 1, [], job_id=7,
                                                 report={"marker": "OLD_REPORT_TEXT"})
            assert "OLD_REPORT_TEXT" in job_context
            assert "OLD_REPORT_TEXT" not in only_skills
            assert "熟悉 Python 后端开发" in build_personal_context(db, 1, ["skills"], job_id=7)
            with pytest.raises(HTTPException) as foreign_job:
                build_personal_context(db, 2, [], job_id=7)
            assert foreign_job.value.status_code == 404
            unconfirmed = build_personal_context(db, 1, ["resume"])
            assert "PRIVATE_RESUME" not in unconfirmed
            assert "没有已确认的简历文字" in unconfirmed
            db.get(Resume, 1).confirmed_at = now
            db.flush()
            assert "PRIVATE_RESUME" in build_personal_context(db, 1, ["resume"])
    finally:
        engine.dispose()


def test_question_mode_rejects_unselected_data_scope(tmp_path):
    engine = make_db(tmp_path)
    try:
        with Session(engine, expire_on_commit=False) as db:
            row = chat.create_session(chat.SessionCreate(), db.get(User, 1), db)
            for mode, sources in [("plain", ["resume"]), ("personal", []),
                                  ("personal", ["skills", "skills"])]:
                request = chat.AskRequest(question="test", mode=mode, sources=sources,
                                          request_key="1234567890abcdef")
                with pytest.raises(HTTPException) as invalid:
                    asyncio.run(chat.ask(row.id, request, db.get(User, 1), db))
                assert invalid.value.status_code == 422
    finally:
        engine.dispose()


def test_report_does_not_reintroduce_unselected_resume():
    report = {"company_name": "甲公司", "title": "后端", "items": [{
        "quote": "熟悉 Python", "priority": "required", "status": "supported",
        "reason": "PRIVATE_RESUME", "next_step": "PRIVATE_RESUME",
        "evidence": [{"kind": "resume", "text": "PRIVATE_RESUME"},
                     {"kind": "skill", "text": "SQL 自评"}],
    }]}
    selected = chat._report_for_scope(report, ["skills"])
    assert "SQL 自评" in json.dumps(selected, ensure_ascii=False)
    assert "PRIVATE_RESUME" not in json.dumps(selected, ensure_ascii=False)
    assert "status" not in selected["items"][0]


def test_personal_history_does_not_mix_different_source_scopes(tmp_path):
    engine = make_db(tmp_path)
    try:
        with Session(engine, expire_on_commit=False) as db:
            row = chat.create_session(chat.SessionCreate(), db.get(User, 1), db)
            now = datetime(2026, 10, 19)
            for index, (scope, content) in enumerate([
                (["resume"], "RESUME_ONLY_HISTORY"), (["skills"], "SKILL_ONLY_HISTORY"),
            ]):
                human = ChatMessage(session_id=row.id, user_id=1, role="user", kind="text",
                                    content=content, status="completed", created_at=now)
                answer = ChatMessage(session_id=row.id, user_id=1, role="assistant", kind="text",
                                     content=f"answer {index}", status="completed", created_at=now)
                db.add_all([human, answer])
                db.flush()
                db.add(GenerationRun(session_id=row.id, user_id=1, user_message_id=human.id,
                                     assistant_message_id=answer.id, request_key=f"scope-{index}",
                                     mode="personal", source_scope=scope, status="completed",
                                     started_at=now, ended_at=now))
            db.commit()
            prompt = str(chat._prompt_messages(db, 1, row, "下一步？", "personal", ["skills"]))
            assert "SKILL_ONLY_HISTORY" in prompt
            assert "RESUME_ONLY_HISTORY" not in prompt
            assert "SKILL_ONLY_HISTORY" not in str(chat._prompt_messages(db, 1, row, "hello", "plain"))
    finally:
        engine.dispose()
