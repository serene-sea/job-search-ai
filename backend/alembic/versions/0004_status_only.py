"""岗位只保留一个进度来源：本人状态。"""

from alembic import op
import sqlalchemy as sa

revision = "0004_status_only"
down_revision = "0003_personal_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除列会丢掉它们的历史值；实库当前为空，运行时仍重新核对，防止检查后有人新增岗位。
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar_one()
    if count:
        raise RuntimeError(f"jobs 含 {count} 行；先决定旧投递字段如何保留，再执行迁移")
    # MySQL 需要 user_id 上始终有索引支撑外键；先建替代索引，再删旧索引。
    # MySQL DDL 不整体回滚，按当前实库索引决定是否跳过已完成的步骤，便于失败后重试。
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("jobs")}
    if "ix_jobs_user_id_company_name" not in indexes:
        op.create_index("ix_jobs_user_id_company_name", "jobs", ["user_id", "company_name"])
    with op.batch_alter_table("jobs") as batch:
        if "ix_jobs_user_id_company_name_has_applied" in indexes:
            batch.drop_index("ix_jobs_user_id_company_name_has_applied")
        if "ix_jobs_user_id_has_applied" in indexes:
            batch.drop_index("ix_jobs_user_id_has_applied")
        # 实库中的物理名称带命名约定前缀；op.f 表示名称已经转换过，避免再加一次前缀。
        batch.drop_constraint(op.f("ck_jobs_applied_date_requires_applied"), type_="check")
        batch.drop_column("applied_on")
        batch.drop_column("has_applied")


def downgrade() -> None:
    # 回退只恢复旧结构，无法恢复升级时主动删除的列值。
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("has_applied", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("applied_on", sa.Date(), nullable=True))
        batch.create_check_constraint("applied_date_requires_applied", "has_applied = 1 OR applied_on IS NULL")
    # 同理，先让旧索引接管外键所需的 user_id 前缀，再删新索引。
    op.create_index("ix_jobs_user_id_company_name_has_applied", "jobs", ["user_id", "company_name", "has_applied"])
    op.create_index("ix_jobs_user_id_has_applied", "jobs", ["user_id", "has_applied"])
    op.drop_index("ix_jobs_user_id_company_name", table_name="jobs")
