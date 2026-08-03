from jsonschema import Draft202012Validator
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
    if errors: raise MovieContractError("movie artifact does not match its contract")
    return ValidatedMovieArtifact(value)

def validate_story_fragment(value, registry=None):
    return _validate(value,"story_fragment/1",registry or MovieContractRegistry.built_in(),MAX_STORY_BYTES)

def validate_scene_breakdown(value, registry=None):
    result=_validate(value,"scene_breakdown/1",registry or MovieContractRegistry.built_in(),MAX_RESULT_BYTES)
    scenes=result.value["payload"]["ordered_scenes"]
    from vss_reasoning_contracts import canonical_digest
    if result.value["integrity"]["payload_sha256"] != canonical_digest(result.value["payload"]):
        raise MovieContractError("scene breakdown payload digest mismatch")
    ids=[s["scene_id"] for s in scenes]; ords=[s["ordinal"] for s in scenes]
    if len(ids)!=len(set(ids)) or len(ords)!=len(set(ords)) or ords != list(range(1,len(ords)+1)):
        raise MovieContractError("scene identity or ordering is invalid")
    return result
