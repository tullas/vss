from __future__ import annotations

import base64
from enum import Enum
from typing import Any

from .foundation import FailureClass, FlightRecorder


class DigitalTwinScenario(str, Enum):
    MALFORMED_CREDENTIALS = "malformed_credentials"
    AUTH_REJECTION = "auth_rejection"
    REQUEST_REJECTION = "request_rejection"
    ACCEPTED_LRO = "accepted_lro"
    DELAYED_POLLING = "delayed_polling"
    QUOTA_TERMINAL_ERROR = "quota_terminal_error"
    VALID_INLINE_MEDIA = "valid_inline_media"
    URI_MEDIA = "uri_media"
    MALFORMED_INLINE_MEDIA = "malformed_inline_media"
    UNEXPECTED_TERMINAL_SHAPE = "unexpected_terminal_shape"
    LOCAL_PERSISTENCE_FAILURE = "local_persistence_failure"
    LEDGER_STATE_FAILURE = "ledger_state_failure"


_OPERATION = "offline/providers/example/operations/twin-1"
_MP4 = b"\x00\x00\x00\x10ftypisom\x00\x00\x00\x00"


class ProviderDigitalTwin:
    """A deterministic fake lifecycle; it never owns or calls a provider."""

    def rehearse(self, scenario: DigitalTwinScenario) -> dict[str, Any]:
        if not isinstance(scenario, DigitalTwinScenario):
            raise ValueError("digital-twin scenario is invalid")
        recorder = FlightRecorder({"provider": "offline-digital-twin", "scenario": scenario.value})
        calls: list[str] = []
        if scenario == DigitalTwinScenario.MALFORMED_CREDENTIALS:
            recorder.record("authentication", status="rejected", failure_class=FailureClass.AUTHENTICATION)
            return {"scenario": scenario.value, "provider_call_count": 0, "calls": calls, "flight_recorder": recorder.freeze()}
        if scenario == DigitalTwinScenario.LEDGER_STATE_FAILURE:
            recorder.record("ledger", status="rejected", failure_class=FailureClass.LEDGER_STATE)
            return {"scenario": scenario.value, "provider_call_count": 0, "calls": calls, "flight_recorder": recorder.freeze()}
        calls.append("submission")
        recorder.record("submission", status="accepted" if scenario not in {DigitalTwinScenario.AUTH_REJECTION, DigitalTwinScenario.REQUEST_REJECTION} else "rejected",
                        failure_class=None if scenario not in {DigitalTwinScenario.AUTH_REJECTION, DigitalTwinScenario.REQUEST_REJECTION} else (FailureClass.AUTHENTICATION if scenario == DigitalTwinScenario.AUTH_REJECTION else FailureClass.REQUEST_CONTRACT))
        if scenario in {DigitalTwinScenario.AUTH_REJECTION, DigitalTwinScenario.REQUEST_REJECTION}:
            return {"scenario": scenario.value, "provider_call_count": 1, "calls": calls, "flight_recorder": recorder.freeze()}
        polls = 3 if scenario == DigitalTwinScenario.DELAYED_POLLING else 1
        for ordinal in range(1, polls + 1):
            calls.append("poll")
            recorder.record("poll", status="done" if ordinal == polls else "running", metadata={"ordinal": ordinal, "done": ordinal == polls})
        if scenario == DigitalTwinScenario.QUOTA_TERMINAL_ERROR:
            recorder.record("terminal", status="error", failure_class=FailureClass.QUOTA, metadata={"status": "RESOURCE_EXHAUSTED"})
        elif scenario == DigitalTwinScenario.LOCAL_PERSISTENCE_FAILURE:
            recorder.record("persistence", status="failed", failure_class=FailureClass.PERSISTENCE)
        else:
            terminal: dict[str, object] = {"done": True}
            if scenario == DigitalTwinScenario.URI_MEDIA:
                terminal["response"] = {"videos": [{"gcsUri": "gs://offline-twin/video.mp4", "mimeType": "video/mp4"}]}
            elif scenario == DigitalTwinScenario.MALFORMED_INLINE_MEDIA:
                terminal["response"] = {"videos": [{"bytesBase64Encoded": "not-base64", "mimeType": "video/mp4"}]}
            elif scenario == DigitalTwinScenario.UNEXPECTED_TERMINAL_SHAPE:
                terminal["response"] = {"unexpected": []}
            else:
                terminal["response"] = {"videos": [{"bytesBase64Encoded": base64.b64encode(_MP4).decode(), "mimeType": "video/mp4"}]}
            representation: dict[str, object] = {"field_path": "response.videos[0]", "kind": "other"}
            if scenario == DigitalTwinScenario.URI_MEDIA:
                representation.update({"field_path": "response.videos[0].gcsUri", "kind": "uri", "declared_mime_type": "video/mp4", "uri": "gs://offline-twin/video.mp4"})
            elif scenario == DigitalTwinScenario.MALFORMED_INLINE_MEDIA:
                representation.update({"field_path": "response.videos[0].bytesBase64Encoded", "kind": "inline_base64", "declared_mime_type": "video/mp4", "encoded_length": 10, "value_preview": "not-base64"})
            elif scenario != DigitalTwinScenario.UNEXPECTED_TERMINAL_SHAPE:
                representation.update({"field_path": "response.videos[0].bytesBase64Encoded", "kind": "inline_base64", "declared_mime_type": "video/mp4", "encoded_length": len(base64.b64encode(_MP4))})
            recorder.record_terminal({"done": True, "response_keys": sorted(terminal.get("response", {}).keys()) if isinstance(terminal.get("response"), dict) else [], "video_representation": representation})
        return {"scenario": scenario.value, "provider_call_count": 1, "poll_count": polls, "calls": calls, "flight_recorder": recorder.freeze()}
