"""按本次勾选项读取本人记录，并压缩成可追溯的模型上下文。"""

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import EducationEntry, Job, Profile, ProjectEntry, Resume, Skill

SOURCE_ORDER = ("profile", "education", "projects", "skills", "resume")
SOURCE_LABELS = {
    "profile": "基本信息", "education": "教育经历", "projects": "项目经历",
    "skills": "技能", "resume": "已确认简历", "job": "当前岗位及已保存报告",
}
MAX_CONTEXT_CHARS = 22000
CATEGORY_CHAR_BUDGET = {"job": 8000, "resume": 4000, "skills": 3500,
                        "projects": 3500, "education": 2000, "profile": 1000}


def _year_month(year: int | None, month: int | None) -> str:
    if year is None:
        return "未填写"
    return f"{year}年{month}月" if month is not None else f"{year}年"


def build_personal_context(db: Session, user_id: int, sources: list[str], *,
                           job_id: int | None = None, report: dict | None = None) -> str:
    """只取本次勾选的本人资料；关联岗位由会话带入，不能由模型指定。"""

    selected = set(sources)
    items: list[dict[str, str]] = []
    notices: list[str] = []
    used = 0
    used_by_source = {key: 0 for key in CATEGORY_CHAR_BUDGET}
    limited = False

    def add(source: str, record_id: str, text: str) -> None:
        nonlocal used, limited
        content = text.strip()
        if not content:
            return
        # 每类保留一份预算，避免默认全选时前几类占满窗口、简历或岗位完全消失。
        remaining = min(MAX_CONTEXT_CHARS - used, CATEGORY_CHAR_BUDGET[source] - used_by_source[source])
        if remaining <= 0:
            limited = True
            return
        if len(content) > remaining:
            content = content[:remaining]
            limited = True
        # 每条资料带上来源编号，回答提到某段经历时才有地方可核对。
        items.append({"id": record_id, "category": SOURCE_LABELS[source], "text": content})
        used += len(content)
        used_by_source[source] += len(content)

    # 关联岗位属于当前会话的上下文；先放入岗位，避免其他类别抢占全部长度预算。
    if job_id is not None:
        job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
        if job is None:
            raise HTTPException(status_code=404, detail="岗位不存在")
        add("job", f"job:{job.id}", "；".join(filter(None, [
            f"公司（用户录入）：{job.company_name}", f"岗位（用户录入）：{job.title}",
            f"地点：{job.location}" if job.location else "",
            f"招聘要求原文：{job.requirements_text[:4500]}" if job.requirements_text else "",
            f"个人备注：{job.notes[:500]}" if job.notes else "",
        ])))
        if job.requirements_text and len(job.requirements_text) > 4500:
            limited = True
        if report is not None:
            # 上层先按个人勾选范围过滤报告，避免历史证据绕过本次选择。
            report_text = json.dumps(report, ensure_ascii=False)
            add("job", f"report:{job.id}", "历史 AI 岗位报告（需重新核对）：" + report_text[:3500])
            if len(report_text) > 3500:
                limited = True

    profile = db.get(Profile, user_id) if selected & {"profile", "education"} else None
    if "profile" in selected:
        if profile is None:
            notices.append("基本信息尚未填写")
        else:
            add("profile", "profile:basic", "；".join(filter(None, [
                f"目标岗位：{profile.target_roles}" if profile.target_roles else "",
                f"预计毕业年份：{profile.graduation_year}" if profile.graduation_year else "",
                f"经历：{profile.experience_text[:2200]}" if profile.experience_text else "",
            ])))

    if "education" in selected:
        entries = db.scalars(select(EducationEntry).where(EducationEntry.user_id == user_id)
                             .order_by(EducationEntry.id).limit(11)).all()
        for entry in entries[:10]:
            dates = f"{_year_month(entry.start_year, entry.start_month)}—{_year_month(entry.end_year, entry.end_month)}"
            add("education", f"education:{entry.id}", "；".join(filter(None, [
                entry.school, entry.major, entry.degree, dates, (entry.description or "")[:450],
            ])))
        if len(entries) > 10:
            limited = True
        if not entries and profile is not None:
            # 旧资料只有 profiles 的教育字段；独立教育记录存在时避免重复发送。
            add("education", "profile:education", "；".join(filter(None, [
                profile.school, profile.major, profile.degree, (profile.education_text or "")[:1200],
            ])))
        if not entries and profile is None:
            notices.append("教育经历尚未填写")

    if "projects" in selected:
        entries = db.scalars(select(ProjectEntry).where(ProjectEntry.user_id == user_id)
                             .order_by(ProjectEntry.id).limit(11)).all()
        for entry in entries[:10]:
            add("projects", f"project:{entry.id}", "；".join(filter(None, [
                entry.name, (entry.summary or "")[:500], (entry.highlights or "")[:500],
                f"本人填写链接：{entry.source_url[:300]}" if entry.source_url else "",
            ])))
        if len(entries) > 10:
            limited = True
        if not entries:
            notices.append("项目经历尚未填写")

    if "skills" in selected:
        entries = db.scalars(select(Skill).where(Skill.user_id == user_id)
                             .order_by(Skill.importance.desc(), Skill.id).limit(26)).all()
        proficiency = ("不了解", "了解", "掌握", "熟悉", "完全掌握")
        for entry in entries[:25]:
            degree = proficiency[entry.proficiency] if 0 <= entry.proficiency < 5 else "未标注"
            add("skills", f"skill:{entry.id}", f"{entry.name}；自评：{degree}；说明：{(entry.description or '')[:350]}")
        if len(entries) > 25:
            limited = True
        if not entries:
            notices.append("技能尚未填写")

    if "resume" in selected:
        resume = db.scalar(select(Resume).where(Resume.user_id == user_id,
                                                Resume.confirmed_at.is_not(None)))
        if resume is None or not resume.reviewed_text.strip():
            notices.append("没有已确认的简历文字，本次未发送简历")
        else:
            text = resume.reviewed_text.strip()
            add("resume", "resume:confirmed", text[:4000])
            if len(text) > 4000:
                limited = True

    # 没选、没填或超出长度上限，都不能理解成“用户没有这项能力”。
    if not items:
        notices.append("所选范围没有可用记录；不能据此推断用户没有相关经历或能力")
    if limited:
        notices.append("材料超出本次长度或条数上限；未展示的内容不能推断为不存在")
    categories = [SOURCE_LABELS[key] for key in SOURCE_ORDER if key in selected]
    if job_id is not None:
        categories.append("当前岗位")
    return json.dumps({"selected_categories": categories,
                       "records": items, "notices": notices}, ensure_ascii=False)
