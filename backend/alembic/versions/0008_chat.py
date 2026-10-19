"""会话、消息和生成记录；只新增表，不迁移或修改既有用户资料。"""

from alembic import op
import sqlalchemy as sa

revision = "0008_chat"
down_revision = "0007_education_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", "user_id"),
    )
    op.create_index("ix_chat_sessions_user_updated", "chat_sessions", ["user_id", "updated_at"])
    op.create_index("ix_chat_sessions_job_id", "chat_sessions", ["job_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("report_json", sa.JSON()),
        sa.Column("snapshot_version", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id", "user_id"], ["chat_sessions.id", "chat_sessions.user_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id", "id"])
    op.create_index("ix_chat_messages_session_user", "chat_messages", ["session_id", "user_id"])
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), sa.ForeignKey("chat_messages.id"), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("chat_messages.id"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["session_id", "user_id"], ["chat_sessions.id", "chat_sessions.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "request_key"),
    )
    op.create_index("ix_generation_runs_session_status", "generation_runs", ["session_id", "status"])
    op.create_index("ix_generation_runs_session_user", "generation_runs", ["session_id", "user_id"])
    op.create_index("ix_generation_runs_user_message_id", "generation_runs", ["user_message_id"])
    op.create_index("ix_generation_runs_assistant_message_id", "generation_runs", ["assistant_message_id"])


def downgrade() -> None:
    connection = op.get_bind()
    for table_name in ("generation_runs", "chat_messages", "chat_sessions"):
        count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        if count:
            raise RuntimeError(f"{table_name} 含 {count} 行；请先备份或迁出，再考虑回退")
    op.drop_index("ix_generation_runs_assistant_message_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_user_message_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_session_user", table_name="generation_runs")
    op.drop_index("ix_generation_runs_session_status", table_name="generation_runs")
    op.drop_table("generation_runs")
    op.drop_index("ix_chat_messages_session_user", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_job_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_updated", table_name="chat_sessions")
    op.drop_table("chat_sessions")
