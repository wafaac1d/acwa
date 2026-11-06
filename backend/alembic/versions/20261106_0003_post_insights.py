"""Store the latest Threads insight snapshot on a post."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261106_0003"
down_revision: str | None = "20261106_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("insights", postgresql.JSONB()))
    op.add_column("posts", sa.Column("insights_collected_at", sa.DateTime(timezone=True)))
    op.add_column("posts", sa.Column("insights_error", sa.Text()))


def downgrade() -> None:
    op.drop_column("posts", "insights_error")
    op.drop_column("posts", "insights_collected_at")
    op.drop_column("posts", "insights")
