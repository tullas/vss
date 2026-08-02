from __future__ import annotations

import math
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Mapping

from .errors import InvalidPerformanceProfile

PROFILE_VERSION = "1"
WORKLOAD_IDENTITY = "reasoning.generate-options/1"
FIXTURE_IDENTITY = "generate-options-runtime-valid/1"
EXPECTED_CONTENT_DIGEST = "74da3d2ab42310fd661832264f3169f642aa55b4ba465be945af4f9cb46869a7"  # pragma: allowlist secret
HARD_MAX_CONCURRENCY = 16
HARD_MAX_REQUESTS = 500
HARD_MAX_ENDURANCE_SECONDS = 60.0
HARD_MAX_TOTAL_TIMEOUT_SECONDS = 300.0


def _integer(value: object, name: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidPerformanceProfile(f"performance profile {name} is invalid")
    return value


def _number(value: object, name: str, *, minimum: float, maximum: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise InvalidPerformanceProfile(f"performance profile {name} is invalid")
    return float(value)


@dataclass(frozen=True, slots=True)
class PerformanceProfile:
    identity: str
    version: str
    workload_identity: str
    fixture_identity: str
    expected_content_digest: str
    expected_option_count: int
    warmup_requests: int
    measured_requests: int
    concurrency: int
    maximum_outstanding: int
    request_timeout_seconds: float
    total_timeout_seconds: float
    stress_concurrency_steps: tuple[int, ...]
    stress_requests_per_step: int
    endurance_seconds: float
    endurance_request_limit: int
    verify_audit: bool = True
    failure_tolerance: int = 0

    def __post_init__(self) -> None:
        if type(self.stress_concurrency_steps) is not tuple:
            raise InvalidPerformanceProfile("stress concurrency steps are not immutable")
        if self.version != PROFILE_VERSION or self.workload_identity != WORKLOAD_IDENTITY:
            raise InvalidPerformanceProfile("performance profile identity is unsupported")
        if self.fixture_identity != FIXTURE_IDENTITY or len(self.expected_content_digest) != 64:
            raise InvalidPerformanceProfile("performance fixture identity is unsupported")
        _integer(self.expected_option_count, "expected_option_count", minimum=1, maximum=8)
        _integer(self.warmup_requests, "warmup_requests", minimum=0, maximum=32)
        _integer(self.measured_requests, "measured_requests", minimum=1, maximum=HARD_MAX_REQUESTS)
        _integer(self.concurrency, "concurrency", minimum=1, maximum=HARD_MAX_CONCURRENCY)
        _integer(self.maximum_outstanding, "maximum_outstanding", minimum=1, maximum=HARD_MAX_CONCURRENCY)
        if self.maximum_outstanding < self.concurrency or self.measured_requests < self.concurrency:
            raise InvalidPerformanceProfile("performance profile concurrency is inconsistent")
        _number(self.request_timeout_seconds, "request_timeout_seconds", minimum=0.001, maximum=300.0)
        _number(self.total_timeout_seconds, "total_timeout_seconds", minimum=0.001, maximum=HARD_MAX_TOTAL_TIMEOUT_SECONDS)
        _integer(self.stress_requests_per_step, "stress_requests_per_step", minimum=0, maximum=64)
        _number(self.endurance_seconds, "endurance_seconds", minimum=0.0, maximum=HARD_MAX_ENDURANCE_SECONDS)
        _integer(self.endurance_request_limit, "endurance_request_limit", minimum=0, maximum=HARD_MAX_REQUESTS)
        _integer(self.failure_tolerance, "failure_tolerance", minimum=0, maximum=8)
        if type(self.verify_audit) is not bool:
            raise InvalidPerformanceProfile("performance profile audit policy is invalid")
        previous = 0
        for step in self.stress_concurrency_steps:
            _integer(step, "stress_concurrency_step", minimum=1, maximum=HARD_MAX_CONCURRENCY)
            if step <= previous:
                raise InvalidPerformanceProfile("stress concurrency steps must increase")
            previous = step


_PROFILES: Mapping[str, PerformanceProfile] = MappingProxyType({
    "ci_safe": PerformanceProfile(
        "ci_safe", "1", WORKLOAD_IDENTITY, FIXTURE_IDENTITY, EXPECTED_CONTENT_DIGEST,
        4, 1, 8, 2, 2, 2.0, 30.0, (), 0, 0.0, 0,
    ),
    "laptop_small": PerformanceProfile(
        "laptop_small", "1", WORKLOAD_IDENTITY, FIXTURE_IDENTITY, EXPECTED_CONTENT_DIGEST,
        4, 2, 25, 4, 4, 2.0, 120.0, (1, 2, 4, 8), 8, 3.0, 100,
    ),
    "laptop_standard": PerformanceProfile(
        "laptop_standard", "1", WORKLOAD_IDENTITY, FIXTURE_IDENTITY, EXPECTED_CONTENT_DIGEST,
        4, 5, 100, 8, 8, 2.0, 300.0, (1, 2, 4, 8, 16), 16, 5.0, 200,
    ),
})


def get_profile(identity: str) -> PerformanceProfile:
    if type(identity) is not str or identity not in _PROFILES:
        raise InvalidPerformanceProfile("unknown performance profile")
    return _PROFILES[identity]


def profile_identities() -> tuple[str, ...]:
    return tuple(_PROFILES)


def profile_digest(profile: PerformanceProfile) -> str:
    from vss_reasoning_contracts import canonical_digest

    snapshot = {}
    for field in fields(profile):
        value = getattr(profile, field.name)
        snapshot[field.name] = list(value) if type(value) is tuple else value
    return canonical_digest(snapshot)
