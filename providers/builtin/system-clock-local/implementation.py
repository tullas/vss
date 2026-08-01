from __future__ import annotations

import time
from datetime import datetime, timezone

from vss_providers.contracts import MonotonicReading, UtcTimestamp


class LocalClockProvider:
    def now_utc(self) -> UtcTimestamp:
        value = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return UtcTimestamp(value)

    def monotonic_time(self) -> MonotonicReading:
        return MonotonicReading(time.monotonic())


def create_provider() -> LocalClockProvider:
    return LocalClockProvider()
