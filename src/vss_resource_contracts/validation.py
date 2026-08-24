import hashlib

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json, validate_json_value

from .errors import ResourceContractError
from .models import AdmittedCreativeDecision, ValidatedResourceArtifact
from .registry import ResourceContractRegistry


MAX_RESOURCE_BYTES = 65536


def _validate(value, identity, registry=None):
    try:
        validate_json_value(value, maximum_bytes=MAX_RESOURCE_BYTES)
    except Exception as exc:
        raise ResourceContractError("resource artifact is unsafe") from exc
    if not isinstance(value, dict):
        raise ResourceContractError("resource artifact must be an object")
    registry = registry or ResourceContractRegistry.built_in()
    errors = list(registry.iter_errors(identity, value))
    if errors:
        raise ResourceContractError("resource artifact does not match its contract")
    return value


def artifact_seal_material(value):
    return {**value, "artifact_sha256": "0" * 64}


def resource_identity_material(value):
    return {
        "resource_kind": value["resource_kind"], "scope": value["scope"],
        "activity": value["activity"], "content_sha256": value["content_sha256"],
        "media_type": value["media_type"],
    }


def artifact_identity_material(value):
    return {
        "resource_id": value["resource_id"], "resource_revision": value["resource_revision"],
        "rights": value["rights"], "lineage": value["lineage"],
    }


def admission_seal_material(value):
    return {**value, "admission_sha256": "0" * 64}


def admission_identity_material(value):
    return {key: item for key, item in value.items()
            if key not in {"admission_id", "admission_sha256"}}


def asset_seal_material(value):
    return {**value, "asset_sha256": "0" * 64}


def asset_identity_material(value):
    return {
        "scope": value["scope"], "purpose": value["purpose"],
        "content_sha256": value["content_sha256"], "source": value["source"],
        "admission": value["admission"], "rights": value["rights"],
    }


def resolution_request_seal_material(value):
    return {**value, "request_sha256": "0" * 64}


def resolution_request_identity_material(value):
    return {key: item for key, item in value.items()
            if key not in {"request_id", "request_sha256"}}


def resolution_result_seal_material(value):
    return {**value, "result_sha256": "0" * 64}


def resolution_result_identity_material(value):
    return {key: item for key, item in value.items()
            if key not in {"resolution_id", "result_sha256"}}


def validate_production_resource_artifact(value, *, content=None, registry=None):
    value = _validate(value, "production_resource_artifact/1", registry)
    expected_resource_id = "resource-" + canonical_digest(resource_identity_material(value))[:32]
    if value["resource_id"] != expected_resource_id:
        raise ResourceContractError("production resource logical identity mismatch")
    expected_artifact_id = "artifact-" + canonical_digest(artifact_identity_material(value))[:32]
    if value["artifact_id"] != expected_artifact_id:
        raise ResourceContractError("production artifact identity mismatch")
    rights = value["rights"]
    if rights["permissions"] != sorted(rights["permissions"]) or rights["restrictions"] != sorted(rights["restrictions"]):
        raise ResourceContractError("resource rights are not canonical")
    ancestors = value["lineage"]["ancestors"]
    ancestor_keys = [(item["resource_id"], item["resource_revision"]) for item in ancestors]
    if ancestor_keys != sorted(ancestor_keys) or len(ancestor_keys) != len(set(ancestor_keys)):
        raise ResourceContractError("resource ancestors are not canonical")
    if value["artifact_sha256"] != canonical_digest(artifact_seal_material(value)):
        raise ResourceContractError("production resource artifact seal mismatch")
    if content is not None:
        if type(content) is not bytes:
            raise ResourceContractError("resource content must be bytes")
        if hashlib.sha256(content).hexdigest() != value["content_sha256"]:
            raise ResourceContractError("production resource content digest mismatch")
    return ValidatedResourceArtifact._create(value)


def validate_reusable_asset_admission(value, *, registry=None):
    value = _validate(value, "reusable_asset_admission/1", registry)
    expected_id = "asset-admission-" + canonical_digest(admission_identity_material(value))[:32]
    if value["admission_id"] != expected_id:
        raise ResourceContractError("reusable asset admission identity mismatch")
    if value["carried_restrictions"] != sorted(value["carried_restrictions"]):
        raise ResourceContractError("admission restrictions are not canonical")
    if value["admission_sha256"] != canonical_digest(admission_seal_material(value)):
        raise ResourceContractError("reusable asset admission seal mismatch")
    return ValidatedResourceArtifact._create(value)


def validate_reusable_asset(value, *, source_artifact, admission, source_content=None,
                            registry=None):
    value = _validate(value, "reusable_asset/1", registry)
    if not isinstance(source_artifact, ValidatedResourceArtifact) or not isinstance(admission, ValidatedResourceArtifact):
        raise ResourceContractError("reusable asset requires validated source and admission")
    source = validate_production_resource_artifact(
        source_artifact.to_json_value(), content=source_content, registry=registry)
    admitted = validate_reusable_asset_admission(admission.to_json_value(), registry=registry)
    source_value = source.value
    admission_value = admitted.value
    scope = source_value["scope"]
    expected_admission_source = {
        "artifact_id": source_value["artifact_id"],
        "artifact_sha256": source_value["artifact_sha256"],
        "resource_id": source_value["resource_id"],
        "resource_revision": source_value["resource_revision"],
        "content_sha256": source_value["content_sha256"],
        "tenant_id": scope["tenant_id"], "universe_id": scope["universe_id"],
        "production_id": scope["production_id"],
    }
    if admission_value["source"] != expected_admission_source:
        raise ResourceContractError("reusable asset admission source mismatch")
    if scope["universe_id"] is None or admission_value["destination"]["tenant_id"] != scope["tenant_id"] or admission_value["destination"]["universe_id"] != scope["universe_id"]:
        raise ResourceContractError("reusable asset admission scope mismatch")
    expected_source = {
        "artifact_id": source_value["artifact_id"],
        "artifact_sha256": source_value["artifact_sha256"],
        "resource_id": source_value["resource_id"],
        "resource_revision": source_value["resource_revision"],
        "content_sha256": source_value["content_sha256"],
        "production_id": scope["production_id"],
        "activity": thaw_json(source_value["activity"]),
        "ancestors": thaw_json(source_value["lineage"]["ancestors"]),
    }
    expected_admission = {
        "admission_id": admission_value["admission_id"],
        "admission_sha256": admission_value["admission_sha256"],
        "operation_identity": admission_value["operation_identity"],
        "operation_version": admission_value["operation_version"],
        "policy_identity": admission_value["policy_identity"],
        "policy_version": admission_value["policy_version"],
    }
    if value["scope"] != admission_value["destination"] or value["source"] != expected_source or value["admission"] != expected_admission:
        raise ResourceContractError("reusable asset authoritative binding mismatch")
    rights = source_value["rights"]
    expected_rights = {
        "ownership_class": rights["ownership_class"], "status": "confirmed",
        "permissions": ["reuse_as_universe_visual_reference"],
        "restrictions": thaw_json(rights["restrictions"]),
        "rights_reference": rights["rights_reference"],
        "rights_policy_identity": rights["rights_policy_identity"],
        "rights_policy_version": rights["rights_policy_version"],
    }
    if value["rights"] != expected_rights or value["content_sha256"] != source_value["content_sha256"]:
        raise ResourceContractError("reusable asset authoritative rights mismatch")
    expected_id = "asset-" + canonical_digest(asset_identity_material(value))[:32]
    if value["asset_id"] != expected_id:
        raise ResourceContractError("reusable asset identity mismatch")
    if value["rights"]["restrictions"] != sorted(value["rights"]["restrictions"]):
        raise ResourceContractError("asset restrictions are not canonical")
    if value["asset_sha256"] != canonical_digest(asset_seal_material(value)):
        raise ResourceContractError("reusable asset seal mismatch")
    return ValidatedResourceArtifact._create(value)


def validate_resource_resolution_request(value, *, registry=None):
    value = _validate(value, "resource_resolution_request/1", registry)
    expected_id = "resource-resolution-" + canonical_digest(
        resolution_request_identity_material(value))[:32]
    if value["request_id"] != expected_id:
        raise ResourceContractError("resource resolution request identity mismatch")
    if value["restrictions"] != sorted(value["restrictions"]):
        raise ResourceContractError("resource resolution restrictions are not canonical")
    if value["request_sha256"] != canonical_digest(resolution_request_seal_material(value)):
        raise ResourceContractError("resource resolution request seal mismatch")
    return ValidatedResourceArtifact._create(value)


def validate_resource_resolution_result(value, *, request, source_artifact, admission,
                                        asset, source_content=None, registry=None):
    value = _validate(value, "resource_resolution_result/1", registry)
    if not all(isinstance(item, ValidatedResourceArtifact)
               for item in (request, source_artifact, admission, asset)):
        raise ResourceContractError("resource resolution requires validated authorities")
    validated_request = validate_resource_resolution_request(request.to_json_value(), registry=registry)
    validated_asset = validate_reusable_asset(
        asset.to_json_value(), source_artifact=source_artifact, admission=admission,
        source_content=source_content, registry=registry)
    request_value = validated_request.value
    asset_value = validated_asset.value
    expected_request_asset = {key: asset_value[key] for key in (
        "asset_id", "asset_revision", "asset_sha256", "content_sha256")}
    expected_request_source = {key: asset_value["source"][key] for key in (
        "artifact_id", "artifact_sha256", "resource_id", "resource_revision")}
    expected_request_admission = {key: asset_value["admission"][key] for key in (
        "admission_id", "admission_sha256")}
    if (request_value["asset"] != expected_request_asset
            or request_value["source"] != expected_request_source
            or request_value["admission"] != expected_request_admission
            or request_value["consumer"]["tenant_id"] != asset_value["scope"]["tenant_id"]
            or request_value["consumer"]["universe_id"] != asset_value["scope"]["universe_id"]
            or request_value["purpose"] != asset_value["purpose"]
            or request_value["permission"] not in asset_value["rights"]["permissions"]
            or request_value["restrictions"] != asset_value["rights"]["restrictions"]
            or request_value["rights_reference"] != asset_value["rights"]["rights_reference"]):
        raise ResourceContractError("resource resolution request authoritative binding mismatch")
    expected = {
        "schema_version": "1", "contract_identity": "resource_resolution_result",
        "contract_version": "1", "resolution_id": "resolved-resource-" + "0" * 32,
        "request": {key: request_value[key] for key in (
            "request_id", "request_sha256", "operation_identity", "operation_version")},
        "consumer": thaw_json(request_value["consumer"]), "purpose": request_value["purpose"],
        "resolved_asset": {key: asset_value[key] for key in (
            "asset_id", "asset_revision", "asset_sha256", "asset_kind", "content_sha256", "media_type")},
        "source": thaw_json(asset_value["source"]),
        "admission": thaw_json(asset_value["admission"]),
        "rights": {
            "ownership_class": asset_value["rights"]["ownership_class"],
            "status": asset_value["rights"]["status"],
            "permission": request_value["permission"],
            "restrictions": thaw_json(asset_value["rights"]["restrictions"]),
            "rights_reference": asset_value["rights"]["rights_reference"],
            "rights_policy_identity": asset_value["rights"]["rights_policy_identity"],
            "rights_policy_version": asset_value["rights"]["rights_policy_version"],
        },
        "limitations": ["inert_resolution", "not_production_approval",
                        "not_publication_authority", "not_redistribution_authority",
                        "not_runtime_authority", "not_training_permission",
                        "no_storage_authority", "exact_asset_revision_only"],
        "result_sha256": "0" * 64,
    }
    expected["resolution_id"] = "resolved-resource-" + canonical_digest(
        resolution_result_identity_material(expected))[:32]
    expected["result_sha256"] = canonical_digest(resolution_result_seal_material(expected))
    if value != expected:
        raise ResourceContractError("resource resolution authoritative binding mismatch")
    return ValidatedResourceArtifact._create(value)


def creative_decision_identity_material(value):
    return {"decision_kind": value["decision_kind"], "scope": value["scope"]}


def creative_decision_seal_material(value):
    return {**value, "decision_sha256": "0" * 64}


def canon_snapshot_identity_material(value):
    return {"snapshot_version": value["snapshot_version"], "scope": value["scope"],
            "decisions": value["decisions"]}


def canon_snapshot_seal_material(value):
    return {**value, "canon_sha256": "0" * 64}


def production_canon_binding_identity_material(value):
    return {"operation_identity": value["operation_identity"],
            "operation_version": value["operation_version"], "scope": value["scope"],
            "purpose": value["purpose"], "canon_snapshot": value["canon_snapshot"],
            "decisions": value["decisions"], "production_input": value["production_input"]}


def production_canon_binding_seal_material(value):
    return {**value, "result_sha256": "0" * 64}


def dependency_impact_request_seal_material(value):
    return {**value, "request_sha256": "0" * 64}


def dependency_impact_result_identity_material(value):
    return {key: item for key, item in value.items()
            if key not in {"assessment_id", "result_sha256"}}


def dependency_impact_result_seal_material(value):
    return {**value, "result_sha256": "0" * 64}


def media_provenance_request_seal_material(value):
    return {**value, "request_sha256": "0" * 64}


def media_provenance_view_identity_material(value):
    return {key: item for key, item in value.items()
            if key not in {"provenance_id", "result_sha256"}}


def media_provenance_view_seal_material(value):
    return {**value, "result_sha256": "0" * 64}


def validate_media_provenance_request(value, *, registry=None):
    try:
        value = _validate(value, "media_provenance_request/1", registry)
        if value["request_sha256"] != canonical_digest(
                media_provenance_request_seal_material(value)):
            raise ResourceContractError("media provenance request seal mismatch")
    except ResourceContractError as exc:
        raise ResourceContractError("media_provenance_request_invalid") from exc
    return ValidatedResourceArtifact._create(value)


def validate_media_provenance_view(value, *, registry=None):
    try:
        value = _validate(value, "media_provenance_view/1", registry)
        expected_id = "media-provenance-" + canonical_digest(
            media_provenance_view_identity_material(value))[:32]
        if value["provenance_id"] != expected_id:
            raise ResourceContractError("media provenance view identity mismatch")
        if value["lineage"] != sorted(value["lineage"], key=lambda item: item["kind"]):
            raise ResourceContractError("media provenance lineage is not canonical")
        if value["rights"]["permissions"] != sorted(value["rights"]["permissions"]):
            raise ResourceContractError("media provenance permissions are not canonical")
        if value["rights"]["restrictions"] != sorted(value["rights"]["restrictions"]):
            raise ResourceContractError("media provenance restrictions are not canonical")
        if value["result_sha256"] != canonical_digest(
                media_provenance_view_seal_material(value)):
            raise ResourceContractError("media provenance view seal mismatch")
    except ResourceContractError as exc:
        raise ResourceContractError("media_provenance_view_invalid") from exc
    return ValidatedResourceArtifact._create(value)


def validate_dependency_impact_request(value, *, registry=None):
    try:
        value = _validate(value, "dependency_impact_request/1", registry)
        if value["request_sha256"] != canonical_digest(
                dependency_impact_request_seal_material(value)):
            raise ResourceContractError("dependency impact request seal mismatch")
    except ResourceContractError as exc:
        raise ResourceContractError("impact_request_invalid") from exc
    return ValidatedResourceArtifact._create(value)


def validate_dependency_impact_result(value, *, registry=None):
    try:
        value = _validate(value, "dependency_impact_result/1", registry)
        expected_id = "dependency-impact-" + canonical_digest(
            dependency_impact_result_identity_material(value))[:32]
        if value["assessment_id"] != expected_id:
            raise ResourceContractError("dependency impact result identity mismatch")
        if value["evidence"] != sorted(value["evidence"], key=lambda item: item["dependency_kind"]):
            raise ResourceContractError("dependency impact evidence is not canonical")
        classifications = {
            "exact_dependencies_unchanged": "unaffected",
            "selected_dependency_changed": "affected_reassessment_required",
            "prior_authoritative_chain_incomplete": "incomplete_fail_closed",
            "candidate_authoritative_chain_incomplete": "incomplete_fail_closed",
            "scope_mismatch": "incomplete_fail_closed",
            "dependency_identity_ambiguous": "incomplete_fail_closed",
        }
        if value["classification"] != classifications[value["reason_code"]]:
            raise ResourceContractError("dependency impact classification mismatch")
        evidence = value["evidence"]
        if value["classification"] == "incomplete_fail_closed":
            if evidence:
                raise ResourceContractError("incomplete dependency impact cannot claim evidence")
        elif (len(evidence) != 2
              or {item["dependency_kind"] for item in evidence}
              != {"canon_snapshot", "creative_decision_revision"}):
            raise ResourceContractError("complete dependency impact requires exact evidence")
        elif value["classification"] == "unaffected" and any(
                item["changed"] for item in evidence):
            raise ResourceContractError("unaffected dependency evidence changed")
        elif value["classification"] == "affected_reassessment_required" and not any(
                item["changed"] for item in evidence):
            raise ResourceContractError("affected dependency evidence is unchanged")
        if value["result_sha256"] != canonical_digest(
                dependency_impact_result_seal_material(value)):
            raise ResourceContractError("dependency impact result seal mismatch")
    except ResourceContractError as exc:
        raise ResourceContractError("impact_result_invalid") from exc
    return ValidatedResourceArtifact._create(value)


def validate_creative_decision_revision(value, *, registry=None):
    value = _validate(value, "creative_decision_revision/1", registry)
    expected_id = "decision-" + canonical_digest(creative_decision_identity_material(value))[:32]
    if value["decision_id"] != expected_id:
        raise ResourceContractError("creative decision identity mismatch")
    prior = value["previous_revision"]
    if value["revision"] == 1 and prior is not None:
        raise ResourceContractError("first creative decision revision cannot have a predecessor")
    if value["revision"] > 1 and (prior is None
            or prior["decision_id"] != value["decision_id"]
            or prior["revision"] != value["revision"] - 1):
        raise ResourceContractError("creative decision revision predecessor mismatch")
    outcome = value["semantic_payload"]["review_outcome"]
    if ((value["status"] == "accepted" and outcome != "accept")
            or (value["status"] == "rejected" and outcome not in ("reject", "defer"))
            or (value["status"] in ("deprecated", "superseded") and outcome != "accept")):
        raise ResourceContractError("creative decision status is not authoritative")
    if value["dependencies"] != sorted(value["dependencies"], key=lambda item: item["kind"]):
        raise ResourceContractError("creative decision dependencies are not canonical")
    if value["evidence_references"] != sorted(value["evidence_references"]):
        raise ResourceContractError("creative decision evidence is not canonical")
    if value["decision_sha256"] != canonical_digest(creative_decision_seal_material(value)):
        raise ResourceContractError("creative decision seal mismatch")
    return ValidatedResourceArtifact._create(value)


def _decision_binding(value):
    return {"decision_id": value["decision_id"], "revision": value["revision"],
            "decision_sha256": value["decision_sha256"], "status": value["status"],
            "scene_id": value["scope"]["scene_id"]}


def validate_canon_snapshot(value, *, decisions, registry=None):
    value = _validate(value, "canon_snapshot/1", registry)
    if not decisions or not all(isinstance(item, AdmittedCreativeDecision) for item in decisions):
        raise ResourceContractError("canon snapshot requires authoritative decision revisions")
    checked = [validate_creative_decision_revision(item.to_json_value(), registry=registry)
               for item in decisions]
    if any(item.value["status"] != "accepted" for item in checked):
        raise ResourceContractError("canon snapshot requires accepted decision revisions")
    scopes = [item.value["scope"] for item in checked]
    expected_scope = {key: scopes[0][key] for key in ("tenant_id", "universe_id", "production_id")}
    expected_scope["scope_kind"] = "production"
    if any({key: scope[key] for key in ("tenant_id", "universe_id", "production_id")}
           != {key: scopes[0][key] for key in ("tenant_id", "universe_id", "production_id")}
           for scope in scopes):
        raise ResourceContractError("canon decision scopes do not match")
    expected_decisions = sorted((_decision_binding(item.value) for item in checked),
                                key=lambda item: (item["decision_id"], item["revision"]))
    if len({item["decision_id"] for item in expected_decisions}) != len(expected_decisions):
        raise ResourceContractError("canon snapshot permits only one revision per decision")
    if value["scope"] != expected_scope or value["decisions"] != expected_decisions:
        raise ResourceContractError("canon snapshot authoritative binding mismatch")
    expected_id = "canon-" + canonical_digest(canon_snapshot_identity_material(value))[:32]
    if value["canon_snapshot_id"] != expected_id:
        raise ResourceContractError("canon snapshot identity mismatch")
    if value["canon_sha256"] != canonical_digest(canon_snapshot_seal_material(value)):
        raise ResourceContractError("canon snapshot seal mismatch")
    return ValidatedResourceArtifact._create(value)


def validate_production_canon_binding(value, *, canon_snapshot, decisions,
                                      production_input, scope, registry=None):
    value = _validate(value, "production_canon_binding/1", registry)
    checked_canon = validate_canon_snapshot(
        canon_snapshot.to_json_value(), decisions=decisions, registry=registry)
    expected_decisions = thaw_json(checked_canon.value["decisions"])
    expected = {
        "schema_version": "1", "contract_identity": "production_canon_binding",
        "contract_version": "1", "binding_id": "production-canon-binding-" + "0" * 32,
        "operation_identity": "bind_scene_shot_plan_input_to_exact_canon",
        "operation_version": "1", "scope": scope, "purpose": "scene_shot_plan_input",
        "canon_snapshot": {key: checked_canon.value[key] for key in (
            "canon_snapshot_id", "snapshot_version", "canon_sha256")},
        "decisions": expected_decisions, "production_input": production_input,
        "limitations": ["inert_production_input_binding", "not_production_approval",
                        "not_runtime_authority", "not_provider_authority",
                        "not_workflow_authority", "not_scheduling_authority",
                        "not_regeneration_authority", "not_publication_authority",
                        "no_storage_authority", "not_rights_authority",
                        "exact_canon_and_decision_revisions_only"],
        "result_sha256": "0" * 64,
    }
    expected["binding_id"] = "production-canon-binding-" + canonical_digest(
        production_canon_binding_identity_material(expected))[:32]
    expected["result_sha256"] = canonical_digest(production_canon_binding_seal_material(expected))
    if value != expected:
        raise ResourceContractError("production canon authoritative binding mismatch")
    return ValidatedResourceArtifact._create(value)
