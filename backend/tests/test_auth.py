"""登录接口测试：只用样例账号，不连接或修改用户的真实 MySQL 数据。"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.models import AuthSession, JobStatus, User
from backend.db.session import get_db_session
from backend.main import app
from backend.routers.auth import utc_now

write_headers = {"Origin": "http://testserver", "X-Job-App-Request": "1"}


@pytest.fixture
def auth_db(monkeypatch: pytest.MonkeyPatch):
    """每个测试使用一份全新的内存库，避免账号和会话互相影响。"""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = override_db
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    try:
        yield session_factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def post(client: TestClient, path: str, body: dict):
    return client.post(path, json=body, headers=write_headers)


def test_register_login_me_logout(auth_db):
    with TestClient(app) as client:
        assert client.get("/api/me").status_code == 401

        registered = post(
            client, "/api/auth/register", {"username": "  Alice  ", "password": "a-long-password-123"}
        )
        assert registered.status_code == 201
        assert registered.json() == {"id": 1, "username": "alice"}
        assert post(
            client, "/api/auth/register", {"username": "alice", "password": "another-password-123"}
        ).status_code == 409

        with auth_db() as db:
            user = db.scalar(select(User).where(User.username == "alice"))
            assert user is not None
            assert user.password_hash != "a-long-password-123"
            assert user.password_hash.startswith("$argon2id$")
            assert db.scalars(
                select(JobStatus.name).where(JobStatus.user_id == user.id).order_by(JobStatus.sort_order)
            ).all() == [
                "想投", "准备投递", "已投", "准备测评", "已测评", "准备笔试", "已笔试",
                "准备面试", "已一面", "已二面", "已终面", "等待结果", "收到 Offer", "未通过", "已放弃",
            ]

        wrong = post(client, "/api/auth/login", {"username": "alice", "password": "wrong"})
        missing = post(client, "/api/auth/login", {"username": "unknown", "password": "wrong"})
        assert wrong.status_code == missing.status_code == 401
        assert wrong.json() == missing.json()

        logged_in = post(
            client, "/api/auth/login", {"username": "ALICE", "password": "a-long-password-123"}
        )
        assert logged_in.status_code == 200
        assert logged_in.json() == {"id": 1, "username": "alice"}
        cookie = logged_in.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert "path=/api" in cookie
        assert client.get("/api/me").json() == {"id": 1, "username": "alice"}

        with auth_db() as db:
            login_session = db.scalar(select(AuthSession))
            assert login_session is not None
            assert login_session.token_hash != client.cookies.get("job_session")
            assert len(login_session.token_hash) == 64

        assert post(client, "/api/auth/logout", {}).status_code == 204
        assert client.get("/api/me").status_code == 401
        with auth_db() as db:
            assert isinstance(db.scalar(select(AuthSession.revoked_at)), datetime)


def test_two_clients_and_expired_session(auth_db):
    with TestClient(app) as alice, TestClient(app) as bob:
        post(alice, "/api/auth/register", {"username": "alice", "password": "alice-password-123"})
        post(bob, "/api/auth/register", {"username": "bob", "password": "bob-password-123"})
        post(alice, "/api/auth/login", {"username": "alice", "password": "alice-password-123"})
        post(bob, "/api/auth/login", {"username": "bob", "password": "bob-password-123"})
        assert alice.get("/api/me").json()["username"] == "alice"
        assert bob.get("/api/me").json()["username"] == "bob"
        assert alice.cookies.get("job_session") != bob.cookies.get("job_session")

        with auth_db() as db:
            alice_session = db.scalar(
                select(AuthSession).join(User).where(User.username == "alice")
            )
            assert alice_session is not None
            alice_session.expires_at = utc_now() - timedelta(seconds=1)
            db.commit()
        assert alice.get("/api/me").status_code == 401
        assert bob.get("/api/me").status_code == 200


def test_write_requests_need_own_origin_and_header(auth_db):
    with TestClient(app) as client:
        body = {"username": "alice", "password": "a-long-password-123"}
        assert post(
            client, "/api/auth/register", {"username": "a", "password": "short"}
        ).status_code == 422
        assert client.post("/api/auth/register", json=body).status_code == 403
        assert client.post(
            "/api/auth/register", json=body,
            headers={"Origin": "https://other.example", "X-Job-App-Request": "1"},
        ).status_code == 403
        assert client.post(
            "/api/auth/register", json=body, headers={"Origin": "http://testserver"}
        ).status_code == 403
        assert client.post(
            "/api/auth/register", data=body, headers=write_headers
        ).status_code == 403
        assert post(client, "/api/auth/register", body).status_code == 201
