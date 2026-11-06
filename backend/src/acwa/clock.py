from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._moment = moment.astimezone(UTC)

    def now(self) -> datetime:
        return self._moment

    def advance(self, delta: timedelta) -> None:
        self._moment += delta

    def set(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._moment = moment.astimezone(UTC)
