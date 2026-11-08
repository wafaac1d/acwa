from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from acwa.clock import FrozenClock
from acwa.integrations.demo import DemoThreads
from acwa.integrations.types import ErrorKind, GenerationResult, IntegrationError
from acwa.models import Campaign, Job, Post, SkippedSlot, ThreadsAccount
from acwa.services.jobs import claim_next_job, recover_stuck_jobs
from acwa.services.pipeline import run_generation, run_publish
from acwa.services.planner import plan_campaign
from acwa.services.worker import run_once

pytestmark = pytest.mark.integration


class CountingGenerator:
    def __init__(self, text: str = "Спокойный демонстрационный пост.") -> None:
        self.calls = 0
        self.text = text
        self.error: IntegrationError | None = None

    def generate(self, prompt: object) -> GenerationResult:
        del prompt
        self.calls += 1
        if self.error is not None:
            raise self.error
        return GenerationResult(text=self.text, model="fake", usage={"total_tokens": 1})


def _account(session, cipher) -> ThreadsAccount:
    now = datetime(2026, 1, 5, tzinfo=UTC)
    account = ThreadsAccount(
        threads_user_id="demo",
        username="demo_account",
        display_name="Демонстрационный аккаунт",
        status="connected",
        is_demo=True,
        token_ciphertext=cipher.encrypt("plain-token-should-not-leak"),
        connected_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    session.flush()
    return account


def _campaign(session, account, **overrides) -> Campaign:
    now = datetime(2026, 1, 5, 9, tzinfo=UTC)
    data = dict(
        account_id=account.id,
        name="Кампания",
        topic="Тема дня",
        context="",
        audience="",
        language="ru",
        tone="спокойный",
        goal="",
        desired_length="short",
        extra_instructions="",
        required_points="",
        forbidden="",
        examples="",
        allow_emoji=False,
        allow_hashtags=False,
        allow_links=False,
        publish_mode="manual",
        timezone="UTC",
        weekdays=[1, 2, 3, 4, 5, 6, 7],
        times_of_day=["10:00", "11:00", "12:00"],
        starts_on=datetime(2026, 1, 5, tzinfo=UTC).date(),
        ends_on=None,
        status="active",
        schedule_cursor=now,
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    campaign = Campaign(**data)
    session.add(campaign)
    session.flush()
    return campaign


def test_missed_slots_publish_only_the_latest_inside_grace(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    account = _account(session, cipher)
    campaign = _campaign(session, account)
    now = datetime(2026, 1, 5, 12, 10, tzinfo=UTC)
    plan_campaign(session, campaign, now, settings)
    session.commit()
    posts = session.scalars(select(Post)).all()
    skipped = session.scalars(select(SkippedSlot).order_by(SkippedSlot.slot_at)).all()
    assert len(posts) == 1
    assert posts[0].scheduled_for == datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    assert [item.slot_at for item in skipped] == [
        datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        datetime(2026, 1, 5, 11, 0, tzinfo=UTC),
    ]
    session.close()


def test_pause_and_schedule_change_stop_unsent_posts(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher
    from acwa.services.planner import apply_schedule_change, pause_campaign

    cipher = TokenCipher(settings.token_encryption_key)
    account = _account(session, cipher)
    campaign = _campaign(session, account, publish_mode="automatic", times_of_day=["10:00"])
    now = datetime(2026, 1, 5, 10, 5, tzinfo=UTC)
    plan_campaign(session, campaign, now, settings)
    session.commit()
    pause_campaign(session, campaign, now + timedelta(minutes=1))
    session.commit()
    assert session.scalars(select(Post)).one().status == "CANCELLED"
    campaign.status = "active"
    campaign.schedule_cursor = datetime(2026, 1, 6, 8, tzinfo=UTC)
    future = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="SCHEDULED",
        scheduled_for=datetime(2026, 1, 6, 10, tzinfo=UTC),
        text="Будущий пост",
        created_at=now,
        updated_at=now,
    )
    session.add(future)
    session.commit()
    apply_schedule_change(session, campaign, datetime(2026, 1, 6, 8, tzinfo=UTC))
    session.commit()
    session.refresh(future)
    assert future.status == "CANCELLED"
    session.close()


def test_manual_approval_and_publish_retry_does_not_regenerate(session_factory, settings, app) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account, publish_mode="manual", status="paused")
    session.commit()
    generator = CountingGenerator()
    threads = DemoThreads()
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="trial",
        status="GENERATING",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add(post)
    session.commit()
    run_generation(session, post.id, generator=generator, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "PENDING_APPROVAL"
    assert generator.calls == 1
    run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "PENDING_APPROVAL"
    assert threads.publish_calls == 0
    from acwa.services.pipeline import approve_post

    approve_post(session, post, clock, settings)
    session.commit()
    run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "PUBLISHED"
    assert post.is_demo_publication is True
    assert post.permalink is None
    assert post.external_id is not None and post.external_id.startswith("demo:")
    assert generator.calls == 1
    post.external_id = None
    post.status = "FAILED"
    post.publish_dispatched_at = None
    from acwa.services.pipeline import retry_publish

    retry_publish(session, post, clock, settings)
    session.commit()
    publish_jobs = session.scalars(
        select(Job).where(Job.post_id == post.id, Job.kind == "publish", Job.status == "pending")
    ).all()
    assert publish_jobs
    assert generator.calls == 1
    session.close()


def test_learning_does_not_invent_demo_stats_and_ranks_live_totals(session_factory, settings) -> None:
    session = session_factory()
    from acwa.integrations.types import MediaInsights
    from acwa.security.crypto import TokenCipher
    from acwa.services.learning import learn_due_campaigns

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(
        session,
        account,
        context="Исходный контекст",
        learning_enabled=True,
        learning_next_at=datetime(2026, 1, 5, 0, tzinfo=UTC),
    )
    session.commit()
    learn_due_campaigns(
        session,
        clock=clock,
        settings=settings,
        threads=DemoThreads(),
        cipher=cipher,
    )
    session.flush()
    session.refresh(campaign)
    assert campaign.context == "Исходный контекст"
    assert campaign.learning_notes == ""
    assert campaign.learning_status is not None and "не запрашива" in campaign.learning_status
    assert campaign.learning_next_at is not None and campaign.learning_next_at > clock.now()

    live = settings.model_copy(update={"integration_mode": "live"})
    account.is_demo = False
    account.token_expires_at = datetime(2026, 3, 1, tzinfo=UTC)
    strong = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="PUBLISHED",
        text="Сильный конкретный пост",
        external_id="1789001",
        is_demo_publication=False,
        published_at=datetime(2026, 1, 4, 15, tzinfo=UTC),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    weak = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="PUBLISHED",
        text="Слабый общий пост",
        external_id="1789002",
        is_demo_publication=False,
        published_at=datetime(2026, 1, 4, 16, tzinfo=UTC),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add_all([strong, weak])
    campaign.learning_next_at = datetime(2026, 1, 5, 0, tzinfo=UTC)
    session.commit()

    class RecordingThreads(DemoThreads):
        def media_insights(self, media_id: str, access_token: str) -> MediaInsights:
            del access_token
            self.insight_calls += 1
            if media_id == "1789001":
                return MediaInsights(views=20, likes=4, replies=1, reposts=0, quotes=0, shares=1)
            return MediaInsights(views=2, likes=0, replies=0, reposts=0, quotes=0, shares=0)

    learn_due_campaigns(
        session,
        clock=clock,
        settings=live,
        threads=RecordingThreads(),
        cipher=cipher,
    )
    session.flush()
    session.refresh(campaign)
    assert campaign.context == "Исходный контекст"
    assert "Сильный конкретный пост" in campaign.learning_notes
    assert campaign.learning_notes.index("Сильный конкретный пост") < campaign.learning_notes.index("Слабый общий пост")
    assert "просмотры 20" in campaign.learning_notes
    from sqlalchemy import select

    from acwa.models import LearningEvent

    events = session.scalars(
        select(LearningEvent).where(LearningEvent.campaign_id == campaign.id).order_by(LearningEvent.created_at)
    ).all()
    assert len(events) == 2
    assert events[0].changed is False
    assert events[0].reason and "не запрашива" in events[0].reason
    assert events[0].notes == ""
    assert events[1].changed is True
    assert events[1].previous_notes == ""
    assert "просмотры 20" in events[1].reason
    assert events[1].reason.index("Сильный конкретный пост") < events[1].reason.index("Слабый общий пост")
    assert events[1].notes == campaign.learning_notes
    session.close()


def test_campaign_reply_is_copied_onto_a_new_trial(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher
    from acwa.services.pipeline import request_trial

    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, TokenCipher(settings.token_encryption_key))
    campaign = _campaign(session, account, reply_text="Продолжение из кампании")
    post = request_trial(session, campaign, clock, settings)
    assert post.reply_text == "Продолжение из кампании"
    session.close()


def test_reply_continues_the_thread_and_topic_is_only_on_the_root(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account, publish_mode="automatic")
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="SCHEDULED",
        text="Основной текст",
        reply_text="Продолжение в комментарии",
        topic_tag="книги",
        scheduled_for=clock.now(),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add(post)
    session.commit()
    threads = DemoThreads()
    run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "PUBLISHED"
    assert post.external_id is not None and post.external_id.startswith("demo:")
    assert post.reply_external_id is not None and post.reply_external_id.startswith("demo:")
    assert post.permalink is None
    assert post.reply_permalink is None
    assert post.is_demo_publication is True
    assert threads.creates[0]["topic_tag"] == "книги"
    assert threads.creates[0]["reply_to_id"] is None
    assert threads.creates[1]["reply_to_id"] == post.external_id
    assert threads.creates[1]["topic_tag"] is None
    assert threads.creates[1]["text"] == "Продолжение в комментарии"
    session.close()


def test_yesterday_insights_do_not_call_threads_for_demo(session_factory, settings) -> None:
    session = session_factory()
    from acwa.integrations.types import MediaInsights
    from acwa.security.crypto import TokenCipher
    from acwa.services.insights import collect_yesterday_insights

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account)
    yesterday = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="PUBLISHED",
        text="Вчерашний пост",
        external_id="demo:yesterday",
        is_demo_publication=True,
        published_at=datetime(2026, 1, 4, 15, tzinfo=UTC),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    today = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="PUBLISHED",
        text="Сегодняшний пост",
        external_id="demo:today",
        is_demo_publication=True,
        published_at=datetime(2026, 1, 5, 10, tzinfo=UTC),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add_all([yesterday, today])
    session.commit()
    threads = DemoThreads()
    notice = collect_yesterday_insights(
        session, campaign, threads=threads, cipher=cipher, clock=clock, settings=settings
    )
    session.refresh(yesterday)
    assert "не запрашива" in notice
    assert threads.insight_calls == 0
    assert yesterday.insights is None

    live = settings.model_copy(update={"integration_mode": "live"})
    account.is_demo = False
    account.token_expires_at = datetime(2026, 3, 1, tzinfo=UTC)
    yesterday.external_id = "1789001"
    yesterday.is_demo_publication = False
    session.commit()

    class RecordingThreads(DemoThreads):
        def media_insights(self, media_id: str, access_token: str) -> MediaInsights:
            self.insight_calls += 1
            assert media_id == "1789001"
            assert access_token == "plain-token-should-not-leak"
            return MediaInsights(views=10, likes=2, replies=1, reposts=0, quotes=0, shares=3)

    recording = RecordingThreads()
    notice = collect_yesterday_insights(session, campaign, threads=recording, cipher=cipher, clock=clock, settings=live)
    session.flush()
    session.refresh(yesterday)
    session.refresh(today)
    assert notice == ""
    assert recording.insight_calls == 1
    assert yesterday.insights == {
        "views": 10,
        "likes": 2,
        "replies": 1,
        "reposts": 0,
        "quotes": 0,
        "shares": 3,
    }
    assert today.insights is None
    session.close()


def test_ambiguous_timeout_does_not_publish_again(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account, publish_mode="automatic")
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="SCHEDULED",
        text="Один и тот же текст",
        approved_at=None,
        scheduled_for=clock.now(),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add(post)
    session.commit()
    threads = DemoThreads()
    threads.fail_publish_times = 1
    run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "UNKNOWN"
    assert threads.publish_calls == 1
    run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "UNKNOWN"
    assert threads.publish_calls == 1
    session.close()


def test_rate_limit_and_expired_authorization(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account, publish_mode="automatic")
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="schedule",
        status="SCHEDULED",
        text="Текст для лимита",
        scheduled_for=clock.now(),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add(post)
    session.commit()
    threads = DemoThreads()
    threads.rate_limit_times = 1
    with pytest.raises(IntegrationError) as limited:
        run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    assert limited.value.kind == ErrorKind.RATE_LIMIT
    session.refresh(post)
    assert post.publish_dispatched_at is None
    assert post.status == "SCHEDULED"
    threads.auth_failures = 1
    run_publish(session, post.id, threads=threads, cipher=cipher, clock=clock, settings=settings)
    session.refresh(post)
    session.refresh(account)
    assert post.status == "FAILED"
    assert account.status == "needs_reauth"
    assert "plain-token" not in (post.last_error or "")
    session.close()


def test_deepseek_failure_marks_post_without_publishing(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account)
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="trial",
        status="GENERATING",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add(post)
    session.commit()
    generator = CountingGenerator()
    generator.error = IntegrationError(ErrorKind.PERMANENT, "DeepSeek отклонил запрос")
    with pytest.raises(IntegrationError):
        run_generation(session, post.id, generator=generator, clock=clock, settings=settings)
    session.refresh(post)
    assert post.status == "FAILED"
    assert post.text is None
    assert "ключ" not in (post.last_error or "").lower() or "отклонил" in (post.last_error or "")
    session.close()


def test_concurrent_claim_and_stuck_recovery(session_factory) -> None:
    first = session_factory()
    now = datetime(2026, 1, 5, 12, tzinfo=UTC)
    from acwa.config import DEV_FERNET_KEY
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(DEV_FERNET_KEY)
    account = _account(first, cipher)
    campaign = _campaign(first, account, status="paused")
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="trial",
        status="GENERATING",
        created_at=now,
        updated_at=now,
    )
    first.add(post)
    first.flush()
    job = Job(
        post_id=post.id,
        kind="generate",
        status="pending",
        run_at=now,
        max_attempts=3,
        attempts=0,
        created_at=now,
        updated_at=now,
    )
    first.add(job)
    first.commit()
    claimed = claim_next_job(first, now, "worker-a")
    assert claimed is not None
    second = session_factory()
    assert claim_next_job(second, now, "worker-b") is None
    first.commit()
    third = session_factory()
    assert claim_next_job(third, now, "worker-c") is None
    third.close()
    second.close()
    stuck = session_factory()
    running = stuck.get(Job, job.id)
    assert running is not None
    running.locked_at = now - timedelta(minutes=30)
    running.status = "running"
    post_row = stuck.get(Post, post.id)
    assert post_row is not None
    post_row.status = "PUBLISHING"
    post_row.publish_dispatched_at = now - timedelta(minutes=20)
    stuck.commit()
    recovered = session_factory()
    assert recover_stuck_jobs(recovered, now, timedelta(minutes=5)) == 1
    recovered.commit()
    checked = recovered.get(Post, post.id)
    assert checked is not None
    assert checked.status == "UNKNOWN"
    job_row = recovered.get(Job, job.id)
    assert job_row is not None
    assert job_row.kind == "reconcile"
    assert job_row.status == "pending"
    first.close()
    stuck.close()
    recovered.close()


def test_restart_processes_a_persisted_job(session_factory, settings) -> None:
    session = session_factory()
    from acwa.security.crypto import TokenCipher

    cipher = TokenCipher(settings.token_encryption_key)
    clock = FrozenClock(datetime(2026, 1, 5, 12, tzinfo=UTC))
    account = _account(session, cipher)
    campaign = _campaign(session, account, status="paused")
    post = Post(
        campaign_id=campaign.id,
        account_id=account.id,
        origin="trial",
        status="GENERATING",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    session.add(post)
    session.flush()
    session.add(
        Job(
            post_id=post.id,
            kind="generate",
            status="pending",
            run_at=clock.now(),
            max_attempts=3,
            attempts=0,
            created_at=clock.now(),
            updated_at=clock.now(),
        )
    )
    session.commit()
    session.close()
    restarted = session_factory()
    generator = CountingGenerator("Текст после перезапуска")
    worked = run_once(
        restarted,
        settings=settings,
        clock=clock,
        generator=generator,
        threads=DemoThreads(),
        cipher=cipher,
        worker_id="after-restart",
    )
    assert worked is True
    stored = restarted.scalars(select(Post)).one()
    assert stored.status == "PENDING_APPROVAL"
    assert stored.text == "Текст после перезапуска"
    restarted.close()


def test_api_demo_flow_and_secret_hiding(client, app, settings) -> None:
    created = client.post("/api/accounts/demo")
    assert created.status_code == 200, created.text
    account = created.json()
    assert "plain-token" not in created.text
    assert "sk-integration-secret" not in created.text
    assert "token" not in account
    body = _payload(account["id"])
    campaign = client.post("/api/campaigns", json=body)
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["id"]
    trial = client.post(f"/api/campaigns/{campaign_id}/trial")
    assert trial.status_code == 202, trial.text
    post_id = trial.json()["id"]
    _run(app, settings)
    pending = client.get(f"/api/posts/{post_id}")
    assert pending.json()["status"] == "PENDING_APPROVAL"
    edited = "Исправленный демонстрационный текст."
    update = client.patch(f"/api/posts/{post_id}", json={"text": edited})
    assert update.status_code == 200, update.text
    approved = client.post(f"/api/posts/{post_id}/approve")
    assert approved.status_code == 200, approved.text
    _run(app, settings)
    published = client.get(f"/api/posts/{post_id}")
    payload = published.json()
    assert payload["status"] == "PUBLISHED"
    assert payload["text"] == edited
    assert payload["is_demo_publication"] is True
    assert payload["permalink"] is None
    assert str(payload["external_id"]).startswith("demo:")
    assert payload["model"] == "demo"
    listed = client.get("/api/posts", params={"view": "history"}).json()
    assert listed["items"][0]["id"] == post_id
    settings_body = client.get("/api/settings").text
    assert "sk-integration-secret" not in settings_body
    assert DEV_FERNET not in settings_body
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["demo_banner"]
    assert "sk-integration-secret" not in dashboard.text


def test_api_rejects_missing_and_wrong_password(app, settings) -> None:
    with TestClient(app) as bare:
        health = bare.get("/api/health")
        assert health.status_code == 200
        assert health.json()["auth_required"] is True
        denied = bare.get("/api/dashboard")
        assert denied.status_code == 401
        assert settings.auth_token not in denied.text
        wrong = bare.get("/api/settings", headers={"Authorization": "Bearer not-the-password"})
        assert wrong.status_code == 401
        assert settings.auth_token not in wrong.text
        docs = bare.get("/docs")
        assert docs.status_code == 401


def _run(app, settings) -> None:
    from acwa.clock import SystemClock

    session = app.state.session_factory()
    try:
        run_once(
            session,
            settings=settings,
            clock=SystemClock(),
            generator=app.state.generator,
            threads=app.state.threads,
            cipher=app.state.cipher,
            worker_id="test",
        )
    finally:
        session.close()


def _payload(account_id: str) -> dict[str, object]:
    return {
        "account_id": account_id,
        "name": "Демонстрационная кампания",
        "topic": "Тема дня",
        "context": "Демонстрационные данные",
        "audience": "",
        "language": "ru",
        "tone": "спокойный",
        "goal": "",
        "desired_length": "short",
        "extra_instructions": "",
        "required_points": "",
        "forbidden": "",
        "examples": "",
        "allow_emoji": False,
        "allow_hashtags": False,
        "allow_links": False,
        "publish_mode": "manual",
        "timezone": "Europe/Moscow",
        "weekdays": [1, 2, 3, 4, 5],
        "times_of_day": ["10:00"],
        "starts_on": "2026-01-05",
        "ends_on": None,
        "activate": False,
    }


DEV_FERNET = "LT9kgrT3RvPvRfszF9yrxTTVqCqlwnkN7nlzgzwzjLo="
