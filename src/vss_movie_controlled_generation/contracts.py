from __future__ import annotations

from typing import Any

import hashlib

from vss_reasoning_contracts import canonical_digest
from vss_resource_contracts import ResourceContractError, ResourceContractRegistry


MAX_CONTRACT_BYTES = 131072


def seal_material(value: dict[str, Any], field: str) -> dict[str, Any]:
    return {**value, field: "0" * 64}


def validate_contract(value: Any, identity: str, seal_field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResourceContractError("controlled media artifact must be an object")
    errors = list(ResourceContractRegistry.built_in().iter_errors(identity, value))
    if errors:
        raise ResourceContractError("controlled media artifact does not match its contract")
    if value[seal_field] != canonical_digest(seal_material(value, seal_field)):
        raise ResourceContractError("controlled media artifact seal mismatch")
    return value


def validate_generation_request(value: Any) -> dict[str, Any]:
    return validate_contract(value, "controlled_storyboard_frame_generation_request/2", "request_sha256")


def validate_attempt(value: Any) -> dict[str, Any]:
    return validate_contract(value, "controlled_media_generation_attempt/1", "attempt_sha256")


def validate_attempt_outcome(value: Any) -> dict[str, Any]:
    return validate_contract(value, "controlled_media_generation_attempt_outcome/1", "outcome_sha256")


def validate_candidate(value: Any) -> dict[str, Any]:
    value = validate_contract(value, "generated_review_candidate/2", "candidate_sha256")
    expected = "generated-review-" + canonical_digest({
        key: item for key, item in value.items() if key not in {"candidate_id", "candidate_sha256"}
    })[:32]
    if value["candidate_id"] != expected:
        raise ResourceContractError("generated review candidate identity mismatch")
    return value


def validate_candidate_media(value: Any, content: bytes) -> dict[str, Any]:
    from .service import content_credentials_summary

    value = validate_candidate(value)
    if (not isinstance(content, bytes)
            or value["media"]["content_sha256"] != hashlib.sha256(content).hexdigest()
            or value["media"]["byte_count"] != len(content)
            or value["media"]["content_credentials"] != content_credentials_summary(content)):
        raise ResourceContractError("generated review candidate media reconstruction mismatch")
    return value


def validate_empty_review(value: Any) -> dict[str, Any]:
    return validate_contract(value, "generated_review_candidate_review/1", "review_sha256")
