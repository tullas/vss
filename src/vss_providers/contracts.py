from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UtcTimestamp:
    value: str


@dataclass(frozen=True, slots=True)
class MonotonicReading:
    seconds: float


class ClockProvider(Protocol):
    def now_utc(self) -> UtcTimestamp: ...

    def monotonic_time(self) -> MonotonicReading: ...
