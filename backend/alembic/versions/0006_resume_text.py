"""每个账号一份当前简历文本；不保存原始 PDF/DOCX/TXT 文件。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = "0006_resume_text"
down_revision = "0005_profiles_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("source_filename", sa.String(255)),
        sa.Column("source_format", sa.String(10)),
        sa.Column("raw_extracted_text", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("reviewed_text", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    # 回退会丢掉简历文本，执行前要由用户另行备份。
    op.drop_table("resumes")
