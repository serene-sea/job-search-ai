"""首次建表：用户、会话、公司、状态、岗位、个人岗位记录。"""

from alembic import op
import sqlalchemy as sa

revision = "0001_core_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """先建被引用的表，最后建 user_jobs，避免外键目标尚不存在。"""

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id_expires_at", "auth_sessions", ["user_id", "expires_at"])
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
        "job_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("id", "user_id"),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index("ix_job_statuses_user_id_sort_order", "job_statuses", ["user_id", "sort_order"])
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
        "ix_user_jobs_user_id_company_id_has_applied",
        "user_jobs",
        ["user_id", "company_id", "has_applied"],
    )
    op.create_index("ix_user_jobs_user_id_status_id", "user_jobs", ["user_id", "status_id"])


def downgrade() -> None:
    """逆序删除：先删引用方，再删被引用方；会丢失这些表中的数据。"""

    op.drop_index("ix_user_jobs_user_id_status_id", table_name="user_jobs")
    op.drop_index("ix_user_jobs_user_id_company_id_has_applied", table_name="user_jobs")
    op.drop_table("user_jobs")
    op.drop_index("ix_jobs_owner_user_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_job_statuses_user_id_sort_order", table_name="job_statuses")
    op.drop_table("job_statuses")
    op.drop_table("companies")
    op.drop_index("ix_auth_sessions_user_id_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
