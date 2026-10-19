"""给仍使用旧版五个默认状态的账号补齐常见求职进度。"""

from alembic import op
import sqlalchemy as sa

revision = "0002_expand_default_statuses"
down_revision = "0001_core_schema"
branch_labels = None
depends_on = None

old_defaults = ("想投", "已投", "准备笔试", "已笔试", "准备面试")
new_defaults = (
    "想投", "准备投递", "已投", "准备测评", "已测评", "准备笔试", "已笔试",
    "准备面试", "已一面", "已二面", "已终面", "等待结果", "收到 Offer", "未通过", "已放弃",
)


def upgrade() -> None:
    """只补原样保留旧模板的账号；用户改过的状态不擅自覆盖。"""

    db = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Integer()))
    statuses = sa.table(
        "job_statuses",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.Integer()),
        sa.column("name", sa.String(100)),
        sa.column("sort_order", sa.Integer()),
    )

    for user_id in db.execute(sa.select(users.c.id)).scalars().all():
        rows = db.execute(
            sa.select(statuses.c.id, statuses.c.name, statuses.c.sort_order)
            .where(statuses.c.user_id == user_id)
            .order_by(statuses.c.sort_order, statuses.c.id)
        ).all()
        if [(row.name, row.sort_order) for row in rows] != [
            (name, order) for order, name in enumerate(old_defaults, start=1)
        ]:
            continue

        # 保留旧状态的 ID，岗位记录原有的 status_id 才不会变。
        for row in rows:
            db.execute(
                statuses.update()
                .where(statuses.c.id == row.id)
                .values(sort_order=new_defaults.index(row.name) + 1)
            )
        for order, name in enumerate(new_defaults, start=1):
            if name not in old_defaults:
                db.execute(statuses.insert().values(user_id=user_id, name=name, sort_order=order))


def downgrade() -> None:
    """不自动删状态：升级后用户可能已经使用或修改了它们。"""
