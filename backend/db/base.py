"""所有 ORM 模型共享的表元数据。"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# 命名约定让 Alembic 迁移里的约束名称稳定，后续删除/修改约束时可准确引用。
CONSTRAINT_NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """模型继承此类后，SQLAlchemy 会把字段和约束收集到 metadata。"""

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING)
