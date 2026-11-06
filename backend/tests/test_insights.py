from datetime import UTC, datetime

from acwa.services.insights import yesterday_window


def test_yesterday_window_follows_the_campaign_timezone() -> None:
    now = datetime(2026, 11, 6, 0, 30, tzinfo=UTC)
    start, end, label = yesterday_window(now, "Europe/Minsk")
    assert label == "2026-11-05"
    assert start == datetime(2026, 11, 4, 21, tzinfo=UTC)
    assert end == datetime(2026, 11, 5, 21, tzinfo=UTC)
