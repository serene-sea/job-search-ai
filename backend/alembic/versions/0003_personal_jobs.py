"""岗位归本人一张表；旧业务表有数据时拒绝删表。"""

from alembic import op
import sqlalchemy as sa

revision = "0003_personal_jobs"
down_revision = "0002_expand_default_statuses"
branch_labels = None
depends_on = None


def require_empty(*table_names: str) -> None:
    """DDL 在 MySQL 中不能可靠地随异常回滚，先阻止含数据的旧表被删除。"""

    connection = op.get_bind()
    for table_name in table_names:
        # 表名只来自下面写死的调用参数，不拼接用户输入。
        count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        if count:
            raise RuntimeError(f"{table_name} 含 {count} 行；请先制定数据搬迁方案，迁移未修改旧表")


def upgrade() -> None:
    # user_jobs 先删，才能解除它对 jobs 和 companies 的外键引用。
    # 正式运行时还必须暂停应用写入，避免预检查后又有新岗位插入。
    require_empty("user_jobs", "jobs", "companies")
    op.drop_table("user_jobs")
    op.drop_table("jobs")
    op.drop_table("companies")

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200)),
        sa.Column("source_url", sa.Text()),
        sa.Column("requirements_text", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("has_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("applied_on", sa.Date()),
        # 同一状态编号和用户编号必须共同指向该用户自己的状态。
        sa.ForeignKeyConstraint(["status_id", "user_id"], ["job_statuses.id", "job_statuses.user_id"]),
        sa.CheckConstraint("has_applied = 1 OR applied_on IS NULL", name="applied_date_requires_applied"),
    )
    # 索引先按 user_id 缩小到当前账号，再按公司或投递事实筛选。
    op.create_index(
        "ix_jobs_user_id_company_name_has_applied", "jobs", ["user_id", "company_name", "has_applied"]
    )
    op.create_index("ix_jobs_user_id_has_applied", "jobs", ["user_id", "has_applied"])
    op.create_index("ix_jobs_status_id_user_id", "jobs", ["status_id", "user_id"])


def downgrade() -> None:
    # 新岗位若已有记录，旧模型无法无损拆回三张表；明确拒绝丢数据。
    require_empty("jobs")
    op.drop_table("jobs")
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("id", "user_id"),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("canonical_key", sa.String(255)),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200)),
        sa.Column("source_url", sa.Text()),
        sa.UniqueConstraint("canonical_key"),
        sa.CheckConstraint(
            "(owner_user_id IS NULL AND canonical_key IS NOT NULL) OR "
            "(owner_user_id IS NOT NULL AND canonical_key IS NULL)",
            name="public_or_private",
        ),
    )
    op.create_index("ix_jobs_owner_user_id", "jobs", ["owner_user_id"])
    op.create_table(
        "user_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("has_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("applied_on", sa.Date()),
        sa.UniqueConstraint("user_id", "job_id"),
        sa.ForeignKeyConstraint(["company_id", "user_id"], ["companies.id", "companies.user_id"]),
        sa.ForeignKeyConstraint(["status_id", "user_id"], ["job_statuses.id", "job_statuses.user_id"]),
        sa.CheckConstraint("has_applied = 1 OR applied_on IS NULL", name="applied_date_requires_applied"),
    )
    op.create_index(
        "ix_user_jobs_user_id_company_id_has_applied", "user_jobs", ["user_id", "company_id", "has_applied"]
    )
    op.create_index("ix_user_jobs_user_id_status_id", "user_jobs", ["user_id", "status_id"])
