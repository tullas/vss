from __future__ import annotations

import math
import re
import hashlib
import xml.etree.ElementTree as ET

from .contracts import ClockProvider, CreativeExperimentProvider, CreativeExperimentRequest, CreativeExperimentResult, GeneratedMedia, MonotonicReading, PictorialFrameProvider, PictorialFrameRequest, StoryboardRenderProvider, StoryboardRenderRequest, UtcTimestamp
from .errors import ExperimentalProviderDiagnostic, ProviderAccessDenied, ProviderExecutionFailure
from .png import validate_pictorial_png
from .experimental_png import inspect_experimental_png, validate_experimental_openai_png

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

    __slots__ = ("__clock", "__storyboard", "__pictorial", "__experiment")

    def __init__(
        self,
        clock: ClockProvider | None = None,
        storyboard: StoryboardRenderProvider | None = None,
        pictorial: PictorialFrameProvider | None = None,
        experiment: CreativeExperimentProvider | None = None,
    ) -> None:
        object.__setattr__(self, "_ProviderAccess__clock", SafeClockHandle(clock) if clock is not None else None)
        object.__setattr__(self, "_ProviderAccess__storyboard", SafeStoryboardRenderHandle(storyboard) if storyboard is not None else None)
        object.__setattr__(self, "_ProviderAccess__pictorial", SafePictorialFrameHandle(pictorial) if pictorial is not None else None)
        object.__setattr__(self, "_ProviderAccess__experiment", SafeCreativeExperimentHandle(experiment) if experiment is not None else None)

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

    def get_creative_experiment_generator(self) -> "SafeCreativeExperimentHandle":
        if self.__experiment is None:
            raise ProviderAccessDenied("creative experiment provider access was not declared and authorized")
        return self.__experiment


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


class SafeCreativeExperimentHandle:
    __slots__ = ("__provider", "__calls")

    def __init__(self, provider: CreativeExperimentProvider) -> None:
        object.__setattr__(self, "_SafeCreativeExperimentHandle__provider", provider)
        object.__setattr__(self, "_SafeCreativeExperimentHandle__calls", 0)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("creative experiment provider handle is immutable")

    def generate(self, request: CreativeExperimentRequest) -> CreativeExperimentResult:
        if self.__calls:
            raise ProviderAccessDenied("creative experiment provider call ceiling exceeded")
        object.__setattr__(self, "_SafeCreativeExperimentHandle__calls", 1)
        try:
            result = self.__provider.generate(request)
        except ProviderExecutionFailure as exc:
            raise ProviderExecutionFailure("creative experiment provider execution failed", diagnostic=exc.diagnostic) from exc
        except Exception as exc:
            raise ProviderExecutionFailure("creative experiment provider execution failed") from exc
        if (not isinstance(result, CreativeExperimentResult) or result.provider_call_count != 1
                or not isinstance(result.latency_ms, int) or result.latency_ms < 0
                or not isinstance(result.usage, dict)
                or set(result.usage) - {"input_tokens", "output_tokens", "total_tokens"}
                or any(not isinstance(value, int) or value < 0 or value > 10000000 for value in result.usage.values())
                or type(result.content_credentials_present) is not bool
                or not (result.content_credentials_chunk_bytes is None
                        or type(result.content_credentials_chunk_bytes) is int
                        and 0 <= result.content_credentials_chunk_bytes <= 4 * 1024 * 1024)
                or (result.content_credentials_present != (result.content_credentials_chunk_bytes is not None))):
            raise ProviderExecutionFailure("creative experiment provider returned invalid evidence", diagnostic=
                ExperimentalProviderDiagnostic(True, "provider_result_invalid", 200,
                    message="provider response failed bounded validation"))
        media = result.media
        if (not isinstance(media, GeneratedMedia) or media.media_type != "image/png"
                or media.content_sha256 != hashlib.sha256(media.content).hexdigest()):
            raise ProviderExecutionFailure("creative experiment provider returned invalid media", diagnostic=
                ExperimentalProviderDiagnostic(True, "provider_result_invalid", 200,
                    message="provider response failed bounded validation"))
        if validate_experimental_openai_png(media.content) != (media.width, media.height):
            raise ProviderExecutionFailure("creative experiment provider returned inconsistent media", diagnostic=
                ExperimentalProviderDiagnostic(True, "provider_result_invalid", 200,
                    message="provider response failed bounded validation", decoded_media_bytes=len(media.content),
                    media_sha256=hashlib.sha256(media.content).hexdigest()))
        png_evidence = inspect_experimental_png(media.content)
        if ((result.content_credentials_present, result.content_credentials_chunk_bytes)
                != (png_evidence.content_credentials_present, png_evidence.content_credentials_chunk_bytes)):
            raise ProviderExecutionFailure("creative experiment provider returned inconsistent provenance evidence",
                diagnostic=ExperimentalProviderDiagnostic(True, "provider_result_invalid", 200,
                    message="provider response failed bounded validation", decoded_media_bytes=len(media.content),
                    media_sha256=hashlib.sha256(media.content).hexdigest(), png=png_evidence))
        return result
