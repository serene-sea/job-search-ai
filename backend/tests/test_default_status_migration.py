"""旧账号补齐状态时，保留用户自己的修改和岗位引用。"""

import importlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import JobStatus, User


def test_expand_old_defaults_without_changing_custom_statuses(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        legacy = User(username="legacy", password_hash="test-only")
        custom = User(username="custom", password_hash="test-only")
        db.add_all([legacy, custom])
        db.flush()
        old_names = ("想投", "已投", "准备笔试", "已笔试", "准备面试")
        db.add_all(
            JobStatus(user_id=legacy.id, name=name, sort_order=order)
            for order, name in enumerate(old_names, start=1)
        )
        db.add(JobStatus(user_id=custom.id, name="我自己定义的状态", sort_order=1))
        db.commit()
        legacy_id, custom_id = legacy.id, custom.id
        old_ids = db.scalars(select(JobStatus.id).where(JobStatus.user_id == legacy_id)).all()

    migration = importlib.import_module("backend.alembic.versions.0002_expand_default_statuses")
    with engine.begin() as connection:
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        migration.upgrade()

    with Session(engine) as db:
        rows = db.scalars(
            select(JobStatus).where(JobStatus.user_id == legacy_id).order_by(JobStatus.sort_order)
        ).all()
        assert [row.name for row in rows] == list(migration.new_defaults)
        assert set(old_ids).issubset({row.id for row in rows})
        assert db.scalars(
            select(JobStatus.name).where(JobStatus.user_id == custom_id)
        ).all() == ["我自己定义的状态"]
    engine.dispose()
