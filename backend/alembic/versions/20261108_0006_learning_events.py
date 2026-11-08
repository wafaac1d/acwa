"""Store each nightly learning pass so the campaign can show what changed."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_0006"
down_revision: str | None = "20261108_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("covered_on", sa.String(length=10), nullable=True),
        sa.Column("changed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("previous_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_events_campaign_created",
        "learning_events",
        ["campaign_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_events_campaign_created", table_name="learning_events")
    op.drop_table("learning_events")
