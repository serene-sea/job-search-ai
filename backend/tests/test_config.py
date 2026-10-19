"""本机配置文件能在新进程中被加载，同时尊重终端已有配置。"""

import os

import pytest

from backend import config
from backend.db.session import get_engine


def test_local_env_fills_missing_value_without_overriding_shell(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///from-file.db\n", encoding="utf-8")
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", env_file)

    monkeypatch.delenv("DATABASE_URL", raising=False)
    config.load_local_env()
    assert os.getenv("DATABASE_URL") == "sqlite:///from-file.db"

    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-shell.db")
    config.load_local_env()
    assert os.getenv("DATABASE_URL") == "sqlite:///from-shell.db"


def test_unescaped_password_separator_is_rejected_before_connect(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:part@rest@127.0.0.1:3306/db")
    get_engine.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="密码中的 @"):
            get_engine()
    finally:
        get_engine.cache_clear()
