import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)


class ThreadsAccount(Base):
    __tablename__ = "threads_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    threads_user_id: Mapped[str | None] = mapped_column(String(64))
    username: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(256))
    profile_picture_url: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    token_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_obtained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(String(512))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="account")

    __table_args__ = (
        Index(
            "uq_threads_user_id_connected",
            "threads_user_id",
            unique=True,
            postgresql_where=sql_text("threads_user_id IS NOT NULL AND status <> 'disconnected'"),
        ),
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads_accounts.id"))
    name: Mapped[str] = mapped_column(String(120))
    topic: Mapped[str] = mapped_column(String(300))
    context: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(300), default="")
    language: Mapped[str] = mapped_column(String(16), default="ru")
    tone: Mapped[str] = mapped_column(String(200), default="дружелюбный и ясный")
    goal: Mapped[str] = mapped_column(String(300), default="")
    desired_length: Mapped[str] = mapped_column(String(16), default="medium")
    extra_instructions: Mapped[str] = mapped_column(Text, default="")
    required_points: Mapped[str] = mapped_column(Text, default="")
    forbidden: Mapped[str] = mapped_column(Text, default="")
    examples: Mapped[str] = mapped_column(Text, default="")
    allow_emoji: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_hashtags: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_links: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_mode: Mapped[str] = mapped_column(String(16), default="manual")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    times_of_day: Mapped[list[str]] = mapped_column(ARRAY(String(5)))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="paused")
    threads_topic_tag: Mapped[str | None] = mapped_column(String(50))
    reply_text: Mapped[str | None] = mapped_column(Text)
    learning_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    learning_notes: Mapped[str] = mapped_column(Text, default="")
    learning_status: Mapped[str | None] = mapped_column(Text)
    learning_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    learning_next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule_cursor: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped[ThreadsAccount] = relationship(back_populates="campaigns")
    posts: Mapped[list["Post"]] = relationship(back_populates="campaign")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads_accounts.id"))
    origin: Mapped[str] = mapped_column(String(16))
    text: Mapped[str | None] = mapped_column(Text)
    reply_text: Mapped[str | None] = mapped_column(Text)
    topic_tag: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    settings_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    generation_error: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(128))
    container_id: Mapped[str | None] = mapped_column(String(128))
    container_status: Mapped[str | None] = mapped_column(String(32))
    permalink: Mapped[str | None] = mapped_column(String(1024))
    reply_container_id: Mapped[str | None] = mapped_column(String(128))
    reply_external_id: Mapped[str | None] = mapped_column(String(128))
    reply_permalink: Mapped[str | None] = mapped_column(String(1024))
    reply_publish_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_allow_republish: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo_publication: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allow_republish: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_count: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(String(32))
    insights: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    insights_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    insights_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="posts")
    account: Mapped[ThreadsAccount] = relationship()
    attempts: Mapped[list["PostAttempt"]] = relationship(back_populates="post")
    jobs: Mapped[list["Job"]] = relationship(back_populates="post")

    __table_args__ = (
        Index(
            "uq_campaign_schedule_slot",
            "campaign_id",
            "scheduled_for",
            unique=True,
            postgresql_where=sql_text(
                "origin = 'schedule' AND scheduled_for IS NOT NULL AND status NOT IN ('CANCELLED')"
            ),
        ),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped[Post] = relationship(back_populates="jobs")

    __table_args__ = (
        Index(
            "ix_jobs_pending_run_at",
            "run_at",
            "id",
            postgresql_where=sql_text("status = 'pending'"),
        ),
    )


class PostAttempt(Base):
    __tablename__ = "post_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(128))
    http_status: Mapped[int | None] = mapped_column(Integer)

    post: Mapped[Post] = relationship(back_populates="attempts")


class OAuthState(Base):
    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    temperature: Mapped[float] = mapped_column(Float, default=0.8)
    max_tokens: Mapped[int] = mapped_column(Integer, default=512)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkippedSlot(Base):
    __tablename__ = "skipped_slots"
    __table_args__ = (UniqueConstraint("campaign_id", "slot_at", name="uq_skipped_slot"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    slot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
