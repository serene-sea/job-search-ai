"""新增多段教育与项目；旧资料只复制已知字段，不猜测入学或毕业月份。"""

from alembic import op
import sqlalchemy as sa

revision = "0007_education_projects"
down_revision = "0006_resume_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "education_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("school", sa.String(200), nullable=False),
        sa.Column("major", sa.String(200)),
        sa.Column("degree", sa.String(100)),
        sa.Column("start_year", sa.Integer()),
        sa.Column("start_month", sa.Integer()),
        sa.Column("end_year", sa.Integer()),
        sa.Column("end_month", sa.Integer()),
        sa.Column("description", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("start_month IS NULL OR start_month BETWEEN 1 AND 12", name="education_start_month_range"),
        sa.CheckConstraint("end_month IS NULL OR end_month BETWEEN 1 AND 12", name="education_end_month_range"),
    )
    op.create_index("ix_education_entries_user_id", "education_entries", ["user_id"])
    op.create_table(
        "project_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("highlights", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_project_entries_user_id", "project_entries", ["user_id"])

    # 旧资料可能只有毕业年份；复制年份并让月份留空，页面提示用户自行补全。
    # 旧列暂不删除，因其中还可能有不能自动归类为项目的文字。
    op.get_bind().execute(sa.text(
        "INSERT INTO education_entries "
        "(user_id, school, major, degree, end_year, description, updated_at) "
        "SELECT user_id, school, major, degree, graduation_year, education_text, updated_at "
        "FROM profiles WHERE school IS NOT NULL AND TRIM(school) <> ''"
    ))


def downgrade() -> None:
    # 旧资料仍在 profiles；但用户后来新增的独立记录没有旧表可存，禁止静默删除。
    connection = op.get_bind()
    for table_name in ("education_entries", "project_entries"):
        count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        if count:
            raise RuntimeError(f"{table_name} 含 {count} 行；请先备份或迁出，再考虑回退")
    op.drop_index("ix_project_entries_user_id", table_name="project_entries")
    op.drop_table("project_entries")
    op.drop_index("ix_education_entries_user_id", table_name="education_entries")
    op.drop_table("education_entries")
