import logging
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.integrations.deepseek import ContentGenerator
from acwa.integrations.threads import ThreadsGateway
from acwa.integrations.types import ErrorKind, IntegrationError, Postpone
from acwa.models import Job, Post
from acwa.security.crypto import TokenCipher
from acwa.security.redact import redact
from acwa.services.jobs import claim_next_job, recover_stuck_jobs
from acwa.services.learning import learn_due_campaigns
from acwa.services.pipeline import run_generation, run_publish
from acwa.services.planner import plan_due_campaigns

logger = logging.getLogger(__name__)


def run_once(
    session: Session,
    *,
    settings: Settings,
    clock: Clock,
    generator: ContentGenerator,
    threads: ThreadsGateway,
    cipher: TokenCipher,
    worker_id: str,
) -> bool:
    recover_stuck_jobs(session, clock.now(), timedelta(seconds=settings.worker_lease_seconds))
    plan_due_campaigns(session, clock, settings)
    learn_due_campaigns(session, clock=clock, settings=settings, threads=threads, cipher=cipher)
    job = claim_next_job(session, clock.now(), worker_id)
    if job is None:
        session.commit()
        return False
    job_id = job.id
    kind = job.kind
    post_id = job.post_id
    session.commit()
    logger.info(
        "job claimed",
        extra={"job_id": job_id, "post_id": post_id, "campaign_id": _campaign_id(session, post_id)},
    )
    try:
        if kind == "generate":
            run_generation(session, post_id, generator=generator, clock=clock, settings=settings)
        else:
            run_publish(
                session,
                post_id,
                threads=threads,
                cipher=cipher,
                clock=clock,
                settings=settings,
            )
        _finish(session, job_id, clock, "succeeded", None)
    except Postpone as exc:
        _finish(session, job_id, clock, "pending", exc.message, delay=exc.delay, increment=False)
    except IntegrationError as exc:
        _finish_error(session, job_id, post_id, clock, exc)
    except Exception as exc:
        logger.exception("job failed", extra={"job_id": job_id, "post_id": post_id})
        _finish_error(
            session,
            job_id,
            post_id,
            clock,
            IntegrationError(ErrorKind.TRANSIENT, redact(str(exc)) or "Внутренняя ошибка задания"),
        )
    return True


def _finish(
    session: Session,
    job_id: uuid.UUID,
    clock: Clock,
    status: str,
    error: str | None,
    *,
    delay: timedelta | None = None,
    increment: bool = False,
) -> None:
    job = session.get(Job, job_id)
    if job is None or job.status in {"succeeded", "failed", "cancelled"}:
        session.commit()
        return
    now = clock.now()
    if increment:
        job.attempts += 1
    job.status = status
    job.locked_at = None
    job.locked_by = None
    job.updated_at = now
    if error:
        job.last_error = redact(error)[:500]
    if delay is not None:
        job.run_at = now + delay
    session.commit()


def _finish_error(
    session: Session,
    job_id: uuid.UUID,
    post_id: uuid.UUID,
    clock: Clock,
    exc: IntegrationError,
) -> None:
    job = session.get(Job, job_id)
    post = session.get(Post, post_id)
    if job is None:
        session.commit()
        return
    now = clock.now()
    job.attempts += 1
    job.last_error = redact(exc.message)[:500]
    job.locked_at = None
    job.locked_by = None
    job.updated_at = now
    terminal = exc.kind in {ErrorKind.PERMANENT, ErrorKind.AUTH} or job.attempts >= job.max_attempts
    if terminal:
        job.status = "failed"
        if post is not None and post.status in {"GENERATING", "PUBLISHING", "SCHEDULED"}:
            post.status = "FAILED"
            post.last_error = job.last_error
            post.error_kind = exc.kind
            post.updated_at = now
    else:
        job.status = "pending"
        delay = exc.retry_after or _backoff(job.attempts, exc.kind)
        job.run_at = now + delay
        if post is not None and post.status == "PUBLISHING" and post.publish_dispatched_at is None:
            post.status = "SCHEDULED"
            post.updated_at = now
    session.commit()


def _backoff(attempt: int, kind: str) -> timedelta:
    if kind == ErrorKind.RATE_LIMIT:
        return timedelta(minutes=15)
    seconds = min(30 * (2 ** max(attempt - 1, 0)), 900)
    return timedelta(seconds=seconds)


def _campaign_id(session: Session, post_id: uuid.UUID) -> uuid.UUID | None:
    post = session.get(Post, post_id)
    return post.campaign_id if post is not None else None
