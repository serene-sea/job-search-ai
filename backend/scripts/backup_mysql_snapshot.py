"""迁移前只读备份当前 MySQL 的表结构与行数据到本地 SQLite。

机器没有 mysqldump 时使用；备份文件含账号与会话摘要，勿上传或提交。
运行：python -m backend.scripts.backup_mysql_snapshot <备份目录>
"""

import base64
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect

from backend.db.session import get_engine


def encode_value(value: object) -> object:
    """JSON 不能直接保存日期、Decimal 和二进制数据，写入显式类型标记。"""

    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "value": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, (datetime, date, time, Decimal)):
        return {"type": type(value).__name__, "value": str(value)}
    return value


def snapshot(destination_dir: Path) -> tuple[Path, dict[str, int], str]:
    destination_dir = destination_dir.resolve(strict=True)
    if not destination_dir.is_dir():
        raise ValueError("备份目标必须是已存在的目录")
    name = f"before_0008_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
    target = destination_dir / name
    if target.exists():
        raise FileExistsError(target)
    temporary = destination_dir / f".{name}.{uuid.uuid4().hex}.tmp"
    counts: dict[str, int] = {}
    try:
        # sqlite3.Connection 的 with 只负责事务提交，不会关闭文件句柄；Windows 重命名前须显式关闭。
        with closing(sqlite3.connect(temporary)) as backup:
            backup.execute("CREATE TABLE table_schema (name TEXT PRIMARY KEY, mysql_create_sql TEXT NOT NULL, columns_json TEXT NOT NULL, row_count INTEGER NOT NULL)")
            backup.execute("CREATE TABLE table_rows (table_name TEXT NOT NULL, row_number INTEGER NOT NULL, values_json TEXT NOT NULL, PRIMARY KEY (table_name, row_number))")
            with get_engine().connect() as source:
                # REPEATABLE READ 一致性快照，避免备份多个表时读到不同时间点。
                source.exec_driver_sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                source.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT")
                try:
                    for table_name in sorted(inspect(source).get_table_names()):
                        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
                            raise ValueError("存在无法安全引用的表名")
                        create_sql = source.exec_driver_sql(f"SHOW CREATE TABLE `{table_name}`").one()[1]
                        result = source.exec_driver_sql(f"SELECT * FROM `{table_name}`")
                        columns = list(result.keys())
                        count = 0
                        for count, row in enumerate(result, 1):
                            backup.execute("INSERT INTO table_rows VALUES (?, ?, ?)", (
                                table_name, count,
                                json.dumps([encode_value(value) for value in row], ensure_ascii=False),
                            ))
                        backup.execute("INSERT INTO table_schema VALUES (?, ?, ?, ?)", (
                            table_name, create_sql, json.dumps(columns, ensure_ascii=False), count,
                        ))
                        counts[table_name] = count
                finally:
                    source.rollback()  # 只读事务始终结束，不改变 MySQL。
            backup.commit()
            saved = backup.execute("SELECT SUM(row_count) FROM table_schema").fetchone()[0] or 0
            actual = backup.execute("SELECT COUNT(*) FROM table_rows").fetchone()[0]
            if saved != actual:
                raise RuntimeError("备份行数校验失败")
        os.replace(temporary, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return target, counts, digest
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：python -m backend.scripts.backup_mysql_snapshot <备份目录>")
    path, row_counts, sha256 = snapshot(Path(sys.argv[1]))
    print(f"备份文件：{path}")
    print(f"备份表数：{len(row_counts)}；记录行数：{sum(row_counts.values())}")
    print(f"SHA-256：{sha256}")
