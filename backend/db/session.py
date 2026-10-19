"""数据库连接入口。导入模块和健康检查均不要求 MySQL 在线。"""

import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.config import load_local_env


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """首次访问数据库时才创建连接池；pool_pre_ping 可淘汰失效连接。"""

    load_local_env()
    # 环境变量有值时优先使用；没有时由 backend/.env 补上。
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("缺少 DATABASE_URL；健康检查不需要配置数据库")
    url = make_url(database_url)
    if url.drivername == "mysql+pymysql":
        if not url.host or "@" in url.host:
            raise RuntimeError("DATABASE_URL 地址格式不正确；密码中的 @ 等符号需先编码")
        # 本机 MySQL 不可达时早点报错，不让注册请求长时间等待。
        return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    # create_engine 本身通常不立即联网；首次执行 SQL 时才实际连接。
    return create_engine(url, pool_pre_ping=True)


def get_db_session() -> Iterator[Session]:
    """为一次请求借出 Session，结束时关闭；写入事务由调用方明确提交。"""

    # 登录和注册各用一份短暂的数据库会话，请求结束就关闭。
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
