from dataclasses import dataclass
import hashlib
from typing import Any

from vss_movie_pictorial import AdmittedPictorialFrame
from vss_providers.png import validate_pictorial_png
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json
from vss_resource_contracts import (
    ResourceContractError,
    ValidatedResourceArtifact,
    admission_identity_material,
    admission_seal_material,
    artifact_identity_material,
    artifact_seal_material,
    asset_identity_material,
    asset_seal_material,
    resource_identity_material,
    resolution_request_identity_material,
    resolution_request_seal_material,
    resolution_result_identity_material,
    resolution_result_seal_material,
    validate_production_resource_artifact,
    validate_reusable_asset,
    validate_reusable_asset_admission,
    validate_resource_resolution_request,
    validate_resource_resolution_result,
)


PERMISSION = "reuse_as_universe_visual_reference"
BLOCKING_RESTRICTION = "no_reuse"
LIMITATIONS = [
    "inert_semantic_asset", "not_production_approval", "not_publication_authority",
    "not_runtime_authority", "not_training_permission", "exact_source_revision_only",
]


@dataclass(frozen=True, slots=True)
class ResourceAdmissionResult:
    admitted: bool
    code: str
    asset: ValidatedResourceArtifact | None


@dataclass(frozen=True, slots=True)
class ResourceResolutionResult:
    resolved: bool
    code: str
    resource: ValidatedResourceArtifact | None


def _identifier(prefix: str, material: Any) -> str:
    return prefix + canonical_digest(material)[:32]


def create_production_artifact(*, pictorial_frame: AdmittedPictorialFrame,
                               resource_revision: int, tenant_id: str,
                               universe_id: str | None,
                               content: bytes, ownership_class: str,
                               rights_status: str, permissions: list[str],
                               restrictions: list[str], rights_reference: str,
                               ancestors: list[dict[str, Any]] | None = None
                               ) -> ValidatedResourceArtifact:
    if not isinstance(pictorial_frame, AdmittedPictorialFrame):
        raise ResourceContractError("resource creation requires authoritative pictorial admission")
    try:
        validate_pictorial_png(content)
    except Exception as exc:
        raise ResourceContractError("resource content is not a validated pictorial PNG") from exc
    scope = {"tenant_id": tenant_id, "universe_id": universe_id,
             "production_id": pictorial_frame.project_id}
    activity = {
        "activity_id": _identifier("pictorial-activity-", pictorial_frame.semantic_request_digest),
        "operation_identity": "generate_one_pictorial_storyboard_frame",
        "operation_version": "1", "output_name": "review_frame",
        "pictorial_admission_id": pictorial_frame.admission_id,
        "storyboard_specification_digest": pictorial_frame.storyboard_specification_digest,
        "frame_id": pictorial_frame.frame_id,
        "frame_specification_digest": pictorial_frame.frame_specification_digest,
        "semantic_request_digest": pictorial_frame.semantic_request_digest,
    }
    content_digest = hashlib.sha256(content).hexdigest()
    rights = {
        "ownership_class": ownership_class, "status": rights_status,
        "permissions": sorted(permissions), "restrictions": sorted(restrictions),
        "rights_reference": rights_reference, "rights_policy_identity": "vss.resource-rights",
        "rights_policy_version": "1.0.0",
    }
    lineage = {"kind": "exact_production_output",
               "ancestors": sorted(ancestors or [], key=lambda item: (item["resource_id"], item["resource_revision"]))}
    value = {
        "schema_version": "1", "contract_identity": "production_resource_artifact",
        "contract_version": "1", "artifact_id": "artifact-" + "0" * 32,
        "resource_id": "resource-" + "0" * 32, "resource_revision": resource_revision,
        "resource_kind": "storyboard_review_frame", "scope": scope, "activity": activity,
        "content_sha256": content_digest, "media_type": "image/png", "rights": rights,
        "lineage": lineage, "artifact_sha256": "0" * 64,
    }
    value["resource_id"] = _identifier("resource-", resource_identity_material(value))
    value["artifact_id"] = _identifier("artifact-", artifact_identity_material(value))
    value["artifact_sha256"] = canonical_digest(artifact_seal_material(value))
    return validate_production_resource_artifact(value, content=content)


def create_universe_admission(*, source_artifact: ValidatedResourceArtifact,
                              destination_tenant_id: str, destination_universe_id: str,
                              requested_permissions: list[str] | None = None,
                              carried_restrictions: list[str] | None = None,
                              rights_reference: str | None = None,
                              rights_status: str | None = None) -> ValidatedResourceArtifact:
    if not isinstance(source_artifact, ValidatedResourceArtifact):
        raise ResourceContractError("admission requires a validated source artifact")
    source = source_artifact.value
    universe_id = source["scope"]["universe_id"]
    source_binding = {
        "artifact_id": source["artifact_id"], "artifact_sha256": source["artifact_sha256"],
        "resource_id": source["resource_id"], "resource_revision": source["resource_revision"],
        "content_sha256": source["content_sha256"], "tenant_id": source["scope"]["tenant_id"],
        "universe_id": universe_id or destination_universe_id,
        "production_id": source["scope"]["production_id"],
    }
    destination = {"tenant_id": destination_tenant_id, "universe_id": destination_universe_id,
                   "scope_kind": "universe"}
    value = {
        "schema_version": "1", "contract_identity": "reusable_asset_admission",
        "contract_version": "1", "admission_id": "asset-admission-" + "0" * 32,
        "operation_identity": "admit_storyboard_review_frame_as_universe_visual_reference",
        "operation_version": "1", "decision": "admit", "source": source_binding,
        "destination": destination, "purpose": "storyboard_visual_reference",
        "requested_permissions": requested_permissions or [PERMISSION],
        "carried_restrictions": sorted(carried_restrictions if carried_restrictions is not None else thaw_json(source["rights"]["restrictions"])),
        "rights_reference": rights_reference or source["rights"]["rights_reference"],
        "rights_status": rights_status or source["rights"]["status"],
        "policy_identity": "vss.universe-visual-reference-admission", "policy_version": "1.0.0",
        "admission_sha256": "0" * 64,
    }
    value["admission_id"] = _identifier("asset-admission-", admission_identity_material(value))
    value["admission_sha256"] = canonical_digest(admission_seal_material(value))
    return validate_reusable_asset_admission(value)


def _reject(code: str) -> ResourceAdmissionResult:
    return ResourceAdmissionResult(False, code, None)


def admit_storyboard_frame_to_universe(source_artifact: Any, *, source_content: bytes,
                                       admission_request: Any) -> ResourceAdmissionResult:
    if not isinstance(source_artifact, ValidatedResourceArtifact):
        return _reject("invalid_source_artifact")
    try:
        source = validate_production_resource_artifact(
            source_artifact.to_json_value(), content=source_content)
    except ResourceContractError:
        return _reject("invalid_source_artifact")
    try:
        request = validate_reusable_asset_admission(
            admission_request.to_json_value() if isinstance(admission_request, ValidatedResourceArtifact)
            else admission_request)
    except (ResourceContractError, AttributeError, TypeError):
        return _reject("invalid_admission")
    artifact = source.value
    admission = request.value
    scope = artifact["scope"]
    if scope["universe_id"] is None:
        return _reject("source_has_no_universe")
    expected_source = {
        "artifact_id": artifact["artifact_id"], "artifact_sha256": artifact["artifact_sha256"],
        "resource_id": artifact["resource_id"], "resource_revision": artifact["resource_revision"],
        "content_sha256": artifact["content_sha256"], "tenant_id": scope["tenant_id"],
        "universe_id": scope["universe_id"], "production_id": scope["production_id"],
    }
    if thaw_json(admission["source"]) != expected_source:
        return _reject("source_binding_mismatch")
    destination = admission["destination"]
    if destination["tenant_id"] != scope["tenant_id"]:
        return _reject("tenant_mismatch")
    if destination["universe_id"] != scope["universe_id"]:
        return _reject("universe_mismatch")
    rights = artifact["rights"]
    if rights["status"] != "confirmed" or admission["rights_status"] != "confirmed":
        return _reject("rights_not_confirmed")
    if admission["rights_reference"] != rights["rights_reference"]:
        return _reject("rights_reference_mismatch")
    if PERMISSION not in rights["permissions"]:
        return _reject("permission_not_granted")
    if list(admission["requested_permissions"]) != [PERMISSION]:
        return _reject("permission_expansion")
    if BLOCKING_RESTRICTION in rights["restrictions"]:
        return _reject("reuse_restricted")
    if list(admission["carried_restrictions"]) != list(rights["restrictions"]):
        return _reject("restriction_mismatch")
    source_lineage = {
        "artifact_id": artifact["artifact_id"], "artifact_sha256": artifact["artifact_sha256"],
        "resource_id": artifact["resource_id"], "resource_revision": artifact["resource_revision"],
        "content_sha256": artifact["content_sha256"], "production_id": scope["production_id"],
        "activity": thaw_json(artifact["activity"]),
        "ancestors": thaw_json(artifact["lineage"]["ancestors"]),
    }
    admission_binding = {
        "admission_id": admission["admission_id"], "admission_sha256": admission["admission_sha256"],
        "operation_identity": admission["operation_identity"],
        "operation_version": admission["operation_version"],
        "policy_identity": admission["policy_identity"], "policy_version": admission["policy_version"],
    }
    asset_rights = {
        "ownership_class": rights["ownership_class"], "status": "confirmed",
        "permissions": [PERMISSION], "restrictions": thaw_json(rights["restrictions"]),
        "rights_reference": rights["rights_reference"],
        "rights_policy_identity": rights["rights_policy_identity"],
        "rights_policy_version": rights["rights_policy_version"],
    }
    value = {
        "schema_version": "1", "contract_identity": "reusable_asset", "contract_version": "1",
        "asset_id": "asset-" + "0" * 32, "asset_revision": 1,
        "asset_kind": "storyboard_visual_reference", "scope": thaw_json(destination),
        "purpose": admission["purpose"], "content_sha256": artifact["content_sha256"],
        "media_type": artifact["media_type"], "source": source_lineage,
        "admission": admission_binding, "rights": asset_rights, "limitations": LIMITATIONS,
        "asset_sha256": "0" * 64,
    }
    value["asset_id"] = _identifier("asset-", asset_identity_material(value))
    value["asset_sha256"] = canonical_digest(asset_seal_material(value))
    try:
        asset = validate_reusable_asset(value, source_artifact=source, admission=request,
                                        source_content=source_content)
    except ResourceContractError:
        return _reject("invalid_derived_asset")
    return ResourceAdmissionResult(True, "admitted", asset)


def create_resource_resolution_request(*, source_artifact: ValidatedResourceArtifact,
                                       admission: ValidatedResourceArtifact,
                                       asset: ValidatedResourceArtifact,
                                       source_content: bytes, tenant_id: str,
                                       universe_id: str, production_id: str,
                                       purpose: str = "storyboard_visual_reference"
                                       ) -> ValidatedResourceArtifact:
    validated_asset = validate_reusable_asset(
        asset.to_json_value(), source_artifact=source_artifact, admission=admission,
        source_content=source_content)
    item = validated_asset.value
    value = {
        "schema_version": "1", "contract_identity": "resource_resolution_request",
        "contract_version": "1", "request_id": "resource-resolution-" + "0" * 32,
        "operation_identity": "resolve_universe_visual_reference_for_production",
        "operation_version": "1",
        "consumer": {"tenant_id": tenant_id, "universe_id": universe_id,
                     "production_id": production_id, "scope_kind": "production"},
        "purpose": purpose,
        "asset": {key: item[key] for key in (
            "asset_id", "asset_revision", "asset_sha256", "content_sha256")},
        "source": {key: item["source"][key] for key in (
            "artifact_id", "artifact_sha256", "resource_id", "resource_revision")},
        "admission": {key: item["admission"][key]
                      for key in ("admission_id", "admission_sha256")},
        "permission": PERMISSION,
        "restrictions": thaw_json(item["rights"]["restrictions"]),
        "rights_reference": item["rights"]["rights_reference"],
        "request_sha256": "0" * 64,
    }
    value["request_id"] = _identifier(
        "resource-resolution-", resolution_request_identity_material(value))
    value["request_sha256"] = canonical_digest(resolution_request_seal_material(value))
    return validate_resource_resolution_request(value)


def _resolution_reject(code: str) -> ResourceResolutionResult:
    return ResourceResolutionResult(False, code, None)


def resolve_universe_visual_reference(*, source_artifact: Any, admission: Any,
                                      asset: Any, source_content: bytes, request: Any,
                                      tenant_id: str, universe_id: str,
                                      production_id: str,
                                      purpose: str = "storyboard_visual_reference"
                                      ) -> ResourceResolutionResult:
    if not all(isinstance(item, ValidatedResourceArtifact)
               for item in (source_artifact, admission, asset)):
        return _resolution_reject("invalid_authoritative_chain")
    try:
        validated_asset = validate_reusable_asset(
            asset.to_json_value(), source_artifact=source_artifact, admission=admission,
            source_content=source_content)
    except (ResourceContractError, AttributeError, TypeError):
        return _resolution_reject("invalid_authoritative_chain")
    try:
        validated_request = validate_resource_resolution_request(
            request.to_json_value() if isinstance(request, ValidatedResourceArtifact) else request)
    except (ResourceContractError, AttributeError, TypeError):
        return _resolution_reject("invalid_request")
    item = validated_asset.value
    requested = validated_request.value
    consumer = {"tenant_id": tenant_id, "universe_id": universe_id,
                "production_id": production_id, "scope_kind": "production"}
    if requested["consumer"] != consumer:
        return _resolution_reject("consumer_scope_mismatch")
    if item["scope"]["tenant_id"] != tenant_id:
        return _resolution_reject("tenant_mismatch")
    if item["scope"]["universe_id"] != universe_id:
        return _resolution_reject("universe_mismatch")
    if requested["purpose"] != purpose or item["purpose"] != purpose:
        return _resolution_reject("purpose_mismatch")
    expected_request = create_resource_resolution_request(
        source_artifact=source_artifact, admission=admission, asset=validated_asset,
        source_content=source_content, tenant_id=tenant_id, universe_id=universe_id,
        production_id=production_id, purpose=purpose)
    if requested != expected_request.value:
        return _resolution_reject("authoritative_binding_mismatch")
    value = {
        "schema_version": "1", "contract_identity": "resource_resolution_result",
        "contract_version": "1", "resolution_id": "resolved-resource-" + "0" * 32,
        "request": {key: requested[key] for key in (
            "request_id", "request_sha256", "operation_identity", "operation_version")},
        "consumer": thaw_json(requested["consumer"]), "purpose": purpose,
        "resolved_asset": {key: item[key] for key in (
            "asset_id", "asset_revision", "asset_sha256", "asset_kind",
            "content_sha256", "media_type")},
        "source": thaw_json(item["source"]), "admission": thaw_json(item["admission"]),
        "rights": {
            "ownership_class": item["rights"]["ownership_class"], "status": "confirmed",
            "permission": PERMISSION,
            "restrictions": thaw_json(item["rights"]["restrictions"]),
            "rights_reference": item["rights"]["rights_reference"],
            "rights_policy_identity": item["rights"]["rights_policy_identity"],
            "rights_policy_version": item["rights"]["rights_policy_version"],
        },
        "limitations": ["inert_resolution", "not_production_approval",
                        "not_publication_authority", "not_redistribution_authority",
                        "not_runtime_authority", "not_training_permission",
                        "no_storage_authority", "exact_asset_revision_only"],
        "result_sha256": "0" * 64,
    }
    value["resolution_id"] = _identifier(
        "resolved-resource-", resolution_result_identity_material(value))
    value["result_sha256"] = canonical_digest(resolution_result_seal_material(value))
    try:
        resource = validate_resource_resolution_result(
            value, request=validated_request, source_artifact=source_artifact,
            admission=admission, asset=validated_asset, source_content=source_content)
    except ResourceContractError:
        return _resolution_reject("invalid_resolution_result")
    return ResourceResolutionResult(True, "resolved", resource)
