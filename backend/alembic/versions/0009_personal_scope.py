"""为每次生成保存用户选择的资料范围；旧记录保持空值。"""

from alembic import op
import sqlalchemy as sa

revision = "0009_personal_scope"
down_revision = "0008_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_runs", sa.Column("source_scope", sa.JSON(), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    used = connection.execute(sa.text(
        "SELECT COUNT(*) FROM generation_runs WHERE source_scope IS NOT NULL"
    )).scalar_one()
    if used:
        raise RuntimeError("已有按资料范围生成的记录；请先备份或迁出，再考虑回退")
    op.drop_column("generation_runs", "source_scope")
