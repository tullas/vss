from __future__ import annotations

import math
import re

from .contracts import ClockProvider, MonotonicReading, UtcTimestamp
from .errors import ProviderAccessDenied, ProviderExecutionFailure

UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class SafeClockHandle:
    __slots__ = ("__provider",)

    def __init__(self, provider: ClockProvider) -> None:
        self.__provider = provider

    def now_utc(self) -> UtcTimestamp:
        try:
            result = self.__provider.now_utc()
        except Exception as exc:
            raise ProviderExecutionFailure("clock provider execution failed") from exc
        if not isinstance(result, UtcTimestamp) or not UTC_TIMESTAMP.fullmatch(result.value):
            raise ProviderExecutionFailure("clock provider returned an invalid UTC timestamp")
        return result

    def monotonic_time(self) -> MonotonicReading:
        try:
            result = self.__provider.monotonic_time()
        except Exception as exc:
            raise ProviderExecutionFailure("clock provider execution failed") from exc
        if (
            not isinstance(result, MonotonicReading)
            or not isinstance(result.seconds, (int, float))
            or not math.isfinite(result.seconds)
            or result.seconds < 0
        ):
            raise ProviderExecutionFailure("clock provider returned an invalid monotonic reading")
        return result


class ProviderAccess:
    """A non-enumerable set of provider handles authorized for one execution."""

    __slots__ = ("__clock",)

    def __init__(
        self,
        clock: ClockProvider | None = None,
    ) -> None:
        self.__clock = SafeClockHandle(clock) if clock is not None else None

    def get_clock(self) -> SafeClockHandle:
        if self.__clock is None:
            raise ProviderAccessDenied("clock provider access was not declared and authorized")
        return self.__clock
