from __future__ import annotations

import math
import re
import hashlib
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET
from collections.abc import Mapping

from .contracts import ClockProvider, ControlledFrameProvider, ControlledFrameRequest, ControlledFrameResult, GeneratedMedia, MonotonicReading, PictorialFrameProvider, PictorialFrameRequest, StoryboardRenderProvider, StoryboardRenderRequest, UtcTimestamp
from .errors import ProviderAccessDenied, ProviderExecutionFailure
from .png import validate_pictorial_png

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

    __slots__ = ("__clock", "__storyboard", "__pictorial", "__controlled")

    def __init__(
        self,
        clock: ClockProvider | None = None,
        storyboard: StoryboardRenderProvider | None = None,
        pictorial: PictorialFrameProvider | None = None,
        controlled: ControlledFrameProvider | None = None,
        controlled_secret_reader=None,
        controlled_transport=None,
    ) -> None:
        object.__setattr__(self, "_ProviderAccess__clock", SafeClockHandle(clock) if clock is not None else None)
        object.__setattr__(self, "_ProviderAccess__storyboard", SafeStoryboardRenderHandle(storyboard) if storyboard is not None else None)
        object.__setattr__(self, "_ProviderAccess__pictorial", SafePictorialFrameHandle(pictorial) if pictorial is not None else None)
        object.__setattr__(self, "_ProviderAccess__controlled", SafeControlledFrameHandle(
            controlled, controlled_secret_reader, controlled_transport) if controlled is not None else None)

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

    def get_pictorial_frame_generator(self) -> "SafePictorialFrameHandle":
        if self.__pictorial is None:
            raise ProviderAccessDenied("pictorial frame provider access was not declared and authorized")
        return self.__pictorial

    def get_controlled_frame_generator(self) -> "SafeControlledFrameHandle":
        if self.__controlled is None:
            raise ProviderAccessDenied("controlled frame provider access was not declared and authorized")
        return self.__controlled


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


class SafePictorialFrameHandle:
    __slots__ = ("__provider", "__calls")

    def __init__(self, provider: PictorialFrameProvider) -> None:
        object.__setattr__(self, "_SafePictorialFrameHandle__provider", provider)
        object.__setattr__(self, "_SafePictorialFrameHandle__calls", 0)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("pictorial frame provider handle is immutable")

    def generate(self, request: PictorialFrameRequest) -> GeneratedMedia:
        if self.__calls != 0:
            raise ProviderAccessDenied("pictorial frame provider call ceiling exceeded")
        object.__setattr__(self, "_SafePictorialFrameHandle__calls", 1)
        try:
            result = self.__provider.generate(request)
        except Exception as exc:
            raise ProviderExecutionFailure("pictorial frame provider execution failed") from exc
        if (not isinstance(result, GeneratedMedia) or result.media_type != "image/png"
                or not isinstance(result.content, bytes)
                or result.content_sha256 != hashlib.sha256(result.content).hexdigest()):
            raise ProviderExecutionFailure("pictorial frame provider returned invalid media")
        width, height = validate_pictorial_png(result.content)
        if (result.width, result.height) != (width, height):
            raise ProviderExecutionFailure("pictorial frame provider returned inconsistent dimensions")
        return result


class SafeControlledFrameHandle:
    __slots__ = ("__provider", "__secret_reader", "__transport", "__calls")

    def __init__(self, provider: ControlledFrameProvider, secret_reader, transport) -> None:
        object.__setattr__(self, "_SafeControlledFrameHandle__provider", provider)
        object.__setattr__(self, "_SafeControlledFrameHandle__secret_reader", secret_reader)
        object.__setattr__(self, "_SafeControlledFrameHandle__transport", transport)
        object.__setattr__(self, "_SafeControlledFrameHandle__calls", 0)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("controlled frame provider handle is immutable")

    def generate(self, request: ControlledFrameRequest) -> ControlledFrameResult:
        if self.__calls:
            raise ProviderAccessDenied("controlled frame provider call ceiling exceeded")
        object.__setattr__(self, "_SafeControlledFrameHandle__calls", 1)
        from vss_movie_controlled_generation import SECRET_NAME
        try:
            secret = self.__secret_reader(SECRET_NAME)
        except Exception as exc:
            raise ProviderExecutionFailure("controlled frame provider credential is unavailable") from exc
        if not isinstance(secret, str) or not secret or len(secret) > 512:
            raise ProviderExecutionFailure("controlled frame provider credential is unavailable")
        try:
            result = self.__provider.generate(request, credential=secret, transport=self.__transport)
        except (ProviderAccessDenied, ProviderExecutionFailure):
            raise
        except Exception as exc:
            raise ProviderExecutionFailure("controlled frame provider execution failed") from exc
        if (not isinstance(result, ControlledFrameResult) or not isinstance(result.media, GeneratedMedia)
                or result.media.media_type != "image/png" or result.media.width != 1280
                or result.media.height != 720 or len(result.media.content) > 10 * 1024 * 1024
                or result.media.content_sha256 != hashlib.sha256(result.media.content).hexdigest()
                or result.content_credentials_present is not False
                or not isinstance(result.latency_ms, int) or not 0 <= result.latency_ms <= 600000
                or not isinstance(result.estimated_cost_usd, str)
                or not re.fullmatch(r"[0-9]+\.[0-9]{6}", result.estimated_cost_usd)
                or not re.fullmatch(r"[0-9a-f]{64}", result.response_sha256)):
            raise ProviderExecutionFailure("controlled frame provider returned invalid media")
        if (not isinstance(result.usage, Mapping)
                or set(result.usage) != {"input_tokens", "output_tokens", "total_tokens"}
                or any(type(value) is not int or not 0 <= value <= 10_000_000
                       for value in result.usage.values())
                or result.usage["total_tokens"] != result.usage["input_tokens"] + result.usage["output_tokens"]
                or not (result.provider_created is None
                        or type(result.provider_created) is int and result.provider_created >= 0)
                or not (result.request_id is None
                        or isinstance(result.request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", result.request_id))):
            raise ProviderExecutionFailure("controlled frame provider returned invalid provenance")
        try:
            if Decimal(result.estimated_cost_usd) > Decimal("0.100000"):
                raise ProviderExecutionFailure("controlled frame provider exceeded its cost ceiling")
        except InvalidOperation as exc:
            raise ProviderExecutionFailure("controlled frame provider returned invalid cost") from exc
        from vss_movie_creative_smoke.png import validate_openai_png
        summary = validate_openai_png(result.media.content)
        if summary.content_credentials_present:
            raise ProviderExecutionFailure("controlled frame provider output asserted untrusted credentials")
        return result
