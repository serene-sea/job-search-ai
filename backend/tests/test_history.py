"""教育和项目的隔离与年月校验；全程使用临时库和模拟账号。"""

from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.test_auth import auth_db, write_headers  # noqa: F401
from backend.tests.test_personal import login


def write(client: TestClient, method: str, path: str, body: dict):
    return client.request(method, path, json=body, headers=write_headers)


def test_education_project_crud_and_user_isolation(auth_db) -> None:
    with TestClient(app) as alice, TestClient(app) as bob:
        login(alice, "alice")
        login(bob, "bob")
        education = {"school": "某大学", "degree": "硕士", "major": "网络空间安全",
                     "start_year": 2024, "start_month": 9, "end_year": 2027, "end_month": 6,
                     "description": "真实研究方向"}
        created = write(alice, "POST", "/api/educations", education)
        assert created.status_code == 201, created.text
        education_id = created.json()["id"]
        assert alice.get("/api/educations").json()[0]["start_month"] == 9
        assert bob.get("/api/educations").json() == []
        assert write(bob, "PATCH", f"/api/educations/{education_id}", {"school": "篡改"}).status_code == 404
        assert write(bob, "DELETE", f"/api/educations/{education_id}", {}).status_code == 404
        assert write(alice, "POST", "/api/educations", {**education, "end_year": 2023}).status_code == 422
        assert write(alice, "PATCH", f"/api/educations/{education_id}", {"end_month": 5}).status_code == 200

        project = {"name": "真实项目", "summary": "解决的问题", "source_url": "https://example.org/project",
                   "highlights": "我实际做过的功能"}
        saved = write(alice, "POST", "/api/projects", project)
        assert saved.status_code == 201, saved.text
        project_id = saved.json()["id"]
        assert bob.get("/api/projects").json() == []
        assert write(bob, "PATCH", f"/api/projects/{project_id}", {"name": "篡改"}).status_code == 404
        assert write(bob, "DELETE", f"/api/projects/{project_id}", {}).status_code == 404
        assert write(alice, "POST", "/api/projects", {**project, "source_url": "javascript:alert(1)"}).status_code == 422
        assert write(alice, "PATCH", f"/api/projects/{project_id}", {"highlights": "本人可解释的设计"}).status_code == 200
        assert alice.get("/api/projects").json()[0]["highlights"] == "本人可解释的设计"
        assert write(alice, "DELETE", f"/api/projects/{project_id}", {}).status_code == 204
        assert write(alice, "DELETE", f"/api/educations/{education_id}", {}).status_code == 204

        with TestClient(app) as anonymous:
            assert anonymous.get("/api/educations").status_code == 401
            assert anonymous.get("/api/projects").status_code == 401


def test_legacy_profile_education_keeps_unknown_months(tmp_path, monkeypatch) -> None:
    """旧学校资料复制到新表；缺失年月不由程序猜测。"""

    from alembic import command
    from sqlalchemy import create_engine, text

    from backend.tests.test_database_schema import migration_config

    file = tmp_path / "legacy_education.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{file.as_posix()}")
    command.upgrade(migration_config(), "0006_resume_text")
    engine = create_engine(f"sqlite:///{file.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, username, password_hash) VALUES (1, 'owner', 'hash')"))
            connection.execute(text("INSERT INTO profiles "
                                    "(user_id, school, major, degree, graduation_year, education_text, updated_at) "
                                    "VALUES (1, '某大学', '网安', '硕士', 2027, '课程说明', '2026-10-17')"))
        command.upgrade(migration_config(), "head")
        with engine.connect() as connection:
            row = connection.execute(text("SELECT school, end_year, start_month, end_month, description "
                                          "FROM education_entries WHERE user_id=1")).one()
            assert row == ("某大学", 2027, None, None, "课程说明")
            assert connection.execute(text("SELECT education_text FROM profiles WHERE user_id=1")).scalar_one() == "课程说明"
    finally:
        engine.dispose()
