"""Store the campaign's default reply continuation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0004"
down_revision: str | None = "20261106_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("reply_text", sa.Text()))


def downgrade() -> None:
    op.drop_column("campaigns", "reply_text")
