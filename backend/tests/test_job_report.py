"""用假模型检查：报告是单篇正文，引用编号只供后端校验。"""

import json

from backend.services import job_report
from backend.services.job_analysis import AnalysisItem, Evidence, JobAnalysisResult


def fake_alignment() -> JobAnalysisResult:
    return JobAnalysisResult(job_id=7, company_name="甲公司", title="后端", resume_used=False,
                             context_limited=False, items=[
        AnalysisItem(quote="熟悉 SQL", priority="required", status="partial",
                     evidence=[Evidence(id="skill:1", kind="skill", text="会基础 SQL，缺少事务实践")],
                     reason="有基础查询经验，事务实践不足", next_step="完成事务练习"),
        AnalysisItem(quote="有三年开发经验", priority="required", status="no_evidence",
                     evidence=[], reason="材料未提供工作年限", next_step="核实岗位门槛"),
    ])


REPORT = """岗位拆解
原文要求 SQL 和开发经验，具体方向仍需看完整职位描述。
你的现状盘点
技能自评提到基础 SQL，事务实践不足；工作年限在本次材料中未见。
差距分析
先补事务练习。年限要求需与招聘方核实，不能假设已经满足。
简历优化方案
只写确实完成的 SQL 练习和项目，不填未做过的经历。
投递与面试策略
先核实官网岗位是否开放；准备事务相关技术问题。
行动计划
今天核实要求，本周完成练习，面试前复盘真实项目。"""


def test_single_report_text_hides_internal_ids(monkeypatch):
    def fake_model(_prompt, payload, *, max_tokens):
        assert max_tokens == 2200
        assert payload["evidence"][0]["id"] == "skill:1"
        assert "focus" not in payload and "question" not in payload
        return json.dumps({"report_text": REPORT, "used_evidence_ids": ["skill:1"]}, ensure_ascii=False)

    monkeypatch.setattr(job_report, "chat_json", fake_model)
    guide = job_report.build_guide(fake_alignment())
    assert not guide.limited
    assert guide.text == REPORT
    assert guide.used_evidence_ids == ["skill:1"]
    assert "skill:1" not in guide.text


def test_bad_report_or_reference_is_marked_limited(monkeypatch):
    responses = [
        {"report_text": REPORT, "used_evidence_ids": ["resume:999"]},
        {"report_text": REPORT.replace("行动计划", "后续安排"), "used_evidence_ids": []},
        {"report_text": REPORT + "\n证据：skill:1", "used_evidence_ids": ["skill:1"]},
    ]
    for response in responses:
        monkeypatch.setattr(job_report, "chat_json", lambda *_args, **_kwargs: json.dumps(response, ensure_ascii=False))
        guide = job_report.build_guide(fake_alignment())
        assert guide.limited
        assert "skill:1" not in guide.text and "resume:999" not in guide.text


def test_invalid_shape_is_marked_limited(monkeypatch):
    monkeypatch.setattr(job_report, "chat_json", lambda *_args, **_kwargs: '{"wrong":"shape"}')
    guide = job_report.build_guide(fake_alignment())
    assert guide.limited
    assert guide.used_evidence_ids == []
