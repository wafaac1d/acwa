from datetime import UTC, datetime

from acwa.integrations.types import ErrorKind, IntegrationError
from acwa.services.insights import explain_insights_error, token_lacks_insights_scope, yesterday_window


def test_stored_token_without_insights_is_not_described_as_a_missing_app_permission() -> None:
    assert token_lacks_insights_scope("threads_basic,threads_content_publish") is True
    assert token_lacks_insights_scope("threads_basic,threads_content_publish,threads_manage_insights") is False
    assert token_lacks_insights_scope(None) is False
    message = explain_insights_error(
        IntegrationError(ErrorKind.PERMANENT, "(#100) The value must be a valid insights metric", code=100)
    )
    assert "threads_manage_insights" not in message
    assert "valid insights metric" in message


def test_yesterday_window_follows_the_campaign_timezone() -> None:
    now = datetime(2026, 11, 6, 0, 30, tzinfo=UTC)
    start, end, label = yesterday_window(now, "Europe/Minsk")
    assert label == "2026-11-05"
    assert start == datetime(2026, 11, 4, 21, tzinfo=UTC)
    assert end == datetime(2026, 11, 5, 21, tzinfo=UTC)
