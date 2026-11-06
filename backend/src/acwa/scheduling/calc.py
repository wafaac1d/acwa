"""Local schedule math.

Wall-clock times are interpreted in the campaign IANA timezone.
Instants returned to the rest of the application are UTC.
A local time that does not exist on a DST spring-forward day is skipped.
An ambiguous local time on a fall-back day uses the earlier offset (fold=0).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Schedule:
    timezone: str
    weekdays: tuple[int, ...]
    times: tuple[str, ...]
    starts_on: date
    ends_on: date | None


def validate_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Неизвестный часовой пояс: {name}") from exc
    return name


def parse_hhmm(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Время должно быть в формате ЧЧ:ММ: {value}")
    hour, minute = int(parts[0]), int(parts[1])
    if hour > 23 or minute > 59 or len(parts[0]) != 2 or len(parts[1]) != 2:
        raise ValueError(f"Время должно быть в формате ЧЧ:ММ: {value}")
    return time(hour, minute)


def local_slot_to_utc(day: date, value: str, zone: ZoneInfo) -> datetime | None:
    clock = parse_hhmm(value)
    naive = datetime.combine(day, clock)
    first = naive.replace(tzinfo=zone, fold=0)
    roundtrip = first.astimezone(UTC).astimezone(zone)
    if (roundtrip.date(), roundtrip.hour, roundtrip.minute) != (day, clock.hour, clock.minute):
        return None
    return first.astimezone(UTC)


def slots_between(schedule: Schedule, after: datetime, until: datetime) -> list[datetime]:
    """Return UTC instants in (after, until]."""
    if after.tzinfo is None or until.tzinfo is None:
        raise ValueError("schedule bounds must be timezone-aware")
    after_utc = after.astimezone(UTC)
    until_utc = until.astimezone(UTC)
    if until_utc <= after_utc:
        return []
    zone = ZoneInfo(schedule.timezone)
    weekdays = set(schedule.weekdays)
    start_day = max(after_utc.astimezone(zone).date(), schedule.starts_on)
    end_day = until_utc.astimezone(zone).date()
    if schedule.ends_on is not None:
        end_day = min(end_day, schedule.ends_on)
    found: list[datetime] = []
    day = start_day
    while day <= end_day:
        if _iso_weekday(day) in weekdays:
            for value in schedule.times:
                instant = local_slot_to_utc(day, value, zone)
                if instant is None:
                    continue
                if after_utc < instant <= until_utc:
                    found.append(instant)
        day += timedelta(days=1)
    found.sort()
    return found


def upcoming_slots(schedule: Schedule, after: datetime, count: int) -> list[datetime]:
    if count <= 0:
        return []
    zone = ZoneInfo(schedule.timezone)
    weekdays = set(schedule.weekdays)
    start_day = max(after.astimezone(zone).date(), schedule.starts_on)
    found: list[datetime] = []
    day = start_day
    after_utc = after.astimezone(UTC)
    for _ in range(400):
        if schedule.ends_on is not None and day > schedule.ends_on:
            break
        if _iso_weekday(day) in weekdays:
            for value in schedule.times:
                instant = local_slot_to_utc(day, value, zone)
                if instant is not None and instant > after_utc:
                    found.append(instant)
                    if len(found) >= count:
                        found.sort()
                        return found[:count]
        day += timedelta(days=1)
    found.sort()
    return found[:count]


def schedule_from_campaign(campaign: Any) -> Schedule:
    return Schedule(
        timezone=str(campaign.timezone),
        weekdays=tuple(int(item) for item in campaign.weekdays),
        times=tuple(str(item) for item in campaign.times_of_day),
        starts_on=campaign.starts_on,
        ends_on=campaign.ends_on,
    )


def _iso_weekday(day: date) -> int:
    return day.isoweekday()
