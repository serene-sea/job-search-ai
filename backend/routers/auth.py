"""注册、登录和退出。个人资料接口以后都要复用这里的当前用户检查。"""

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.models import AuthSession, JobStatus, User
from backend.db.session import get_db_session

router = APIRouter(prefix="/api", tags=["account"])
# 密码只交给这个工具生成和核对摘要，不保存用户输入的原文。
password_hasher = PasswordHash.recommended()
# 浏览器只把这个 Cookie 发送到 /api 路径；有效期为七天。
cookie_name = "job_session"
cookie_path = "/api"
session_lifetime = timedelta(days=7)
# 只是初始选项；岗位可跳过任何环节，后续也能自定义状态。
default_statuses = (
    "想投",
    "准备投递",
    "已投",
    "准备测评",
    "已测评",
    "准备笔试",
    "已笔试",
    "准备面试",
    "已一面",
    "已二面",
    "已终面",
    "等待结果",
    "收到 Offer",
    "未通过",
    "已放弃",
)
username_pattern = re.compile(r"^[a-z0-9_]+$")


def utc_now() -> datetime:
    """MySQL 的 DATETIME 不带时区，统一用 UTC 写入和比较。"""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_hash(token: str) -> str:
    """数据库只存令牌的摘要；拿到数据库内容也不能直接当 Cookie 使用。"""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LoginInput(BaseModel):
    """后端再次检查输入，不能把浏览器里的检查当作唯一防线。"""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        # 注册与登录都用同一写法查用户名：去空格并转成小写。
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str) -> str:
        if not username_pattern.fullmatch(value):
            raise ValueError("用户名只支持字母、数字和下划线")
        return value


class RegisterInput(LoginInput):
    """注册比登录多一个要求：新密码至少 12 位。"""

    password: str = Field(min_length=12, max_length=128)


class UserInfo(BaseModel):
    """只把编号和用户名返回页面，密码摘要不会出现在响应中。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


@dataclass
class CurrentAuth:
    user: User
    login_session: AuthSession


def _check_write_request(request: Request, accepted_type: str) -> None:
    """JSON 与上传共用来源检查，仅各自允许预期的内容类型。"""

    # 页面提交时带 Origin、自定义请求头和预期类型；少一项就拒绝。
    allowed = {
        item.strip()
        for item in os.getenv(
            "AUTH_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if item.strip()
    }
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if (
        request.headers.get("origin") not in allowed
        or request.headers.get("x-job-app-request") != "1"
        or content_type != accepted_type
    ):
        raise HTTPException(status_code=403, detail="请求来源未通过检查")


def check_write_request(request: Request) -> None:
    """普通 JSON 写请求的来源检查。"""

    _check_write_request(request, "application/json")


def check_upload_request(request: Request) -> None:
    """文件上传使用 multipart；仍须来自本站并带自定义头。"""

    _check_write_request(request, "multipart/form-data")


def get_current_auth(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
) -> CurrentAuth:
    """用 Cookie 找到仍有效的登录记录，再从服务端确定用户身份。"""

    token = request.cookies.get(cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")

    # 把 Cookie 中的随机令牌算成摘要，再找数据库中未撤销、未过期的记录。
    login_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
    )
    if login_session is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    # 用户编号来自查到的会话，不接受浏览器自行填写的编号。
    user = db.get(User, login_session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return CurrentAuth(user=user, login_session=login_session)


def get_current_user(auth: Annotated[CurrentAuth, Depends(get_current_auth)]) -> User:
    """业务接口依赖它即可获得已核实的用户，而不是相信前端传来的用户 ID。"""

    return auth.user


@router.post("/auth/register", response_model=UserInfo, status_code=201, dependencies=[Depends(check_write_request)])
def register(body: RegisterInput, db: Annotated[Session, Depends(get_db_session)]) -> User:
    # 先给“用户名已存在”一个清楚的提示；数据库唯一约束仍会兜底。
    if db.scalar(select(User.id).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 注册只存密码摘要，不在这里创建登录会话。
    user = User(username=body.username, password_hash=password_hasher.hash(body.password))
    try:
        # 用户和默认状态一起保存；中途失败时一个都不留下。
        db.add(user)
        # 先取得新用户编号，下面的默认状态才能关联到这个用户。
        db.flush()
        db.add_all(
            JobStatus(user_id=user.id, name=name, sort_order=order)
            for order, name in enumerate(default_statuses, start=1)
        )
        db.commit()
    except IntegrityError as exc:
        # 写入失败后撤销本次未完成的改动。
        db.rollback()
        # 并发注册也可能在插入时撞上用户名唯一约束。
        if db.scalar(select(User.id).where(User.username == body.username)) is not None:
            raise HTTPException(status_code=409, detail="用户名已存在") from exc
        raise HTTPException(status_code=500, detail="注册失败，请稍后再试") from exc
    return user


@router.post("/auth/login", response_model=UserInfo, dependencies=[Depends(check_write_request)])
def login(
    body: LoginInput,
    response: Response,
    db: Annotated[Session, Depends(get_db_session)],
) -> User:
    # 用同一个错误回复“用户名不存在”和“密码错误”，避免暴露账号是否存在。
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not password_hasher.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 每次登录生成新的随机令牌；数据库只存它的摘要。
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=utc_now() + session_lifetime,
        )
    )
    # 会话记录存好之后，才把原令牌写进浏览器 Cookie。
    db.commit()
    # Cookie 只在会话保存成功后发出；前端脚本读不到其中的令牌。
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=int(session_lifetime.total_seconds()),
        path=cookie_path,
        httponly=True,
        secure=os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
    )
    return user


@router.get("/me", response_model=UserInfo)
def me(user: Annotated[User, Depends(get_current_user)], response: Response) -> User:
    # get_current_user 已确认 Cookie 有效；这里返回页面需要的用户信息。
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/auth/logout", status_code=204, dependencies=[Depends(check_write_request)])
def logout(
    response: Response,
    auth: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[Session, Depends(get_db_session)],
) -> None:
    # 先在数据库中标记会话失效，再让浏览器删掉 Cookie。
    auth.login_session.revoked_at = utc_now()
    db.commit()
    response.delete_cookie(key=cookie_name, path=cookie_path)
