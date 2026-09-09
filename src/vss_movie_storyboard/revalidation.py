"""Bounded evidence for re-grounding immutable existing review media."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_resource_contracts import ResourceContractError, validate_existing_media_revalidation_evidence
from vss_movie_contracts import validate_existing_media_current_shot_binding

_KEY = object()
_FALSE = {"canon": False, "publication": False, "production": False, "runtime": False,
          "provider": False, "deployment": False, "regeneration": False, "ranking": False,
          "recommendation": False, "autonomous_workflow": False, "workflow_activation": False,
          "generation": False, "shot_selection": False, "asset_promotion": False,
          "rights_decision": False}
_LIMITATIONS = ["existing_media_revalidation_evidence_only", "exact_media_bytes_verified_by_sha256",
 "historical_lineage_is_historical_only", "historical_candidate_not_claimed_as_current_production",
 "new_human_grounding_review_required_against_current_lineage", "preserve_all_non_canonical_limitations",
 "no_canon_publication_production_runtime_provider_deployment_authority",
 "no_regeneration_ranking_recommendation_or_autonomous_workflow_authority"]
_BINDING_LIMITATIONS = ["current_lineage_reference_only", "revalidation_review_required",
 "historical_lineage_not_rewritten", "not_production_or_generation_authority",
 "not_provider_or_runtime_authority", "not_publication_export_scheduling_or_workflow_authority",
 "not_canon_or_rights_authority"]

def _schema(name):
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[2] / "schemas" / name).read_text())

def _lineage(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"story_fragment", "scene_breakdown", "production_option_set", "review_packet", "review_decision", "creative_decision_revision", "canon_snapshot", "production_canon_binding", "shot_plan_draft", "storyboard_specification", "storyboard_frame"} or not all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item) for item in value.values()):
        raise ResourceContractError("revalidation lineage is invalid")
    return dict(value)

def _check(value, media=None):
    try:
        return validate_existing_media_revalidation_evidence(value, media=media)
    except ResourceContractError:
        raise
    except Exception as exc:
        raise ResourceContractError("revalidation evidence is invalid") from exc

@dataclass(frozen=True, slots=True, init=False)
class ExistingMediaRevalidationEvidence:
    _value: Any
    def __init__(self, key, value):
        if key is not _KEY: raise TypeError("revalidation evidence requires authoritative construction")
        object.__setattr__(self, "_value", freeze_json(value))
    def to_json_value(self): return thaw_json(self._value)

@dataclass(frozen=True, slots=True, init=False)
class ExistingMediaCurrentShotBinding:
    _value: Any
    def __init__(self, key, value):
        if key is not _KEY: raise TypeError("current shot binding requires authoritative construction")
        object.__setattr__(self, "_value", freeze_json(value))
    def to_json_value(self): return thaw_json(self._value)

def prepare_existing_media_revalidation(*, media: bytes, media_reference: str,
        historical_only: dict[str, Any], current_target: dict[str, Any]) -> ExistingMediaRevalidationEvidence:
    """Build a pending review request; no historical review is accepted as re-review."""
    if type(media) is not bytes: raise ResourceContractError("existing media must be bytes")
    required = {"candidate_sha256", "grounding_review_sha256", "promotion_sha256", "admission_sha256", "catalog_asset_sha256", "lineage"}
    if set(historical_only) != required: raise ResourceContractError("historical evidence must be explicit and complete")
    hist = dict(historical_only); hist["lineage"] = _lineage(hist["lineage"])
    if not all(isinstance(hist[k], str) and re.fullmatch(r"[0-9a-f]{64}", hist[k]) for k in required - {"lineage"}):
        raise ResourceContractError("historical evidence digest is invalid")
    required_target = {"project_id", "scene_id", "shot_id", "frame_id", "option_id", "shot_card_digest", "frame_specification_digest", "storyboard_specification_digest", "lineage"}
    if set(current_target) != required_target: raise ResourceContractError("current authoritative target is incomplete")
    target = dict(current_target); target["lineage"] = _lineage(target["lineage"])
    review = {"status":"required_new_review", "review_request_sha256":"0" * 64, "review_sha256":None,
              "candidate_sha256":None, "scene_id":target["scene_id"], "shot_id":target["shot_id"],
              "frame_id":target["frame_id"], "option_id":target["option_id"], "disposition":"PENDING",
              "reviewer_accountability_id":"pending-human-review"}
    review["review_request_sha256"] = canonical_digest({**review, "review_request_sha256":"0" * 64})
    value = {"schema_version":"1", "contract_identity":"existing_media_revalidation_evidence", "contract_version":"1",
             "revalidation_id":"0", "status":"awaiting_new_human_grounding_review",
             "media":{"media_sha256":hashlib.sha256(media).hexdigest(), "media_type":"image/png", "media_reference":media_reference},
             "historical_only":hist, "current_authoritative_target":target, "human_grounding_review":review,
             "authority":dict(_FALSE), "limitations":list(_LIMITATIONS), "revalidation_sha256":"0" * 64}
    value["revalidation_id"] = "media-revalidation-" + canonical_digest({k:v for k,v in value.items() if k not in {"revalidation_id", "revalidation_sha256"}})[:32]
    value["revalidation_sha256"] = canonical_digest({**value, "revalidation_sha256":"0" * 64})
    return _check(value, media)

def complete_existing_media_revalidation(pending: ExistingMediaRevalidationEvidence, *,
        review: dict[str, Any]) -> ExistingMediaRevalidationEvidence:
    value = _check(pending.to_json_value())
    if value.value["status"] != "awaiting_new_human_grounding_review": raise ResourceContractError("revalidation is not pending")
    # Resource validation freezes nested values; thaw the authoritative target
    # before constructing the separately validated JSON binding artifact.
    target = thaw_json(value.value["current_authoritative_target"])
    required = {"review_sha256", "candidate_sha256", "scene_id", "shot_id", "frame_id", "option_id", "disposition", "reviewer_accountability_id"}
    if set(review) != required or review["disposition"] not in {"USE", "REGENERATE", "REJECT"}: raise ResourceContractError("new human review is incomplete")
    if any(review[k] != target[k] for k in ("scene_id", "shot_id", "frame_id", "option_id")) or review["candidate_sha256"] == value.value["historical_only"]["candidate_sha256"]:
        raise ResourceContractError("review is historical or bound to the wrong current target")
    if review["review_sha256"] != canonical_digest({**review, "review_sha256":"0" * 64}): raise ResourceContractError("new human review seal mismatch")
    out = value.to_json_value(); out["status"] = "revalidated_review_only"
    out["human_grounding_review"].update({"status":"complete", **review})
    out["revalidation_id"] = "media-revalidation-" + canonical_digest({k:v for k,v in out.items() if k not in {"revalidation_id", "revalidation_sha256"}})[:32]
    out["revalidation_sha256"] = canonical_digest({**out, "revalidation_sha256":"0" * 64})
    return _check(out)

def bind_existing_media_to_current_shot(revalidation: ExistingMediaRevalidationEvidence, *, media: bytes,
        current_target: dict[str, Any]) -> ExistingMediaCurrentShotBinding:
    value = _check(revalidation.to_json_value(), media)
    if value.value["status"] != "revalidated_review_only": raise ResourceContractError("current shot binding requires completed new human review")
    # Resource validation freezes nested values; thaw the authoritative target
    # before constructing the separately validated JSON binding artifact.
    target = thaw_json(value.value["current_authoritative_target"])
    checked_target = dict(current_target)
    checked_target["lineage"] = _lineage(checked_target.get("lineage"))
    if checked_target != target:
        raise ResourceContractError("current authoritative lineage mismatch")
    out = {"schema_version":"1", "contract_identity":"existing_media_current_shot_binding", "contract_version":"1",
           "binding_status":"sealed_current_visual_basis_reference_only", "revalidation_id":value.value["revalidation_id"],
           "revalidation_sha256":value.value["revalidation_sha256"], "media_sha256":value.value["media"]["media_sha256"],
           **{key:target[key] for key in ("project_id", "scene_id", "shot_id", "frame_id", "option_id")},
           "current_lineage":target["lineage"], "human_review_sha256":value.value["human_grounding_review"]["review_sha256"],
           "authority":{"canon":False,"publication":False,"production":False,"runtime":False,"provider":False,"deployment":False,"regeneration":False,"workflow_activation":False},
           "limitations":list(_BINDING_LIMITATIONS), "binding_sha256":"0" * 64}
    out["binding_sha256"] = canonical_digest(out)
    try:
        validate_existing_media_current_shot_binding(out)
    except Exception as exc:
        raise ResourceContractError("current shot binding contract validation failed") from exc
    return ExistingMediaCurrentShotBinding(_KEY, out)
