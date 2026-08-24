import hashlib

from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json, validate_json_value

from .errors import ResourceContractError
from .models import ValidatedResourceArtifact
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
