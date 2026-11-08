from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    database: str
    integration_mode: Literal["demo", "live"]
    auth_required: bool
    public_deployment_ready: bool = False


class AccountRead(BaseModel):
    id: UUID
    threads_user_id: str | None
    username: str | None
    display_name: str | None
    profile_picture_url: str | None
    status: str
    token_expires_at: datetime | None
    is_demo: bool
    connected_at: datetime | None
    reauth_message: str | None


class OAuthStartRead(BaseModel):
    authorization_url: str


class GenerationSettings(BaseModel):
    temperature: float
    max_tokens: int
    prompt_version: str
    model: str


class DeepSeekPublic(BaseModel):
    configured: bool
    model: str
    base_url: str


class ThreadsPublic(BaseModel):
    configured: bool
    graph_base_url: str
    authorize_url: str
    redirect_uri: str
    scopes: list[str]
    text_limit: int


class SettingsRead(BaseModel):
    integration_mode: Literal["demo", "live"]
    auth_required: bool
    public_deployment_ready: bool = False
    demo_banner: str | None
    missed_slot_policy: str
    unapproved_policy: str
    generation: GenerationSettings
    deepseek: DeepSeekPublic
    threads: ThreadsPublic


class SettingsUpdate(BaseModel):
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=16, le=1024)


class SlotRead(BaseModel):
    scheduled_for: datetime
    local_time: str
    timezone: str


class SkippedSlotRead(BaseModel):
    slot_at: datetime
    local_time: str
    reason: str
    reason_label: str


class CampaignWrite(BaseModel):
    account_id: UUID
    name: str
    topic: str
    context: str = ""
    audience: str = ""
    language: str = "ru"
    tone: str = "дружелюбный и ясный"
    goal: str = ""
    desired_length: Literal["short", "medium", "long"] = "medium"
    extra_instructions: str = ""
    required_points: str = ""
    forbidden: str = ""
    examples: str = ""
    allow_emoji: bool = False
    allow_hashtags: bool = False
    allow_links: bool = False
    publish_mode: Literal["manual", "automatic"] = "manual"
    timezone: str = "Europe/Moscow"
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    times_of_day: list[str] = Field(default_factory=lambda: ["10:00"])
    starts_on: date
    ends_on: date | None = None
    threads_topic_tag: str = ""
    reply_text: str = ""
    learning_enabled: bool = False
    activate: bool = False


class CampaignRead(BaseModel):
    id: UUID
    account_id: UUID
    name: str
    topic: str
    context: str
    audience: str
    language: str
    tone: str
    goal: str
    desired_length: str
    extra_instructions: str
    required_points: str
    forbidden: str
    examples: str
    allow_emoji: bool
    allow_hashtags: bool
    allow_links: bool
    publish_mode: str
    timezone: str
    weekdays: list[int]
    times_of_day: list[str]
    starts_on: date
    ends_on: date | None
    threads_topic_tag: str | None
    reply_text: str | None
    learning_enabled: bool
    learning_notes: str
    learning_status: str | None
    learning_checked_at: datetime | None
    learning_next_at: datetime | None
    status: str
    schedule_cursor: datetime | None
    created_at: datetime
    updated_at: datetime
    upcoming: list[SlotRead]
    skipped: list[SkippedSlotRead] = Field(default_factory=list)
    missed_slot_policy: str


class CampaignSummary(BaseModel):
    id: UUID
    name: str
    status: str
    publish_mode: str
    timezone: str
    topic: str
    account_id: UUID
    next_slot: SlotRead | None


class PostRead(BaseModel):
    id: UUID
    campaign_id: UUID
    account_id: UUID
    campaign_name: str
    origin: str
    text: str | None
    reply_text: str | None
    topic_tag: str | None
    reply_external_id: str | None
    reply_permalink: str | None
    status: str
    scheduled_for: datetime | None
    scheduled_local_time: str | None
    timezone: str
    published_at: datetime | None
    generated_at: datetime | None
    approved_at: datetime | None
    model: str | None
    prompt_version: str | None
    usage: dict[str, int] | None
    external_id: str | None
    container_id: str | None
    container_status: str | None
    permalink: str | None
    is_demo_publication: bool
    attempt_count: int
    generation_count: int
    last_error: str | None
    error_kind: str | None
    created_at: datetime
    updated_at: datetime


class PostTextUpdate(BaseModel):
    text: str
    reply_text: str | None = None
    topic_tag: str | None = None


class AttemptRead(BaseModel):
    id: UUID
    kind: str
    started_at: datetime
    finished_at: datetime | None
    outcome: str
    error_message: str | None
    http_status: int | None


class Page(BaseModel):
    items: list[CampaignSummary] | list[PostRead] | list[AccountRead]
    next_cursor: str | None


class CampaignPage(BaseModel):
    items: list[CampaignSummary]
    next_cursor: str | None


class PostPage(BaseModel):
    items: list[PostRead]
    next_cursor: str | None


class AccountPage(BaseModel):
    items: list[AccountRead]
    next_cursor: str | None


class InsightMetrics(BaseModel):
    views: int | None = None
    likes: int | None = None
    replies: int | None = None
    reposts: int | None = None
    quotes: int | None = None
    shares: int | None = None


class YesterdayPostInsight(BaseModel):
    post_id: UUID
    text: str | None
    published_at: datetime
    local_time: str
    permalink: str | None
    is_demo_publication: bool
    metrics: InsightMetrics | None
    collected_at: datetime | None
    error: str | None


class YesterdayInsights(BaseModel):
    date: str
    timezone: str
    notice: str | None
    posts: list[YesterdayPostInsight]
    totals: InsightMetrics


class DashboardRead(BaseModel):
    integration_mode: str
    auth_required: bool
    public_deployment_ready: bool
    demo_banner: str | None
    missed_slot_policy: str
    accounts: list[AccountRead]
    active_campaigns: int
    paused_campaigns: int
    upcoming: list[SlotRead]
    recent_errors: list[PostRead]
    skipped: list[SkippedSlotRead]
