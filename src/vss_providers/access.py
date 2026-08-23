from __future__ import annotations

import math
import re
import hashlib
import xml.etree.ElementTree as ET

from .contracts import ClockProvider, GeneratedMedia, MonotonicReading, StoryboardRenderProvider, StoryboardRenderRequest, UtcTimestamp
from .errors import ProviderAccessDenied, ProviderExecutionFailure

UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class SafeClockHandle:
    __slots__ = ("__provider",)

    def __init__(self, provider: ClockProvider) -> None:
        object.__setattr__(self, "_SafeClockHandle__provider", provider)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("clock provider handle is immutable")

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

    __slots__ = ("__clock", "__storyboard")

    def __init__(
        self,
        clock: ClockProvider | None = None,
        storyboard: StoryboardRenderProvider | None = None,
    ) -> None:
        object.__setattr__(self, "_ProviderAccess__clock", SafeClockHandle(clock) if clock is not None else None)
        object.__setattr__(self, "_ProviderAccess__storyboard", SafeStoryboardRenderHandle(storyboard) if storyboard is not None else None)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("provider access is immutable")

    def get_clock(self) -> SafeClockHandle:
        if self.__clock is None:
            raise ProviderAccessDenied("clock provider access was not declared and authorized")
        return self.__clock

    def get_storyboard_renderer(self) -> "SafeStoryboardRenderHandle":
        if self.__storyboard is None:
            raise ProviderAccessDenied("storyboard render provider access was not declared and authorized")
        return self.__storyboard


class SafeStoryboardRenderHandle:
    __slots__ = ("__provider",)

    def __init__(self, provider: StoryboardRenderProvider) -> None:
        object.__setattr__(self, "_SafeStoryboardRenderHandle__provider", provider)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("storyboard render provider handle is immutable")

    def render(self, request: StoryboardRenderRequest) -> GeneratedMedia:
        try:
            result = self.__provider.render(request)
        except Exception as exc:
            raise ProviderExecutionFailure("storyboard render provider execution failed") from exc
        if (not isinstance(result, GeneratedMedia) or result.media_type != "image/svg+xml"
                or not isinstance(result.content, bytes) or len(result.content) > 262144
                or result.width != 1200 or result.height != 1500
                or result.content_sha256 != hashlib.sha256(result.content).hexdigest()):
            raise ProviderExecutionFailure("storyboard render provider returned invalid media")
        try:
            if b"<!DOCTYPE" in result.content.upper() or b"<!ENTITY" in result.content.upper():
                raise ValueError
            root = ET.fromstring(result.content)
            if root.tag != "{http://www.w3.org/2000/svg}svg" or root.get("width") != "1200" or root.get("height") != "1500":
                raise ValueError
            panels = 0
            for element in root.iter():
                local = element.tag.rsplit("}", 1)[-1].lower()
                if local == "rect" and element.get("class") == "panel":
                    panels += 1
                if local in {"script", "foreignobject", "iframe", "object", "embed", "image", "audio", "video", "animate", "animatetransform", "set", "use"}:
                    raise ValueError
                for name, value in element.attrib.items():
                    if name.lower().startswith("on") or name.rsplit("}", 1)[-1].lower() in {"href", "src"} or "url(" in value.lower():
                        raise ValueError
            if panels != len(request.frames) or request.storyboard_specification_digest.encode("ascii") not in result.content:
                raise ValueError
            for frame in request.frames:
                for key in ("frame_id", "frame_specification_digest"):
                    if str(frame[key]).encode("ascii") not in result.content:
                        raise ValueError
        except (ET.ParseError, UnicodeError, ValueError, KeyError) as exc:
            raise ProviderExecutionFailure("storyboard render provider returned unsafe SVG") from exc
        return result
