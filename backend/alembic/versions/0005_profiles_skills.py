"""新增本人资料和多条技能；不修改已有岗位数据。"""

from alembic import op
import sqlalchemy as sa

revision = "0005_profiles_skills"
down_revision = "0004_status_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("school", sa.String(200)),
        sa.Column("major", sa.String(200)),
        sa.Column("degree", sa.String(100)),
        sa.Column("graduation_year", sa.Integer()),
        sa.Column("target_roles", sa.String(500)),
        sa.Column("education_text", sa.Text()),
        sa.Column("experience_text", sa.Text()),
        sa.Column("birth_date", sa.Date()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("proficiency", sa.Integer(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "name"),
        sa.CheckConstraint("proficiency BETWEEN 0 AND 4", name="proficiency_range"),
        sa.CheckConstraint("importance BETWEEN 1 AND 5", name="importance_range"),
    )
    op.create_index("ix_skills_user_id_importance", "skills", ["user_id", "importance"])


def downgrade() -> None:
    # 回退会删除这两张新表的数据；已有四张表不受影响。
    op.drop_index("ix_skills_user_id_importance", table_name="skills")
    op.drop_table("skills")
    op.drop_table("profiles")
