"""Inert reusable-asset evidence admission for one promoted grounded candidate."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import ResourceContractError

from .comparison import GroundedStoryboardPromotion, PROMOTION_AUTHORITY


_ADMISSION_KEY = object()
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_ID = re.compile(r"^generated-review-[0-9a-f]{32}$")
_REVIEW_ID = re.compile(r"^visual-grounding-review-[0-9a-f]{32}$")
_FRAME_ID = re.compile(r"^frame-[0-9a-f]{24}$")
_ID = re.compile(r"^[a-z][a-z0-9._:-]{2,127}$")
_ACCOUNTABILITY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@/-]{0,127}$")

_PROMOTION_KEYS = {
    "schema_version", "promotion_identity", "promotion_version", "promotion_status",
    "comparison_sha256", "selection_sha256", "selected_candidate",
    "promotion_approver_accountability_id", "rationale", "authority", "limitations",
    "promotion_sha256",
}
_CANDIDATE_KEYS = {
    "candidate_id", "candidate_sha256", "request_sha256", "scope",
    "source_repository_lineage", "frame_grounding_sha256", "visual_grounding_profile",
    "provider", "sealed_review",
}
_SCOPE_KEYS = {"tenant_id", "universe_id", "production_id", "project_id", "scene_id", "frame_id"}
_LINEAGE_KEYS = {
    "story_fragment", "scene_breakdown", "production_option_set", "review_packet",
    "review_decision", "creative_decision_revision", "canon_snapshot",
    "production_canon_binding", "shot_plan_draft", "storyboard_specification",
    "storyboard_frame",
}
_PROFILE_KEYS = {"profile_id", "revision", "profile_sha256"}
_PROVIDER_KEYS = {"identity", "version", "implementation_identity", "model_snapshot"}
_REVIEW_KEYS = {
    "review_id", "review_sha256", "candidate_sha256", "frame_grounding_sha256",
    "visual_grounding_profile_sha256", "disposition",
}
_PROMOTION_LIMITATIONS = [
    "accountable_promotion_evidence_only", "not_publication_or_deployment_authority",
    "not_provider_or_runtime_authority", "not_generation_or_regeneration_authority",
    "not_production_asset_canon_rights_or_workflow_authority",
]

ASSET_ADMISSION_AUTHORITY = {
    "publication": False,
    "deployment": False,
    "export": False,
    "scheduling": False,
    "workflow_activation": False,
    "provider_execution": False,
    "runtime_execution": False,
    "generation": False,
    "regeneration": False,
    "pixel_mutation": False,
    "prompt_mutation": False,
    "profile_mutation": False,
    "production_use": False,
    "asset_use": False,
    "canon_decision": False,
    "rights_decision": False,
    "approval": False,
    "reservation": False,
    "catalog_registration": False,
    "durable_storage": False,
    "lifecycle_management": False,
}

ASSET_ADMISSION_LIMITATIONS = [
    "accountable_reusable_asset_evidence_only",
    "exact_promoted_candidate_only",
    "process_local_one_use",
    "not_a_durable_asset_or_catalog_record",
    "not_publication_deployment_export_scheduling_or_workflow_authority",
    "not_provider_runtime_generation_or_regeneration_authority",
    "not_pixel_prompt_or_profile_mutation_authority",
    "not_production_asset_use_canon_or_rights_authority",
]


@dataclass(frozen=True, slots=True, init=False)
class GroundedStoryboardAssetAdmission:
    """Opaque sealed status evidence; it grants no operational or asset-use authority."""

    _value: Any

    def __init__(self, key: object, *, value: dict[str, Any]) -> None:
        if key is not _ADMISSION_KEY:
            raise TypeError("grounded storyboard asset admission requires authoritative construction")
        object.__setattr__(self, "_value", freeze_json(value))

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self._value)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _is_bounded_text(value: Any, maximum: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= maximum


def _expected_provider() -> dict[str, str]:
    # Deferred import preserves the controlled-generation -> storyboard render import path.
    from vss_movie_controlled_generation.service import (
        IMPLEMENTATION_IDENTITY,
        MODEL_SNAPSHOT,
        PROVIDER_IDENTITY,
        PROVIDER_VERSION,
    )

    return {
        "identity": PROVIDER_IDENTITY,
        "version": PROVIDER_VERSION,
        "implementation_identity": IMPLEMENTATION_IDENTITY,
        "model_snapshot": MODEL_SNAPSHOT,
    }


def _valid_selected_candidate(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_KEYS:
        return False
    scope = candidate.get("scope")
    lineage = candidate.get("source_repository_lineage")
    profile = candidate.get("visual_grounding_profile")
    provider = candidate.get("provider")
    review = candidate.get("sealed_review")
    if not all(isinstance(value, dict) for value in (scope, lineage, profile, provider, review)):
        return False
    if (set(scope) != _SCOPE_KEYS or set(lineage) != _LINEAGE_KEYS
            or set(profile) != _PROFILE_KEYS or set(provider) != _PROVIDER_KEYS
            or set(review) != _REVIEW_KEYS):
        return False
    return bool(
        isinstance(candidate["candidate_id"], str)
        and _CANDIDATE_ID.fullmatch(candidate["candidate_id"])
        and _is_digest(candidate["candidate_sha256"])
        and _is_digest(candidate["request_sha256"])
        and all(isinstance(scope[key], str) and _ID.fullmatch(scope[key])
                for key in _SCOPE_KEYS - {"frame_id"})
        and isinstance(scope["frame_id"], str) and _FRAME_ID.fullmatch(scope["frame_id"])
        and all(_is_digest(lineage[key]) for key in _LINEAGE_KEYS)
        and _is_digest(candidate["frame_grounding_sha256"])
        and isinstance(profile["profile_id"], str) and _ID.fullmatch(profile["profile_id"])
        and type(profile["revision"]) is int and 1 <= profile["revision"] <= 2147483647
        and _is_digest(profile["profile_sha256"])
        and provider == _expected_provider()
        and isinstance(review["review_id"], str) and _REVIEW_ID.fullmatch(review["review_id"])
        and _is_digest(review["review_sha256"])
        and review["disposition"] == "USE"
        and review["candidate_sha256"] == candidate["candidate_sha256"]
        and review["frame_grounding_sha256"] == candidate["frame_grounding_sha256"]
        and review["visual_grounding_profile_sha256"] == profile["profile_sha256"]
        and lineage["storyboard_frame"] == candidate["frame_grounding_sha256"]
    )


def _sealed_promotion_value(promotion: Any) -> dict[str, Any]:
    if type(promotion) is not GroundedStoryboardPromotion:
        raise ResourceContractError("asset admission requires authoritative M10.3 promotion evidence")
    try:
        value = promotion.to_json_value()
        expected_seal = canonical_digest({**value, "promotion_sha256": "0" * 64})
        valid = (
            set(value) == _PROMOTION_KEYS
            and value["schema_version"] == "1"
            and value["promotion_identity"] == "grounded_storyboard_selected_candidate_promotion"
            and value["promotion_version"] == "1"
            and value["promotion_status"] == "accountable_evidence_only"
            and _is_digest(value["comparison_sha256"])
            and _is_digest(value["selection_sha256"])
            and value["authority"] == PROMOTION_AUTHORITY
            and value["limitations"] == _PROMOTION_LIMITATIONS
            and isinstance(value["promotion_approver_accountability_id"], str)
            and _ACCOUNTABILITY_ID.fullmatch(value["promotion_approver_accountability_id"])
            and _is_bounded_text(value["rationale"], 1024)
            and value["promotion_sha256"] == expected_seal
            and promotion._authoritative_promotion_sha256 == value["promotion_sha256"]
            and _valid_selected_candidate(value["selected_candidate"])
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ResourceContractError("promotion evidence seal, lineage, or authority mismatch")
    return value


def admit_grounded_storyboard_asset(
    promotion: Any, *, asset_admission_approver_accountability_id: str, rationale: str,
) -> GroundedStoryboardAssetAdmission:
    """Admit exact promotion evidence as reusable-asset status without granting authority."""
    promotion_value = _sealed_promotion_value(promotion)
    if promotion._asset_admission_recorded:
        raise ResourceContractError("grounded storyboard promotion has already been admitted")
    if (not isinstance(asset_admission_approver_accountability_id, str)
            or _ACCOUNTABILITY_ID.fullmatch(asset_admission_approver_accountability_id) is None):
        raise ResourceContractError("asset admission approver accountability identifier is invalid")
    if not _is_bounded_text(rationale, 1024):
        raise ResourceContractError("asset admission rationale is invalid")

    candidate = promotion_value["selected_candidate"]
    value = {
        "schema_version": "1",
        "admission_identity": "grounded_storyboard_asset_admission",
        "admission_version": "1",
        "admission_status": "reusable_asset_evidence_only",
        "source": {
            "comparison_identity": "grounded_storyboard_candidate_comparison",
            "comparison_version": "1",
            "comparison_sha256": promotion_value["comparison_sha256"],
            "selection_identity": "grounded_storyboard_development_review_selection",
            "selection_version": "1",
            "selection_sha256": promotion_value["selection_sha256"],
            "promotion_identity": promotion_value["promotion_identity"],
            "promotion_version": promotion_value["promotion_version"],
            "promotion_sha256": promotion_value["promotion_sha256"],
        },
        "admitted_candidate": candidate,
        "provider_binding_sha256": canonical_digest(candidate["provider"]),
        "asset_admission_approver_accountability_id": asset_admission_approver_accountability_id,
        "rationale": rationale,
        "authority": dict(ASSET_ADMISSION_AUTHORITY),
        "limitations": list(ASSET_ADMISSION_LIMITATIONS),
        "admission_sha256": "0" * 64,
    }
    value["admission_sha256"] = canonical_digest(value)
    object.__setattr__(promotion, "_asset_admission_recorded", True)
    return GroundedStoryboardAssetAdmission(_ADMISSION_KEY, value=value)
