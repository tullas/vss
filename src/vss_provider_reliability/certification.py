"""Domain expertise and provider-certification contracts.

These contracts are development evidence only.  They deliberately expose no
provider transport, credential reader, reservation, or production authority.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Mapping

from vss_reasoning_contracts import canonical_digest


class ExpertiseDisposition(str, Enum):
    GENERIC_SUFFICIENT = "generic_engineering_sufficient"
    SPECIALIST_REVIEW = "specialist_review_required"
    SPECIALIST_CONTRACT = "specialist_owned_contract_or_certification_required"


class CertificationStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    CERTIFIED = "CERTIFIED"
    STALE = "STALE"


REQUIRED_CERTIFICATION_FIELDS = frozenset({
    "schema_version", "contract_identity", "contract_version", "provider",
    "product_service", "model_version", "supported_regions", "generation_modes",
    "request_schema_mapping", "authentication", "submission_semantics",
    "async_operation_semantics", "polling_fetch_semantics", "terminal_response_forms",
    "artifact_delivery_forms", "recovery_semantics", "media_contract", "quota_evidence",
    "pricing_evidence", "unsupported_probes", "deprecations", "authoritative_sources",
    "conformance", "live_certification", "production_eligibility", "authority",
})


def classify_expertise(domains: Mapping[str, str]) -> dict[str, ExpertiseDisposition]:
    """Classify a bounded domain inventory without creating agent roles."""
    specialist_contract = {
        "generative_video", "generative_image", "cloud_iam_authentication",
        "media_containers_codecs", "storage_artifact_persistence", "speech_voice",
        "music_audio", "cinematography_prompting", "character_visual_continuity",
        "rights_licensing_provenance", "cost_quota_billing", "distribution_publication",
    }
    if not isinstance(domains, Mapping) or not domains:
        raise ValueError("expertise inventory is empty")
    result: dict[str, ExpertiseDisposition] = {}
    for domain, disposition in domains.items():
        if not isinstance(domain, str) or not isinstance(disposition, str):
            raise ValueError("expertise inventory is invalid")
        result[domain] = (ExpertiseDisposition.SPECIALIST_CONTRACT
                          if domain in specialist_contract
                          else ExpertiseDisposition.SPECIALIST_REVIEW)
    return result


def validate_provider_certification(value: Mapping[str, Any], *, today: date | None = None) -> None:
    """Fail closed on missing provider facts, stale certification, or authority inflation."""
    if not isinstance(value, Mapping) or set(value) != REQUIRED_CERTIFICATION_FIELDS:
        raise ValueError("provider certification shape is invalid")
    if value["schema_version"] != "1" or value["contract_identity"] != "vss.provider-certification":
        raise ValueError("provider certification identity is invalid")
    for field in ("provider", "product_service", "model_version"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError("provider certification identity is incomplete")
    if not isinstance(value["supported_regions"], list) or not value["supported_regions"]:
        raise ValueError("provider certification regions are missing")
    for field in ("generation_modes", "authoritative_sources", "unsupported_probes", "deprecations"):
        if not isinstance(value[field], list):
            raise ValueError("provider certification list is invalid")
    if not isinstance(value["conformance"], Mapping) or value["conformance"].get("status") != "passed":
        raise ValueError("provider conformance is not passed")
    live = value["live_certification"]
    if not isinstance(live, Mapping) or live.get("status") not in {"UNKNOWN", "CERTIFIED", "STALE"}:
        raise ValueError("live certification status is invalid")
    if live.get("status") == "CERTIFIED" and not live.get("certified_at"):
        raise ValueError("certified provider has no certification date")
    if not isinstance(value["production_eligibility"], Mapping) or type(value["production_eligibility"].get("eligible")) is not bool:
        raise ValueError("provider production eligibility shape is invalid")
    if value["authority"] != {"provider_execution": False, "production": False, "publication": False,
                               "workflow_activation": False, "retry": False, "fallback": False}:
        raise ValueError("provider certification grants authority")


def assert_production_eligible(certification: Mapping[str, Any]) -> None:
    validate_provider_certification(certification)
    if (certification["live_certification"]["status"] != "CERTIFIED"
            or certification["production_eligibility"]["eligible"] is not True):
        raise ValueError("provider certification is not production eligible")


def assess_certification_readiness(certification: Mapping[str, Any], *, credential_present: bool,
                                   quota_evidence_valid: bool, configuration_valid: bool) -> dict[str, Any]:
    """Use certified facts and closed evidence; never probe generation or model metadata."""
    if not isinstance(certification, Mapping):
        raise ValueError("provider certification is unavailable")
    unsupported = certification.get("unsupported_probes", [])
    if not isinstance(unsupported, list) or any(not isinstance(item, str) for item in unsupported):
        raise ValueError("provider unsupported-probe record is invalid")
    checks = {
        "credential_present": credential_present is True,
        "quota_evidence_valid": quota_evidence_valid is True,
        "configuration_valid": configuration_valid is True,
        "metadata_lookup_required": False,
        "provider_generation_called": False,
    }
    return {"checks": checks, "provider_call_count": 0,
            "ready": all(checks[name] for name in ("credential_present", "quota_evidence_valid", "configuration_valid"))}


def assert_request_matches_certification(request: Mapping[str, Any], certification: Mapping[str, Any]) -> None:
    """Bind runtime request semantics to the exact certified provider contract."""
    if not isinstance(request, Mapping) or not isinstance(certification, Mapping):
        raise ValueError("provider contract binding is invalid")
    provider = request.get("provider")
    if not isinstance(provider, Mapping) or provider.get("model_snapshot") != certification.get("model_version"):
        raise ValueError("provider model contract mismatch")
    if provider.get("location") not in certification.get("supported_regions", []):
        raise ValueError("provider region contract mismatch")
    if request.get("bounds", {}).get("maximum_outputs") != 1:
        raise ValueError("provider output bound is uncertified")


def durable_moving_shot_package(request: Mapping[str, Any], immutable_inputs: Mapping[str, str]) -> dict[str, Any]:
    """Persist every semantic request field so a later process can reconstruct it."""
    if not isinstance(request, Mapping) or not isinstance(immutable_inputs, Mapping):
        raise ValueError("durable moving-shot package is invalid")
    source_lineage = request.get("source_lineage")
    if not isinstance(source_lineage, Mapping) or not source_lineage:
        raise ValueError("moving-shot source lineage is required")
    canonical_request = dict(request)
    if not isinstance(canonical_request.get("request_sha256"), str):
        raise ValueError("moving-shot request digest is required")
    return {
        "schema_version": "1",
        "contract_identity": "vss.approved-moving-shot-package",
        "contract_version": "1",
        "canonical_request": canonical_request,
        "immutable_inputs": dict(sorted(immutable_inputs.items())),
        "execution_namespace": f"{canonical_request['scope']['production_id']}/{canonical_request['scope']['shot_id']}",
        "authority": {"provider_execution": False, "production": False, "publication": False,
                      "workflow_activation": False, "retry": False, "fallback": False},
    }


def reconstruct_durable_moving_shot_request(package: Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Reconstruct and verify identity using only serialized package evidence."""
    if not isinstance(package, Mapping) or set(package) != {
        "schema_version", "contract_identity", "contract_version", "canonical_request",
        "immutable_inputs", "execution_namespace", "authority",
    }:
        raise ValueError("durable moving-shot package shape is invalid")
    request = package["canonical_request"]
    if not isinstance(request, Mapping) or not isinstance(package["immutable_inputs"], Mapping):
        raise ValueError("durable moving-shot canonical content is invalid")
    if not isinstance(request.get("source_lineage"), Mapping) or not request["source_lineage"]:
        raise ValueError("durable moving-shot source lineage is missing")
    sealed = dict(request)
    claimed = sealed.get("request_sha256")
    sealed["request_sha256"] = "0" * 64
    reconstructed = canonical_digest(sealed)
    if claimed != reconstructed:
        raise ValueError("durable moving-shot request digest mismatch")
    scope = request.get("scope")
    namespace = f"{scope['production_id']}/{scope['shot_id']}" if isinstance(scope, Mapping) else ""
    if package["execution_namespace"] != namespace:
        raise ValueError("durable moving-shot namespace mismatch")
    if package["authority"] != {"provider_execution": False, "production": False, "publication": False,
                                "workflow_activation": False, "retry": False, "fallback": False}:
        raise ValueError("durable moving-shot authority is invalid")
    return dict(request), reconstructed, namespace
