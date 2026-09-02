"""Inert, deterministic comparison evidence for admitted grounded candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import (
    ResourceContractError,
    ValidatedResourceArtifact,
    validate_production_visual_grounding_profile,
    validate_production_visual_grounding_review,
)


_PACKAGE_KEY = object()
_SELECTION_KEY = object()
_PROMOTION_KEY = object()

COMPARISON_AUTHORITY = {
    "ranking": False,
    "recommendation": False,
    "regeneration": False,
    "profile_mutation": False,
    "prompt_mutation": False,
    "provider_execution": False,
    "runtime_execution": False,
    "production": False,
    "asset_promotion": False,
    "publication": False,
    "workflow_activation": False,
    "canon_decision": False,
    "rights_decision": False,
}

PROMOTION_AUTHORITY = {
    **COMPARISON_AUTHORITY,
    "approval": False,
    "reservation": False,
    "deployment": False,
}


@dataclass(slots=True)
class GroundedStoryboardComparison:
    """An opaque, sealed package with a process-local single selection boundary."""

    _value: Any
    _selection_recorded: bool = field(default=False, init=False, repr=False)

    def __init__(self, key: object, *, value: dict[str, Any]) -> None:
        if key is not _PACKAGE_KEY:
            raise TypeError("grounded storyboard comparison requires authoritative construction")
        self._value = freeze_json(value)
        self._selection_recorded = False

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self._value)


@dataclass(frozen=True, slots=True, init=False)
class DevelopmentReviewSelection:
    _value: Any
    _promotion_recorded: bool = field(default=False, init=False, repr=False,
                                      compare=False)

    def __init__(self, key: object, *, value: dict[str, Any]) -> None:
        if key is not _SELECTION_KEY:
            raise TypeError("development review selection requires an authoritative comparison")
        object.__setattr__(self, "_value", freeze_json(value))
        object.__setattr__(self, "_promotion_recorded", False)

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self._value)


@dataclass(frozen=True, slots=True, init=False)
class GroundedStoryboardPromotion:
    """An opaque, sealed, accountable promotion-evidence record only."""

    _value: Any
    _authoritative_promotion_sha256: str = field(init=False, repr=False, compare=False)
    _asset_admission_recorded: bool = field(default=False, init=False, repr=False,
                                            compare=False)

    def __init__(self, key: object, *, value: dict[str, Any]) -> None:
        if key is not _PROMOTION_KEY:
            raise TypeError("grounded storyboard promotion requires authoritative construction")
        object.__setattr__(self, "_value", freeze_json(value))
        object.__setattr__(self, "_authoritative_promotion_sha256", value["promotion_sha256"])
        object.__setattr__(self, "_asset_admission_recorded", False)

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self._value)


def _candidate_evidence(generation: Any, candidate: Any, review: Any) -> dict[str, Any]:
    # Deferred imports preserve the existing controlled-generation -> storyboard import path.
    from vss_movie_controlled_generation import AdmittedControlledGeneration, AdmittedGeneratedCandidate
    from vss_movie_controlled_generation.contracts import validate_generation_request

    if type(generation) is not AdmittedControlledGeneration or type(candidate) is not AdmittedGeneratedCandidate:
        raise ResourceContractError("comparison requires authoritative admitted grounded candidates")
    if type(review) is not ValidatedResourceArtifact:
        raise ResourceContractError("comparison requires authoritative sealed review evidence")

    request = validate_generation_request(generation.request_json())
    candidate_value = candidate.candidate_json()
    profile_data = generation.grounding_profile_json()
    if request["contract_version"] != "3" or profile_data is None:
        raise ResourceContractError("comparison requires an admitted grounded candidate")
    profile = validate_production_visual_grounding_profile(profile_data)
    checked_review = validate_production_visual_grounding_review(review.to_json_value())
    review_value = checked_review.value

    if (candidate_value["request_sha256"] != request["request_sha256"]
            or candidate_value["lineage"] != request["lineage"]
            or candidate_value["scope"] != request["scope"]
            or candidate_value["provider"]["identity"] != request["provider"]["identity"]
            or candidate_value["provider"]["version"] != request["provider"]["version"]
            or candidate_value["provider"]["implementation_identity"]
            != request["provider"]["implementation_identity"]
            or candidate_value["provider"]["model_snapshot"] != request["provider"]["model_snapshot"]
            or request["projection"]["visual_grounding_profile_sha256"] != profile.value["profile_sha256"]
            or review_value["candidate_sha256"] != candidate_value["candidate_sha256"]
            or review_value["frame_grounding_sha256"] != request["projection"]["frame_grounding_sha256"]
            or review_value["visual_grounding_profile_sha256"] != profile.value["profile_sha256"]
            or any(value is not False for value in review_value["authority"].values())):
        raise ResourceContractError("comparison candidate evidence binding mismatch")

    return {
        "candidate_id": candidate_value["candidate_id"],
        "candidate_sha256": candidate_value["candidate_sha256"],
        "request_sha256": request["request_sha256"],
        "scope": dict(request["scope"]),
        "source_repository_lineage": dict(request["lineage"]),
        "frame_grounding_sha256": request["projection"]["frame_grounding_sha256"],
        "visual_grounding_profile": {
            "profile_id": profile.value["profile_id"],
            "revision": profile.value["revision"],
            "profile_sha256": profile.value["profile_sha256"],
        },
        "provider": {key: request["provider"][key] for key in (
            "identity", "version", "implementation_identity", "model_snapshot",
        )},
        "sealed_review": {key: review_value[key] for key in (
            "review_id", "review_sha256", "candidate_sha256", "frame_grounding_sha256",
            "visual_grounding_profile_sha256", "disposition",
        )},
    }


def create_grounded_storyboard_comparison(
    first_generation: Any, first_candidate: Any, first_review: Any,
    second_generation: Any, second_candidate: Any, second_review: Any,
) -> GroundedStoryboardComparison:
    """Construct evidence only; caller order is preserved and is never a ranking."""
    candidates = [
        _candidate_evidence(first_generation, first_candidate, first_review),
        _candidate_evidence(second_generation, second_candidate, second_review),
    ]
    if candidates[0]["candidate_sha256"] == candidates[1]["candidate_sha256"]:
        raise ResourceContractError("comparison candidates must be distinct")
    if candidates[0]["scope"] != candidates[1]["scope"]:
        raise ResourceContractError("comparison candidates have incompatible scope")
    package = {
        "schema_version": "1",
        "comparison_identity": "grounded_storyboard_candidate_comparison",
        "comparison_version": "1",
        "comparison_status": "development_review_only",
        "candidate_order": "caller_supplied_evidence_order_not_ranking",
        "candidates": candidates,
        "authority": dict(COMPARISON_AUTHORITY),
        "limitations": [
            "deterministic_evidence_only", "not_a_ranking_or_recommendation",
            "not_generation_or_regeneration_authority", "not_provider_or_runtime_authority",
            "not_production_publication_asset_workflow_canon_or_rights_authority",
        ],
        "comparison_sha256": "0" * 64,
    }
    package["comparison_sha256"] = canonical_digest(package)
    return GroundedStoryboardComparison(_PACKAGE_KEY, value=package)


def record_development_review_selection(
    comparison: Any, *, selected_candidate_id: str, reviewer_accountability_id: str,
    rationale: str,
) -> DevelopmentReviewSelection:
    """Record one explicit human selection; it deliberately grants no further authority."""
    if type(comparison) is not GroundedStoryboardComparison:
        raise ResourceContractError("selection requires an authoritative sealed comparison package")
    if comparison._selection_recorded:
        raise ResourceContractError("comparison selection has already been recorded")
    package = comparison.to_json_value()
    expected_seal = canonical_digest({**package, "comparison_sha256": "0" * 64})
    if package["comparison_sha256"] != expected_seal:
        raise ResourceContractError("comparison package seal mismatch")
    selected = [item for item in package["candidates"] if item["candidate_id"] == selected_candidate_id]
    if len(selected) != 1:
        raise ResourceContractError("selection candidate is not an exact comparison member")
    if not isinstance(reviewer_accountability_id, str) or not reviewer_accountability_id:
        raise ResourceContractError("selection reviewer accountability identifier is invalid")
    if not isinstance(rationale, str) or not rationale:
        raise ResourceContractError("selection rationale is invalid")
    value = {
        "schema_version": "1",
        "selection_identity": "grounded_storyboard_development_review_selection",
        "selection_version": "1",
        "comparison_sha256": package["comparison_sha256"],
        "selected_candidate_id": selected_candidate_id,
        "selected_candidate_sha256": selected[0]["candidate_sha256"],
        "reviewer_accountability_id": reviewer_accountability_id,
        "rationale": rationale,
        "authority": dict(COMPARISON_AUTHORITY),
        "limitations": [
            "human_accountability_evidence_only", "not_generation_or_regeneration_authority",
            "not_provider_or_runtime_authority", "not_production_publication_asset_workflow_canon_or_rights_authority",
        ],
        "selection_sha256": "0" * 64,
    }
    value["selection_sha256"] = canonical_digest(value)
    comparison._selection_recorded = True
    return DevelopmentReviewSelection(_SELECTION_KEY, value=value)


def _sealed_comparison_value(comparison: Any) -> dict[str, Any]:
    if type(comparison) is not GroundedStoryboardComparison:
        raise ResourceContractError("promotion requires an authoritative sealed comparison package")
    try:
        package = comparison.to_json_value()
        expected_seal = canonical_digest({**package, "comparison_sha256": "0" * 64})
        is_valid = (
            package["schema_version"] == "1"
            and package["comparison_identity"] == "grounded_storyboard_candidate_comparison"
            and package["comparison_version"] == "1"
            and package["comparison_status"] == "development_review_only"
            and package["comparison_sha256"] == expected_seal
            and isinstance(package["candidates"], list)
            and len(package["candidates"]) == 2
            and package["authority"] == COMPARISON_AUTHORITY
        )
    except (AttributeError, KeyError, TypeError):
        is_valid = False
    if not is_valid:
        raise ResourceContractError("comparison package seal or authority mismatch")
    return package


def _sealed_selection_value(selection: Any, comparison: dict[str, Any]) -> dict[str, Any]:
    if type(selection) is not DevelopmentReviewSelection:
        raise ResourceContractError("promotion requires an authoritative sealed selection evidence")
    try:
        value = selection.to_json_value()
        expected_seal = canonical_digest({**value, "selection_sha256": "0" * 64})
        selected = [item for item in comparison["candidates"]
                    if item["candidate_id"] == value["selected_candidate_id"]]
        is_valid = (
            value["schema_version"] == "1"
            and value["selection_identity"] == "grounded_storyboard_development_review_selection"
            and value["selection_version"] == "1"
            and value["comparison_sha256"] == comparison["comparison_sha256"]
            and value["selection_sha256"] == expected_seal
            and len(selected) == 1
            and value["selected_candidate_sha256"] == selected[0]["candidate_sha256"]
            and value["authority"] == COMPARISON_AUTHORITY
        )
    except (AttributeError, KeyError, TypeError):
        is_valid = False
    if not is_valid:
        raise ResourceContractError("selection evidence seal or comparison binding mismatch")
    return value


def record_grounded_storyboard_promotion(
    comparison: Any, selection: Any, generation: Any, candidate: Any, review: Any, *,
    promotion_approver_accountability_id: str, rationale: str,
) -> GroundedStoryboardPromotion:
    """Seal accountable promotion evidence without granting operational authority."""
    package = _sealed_comparison_value(comparison)
    selection_value = _sealed_selection_value(selection, package)
    if selection._promotion_recorded:
        raise ResourceContractError("selection promotion has already been recorded")
    selected_evidence = _candidate_evidence(generation, candidate, review)
    selected_member = [item for item in package["candidates"]
                       if item["candidate_id"] == selection_value["selected_candidate_id"]]
    if len(selected_member) != 1 or selected_evidence != selected_member[0]:
        raise ResourceContractError("promotion selected candidate evidence binding mismatch")
    if (not isinstance(promotion_approver_accountability_id, str)
            or not promotion_approver_accountability_id):
        raise ResourceContractError("promotion approver accountability identifier is invalid")
    if not isinstance(rationale, str) or not rationale:
        raise ResourceContractError("promotion rationale is invalid")
    value = {
        "schema_version": "1",
        "promotion_identity": "grounded_storyboard_selected_candidate_promotion",
        "promotion_version": "1",
        "promotion_status": "accountable_evidence_only",
        "comparison_sha256": package["comparison_sha256"],
        "selection_sha256": selection_value["selection_sha256"],
        "selected_candidate": selected_evidence,
        "promotion_approver_accountability_id": promotion_approver_accountability_id,
        "rationale": rationale,
        "authority": dict(PROMOTION_AUTHORITY),
        "limitations": [
            "accountable_promotion_evidence_only", "not_publication_or_deployment_authority",
            "not_provider_or_runtime_authority", "not_generation_or_regeneration_authority",
            "not_production_asset_canon_rights_or_workflow_authority",
        ],
        "promotion_sha256": "0" * 64,
    }
    value["promotion_sha256"] = canonical_digest(value)
    object.__setattr__(selection, "_promotion_recorded", True)
    return GroundedStoryboardPromotion(_PROMOTION_KEY, value=value)
