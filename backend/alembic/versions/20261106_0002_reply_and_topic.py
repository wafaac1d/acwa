"""Optional Threads topic tag and a reply that continues the post."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0002"
down_revision: str | None = "20261106_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("threads_topic_tag", sa.String(length=50)))
    op.add_column("posts", sa.Column("topic_tag", sa.String(length=50)))
    op.add_column("posts", sa.Column("reply_text", sa.Text()))
    op.add_column("posts", sa.Column("reply_container_id", sa.String(length=128)))
    op.add_column("posts", sa.Column("reply_external_id", sa.String(length=128)))
    op.add_column("posts", sa.Column("reply_permalink", sa.String(length=1024)))
    op.add_column("posts", sa.Column("reply_publish_dispatched_at", sa.DateTime(timezone=True)))
    op.add_column(
        "posts",
        sa.Column("reply_allow_republish", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("posts", "reply_allow_republish")
    op.drop_column("posts", "reply_publish_dispatched_at")
    op.drop_column("posts", "reply_permalink")
    op.drop_column("posts", "reply_external_id")
    op.drop_column("posts", "reply_container_id")
    op.drop_column("posts", "reply_text")
    op.drop_column("posts", "topic_tag")
    op.drop_column("campaigns", "threads_topic_tag")
