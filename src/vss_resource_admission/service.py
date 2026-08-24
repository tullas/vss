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
    media_provenance_request_seal_material,
    media_provenance_view_identity_material,
    media_provenance_view_seal_material,
    validate_media_provenance_request,
    validate_media_provenance_view,
    validate_canon_snapshot,
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


def _decision_reference(value):
    return {key: value[key] for key in ("decision_id", "revision", "decision_sha256")}


def _canon_reference(value):
    return {key: value[key] for key in (
        "canon_snapshot_id", "snapshot_version", "canon_sha256")}


def create_media_provenance_request(*, production_artifact: ValidatedResourceArtifact,
                                    decision_revision: Any,
                                    canon_snapshot: ValidatedResourceArtifact,
                                    production_canon_binding: ValidatedResourceArtifact,
                                    pictorial_frame: AdmittedPictorialFrame
                                    ) -> ValidatedResourceArtifact:
    try:
        artifact = production_artifact.value
        decision = decision_revision.value
        canon = canon_snapshot.value
        binding = production_canon_binding.value
        if (artifact["contract_identity"] != "production_resource_artifact"
                or canon["contract_identity"] != "canon_snapshot"
                or binding["contract_identity"] != "production_canon_binding"
                or not isinstance(pictorial_frame, AdmittedPictorialFrame)):
            raise ResourceContractError("media provenance authorities are invalid")
        value = {
            "schema_version": "1", "contract_identity": "media_provenance_request",
            "contract_version": "1",
            "operation_identity": "create_storyboard_review_frame_provenance",
            "operation_version": "1",
            "scope": {"tenant_id": artifact["scope"]["tenant_id"],
                      "universe_id": artifact["scope"]["universe_id"],
                      "production_id": artifact["scope"]["production_id"],
                      "scene_id": pictorial_frame.scene_id,
                      "scope_kind": "production_scene"},
            "artifact": {key: artifact[key] for key in (
                "artifact_id", "artifact_sha256", "resource_id", "resource_revision",
                "content_sha256")},
            "decision": _decision_reference(decision),
            "canon": _canon_reference(canon),
            "production_binding": {key: binding[key] for key in (
                "binding_id", "result_sha256")},
            "pictorial_admission": {
                "admission_id": pictorial_frame.admission_id,
                "storyboard_specification_digest": pictorial_frame.storyboard_specification_digest,
                "frame_id": pictorial_frame.frame_id,
                "frame_specification_digest": pictorial_frame.frame_specification_digest,
                "semantic_request_digest": pictorial_frame.semantic_request_digest,
            },
            "request_sha256": "0" * 64,
        }
    except (KeyError, TypeError, AttributeError) as exc:
        raise ResourceContractError("media_provenance_request_invalid") from exc
    value["request_sha256"] = canonical_digest(media_provenance_request_seal_material(value))
    return validate_media_provenance_request(value)


def create_storyboard_review_frame_provenance(
    request_data: dict[str, Any], *, decision_data: Any, review_packet_data: Any,
    option_set_data: Any, scene_breakdown_data: Any, decision_revision: Any,
    canon_snapshot: Any, production_canon_binding: Any, shot_plan_data: Any,
    storyboard_data: Any, admitted_pictorial_frame: Any, production_artifact: Any,
    content: bytes, previous_revision: Any = None,
) -> ValidatedResourceArtifact:
    """Construct one inert provenance view after reconstructing both authoritative chains."""
    from vss_movie_canon import (
        AdmittedCreativeDecision, bind_production_input_to_canon,
        create_creative_decision_revision,
    )
    from vss_movie_pictorial import admit_pictorial_frame

    request = validate_media_provenance_request(request_data)
    if (not isinstance(decision_revision, AdmittedCreativeDecision)
            or not isinstance(canon_snapshot, ValidatedResourceArtifact)
            or not isinstance(production_canon_binding, ValidatedResourceArtifact)
            or not isinstance(admitted_pictorial_frame, AdmittedPictorialFrame)
            or not isinstance(production_artifact, ValidatedResourceArtifact)):
        raise ResourceContractError("media provenance authoritative chain incomplete")
    scope = request.value["scope"]
    try:
        reconstructed_decision = create_creative_decision_revision(
            decision_data, review_packet_data, option_set_data, scene_breakdown_data,
            tenant_id=scope["tenant_id"], universe_id=scope["universe_id"],
            revision=decision_revision.value["revision"],
            status=decision_revision.value["status"], previous_revision=previous_revision)
        if reconstructed_decision != decision_revision:
            raise ResourceContractError("decision reconstruction mismatch")
        checked_canon = validate_canon_snapshot(
            canon_snapshot.to_json_value(), decisions=[decision_revision])
        reconstructed_binding = bind_production_input_to_canon(
            decision_data, review_packet_data, option_set_data, scene_breakdown_data,
            tenant_id=scope["tenant_id"], universe_id=scope["universe_id"],
            decisions=[decision_revision], canon_snapshot=checked_canon,
            previous_revision=previous_revision)
        if reconstructed_binding != production_canon_binding:
            raise ResourceContractError("production binding reconstruction mismatch")
        reconstructed_pictorial = admit_pictorial_frame(
            decision_data, review_packet_data, option_set_data, scene_breakdown_data,
            shot_plan_data, storyboard_data,
            frame_id=admitted_pictorial_frame.frame_id, environment="development")
        if reconstructed_pictorial != admitted_pictorial_frame:
            raise ResourceContractError("pictorial reconstruction mismatch")
        artifact_value = production_artifact.value
        reconstructed_artifact = create_production_artifact(
            pictorial_frame=reconstructed_pictorial,
            resource_revision=artifact_value["resource_revision"],
            tenant_id=scope["tenant_id"], universe_id=scope["universe_id"],
            content=content,
            ownership_class=artifact_value["rights"]["ownership_class"],
            rights_status=artifact_value["rights"]["status"],
            permissions=list(artifact_value["rights"]["permissions"]),
            restrictions=list(artifact_value["rights"]["restrictions"]),
            rights_reference=artifact_value["rights"]["rights_reference"],
            ancestors=list(artifact_value["lineage"]["ancestors"]),
        )
        if reconstructed_artifact != production_artifact:
            raise ResourceContractError("production artifact reconstruction mismatch")
    except ResourceContractError:
        raise
    except Exception as exc:
        raise ResourceContractError("media provenance authoritative chain invalid") from exc

    artifact = reconstructed_artifact.value
    decision = reconstructed_decision.value
    canon = checked_canon.value
    binding = reconstructed_binding.value
    expected_scope = {"tenant_id": artifact["scope"]["tenant_id"],
                      "universe_id": artifact["scope"]["universe_id"],
                      "production_id": artifact["scope"]["production_id"],
                      "scene_id": reconstructed_pictorial.scene_id,
                      "scope_kind": "production_scene"}
    expected_request = create_media_provenance_request(
        production_artifact=reconstructed_artifact, decision_revision=decision_revision,
        canon_snapshot=checked_canon, production_canon_binding=reconstructed_binding,
        pictorial_frame=reconstructed_pictorial)
    if request != expected_request or scope != expected_scope or binding["scope"] != scope:
        raise ResourceContractError("media provenance request authoritative binding mismatch")

    review_digest = decision["semantic_payload"]["decision_complete_digest"]
    lineage = sorted([
        {"kind": "canon_snapshot", "identity": canon["canon_snapshot_id"],
         "version": str(canon["snapshot_version"]), "sha256": canon["canon_sha256"]},
        {"kind": "creative_decision_revision", "identity": decision["decision_id"],
         "version": str(decision["revision"]), "sha256": decision["decision_sha256"]},
        {"kind": "pictorial_admission", "identity": reconstructed_pictorial.frame_id,
         "version": "1", "sha256": reconstructed_pictorial.semantic_request_digest},
        {"kind": "production_canon_binding", "identity": binding["binding_id"],
         "version": binding["operation_version"], "sha256": binding["result_sha256"]},
        {"kind": "review_decision", "identity": decision_data["result_family"],
         "version": decision_data["result_version"], "sha256": review_digest},
        {"kind": "scene_breakdown", "identity": scene_breakdown_data["result_family"],
         "version": scene_breakdown_data["result_version"],
         "sha256": decision["semantic_payload"]["scene_breakdown_digest"]},
        {"kind": "shot_plan_draft", "identity": shot_plan_data["result_family"],
         "version": shot_plan_data["result_version"],
         "sha256": shot_plan_data["integrity"]["complete_result_sha256"]},
        {"kind": "storyboard_frame", "identity": reconstructed_pictorial.frame_id,
         "version": "1", "sha256": reconstructed_pictorial.frame_specification_digest},
        {"kind": "storyboard_specification", "identity": storyboard_data["result_family"],
         "version": storyboard_data["result_version"],
         "sha256": reconstructed_pictorial.storyboard_specification_digest},
    ], key=lambda item: item["kind"])
    value = {
        "schema_version": "1", "contract_identity": "media_provenance_view",
        "contract_version": "1", "provenance_id": "media-provenance-" + "0" * 32,
        "request_sha256": request.value["request_sha256"], "scope": thaw_json(scope),
        "output": {key: artifact[key] for key in (
            "artifact_id", "artifact_sha256", "resource_id", "resource_revision",
            "resource_kind", "content_sha256", "media_type")},
        "production_input": {
            "decision_id": decision["decision_id"], "decision_revision": decision["revision"],
            "decision_sha256": decision["decision_sha256"],
            "canon_snapshot_id": canon["canon_snapshot_id"],
            "canon_snapshot_version": canon["snapshot_version"],
            "canon_sha256": canon["canon_sha256"], "binding_id": binding["binding_id"],
            "binding_sha256": binding["result_sha256"],
        },
        "lineage": lineage, "rights": thaw_json(artifact["rights"]),
        "preservation": {"class": "disposable_intermediate_review_material",
                         "payload_availability": "caller_supplied_not_persisted"},
        "reproducibility": {"level": "identity_and_provenance",
                            "content_identity_verified": True,
                            "semantic_replay_claimed": False,
                            "operational_replay_claimed": False,
                            "exact_byte_replay_claimed": False},
        "unavailable_evidence": ["model_identity", "model_version", "provider_identity",
                                 "provider_version", "runtime_environment_identity"],
        "limitations": ["inert_provenance_view", "not_production_approval",
                        "not_runtime_authority", "not_provider_authority",
                        "not_workflow_authority", "not_scheduling_authority",
                        "not_regeneration_authority", "not_export_or_publication_authority",
                        "not_storage_or_deletion_authority", "not_rights_authority",
                        "not_reproducibility_guarantee", "exact_artifact_revision_only"],
        "result_sha256": "0" * 64,
    }
    value["provenance_id"] = _identifier(
        "media-provenance-", media_provenance_view_identity_material(value))
    value["result_sha256"] = canonical_digest(media_provenance_view_seal_material(value))
    return validate_media_provenance_view(value)


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
