from __future__ import annotations

import math
import statistics
from typing import Iterable

from .errors import PerformanceCorrectnessFailure


def nearest_rank(values: Iterable[float], percentile: int) -> float:
    samples = sorted(float(value) for value in values)
    if not samples or type(percentile) is not int or not 1 <= percentile <= 100:
        raise PerformanceCorrectnessFailure("latency percentile input is invalid")
    if any(not math.isfinite(value) or value < 0 for value in samples):
        raise PerformanceCorrectnessFailure("latency sample is invalid")
    rank = max(1, math.ceil(percentile / 100 * len(samples)))
    return samples[rank - 1]


def latency_summary(values: Iterable[float]) -> dict[str, float | int]:
    samples = tuple(float(value) for value in values)
    if not samples:
        raise PerformanceCorrectnessFailure("latency samples are missing")
    return {
        "sample_count": len(samples),
        "min_ms": round(min(samples) * 1000, 3),
        "mean_ms": round(statistics.fmean(samples) * 1000, 3),
        "p50_ms": round(nearest_rank(samples, 50) * 1000, 3),
        "p90_ms": round(nearest_rank(samples, 90) * 1000, 3),
        "p95_ms": round(nearest_rank(samples, 95) * 1000, 3),
        "p99_ms": round(nearest_rank(samples, 99) * 1000, 3),
        "max_ms": round(max(samples) * 1000, 3),
    }


def throughput(successes: int, duration_seconds: float) -> float:
    if type(successes) is not int or successes < 0:
        raise PerformanceCorrectnessFailure("throughput count is invalid")
    if type(duration_seconds) not in (int, float) or not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise PerformanceCorrectnessFailure("throughput duration is invalid")
    return round(successes / duration_seconds, 3)
