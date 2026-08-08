from jsonschema import Draft202012Validator
import re
from vss_reasoning_contracts.canonicalization import validate_json_value
from .errors import MovieContractError
from .limits import MAX_STORY_BYTES, MAX_RESULT_BYTES
from .models import ValidatedMovieArtifact
from .registry import MovieContractRegistry

def _validate(value, identity, registry, maximum):
    try: validate_json_value(value, maximum_bytes=maximum)
    except Exception as exc: raise MovieContractError("movie artifact is unsafe") from exc
    if not isinstance(value,dict): raise MovieContractError("movie artifact must be an object")
    registry.resolve(identity)
    errors=list(Draft202012Validator(registry.schemas[identity]["schema"]).iter_errors(value))
    if errors: raise MovieContractError("movie artifact does not match its contract: " + errors[0].message)
    return ValidatedMovieArtifact._create(value)

def validate_story_fragment(value, registry=None):
    artifact = _validate(value,"story_fragment/1",registry or MovieContractRegistry.built_in(),MAX_STORY_BYTES)
    if not artifact.value["payload"]["fragment_text"].strip():
        raise MovieContractError("story fragment text is empty")
    return artifact

def validate_scene_task(value, registry=None):
    return _validate(value,"break_down_scenes/1",registry or MovieContractRegistry.built_in(),MAX_STORY_BYTES)

def validate_production_options_task(value, registry=None):
    result = _validate(value, "generate_scene_production_options/1", registry or MovieContractRegistry.built_in(), MAX_STORY_BYTES)
    task = result.value
    if task["expected_context_family"] != "scene_production_options_context" or task["expected_context_version"] != "1":
        raise MovieContractError("production task Context compatibility is invalid")
    if task["expected_result_family"] != "scene_production_option_set" or task["expected_result_version"] != "1":
        raise MovieContractError("production task result compatibility is invalid")
    if task["purpose"] != "scene_production_options_local_validation" or task["environment"] != "development":
        raise MovieContractError("production task policy is invalid")
    return result

def validate_scene_breakdown(value, registry=None):
    result=_validate(value,"scene_breakdown/1",registry or MovieContractRegistry.built_in(),MAX_RESULT_BYTES)
    scenes=result.value["payload"]["ordered_scenes"]
    from vss_reasoning_contracts import canonical_digest
    if result.value["integrity"]["payload_sha256"] != canonical_digest(result.value["payload"]):
        raise MovieContractError("scene breakdown payload digest mismatch")
    ids=[s["scene_id"] for s in scenes]; ords=[s["ordinal"] for s in scenes]
    if len(ids)!=len(set(ids)) or len(ords)!=len(set(ords)) or ords != list(range(1,len(ords)+1)):
        raise MovieContractError("scene identity or ordering is invalid")
    bindings=set(result.value["source_bindings"]); spans=[]
    for scene in scenes:
        if scene["source_binding"] not in bindings:
            raise MovieContractError("unknown scene source binding")
        span=scene["source_span"]
        if span["start"] >= span["end"]: raise MovieContractError("invalid source span")
        for source, start, end in spans:
            if source == scene["source_binding"] and span["start"] < end and start < span["end"]:
                raise MovieContractError("overlapping source spans")
        spans.append((scene["source_binding"], span["start"], span["end"]))
        if not re.fullmatch(r"[a-z][a-z0-9._:-]{0,63}/[1-9][0-9]*(\.[0-9]+){0,2}", scene["boundary_rule"]):
            raise MovieContractError("invalid boundary rule")
        if any(ref not in bindings for ref in scene["evidence_references"]):
            raise MovieContractError("unknown scene evidence reference")
        material = dict(scene); material.pop("scene_content_digest", None)
        if scene["scene_content_digest"] != canonical_digest(material):
            raise MovieContractError("scene content digest mismatch")
    return result

def validate_production_option_set(value, registry=None):
    result = _validate(value, "scene_production_option_set/1", registry or MovieContractRegistry.built_in(), MAX_RESULT_BYTES)
    from vss_reasoning_contracts import canonical_digest
    data = result.value
    if data["integrity"]["payload_sha256"] != canonical_digest(data["payload"]):
        raise MovieContractError("production option payload digest mismatch")
    if data["payload"]["semantic_result_digest"] != canonical_digest({**data["payload"], "semantic_result_digest": None}):
        raise MovieContractError("production semantic result digest mismatch")
    if data["integrity"]["complete_result_sha256"] != canonical_digest({**data, "integrity": {"payload_sha256": data["integrity"]["payload_sha256"]}}):
        raise MovieContractError("production complete result digest mismatch")
    options = data["payload"]["options"]
    if [o["ordinal"] for o in options] != list(range(1, len(options) + 1)):
        raise MovieContractError("production option order is invalid")
    if len({o["option_id"] for o in options}) != len(options) or len({(o["profile_identity"], o["profile_version"]) for o in options}) != len(options):
        raise MovieContractError("production option identity is duplicated")
    prohibited = {"rank", "score", "recommended", "preferred", "winner", "selected", "approval", "execution", "workflow", "capability", "model", "prompt"}
    def reject(node):
        if isinstance(node, dict):
            if prohibited.intersection(node): raise MovieContractError("ranking or execution field is prohibited")
            for child in node.values(): reject(child)
        elif isinstance(node, (list, tuple)):
            for child in node: reject(child)
    reject(data)
    for option in options:
        material = dict(option); digest = material.pop("option_content_digest"); material.pop("option_id")
        if digest != canonical_digest(material): raise MovieContractError("production option content digest mismatch")
        if not option["unknowns"] or not option["limitations"] or not option["external_validation_requirements"]:
            raise MovieContractError("production option qualifications are incomplete")
    return result
