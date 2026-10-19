"""Alembic 运行入口：把 DATABASE_URL 指向的库迁移到指定版本。"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# 允许从项目根目录或 backend 目录执行 Alembic 命令。
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import load_local_env  # noqa: E402
from backend.db.base import Base  # noqa: E402
import backend.db.models  # noqa: E402,F401  注册模型到 Base.metadata

load_local_env()
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 自动生成迁移时对照模型；实际执行的首个迁移已经手工复核并保存到 versions。
target_metadata = Base.metadata


def database_url() -> str:
    """仅迁移命令需要连接串；禁止把真实密码写进 alembic.ini。"""

    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("请先设置 DATABASE_URL，再执行 Alembic 迁移")
    return url


def run_migrations_offline() -> None:
    """只生成 SQL 文本，不连接数据库；用于人工审阅待执行的 DDL。"""

    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连接真实数据库，由 Alembic 按版本顺序执行 upgrade/downgrade。"""

    # 直接传 URL，可保留密码中的 %40 等 URL 编码；迁移进程不保留连接池。
    connectable = create_engine(database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
