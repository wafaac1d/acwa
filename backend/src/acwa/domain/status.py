from enum import StrEnum


class AccountStatus(StrEnum):
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"
    DISCONNECTED = "disconnected"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class PublishMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class DesiredLength(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class PostOrigin(StrEnum):
    TRIAL = "trial"
    SCHEDULE = "schedule"


class PostStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class JobKind(StrEnum):
    GENERATE = "generate"
    PUBLISH = "publish"
    RECONCILE = "reconcile"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


QUEUE_STATUSES = {
    PostStatus.DRAFT,
    PostStatus.GENERATING,
    PostStatus.PENDING_APPROVAL,
    PostStatus.SCHEDULED,
    PostStatus.PUBLISHING,
    PostStatus.UNKNOWN,
}

HISTORY_STATUSES = {
    PostStatus.PUBLISHED,
    PostStatus.FAILED,
    PostStatus.CANCELLED,
}

EDITABLE_STATUSES = {
    PostStatus.DRAFT,
    PostStatus.PENDING_APPROVAL,
    PostStatus.SCHEDULED,
    PostStatus.FAILED,
}

TERMINAL_POST_STATUSES = {
    PostStatus.PUBLISHED,
    PostStatus.CANCELLED,
}

ALLOWED_TRANSITIONS: dict[PostStatus, set[PostStatus]] = {
    PostStatus.DRAFT: {PostStatus.GENERATING, PostStatus.CANCELLED},
    PostStatus.GENERATING: {
        PostStatus.PENDING_APPROVAL,
        PostStatus.SCHEDULED,
        PostStatus.FAILED,
        PostStatus.CANCELLED,
    },
    PostStatus.PENDING_APPROVAL: {
        PostStatus.SCHEDULED,
        PostStatus.GENERATING,
        PostStatus.CANCELLED,
        PostStatus.DRAFT,
    },
    PostStatus.SCHEDULED: {
        PostStatus.PUBLISHING,
        PostStatus.PENDING_APPROVAL,
        PostStatus.GENERATING,
        PostStatus.CANCELLED,
        PostStatus.FAILED,
    },
    PostStatus.PUBLISHING: {
        PostStatus.PUBLISHED,
        PostStatus.FAILED,
        PostStatus.UNKNOWN,
        PostStatus.SCHEDULED,
        PostStatus.CANCELLED,
    },
    PostStatus.PUBLISHED: set(),
    PostStatus.FAILED: {
        PostStatus.GENERATING,
        PostStatus.PENDING_APPROVAL,
        PostStatus.SCHEDULED,
        PostStatus.PUBLISHING,
        PostStatus.CANCELLED,
    },
    PostStatus.CANCELLED: set(),
    PostStatus.UNKNOWN: {
        PostStatus.PUBLISHED,
        PostStatus.FAILED,
        PostStatus.SCHEDULED,
        PostStatus.CANCELLED,
    },
}


class InvalidTransition(Exception):
    def __init__(self, current: PostStatus, target: PostStatus) -> None:
        super().__init__(f"{current} -> {target}")
        self.current = current
        self.target = target


def transition(current: PostStatus | str, target: PostStatus) -> PostStatus:
    source = PostStatus(current)
    if target not in ALLOWED_TRANSITIONS[source] and target != source:
        raise InvalidTransition(source, target)
    return target


MISSED_SLOT_POLICY = (
    "После простоя или перезапуска публикуется не больше одного слота — "
    "и только если его время попало в окно допуска. Более ранние пропущенные "
    "слоты фиксируются как пропущенные и не отправляются пачкой. "
    "Пост без одобрения не публикуется, даже если время слота уже прошло. "
    "Пока в очереди есть незавершённый пост кампании, новый слот не создаётся."
)

UNAPPROVED_OVERDUE_POLICY = (
    "Если время публикации прошло, а пост всё ещё ждёт одобрения, "
    "он остаётся в очереди и не отправляется. Одобрение после этого публикует его сразу."
)
