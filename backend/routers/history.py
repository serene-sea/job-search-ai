"""多段教育与项目记录；只允许登录用户读写自己的行。"""

from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import EducationEntry, ProjectEntry, User
from backend.db.session import get_db_session
from backend.routers.auth import check_write_request, get_current_user, utc_now

router = APIRouter(prefix="/api", tags=["history"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db_session)]


def clean(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


def required_text(value: str | None) -> str:
    if value is None or not value.strip():
        raise ValueError("此项不能为空")
    return value.strip()


def validate_dates(values: dict) -> None:
    """年月按实际时间比较；历史迁入行可暂缺月份，但新行必须完整。"""

    if all(values.get(key) is not None for key in ("start_year", "start_month", "end_year", "end_month")):
        start = (values["start_year"], values["start_month"])
        end = (values["end_year"], values["end_month"])
        if end < start:
            raise ValueError("毕业年月不能早于入学年月")


class EducationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school: str = Field(max_length=200)
    major: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=100)
    start_year: int = Field(ge=1900, le=2100)
    start_month: int = Field(ge=1, le=12)
    end_year: int = Field(ge=1900, le=2100)
    end_month: int = Field(ge=1, le=12)
    description: str | None = Field(default=None, max_length=10000)

    @field_validator("school")
    @classmethod
    def clean_school(cls, value: str) -> str:
        return required_text(value)

    @field_validator("major", "degree", "description")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return clean(value)

    @model_validator(mode="after")
    def check_dates(self) -> "EducationCreate":
        validate_dates(self.model_dump())
        return self


class EducationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school: str | None = Field(default=None, max_length=200)
    major: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=100)
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    start_month: int | None = Field(default=None, ge=1, le=12)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    end_month: int | None = Field(default=None, ge=1, le=12)
    description: str | None = Field(default=None, max_length=10000)

    @field_validator("school")
    @classmethod
    def clean_school(cls, value: str | None) -> str:
        return required_text(value)

    @field_validator("major", "degree", "description")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return clean(value)


class EducationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school: str
    major: str | None
    degree: str | None
    start_year: int | None
    start_month: int | None
    end_year: int | None
    end_month: int | None
    description: str | None
    updated_at: datetime


def own_education(db: Session, user_id: int, entry_id: int) -> EducationEntry:
    entry = db.scalar(select(EducationEntry).where(EducationEntry.id == entry_id, EducationEntry.user_id == user_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="教育经历不存在")
    return entry


@router.get("/educations", response_model=list[EducationOut])
def list_educations(user: CurrentUser, db: Database, response: Response) -> list[EducationEntry]:
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(select(EducationEntry).where(EducationEntry.user_id == user.id)
                           .order_by(EducationEntry.end_year.desc(), EducationEntry.id.desc())).all())


@router.post("/educations", response_model=EducationOut, status_code=201,
             dependencies=[Depends(check_write_request)])
def create_education(body: EducationCreate, user: CurrentUser, db: Database) -> EducationEntry:
    entry = EducationEntry(user_id=user.id, updated_at=utc_now(), **body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/educations/{entry_id}", response_model=EducationOut,
              dependencies=[Depends(check_write_request)])
def update_education(entry_id: int, body: EducationPatch, user: CurrentUser, db: Database) -> EducationEntry:
    entry = own_education(db, user.id, entry_id)
    changes = body.model_dump(exclude_unset=True)
    try:
        validate_dates({key: changes.get(key, getattr(entry, key)) for key in
                        ("start_year", "start_month", "end_year", "end_month")})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key, value in changes.items():
        setattr(entry, key, value)
    entry.updated_at = utc_now()
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/educations/{entry_id}", status_code=204,
               dependencies=[Depends(check_write_request)])
def delete_education(entry_id: int, user: CurrentUser, db: Database) -> None:
    db.delete(own_education(db, user.id, entry_id))
    db.commit()


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)
    summary: str | None = Field(default=None, max_length=10000)
    source_url: str | None = Field(default=None, max_length=1000)
    highlights: str | None = Field(default=None, max_length=10000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return required_text(value)

    @field_validator("summary", "highlights")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return clean(value)

    @field_validator("source_url")
    @classmethod
    def clean_url(cls, value: str | None) -> str | None:
        value = clean(value)
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("在线链接必须以 http:// 或 https:// 开头")
        return value


class ProjectPatch(ProjectCreate):
    name: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str:
        return required_text(value)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    summary: str | None
    source_url: str | None
    highlights: str | None
    updated_at: datetime


def own_project(db: Session, user_id: int, entry_id: int) -> ProjectEntry:
    entry = db.scalar(select(ProjectEntry).where(ProjectEntry.id == entry_id, ProjectEntry.user_id == user_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return entry


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(user: CurrentUser, db: Database, response: Response) -> list[ProjectEntry]:
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(select(ProjectEntry).where(ProjectEntry.user_id == user.id)
                           .order_by(ProjectEntry.id.desc())).all())


@router.post("/projects", response_model=ProjectOut, status_code=201,
             dependencies=[Depends(check_write_request)])
def create_project(body: ProjectCreate, user: CurrentUser, db: Database) -> ProjectEntry:
    entry = ProjectEntry(user_id=user.id, updated_at=utc_now(), **body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/projects/{entry_id}", response_model=ProjectOut,
              dependencies=[Depends(check_write_request)])
def update_project(entry_id: int, body: ProjectPatch, user: CurrentUser, db: Database) -> ProjectEntry:
    entry = own_project(db, user.id, entry_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    entry.updated_at = utc_now()
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/projects/{entry_id}", status_code=204,
               dependencies=[Depends(check_write_request)])
def delete_project(entry_id: int, user: CurrentUser, db: Database) -> None:
    db.delete(own_project(db, user.id, entry_id))
    db.commit()
