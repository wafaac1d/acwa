import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.domain.status import JobKind, JobStatus, PostStatus
from acwa.models import Job, Post


def enqueue_job(
    session: Session,
    *,
    post_id: uuid.UUID,
    kind: JobKind,
    run_at: datetime,
    max_attempts: int,
) -> Job:
    open_job = session.scalar(
        select(Job).where(
            Job.post_id == post_id,
            Job.kind == kind,
            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        )
    )
    if open_job is not None:
        open_job.run_at = min(open_job.run_at, run_at)
        open_job.updated_at = run_at
        return open_job
    job = Job(
        post_id=post_id,
        kind=kind,
        status=JobStatus.PENDING,
        run_at=run_at,
        max_attempts=max_attempts,
        attempts=0,
        created_at=run_at,
        updated_at=run_at,
    )
    session.add(job)
    return job


def cancel_open_jobs(session: Session, post_id: uuid.UUID, now: datetime) -> None:
    jobs = session.scalars(
        select(Job).where(
            Job.post_id == post_id,
            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        )
    ).all()
    for job in jobs:
        if job.status == JobStatus.RUNNING:
            continue
        job.status = JobStatus.CANCELLED
        job.updated_at = now


def claim_next_job(session: Session, now: datetime, worker_id: str) -> Job | None:
    job = session.scalars(
        select(Job)
        .where(Job.status == JobStatus.PENDING, Job.run_at <= now)
        .order_by(Job.run_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.locked_at = now
    job.locked_by = worker_id
    job.updated_at = now
    session.flush()
    return job


def recover_stuck_jobs(session: Session, now: datetime, lease: timedelta) -> int:
    cutoff = now - lease
    jobs = session.scalars(
        select(Job).where(
            Job.status == JobStatus.RUNNING,
            Job.locked_at.is_not(None),
            Job.locked_at < cutoff,
        )
    ).all()
    for job in jobs:
        post = session.get(Post, job.post_id)
        job.locked_at = None
        job.locked_by = None
        job.updated_at = now
        dispatched = (
            post is not None
            and post.publish_dispatched_at is not None
            and post.external_id is None
            and post.status == PostStatus.PUBLISHING
        )
        if dispatched and post is not None:
            post.status = PostStatus.UNKNOWN
            post.error_kind = "ambiguous"
            post.last_error = (
                "Публикация прервалась после отправки запроса. "
                "Автоматический повтор остановлен, пока статус не проверен."
            )
            post.updated_at = now
            job.kind = JobKind.RECONCILE
            job.status = JobStatus.PENDING
            job.run_at = now
            job.attempts = 0
            continue
        job.attempts += 1
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            if post is not None and post.status in {
                PostStatus.GENERATING,
                PostStatus.PUBLISHING,
                PostStatus.SCHEDULED,
            }:
                post.status = PostStatus.FAILED
                post.last_error = "Фоновое задание зависло и исчерпало попытки"
                post.updated_at = now
        else:
            job.status = JobStatus.PENDING
            job.run_at = now
    return len(jobs)
