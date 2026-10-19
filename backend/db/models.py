"""账号、岗位，以及按登录用户隔离的个人资料映射。"""

from datetime import date, datetime
# sqlalchemy 是 SQLAlchemy ORM 的核心包，提供了数据库类型、约束、索引等功能。
from sqlalchemy import (
    DateTime,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    CheckConstraint,
    JSON,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from backend.db.base import Base


class User(Base):
    """一个账号一行；用户名唯一，密码只保存核对用的摘要。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # 注册阶段只写入强哈希值；明文密码绝不能写入此列。
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class AuthSession(Base):
    """一次登录一行；退出或到期后，这一行不能再用于访问账号。"""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 通过这个编号知道当前登录记录属于哪个用户。
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # 只保存随机会话令牌的哈希；浏览器 Cookie 中的原令牌不会落库。
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # MySQL DATETIME 不带时区；后续鉴权代码统一写入/读取 UTC 时间。
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    # 退出时写入时间；不删除记录，也能明确知道令牌已失效。
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime())

    __table_args__ = (Index("ix_auth_sessions_user_id_expires_at", "user_id", "expires_at"),)


class JobStatus(Base):
    __tablename__ = "job_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        UniqueConstraint("user_id", "name"),
        Index("ix_job_statuses_user_id_sort_order", "user_id", "sort_order"),
    )


class Job(Base):
    """每条岗位只属于一个账号；同公司、同名岗位仍可分别保存。"""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 每行只保存一个所属账号编号；所有按 ID 的读写仍必须加 user_id 条件。
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    # 链接只是用户记录的参考，不代表岗位已核实或仍在招聘。
    source_url: Mapped[str | None] = mapped_column(Text())
    # 招聘要求与私人想法分开，后续 AI 能清楚区分用户抄录的岗位文字与个人备注。
    requirements_text: Mapped[str | None] = mapped_column(Text())
    notes: Mapped[str | None] = mapped_column(Text())
    status_id: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        # 两列必须同时匹配同一条状态记录；不能借用另一账号的 status_id。
        ForeignKeyConstraint(["status_id", "user_id"], ["job_statuses.id", "job_statuses.user_id"]),
        # 常用筛选先限定本人，再按公司名定位岗位。
        Index("ix_jobs_user_id_company_name", "user_id", "company_name"),
        # MySQL 的复合外键需要以 status_id、user_id 为前缀的子表索引。
        Index("ix_jobs_status_id_user_id", "status_id", "user_id"),
    )


class Profile(Base):
    """一个账号最多一行；user_id 同时是主键和账号外键。"""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    school: Mapped[str | None] = mapped_column(String(200))
    major: Mapped[str | None] = mapped_column(String(200))
    degree: Mapped[str | None] = mapped_column(String(100))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    target_roles: Mapped[str | None] = mapped_column(String(500))
    education_text: Mapped[str | None] = mapped_column(Text())
    experience_text: Mapped[str | None] = mapped_column(Text())
    birth_date: Mapped[date | None] = mapped_column(Date())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class EducationEntry(Base):
    """一位用户可有多段教育经历；年月分列，旧资料缺少月份时不编造日期。"""

    __tablename__ = "education_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    school: Mapped[str] = mapped_column(String(200), nullable=False)
    major: Mapped[str | None] = mapped_column(String(200))
    degree: Mapped[str | None] = mapped_column(String(100))
    start_year: Mapped[int | None] = mapped_column(Integer)
    start_month: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer)
    end_month: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    __table_args__ = (
        CheckConstraint("start_month IS NULL OR start_month BETWEEN 1 AND 12", name="education_start_month_range"),
        CheckConstraint("end_month IS NULL OR end_month BETWEEN 1 AND 12", name="education_end_month_range"),
        Index("ix_education_entries_user_id", "user_id"),
    )


class ProjectEntry(Base):
    """用户自己录入的项目事实；链接和亮点不会由应用自动补写。"""

    __tablename__ = "project_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text())
    source_url: Mapped[str | None] = mapped_column(String(1000))
    highlights: Mapped[str | None] = mapped_column(Text())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    __table_args__ = (Index("ix_project_entries_user_id", "user_id"),)


class Skill(Base):
    """一人多技能；能力档位和重要性保留整数，界面再翻译成中文。"""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    proficiency: Mapped[int] = mapped_column(Integer, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("proficiency BETWEEN 0 AND 4", name="proficiency_range"),
        CheckConstraint("importance BETWEEN 1 AND 5", name="importance_range"),
        Index("ix_skills_user_id_importance", "user_id", "importance"),
    )


class Resume(Base):
    """一人只保留当前简历文本；原始上传文件不长期存储。"""

    __tablename__ = "resumes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    source_format: Mapped[str | None] = mapped_column(String(10))
    # 修订稿不能覆盖提取原文；MySQL MEDIUMTEXT 容纳常见简历的 UTF-8 文本。
    raw_extracted_text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    reviewed_text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class ChatSession(Base):
    """普通会话或绑定一个岗位的会话；岗位删除后历史报告仍可保留。"""

    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
        Index("ix_chat_sessions_job_id", "job_id"),
    )


class ChatMessage(Base):
    """报告保留结构化结果；普通文本与生成状态仍分别存储。"""

    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    report_json: Mapped[dict | None] = mapped_column(JSON())
    snapshot_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["session_id", "user_id"], ["chat_sessions.id", "chat_sessions.user_id"], ondelete="CASCADE"),
        Index("ix_chat_messages_session_id", "session_id", "id"),
        Index("ix_chat_messages_session_user", "session_id", "user_id"),
    )


class GenerationRun(Base):
    """每次追问一行，记录流式生成的成功、失败或主动中断。"""

    __tablename__ = "generation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), nullable=False)
    assistant_message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    # 每次提问所选的资料类别；旧记录为 NULL，不能据此推断曾授权哪些资料。
    source_scope: Mapped[list[str] | None] = mapped_column(JSON())
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime())

    __table_args__ = (
        ForeignKeyConstraint(["session_id", "user_id"], ["chat_sessions.id", "chat_sessions.user_id"], ondelete="CASCADE"),
        UniqueConstraint("user_id", "request_key"),
        Index("ix_generation_runs_session_status", "session_id", "status"),
        Index("ix_generation_runs_session_user", "session_id", "user_id"),
        Index("ix_generation_runs_user_message_id", "user_message_id"),
        Index("ix_generation_runs_assistant_message_id", "assistant_message_id"),
    )
