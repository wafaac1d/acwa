from datetime import UTC, datetime
from uuid import uuid4

from acwa.integrations.types import ErrorKind, IntegrationError
from acwa.models import Post
from acwa.services.insights import explain_insights_error, token_lacks_insights_scope, yesterday_window
from acwa.services.learning import learning_notes, midnight_after, next_local_midnight


def test_stored_token_without_insights_is_not_described_as_a_missing_app_permission() -> None:
    assert token_lacks_insights_scope("threads_basic,threads_content_publish") is True
    assert token_lacks_insights_scope("threads_basic,threads_content_publish,threads_manage_insights") is False
    assert token_lacks_insights_scope(None) is False
    message = explain_insights_error(
        IntegrationError(ErrorKind.PERMANENT, "(#100) The value must be a valid insights metric", code=100)
    )
    assert "threads_manage_insights" not in message
    assert "valid insights metric" in message


def test_learning_waits_until_local_midnight_and_ranks_real_totals() -> None:
    afternoon = datetime(2026, 11, 8, 12, tzinfo=UTC)
    assert next_local_midnight(afternoon, "Europe/Minsk") == datetime(2026, 11, 8, 21, tzinfo=UTC)
    after_midnight = datetime(2026, 11, 8, 21, 5, tzinfo=UTC)
    assert midnight_after(after_midnight, "Europe/Minsk") == datetime(2026, 11, 9, 21, tzinfo=UTC)
    strong = Post(
        id=uuid4(),
        text="Короткий конкретный совет",
        insights={"views": 20, "likes": 4, "replies": 1, "reposts": 0, "quotes": 0, "shares": 1},
        insights_collected_at=afternoon,
        insights_error=None,
    )
    weak = Post(
        id=uuid4(),
        text="Общий призыв без детали",
        insights={"views": 3, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0, "shares": 0},
        insights_collected_at=afternoon,
        insights_error=None,
    )
    notes = learning_notes([weak, strong], date_label="2026-11-07", timezone="Europe/Minsk")
    assert notes.index("Короткий конкретный совет") < notes.index("Общий призыв без детали")
    assert "просмотры 20" in notes
    assert "не прирост за день" in notes


def test_yesterday_window_follows_the_campaign_timezone() -> None:
    now = datetime(2026, 11, 6, 0, 30, tzinfo=UTC)
    start, end, label = yesterday_window(now, "Europe/Minsk")
    assert label == "2026-11-05"
    assert start == datetime(2026, 11, 4, 21, tzinfo=UTC)
    assert end == datetime(2026, 11, 5, 21, tzinfo=UTC)
