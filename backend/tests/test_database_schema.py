"""临时 SQLite 运行真实迁移；实库 MySQL 要另行核对。"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.db.base import Base
from backend.db import models  # noqa: F401  导入模型，供 Alembic 对照实际表结构。


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture
def migrated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_file = tmp_path / "schema.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    command.upgrade(migration_config(), "head")
    engine = create_engine(f"sqlite:///{database_file.as_posix()}")
    try:
        yield engine
    finally:
        engine.dispose()


def test_personal_job_schema_matches_model_and_can_downgrade_when_empty(migrated_db) -> None:
    assert set(Base.metadata.tables) == {
        "users", "auth_sessions", "job_statuses", "jobs", "profiles", "skills", "resumes",
        "education_entries", "project_entries", "chat_sessions", "chat_messages", "generation_runs"
    }
    assert set(inspect(migrated_db).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    assert inspect(migrated_db).get_check_constraints("jobs") == []
    assert "ix_jobs_user_id_company_name" in {
        item["name"] for item in inspect(migrated_db).get_indexes("jobs")
    }
    # 模型与完整迁移链生成的数据库结构不能悄悄分叉。
    command.check(migration_config())
    command.downgrade(migration_config(), "base")
    assert inspect(migrated_db).get_table_names() == ["alembic_version"]


def test_jobs_reject_foreign_status_and_allow_same_name(migrated_db) -> None:
    tables = Base.metadata.tables
    with migrated_db.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.execute(tables["users"].insert(), [
            {"id": 1, "username": "alice", "password_hash": "hash_a"},
            {"id": 2, "username": "bob", "password_hash": "hash_b"},
        ])
        connection.execute(tables["job_statuses"].insert(), [
            {"id": 11, "user_id": 1, "name": "想投", "sort_order": 1},
            {"id": 22, "user_id": 2, "name": "已投", "sort_order": 1},
        ])
        # 两个完全同名的岗位可以是两条不同记录，数据库不猜测它们是否重复。
        connection.execute(tables["jobs"].insert(), [
            {"user_id": 1, "status_id": 11, "company_name": "甲公司", "title": "后端开发"},
            {"user_id": 1, "status_id": 11, "company_name": "甲公司", "title": "后端开发"},
        ])

    with pytest.raises(IntegrityError), migrated_db.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.execute(tables["jobs"].insert().values(
            user_id=1, status_id=22, company_name="甲公司", title="借用别人状态"
        ))


def test_migration_stops_before_dropping_nonempty_old_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_file = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    command.upgrade(migration_config(), "0002_expand_default_statuses")
    engine = create_engine(f"sqlite:///{database_file.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, username, password_hash) VALUES (1, 'owner', 'hash')"))
            connection.execute(text("INSERT INTO companies (user_id, name) VALUES (1, '保留的公司')"))
        with pytest.raises(RuntimeError, match="companies 含 1 行"):
            command.upgrade(migration_config(), "head")
        assert "companies" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == \
                "0002_expand_default_statuses"
    finally:
        engine.dispose()


def test_new_tables_keep_existing_jobs_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """从当前 0004 升级时，已有岗位不能因为新增资料表而消失。"""

    database_file = tmp_path / "existing_jobs.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    command.upgrade(migration_config(), "0004_status_only")
    engine = create_engine(f"sqlite:///{database_file.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, username, password_hash) VALUES (1, 'owner', 'hash')"))
            connection.execute(text("INSERT INTO job_statuses (id, user_id, name, sort_order) "
                                    "VALUES (1, 1, '想投', 1)"))
            connection.execute(text("INSERT INTO jobs (id, user_id, status_id, company_name, title) "
                                    "VALUES (7, 1, 1, '甲公司', '后端开发')"))
        command.upgrade(migration_config(), "head")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT id, title FROM jobs WHERE user_id = 1")).one() == (7, "后端开发")
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009_personal_scope"
        assert {"profiles", "skills", "resumes", "education_entries", "project_entries",
                "chat_sessions", "chat_messages", "generation_runs"}.issubset(
            set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def test_status_only_migration_stops_before_discarding_existing_job_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_file = tmp_path / "before_status_only.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    command.upgrade(migration_config(), "0003_personal_jobs")
    engine = create_engine(f"sqlite:///{database_file.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, username, password_hash) VALUES (1, 'owner', 'hash')"))
            connection.execute(text("INSERT INTO job_statuses (id, user_id, name, sort_order) "
                                    "VALUES (1, 1, '已投', 1)"))
            connection.execute(text("INSERT INTO jobs (user_id, status_id, company_name, title, has_applied) "
                                    "VALUES (1, 1, '甲公司', '后端开发', 1)"))
        with pytest.raises(RuntimeError, match="jobs 含 1 行"):
            command.upgrade(migration_config(), "head")
        assert "has_applied" in {column["name"] for column in inspect(engine).get_columns("jobs")}
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == \
                "0003_personal_jobs"
    finally:
        engine.dispose()
