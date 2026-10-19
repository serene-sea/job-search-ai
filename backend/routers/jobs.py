"""个人岗位与状态接口；每次读写都以服务端确认的用户为边界。"""

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.models import Job, JobStatus, User
from backend.db.session import get_db_session
from backend.routers.auth import check_write_request, get_current_user

router = APIRouter(prefix="/api", tags=["jobs"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db_session)]


def clean_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("不能为空或只填空格")
    return cleaned


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def clean_url(value: str | None) -> str | None:
    value = clean_optional(value)
    if value is None:
        return None
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ValueError("链接格式不正确") from exc
    # 只核对输入格式，不访问网页，更不据此判断招聘真假或是否过期。
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("链接须以 http:// 或 https:// 开头")
    return value


class StatusCreate(BaseModel):
    name: str = Field(max_length=100)
    sort_order: int = Field(ge=1, le=10000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required(value)


class StatusPatch(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    sort_order: int | None = Field(default=None, ge=1, le=10000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("状态名称不能为空")
        return clean_required(value)


class StatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class JobFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(max_length=200)
    title: str = Field(max_length=200)
    location: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    requirements_text: str | None = Field(default=None, max_length=30000)
    notes: str | None = Field(default=None, max_length=10000)
    status_id: int = Field(gt=0)

    @field_validator("company_name", "title")
    @classmethod
    def normalize_required(cls, value: str) -> str:
        return clean_required(value)

    @field_validator("location", "requirements_text", "notes")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @field_validator("source_url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        return clean_url(value)


class JobPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    requirements_text: str | None = Field(default=None, max_length=30000)
    notes: str | None = Field(default=None, max_length=10000)
    status_id: int | None = Field(default=None, gt=0)

    @field_validator("company_name", "title")
    @classmethod
    def normalize_required(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("公司名和岗位名不能为空")
        return clean_required(value)

    @field_validator("location", "requirements_text", "notes")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @field_validator("source_url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        return clean_url(value)


class JobOut(JobFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status_name: str


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class CompanyGroupOut(BaseModel):
    company_name: str
    total: int


def owned_status(db: Session, user_id: int, status_id: int) -> JobStatus:
    # 必须同时查 id 和 user_id；单靠状态编号无法证明它属于当前账号。
    status = db.scalar(select(JobStatus).where(JobStatus.id == status_id, JobStatus.user_id == user_id))
    if status is None:
        raise HTTPException(status_code=404, detail="状态不存在")
    return status


def owned_job(db: Session, user_id: int, job_id: int) -> Job:
    # 对不属于当前用户的编号统一返回 404，避免暴露别人的岗位是否存在。
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return job


def job_output(job: Job, status_name: str) -> JobOut:
    return JobOut.model_validate({
        "id": job.id,
        "company_name": job.company_name,
        "title": job.title,
        "location": job.location,
        "source_url": job.source_url,
        "requirements_text": job.requirements_text,
        "notes": job.notes,
        "status_id": job.status_id,
        "status_name": status_name,
    })


@router.get("/job-statuses", response_model=list[StatusOut])
def list_statuses(user: CurrentUser, db: Database) -> list[JobStatus]:
    return list(db.scalars(
        select(JobStatus).where(JobStatus.user_id == user.id).order_by(JobStatus.sort_order, JobStatus.id)
    ).all())


@router.post("/job-statuses", response_model=StatusOut, status_code=201,
             dependencies=[Depends(check_write_request)])
def create_status(body: StatusCreate, user: CurrentUser, db: Database) -> JobStatus:
    status = JobStatus(user_id=user.id, **body.model_dump())
    db.add(status)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该状态名称已存在") from None
    db.refresh(status)
    return status


@router.patch("/job-statuses/{status_id}", response_model=StatusOut,
              dependencies=[Depends(check_write_request)])
def update_status(status_id: int, body: StatusPatch, user: CurrentUser, db: Database) -> JobStatus:
    status = owned_status(db, user.id, status_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail="状态字段不能为空")
        setattr(status, key, value)
    try:
        # 改名或排序只更新状态字典；岗位仍引用同一状态编号。
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该状态名称已存在") from None
    db.refresh(status)
    return status


@router.delete("/job-statuses/{status_id}", status_code=204,
               dependencies=[Depends(check_write_request)])
def delete_status(status_id: int, user: CurrentUser, db: Database) -> None:
    status = owned_status(db, user.id, status_id)
    if db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user.id, Job.status_id == status_id)):
        raise HTTPException(status_code=409, detail="该状态仍被岗位使用，请先修改相关岗位")
    if db.scalar(select(func.count()).select_from(JobStatus).where(JobStatus.user_id == user.id)) <= 1:
        raise HTTPException(status_code=409, detail="至少保留一个状态")
    db.delete(status)
    try:
        db.commit()
    except IntegrityError:
        # 计数和删除之间可能有另一请求创建岗位；外键会挡住删除。
        db.rollback()
        raise HTTPException(status_code=409, detail="该状态已被岗位使用，请刷新后重试") from None


@router.get("/jobs/companies", response_model=list[CompanyGroupOut])
def company_groups(user: CurrentUser, db: Database) -> list[CompanyGroupOut]:
    # SQL 的 GROUP BY 只汇总本人岗位；公司名不再依赖独立 companies 表。
    rows = db.execute(
        select(
            Job.company_name,
            func.count(Job.id).label("total"),
        )
        .where(Job.user_id == user.id)
        .group_by(Job.company_name)
        .order_by(Job.company_name)
    ).all()
    return [CompanyGroupOut(company_name=name, total=total) for name, total in rows]


@router.get("/jobs", response_model=JobListOut)
def list_jobs(
    user: CurrentUser,
    db: Database,
    company_name: Annotated[str | None, Query(max_length=200)] = None,
    status_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListOut:
    # 每个列表筛选条件都从 user_id 开始；浏览器无法指定别人的 user_id。
    filters = [Job.user_id == user.id]
    if company_name is not None:
        if not company_name.strip():
            raise HTTPException(status_code=422, detail="公司名不能为空")
        filters.append(Job.company_name == company_name.strip())
    if status_id is not None:
        filters.append(Job.status_id == status_id)
    # 总数不加 limit/offset，前端才能知道是否还有下一页；下面的 rows 才是当前页。
    total = db.scalar(select(func.count()).select_from(Job).where(*filters)) or 0
    rows = db.execute(
        select(Job, JobStatus.name)
        # 同时匹配状态编号与用户编号，取到的状态名称才属于这条岗位的主人。
        .join(JobStatus, (Job.status_id == JobStatus.id) & (Job.user_id == JobStatus.user_id))
        .where(*filters)
        .order_by(Job.company_name, Job.id.desc())
        .limit(limit).offset(offset)
    ).all()
    return JobListOut(items=[job_output(job, name) for job, name in rows],
                      total=total, limit=limit, offset=offset)


@router.post("/jobs", response_model=JobOut, status_code=201,
             dependencies=[Depends(check_write_request)])
def create_job(body: JobFields, user: CurrentUser, db: Database) -> JobOut:
    # 先确认前端选的状态属于当前登录账号；岗位的 user_id 只取服务端会话，不信任表单。
    status = owned_status(db, user.id, body.status_id)
    job = Job(user_id=user.id, **body.model_dump())
    db.add(job)
    # 岗位及其状态引用在同一事务提交；失败就不留下半条记录。
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 状态可能恰在提交前被另一请求删除；不把数据库异常显示给页面。
        raise HTTPException(status_code=409, detail="状态已变化，请刷新后重试") from None
    db.refresh(job)
    return job_output(job, status.name)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: CurrentUser, db: Database) -> JobOut:
    job = owned_job(db, user.id, job_id)
    return job_output(job, owned_status(db, user.id, job.status_id).name)


@router.patch("/jobs/{job_id}", response_model=JobOut,
              dependencies=[Depends(check_write_request)])
def update_job(job_id: int, body: JobPatch, user: CurrentUser, db: Database) -> JobOut:
    job = owned_job(db, user.id, job_id)
    # PATCH 只修改请求中出现的字段；未传的字段保持原值。
    changes = body.model_dump(exclude_unset=True)
    if any(changes.get(key, 1) is None for key in ("company_name", "title", "status_id")):
        raise HTTPException(status_code=422, detail="公司、岗位和状态不能为空")
    if "status_id" in changes:
        # 换状态也必须重新检查归属，不能把岗位指向其他用户的状态。
        owned_status(db, user.id, changes["status_id"])
    for key, value in changes.items():
        setattr(job, key, value)
    try:
        db.commit()
    except IntegrityError:
        # 状态可能在归属检查后被删除；回滚避免把半次修改留下。
        db.rollback()
        raise HTTPException(status_code=409, detail="状态已变化，请刷新后重试") from None
    db.refresh(job)
    return job_output(job, owned_status(db, user.id, job.status_id).name)


@router.delete("/jobs/{job_id}", status_code=204,
               dependencies=[Depends(check_write_request)])
def delete_job(job_id: int, user: CurrentUser, db: Database) -> None:
    db.delete(owned_job(db, user.id, job_id))
    db.commit()
