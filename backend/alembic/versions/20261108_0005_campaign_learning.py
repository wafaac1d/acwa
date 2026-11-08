"""Store the nightly learning toggle and its last prompt adjustment."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_0005"
down_revision: str | None = "20261106_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("learning_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "campaigns",
        sa.Column("learning_notes", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("campaigns", sa.Column("learning_status", sa.Text()))
    op.add_column("campaigns", sa.Column("learning_checked_at", sa.DateTime(timezone=True)))
    op.add_column("campaigns", sa.Column("learning_next_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("campaigns", "learning_next_at")
    op.drop_column("campaigns", "learning_checked_at")
    op.drop_column("campaigns", "learning_status")
    op.drop_column("campaigns", "learning_notes")
    op.drop_column("campaigns", "learning_enabled")
