"""Initial schema for campaigns, posts, and the Postgres job queue."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261106_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "threads_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("threads_user_id", sa.String(64)),
        sa.Column("username", sa.String(128)),
        sa.Column("display_name", sa.String(256)),
        sa.Column("profile_picture_url", sa.String(1024)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("token_ciphertext", sa.LargeBinary()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("token_obtained_at", sa.DateTime(timezone=True)),
        sa.Column("scopes", sa.String(512)),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_threads_user_id_connected",
        "threads_accounts",
        ["threads_user_id"],
        unique=True,
        postgresql_where=sa.text("threads_user_id IS NOT NULL AND status <> 'disconnected'"),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("threads_accounts.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("topic", sa.String(300), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(300), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("tone", sa.String(200), nullable=False),
        sa.Column("goal", sa.String(300), nullable=False),
        sa.Column("desired_length", sa.String(16), nullable=False),
        sa.Column("extra_instructions", sa.Text(), nullable=False),
        sa.Column("required_points", sa.Text(), nullable=False),
        sa.Column("forbidden", sa.Text(), nullable=False),
        sa.Column("examples", sa.Text(), nullable=False),
        sa.Column("allow_emoji", sa.Boolean(), nullable=False),
        sa.Column("allow_hashtags", sa.Boolean(), nullable=False),
        sa.Column("allow_links", sa.Boolean(), nullable=False),
        sa.Column("publish_mode", sa.String(16), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("times_of_day", postgresql.ARRAY(sa.String(5)), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("schedule_cursor", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("threads_accounts.id"), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("settings_snapshot", postgresql.JSONB()),
        sa.Column("usage", postgresql.JSONB()),
        sa.Column("generation_error", sa.Text()),
        sa.Column("external_id", sa.String(128)),
        sa.Column("container_id", sa.String(128)),
        sa.Column("container_status", sa.String(32)),
        sa.Column("permalink", sa.String(1024)),
        sa.Column("is_demo_publication", sa.Boolean(), nullable=False),
        sa.Column("publish_dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("allow_republish", sa.Boolean(), nullable=False),
        sa.Column("generation_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("error_kind", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_campaign_schedule_slot",
        "posts",
        ["campaign_id", "scheduled_for"],
        unique=True,
        postgresql_where=sa.text(
            "origin = 'schedule' AND scheduled_for IS NOT NULL AND status NOT IN ('CANCELLED')"
        ),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by", sa.String(128)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_jobs_pending_run_at",
        "jobs",
        ["run_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "post_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("external_id", sa.String(128)),
        sa.Column("http_status", sa.Integer()),
    )
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(128), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "skipped_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("campaign_id", "slot_at", name="uq_skipped_slot"),
    )


def downgrade() -> None:
    op.drop_table("skipped_slots")
    op.drop_table("app_settings")
    op.drop_table("oauth_states")
    op.drop_table("post_attempts")
    op.drop_table("jobs")
    op.drop_table("posts")
    op.drop_table("campaigns")
    op.drop_table("threads_accounts")
