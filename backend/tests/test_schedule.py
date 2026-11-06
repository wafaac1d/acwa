from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from acwa.content.length import threads_length
from acwa.scheduling.calc import Schedule, local_slot_to_utc, slots_between, upcoming_slots


def _schedule(**overrides: object) -> Schedule:
    data: dict[str, object] = {
        "timezone": "UTC",
        "weekdays": (1, 2, 3, 4, 5, 6, 7),
        "times": ("10:00",),
        "starts_on": date(2026, 1, 1),
        "ends_on": None,
    }
    data.update(overrides)
    return Schedule(
        timezone=str(data["timezone"]),
        weekdays=tuple(data["weekdays"]),  # type: ignore[arg-type]
        times=tuple(data["times"]),  # type: ignore[arg-type]
        starts_on=data["starts_on"],  # type: ignore[arg-type]
        ends_on=data["ends_on"],  # type: ignore[arg-type]
    )


def test_next_slot_uses_zone_not_fixed_offset() -> None:
    schedule = _schedule(timezone="Europe/Moscow", times=("10:00",), weekdays=(1,))
    after = datetime(2026, 1, 4, 0, 0, tzinfo=UTC)  # Sunday
    slots = upcoming_slots(schedule, after, 1)
    assert slots == [datetime(2026, 1, 5, 7, 0, tzinfo=UTC)]
    local = slots[0].astimezone(ZoneInfo("Europe/Moscow"))
    assert (local.hour, local.minute) == (10, 0)


def test_spring_forward_gap_is_skipped() -> None:
    zone = ZoneInfo("America/New_York")
    missing = local_slot_to_utc(date(2026, 3, 8), "02:30", zone)
    present = local_slot_to_utc(date(2026, 3, 8), "03:30", zone)
    assert missing is None
    assert present == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)


def test_fall_back_uses_earlier_offset() -> None:
    zone = ZoneInfo("America/New_York")
    instant = local_slot_to_utc(date(2026, 11, 1), "01:30", zone)
    assert instant == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_europe_dst_gap_and_overlap() -> None:
    zone = ZoneInfo("Europe/Berlin")
    assert local_slot_to_utc(date(2026, 3, 29), "02:30", zone) is None
    overlap = local_slot_to_utc(date(2026, 10, 25), "02:30", zone)
    assert overlap == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


def test_slots_between_are_exclusive_of_cursor() -> None:
    schedule = _schedule(times=("10:00", "11:00"))
    after = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
    until = datetime(2026, 1, 5, 11, 0, tzinfo=UTC)
    assert slots_between(schedule, after, until) == [datetime(2026, 1, 5, 11, 0, tzinfo=UTC)]


def test_end_date_stops_the_schedule() -> None:
    schedule = _schedule(ends_on=date(2026, 1, 5), weekdays=(1,))
    after = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    assert upcoming_slots(schedule, after, 3) == []


def test_emoji_counts_as_utf8_bytes() -> None:
    assert threads_length("привет") == 6
    assert threads_length("a😀") == 5
    assert threads_length("👍") == 4
