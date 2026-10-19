"""个人资料和技能：所有归属都由登录会话确定。"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.models import Profile, Skill, User
from backend.db.session import get_db_session
from backend.routers.auth import check_write_request, get_current_user, utc_now

router = APIRouter(prefix="/api", tags=["personal"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db_session)]


def trimmed(value: str | None) -> str | None:
    """空白输入统一按未填写处理，免得数据库出现看不见的值。"""

    return value.strip() or None if value is not None else None


class ProfileFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school: str | None = Field(default=None, max_length=200)
    major: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=100)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    target_roles: str | None = Field(default=None, max_length=500)
    education_text: str | None = Field(default=None, max_length=10000)
    experience_text: str | None = Field(default=None, max_length=15000)

    @field_validator("school", "major", "degree", "target_roles", "education_text", "experience_text")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return trimmed(value)

class ProfileOut(ProfileFields):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime | None = None


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: Database, response: Response) -> ProfileOut | Profile:
    response.headers["Cache-Control"] = "no-store"
    # 不需要账号主动建立空资料；未保存过时返回空表单结构。
    return db.get(Profile, user.id) or ProfileOut()


@router.patch("/profile", response_model=ProfileOut, dependencies=[Depends(check_write_request)])
def save_profile(body: ProfileFields, user: CurrentUser, db: Database) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, updated_at=utc_now())
        db.add(profile)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    profile.updated_at = utc_now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 同一账号的并发首次保存可能撞上 user_id 主键。
        raise HTTPException(status_code=409, detail="资料已变化，请刷新后重试") from None
    db.refresh(profile)
    return profile


class SkillFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=100)
    proficiency: int = Field(ge=0, le=4)
    importance: int = Field(ge=1, le=5)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("技能名称不能为空")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return trimmed(value)


class SkillPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=100)
    proficiency: int | None = Field(default=None, ge=0, le=4)
    importance: int | None = Field(default=None, ge=1, le=5)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("技能名称不能为空")
        return value.strip()

    @field_validator("proficiency", "importance")
    @classmethod
    def required_number(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("掌握程度和重要性不能为空")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return trimmed(value)


class SkillOut(SkillFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime


def own_skill(db: Session, user_id: int, skill_id: int) -> Skill:
    # 主键只表示一行，不能证明它属于本人；每次按编号操作都追加 user_id。
    skill = db.scalar(select(Skill).where(Skill.id == skill_id, Skill.user_id == user_id))
    if skill is None:
        raise HTTPException(status_code=404, detail="技能不存在")
    return skill


@router.get("/skills", response_model=list[SkillOut])
def list_skills(user: CurrentUser, db: Database, response: Response) -> list[Skill]:
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(
        select(Skill).where(Skill.user_id == user.id).order_by(Skill.importance.desc(), Skill.id)
    ).all())


@router.post("/skills", response_model=SkillOut, status_code=201,
             dependencies=[Depends(check_write_request)])
def create_skill(body: SkillFields, user: CurrentUser, db: Database) -> Skill:
    skill = Skill(user_id=user.id, updated_at=utc_now(), **body.model_dump())
    db.add(skill)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该技能名称已存在") from None
    db.refresh(skill)
    return skill


@router.get("/skills/{skill_id}", response_model=SkillOut)
def get_skill(skill_id: int, user: CurrentUser, db: Database) -> Skill:
    return own_skill(db, user.id, skill_id)


@router.patch("/skills/{skill_id}", response_model=SkillOut,
              dependencies=[Depends(check_write_request)])
def update_skill(skill_id: int, body: SkillPatch, user: CurrentUser, db: Database) -> Skill:
    skill = own_skill(db, user.id, skill_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(skill, key, value)
    skill.updated_at = utc_now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该技能名称已存在") from None
    db.refresh(skill)
    return skill


@router.delete("/skills/{skill_id}", status_code=204,
               dependencies=[Depends(check_write_request)])
def delete_skill(skill_id: int, user: CurrentUser, db: Database) -> None:
    db.delete(own_skill(db, user.id, skill_id))
    db.commit()
