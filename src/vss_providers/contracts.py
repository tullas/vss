from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class UtcTimestamp:
    value: str


@dataclass(frozen=True, slots=True)
class MonotonicReading:
    seconds: float


class ClockProvider(Protocol):
    def now_utc(self) -> UtcTimestamp: ...

    def monotonic_time(self) -> MonotonicReading: ...


@dataclass(frozen=True, slots=True)
class StoryboardRenderRequest:
    project_id: str
    scene_id: str
    storyboard_specification_digest: str
    frames: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class GeneratedMedia:
    media_type: str
    content: bytes
    width: int
    height: int
    content_sha256: str


class StoryboardRenderProvider(Protocol):
    def render(self, request: StoryboardRenderRequest) -> GeneratedMedia: ...


@dataclass(frozen=True, slots=True)
class PictorialFrameRequest:
    project_id: str
    scene_id: str
    storyboard_specification_digest: str
    frame_id: str
    frame_specification_digest: str
    semantic_request_digest: str
    provider_visible_digest: str
    projection: Mapping[str, Any]


class PictorialFrameProvider(Protocol):
    def generate(self, request: PictorialFrameRequest) -> GeneratedMedia: ...


@dataclass(frozen=True, slots=True)
class ControlledFrameRequest:
    prompt: str
    request_sha256: str
    provider_request_sha256: str


@dataclass(frozen=True, slots=True)
class ControlledFrameResult:
    media: GeneratedMedia
    latency_ms: int
    usage: Mapping[str, int]
    estimated_cost_usd: str
    response_sha256: str
    provider_created: int | None
    request_id: str | None
    content_credentials: Mapping[str, Any]


class ControlledFrameProvider(Protocol):
    def generate(self, request: ControlledFrameRequest, *, credential: str, transport: Any = None) -> ControlledFrameResult: ...
