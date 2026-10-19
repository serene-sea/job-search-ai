"""两步岗位分析只用内存数据库与假模型；不发送任何真实资料。"""

import json
import pytest
import httpx

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import job_analysis
from backend.tests.test_auth import auth_db, write_headers  # noqa: F401
from backend.tests.test_jobs import job_body, login_as


def write(client: TestClient, path: str, body: dict):
    return client.post(path, json=body, headers=write_headers)


def extract(client: TestClient, job_id: int):
    return write(client, f"/api/jobs/{job_id}/requirements/extract", {})


def align(client: TestClient, job_id: int, version: str, items: list[dict]):
    return write(client, f"/api/jobs/{job_id}/analysis", {
        "snapshot_version": version, "items": items,
    })


def test_reviewed_flow_uses_only_owned_confirmed_evidence(auth_db, monkeypatch):
    with TestClient(app) as alice, TestClient(app) as bob:
        status = login_as(alice, "alice")
        login_as(bob, "bob")
        job = write(alice, "/api/jobs", job_body(status, requirements_text="需要 Python 后端经验和 MySQL 事务实践"))
        assert job.status_code == 201
        job_id = job.json()["id"]
        assert alice.patch("/api/profile", json={"school": "旧学校", "experience_text": "本人其他经历"},
                           headers=write_headers).status_code == 200
        assert write(alice, "/api/educations", {"school": "新学校", "major": "网安", "degree": "硕士",
                    "start_year": 2024, "start_month": 9, "end_year": 2027, "end_month": 6}).status_code == 201
        assert write(alice, "/api/projects", {"name": "本人项目", "summary": "实际完成的功能"}).status_code == 201
        assert write(alice, "/api/skills", {"name": "MySQL", "proficiency": 2, "importance": 5,
                    "description": "会基础 SQL，缺少事务实践"}).status_code == 201
        assert alice.patch("/api/resume", json={"reviewed_text": "本人 Python 项目经历"}, headers=write_headers).status_code == 200
        assert bob.patch("/api/resume", json={"reviewed_text": "Bob 私人经历"}, headers=write_headers).status_code == 200
        assert write(bob, "/api/resume/confirm", {}).status_code == 200

        calls = []
        include_resume = [False]

        def fake_model(_system_prompt, data):
            calls.append(data)
            if "requirements_text" in data:
                assert "evidence" not in data  # 第一步不发送个人资料。
                return json.dumps({"items": [{"quote": "MySQL 事务实践", "priority": "required"}]})
            evidence = data["evidence"]
            assert all("Bob 私人经历" not in row["text"] and "旧学校" not in row["text"] for row in evidence)
            assert {"education", "project", "skill", "profile"}.issubset({row["kind"] for row in evidence})
            assert ("resume" in {row["kind"] for row in evidence}) == include_resume[0]
            source_id = next(row["id"] for row in evidence if row["kind"] == "skill")
            return json.dumps({"items": [{"requirement_index": 0, "status": "partial",
                                         "evidence_ids": [source_id], "reason": "自评提到事务短板",
                                         "next_step": "补充事务练习"}]})

        monkeypatch.setattr("backend.services.job_analysis.chat_json", fake_model)
        extract_path = f"/api/jobs/{job_id}/requirements/extract"
        assert write(bob, extract_path, {}).status_code == 404
        with TestClient(app) as anonymous:
            assert write(anonymous, extract_path, {}).status_code == 401
        assert calls == []

        draft = extract(alice, job_id)
        assert draft.status_code == 200, draft.text
        version, items = draft.json()["snapshot_version"], draft.json()["items"]
        assert len(version) == 64 and len(calls) == 1
        assert align(bob, job_id, version, items).status_code == 404
        assert align(alice, job_id, version, items).json()["resume_used"] is False

        assert write(alice, "/api/resume/confirm", {}).status_code == 200
        assert align(alice, job_id, version, items).status_code == 409
        include_resume[0] = True
        current = extract(alice, job_id).json()
        result = align(alice, job_id, current["snapshot_version"], current["items"])
        assert result.status_code == 200, result.text
        assert result.json()["resume_used"] is True
        assert result.json()["items"][0]["evidence"][0]["kind"] == "skill"


def test_rejects_fabrication_invalid_reference_and_changed_material(auth_db, monkeypatch):
    with TestClient(app) as client:
        status = login_as(client, "alice")
        job = write(client, "/api/jobs", job_body(status, requirements_text="熟悉 SQL"))
        job_id = job.json()["id"]
        monkeypatch.setattr("backend.services.job_analysis.chat_json", lambda *_: json.dumps({
            "items": [{"quote": "十年工作经验", "priority": "required"}],
        }))
        assert extract(client, job_id).status_code == 502

        calls = []

        def fake_model(_prompt, data):
            calls.append(data)
            if "requirements_text" in data:
                return json.dumps({"items": [{"quote": "熟悉 SQL", "priority": "required"}]})
            return json.dumps({"items": [{"requirement_index": 0, "status": "supported",
                                         "evidence_ids": ["skill:other-user"], "reason": "有经验",
                                         "next_step": "继续练习"}]})

        monkeypatch.setattr("backend.services.job_analysis.chat_json", fake_model)
        draft = extract(client, job_id).json()
        version, items = draft["snapshot_version"], draft["items"]
        assert align(client, job_id, version, [{"quote": "编造的条件", "priority": "required"}]).status_code == 422
        assert len(calls) == 1
        assert align(client, job_id, version, items).status_code == 502
        assert write(client, "/api/skills", {"name": "SQL", "proficiency": 2, "importance": 3}).status_code == 201
        assert align(client, job_id, version, items).status_code == 409
        assert len(calls) == 2  # 过期快照没有发给模型。


def test_model_error_and_missing_config_do_not_expose_material(auth_db, monkeypatch):
    with TestClient(app) as client:
        status = login_as(client, "alice")
        job = write(client, "/api/jobs", job_body(status, requirements_text="熟悉 SQL"))
        job_id = job.json()["id"]
        monkeypatch.setenv("JOB_AI_API_KEY", "")
        monkeypatch.setenv("JOB_AI_BASE_URL", "")
        monkeypatch.setenv("JOB_AI_MODEL", "")
        assert extract(client, job_id).status_code == 503

        monkeypatch.setattr("backend.services.job_analysis.chat_json", lambda *_: "not-json")
        assert extract(client, job_id).status_code == 502

        def failed_model(*_args):
            raise HTTPException(status_code=502, detail="模型服务失败或返回格式不正确，请稍后重试")

        monkeypatch.setattr("backend.services.job_analysis.chat_json", failed_model)
        assert extract(client, job_id).status_code == 502


def test_no_personal_material_reports_no_evidence(auth_db, monkeypatch):
    with TestClient(app) as client:
        status = login_as(client, "alice")
        job = write(client, "/api/jobs", job_body(status, requirements_text="熟悉 SQL"))
        job_id = job.json()["id"]

        def fake_model(_prompt, data):
            if "requirements_text" in data:
                return json.dumps({"items": [{"quote": "熟悉 SQL", "priority": "required"}]})
            assert data["evidence"] == []
            return json.dumps({"items": [{"requirement_index": 0, "status": "no_evidence",
                                         "evidence_ids": [], "reason": "材料中未提及 SQL",
                                         "next_step": "先补充真实技能说明"}]})

        monkeypatch.setattr("backend.services.job_analysis.chat_json", fake_model)
        draft = extract(client, job_id).json()
        result = align(client, job_id, draft["snapshot_version"], draft["items"])
        assert result.status_code == 200, result.text
        assert result.json()["items"][0]["status"] == "no_evidence"
        assert result.json()["items"][0]["evidence"] == []


def test_report_model_error_explains_safe_cause_without_response_body(monkeypatch):
    # 本机 MockTransport 拦截请求；即使回归测试失败，也不会连接真实模型。
    monkeypatch.setenv("JOB_AI_BASE_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("JOB_AI_MODEL", "test-model")
    monkeypatch.setenv("JOB_AI_API_KEY", "fake-key")
    original_client = httpx.Client
    reply = [httpx.Response(400, json={"error": {"message": "PRIVATE_UPSTREAM_BODY"}})]

    def fake_client(*args, **kwargs):
        return original_client(transport=httpx.MockTransport(lambda _request: reply[0]), **kwargs)

    monkeypatch.setattr(job_analysis.httpx, "Client", fake_client)
    with pytest.raises(HTTPException) as invalid_request:
        job_analysis.chat_json("请输出 JSON", {})
    assert invalid_request.value.status_code == 502
    assert "模型配置" in invalid_request.value.detail
    assert "PRIVATE_UPSTREAM_BODY" not in invalid_request.value.detail

    reply[0] = httpx.Response(200, json={"choices": [{"finish_reason": "length",
                                                      "message": {"content": "{}"}}]})
    with pytest.raises(HTTPException) as truncated:
        job_analysis.chat_json("请输出 JSON", {})
    assert "未生成完整" in truncated.value.detail


def test_report_ignores_unused_model_fields_but_rejects_invalid_status(monkeypatch, caplog):
    snapshot = job_analysis.AnalysisSnapshot(
        job_id=1, company_name="测试公司", title="后端", requirements_text="熟悉 SQL",
        evidence=[], resume_used=False, context_limited=False, version="0" * 64)
    requirements = [job_analysis.RequirementDraft(quote="熟悉 SQL", priority="required")]
    item = {"requirement_index": 0, "status": "no_evidence", "evidence_ids": [],
            "reason": "当前材料未提供相关证据", "next_step": "补充真实技能说明", "extra_note": "UNTRUSTED_PRIVATE"}
    monkeypatch.setattr(job_analysis, "chat_json", lambda *_: json.dumps({
        "items": [item], "extra_summary": "UNTRUSTED_PRIVATE"}, ensure_ascii=False))
    result = job_analysis.align_requirements(snapshot, requirements)
    assert result.items[0].status == "no_evidence"
    assert "UNTRUSTED_PRIVATE" not in result.model_dump_json()

    item["status"] = "expert"  # 多余字段可丢弃，关键枚举仍不能放宽。
    with pytest.raises(HTTPException) as invalid:
        job_analysis.align_requirements(snapshot, requirements)
    assert invalid.value.status_code == 502
    assert "status:literal_error" in caplog.text
    assert "UNTRUSTED_PRIVATE" not in caplog.text
