import hashlib, json, os, stat
from pathlib import Path
from types import MappingProxyType
from jsonschema import Draft202012Validator
from vss_reasoning_contracts import canonical_digest
from .errors import MovieRegistryError, MovieContractError
from .models import MovieRegistration
from vss_reasoning_contracts.canonicalization import freeze_json

ROOT = Path(__file__).resolve().parents[2] / "schemas"
FILES = MappingProxyType({
    "story_fragment/1":"story-fragment-v1.schema.json",
    "break_down_scenes/1":"break-down-scenes-task-v1.schema.json",
    "scene_breakdown/1":"scene-breakdown-v1.schema.json",
    "generate_scene_production_options/1":"generate-scene-production-options-task-v1.schema.json",
    "scene_production_option_set/1":"scene-production-option-set-v1.schema.json",
    "character_reference/1":"character-reference-v1.schema.json",
    "character_identity/1":"character-identity-v1.schema.json",
    "continuity_sequence/1":"continuity-sequence-v1.schema.json",
    "character_observation/1":"character-observation-v1.schema.json",
    "analyze_character_continuity/1":"analyze-character-continuity-task-v1.schema.json",
    "analyze_character_continuity/2":"analyze-character-continuity-task-v2.schema.json",
    "analyze_character_continuity/3":"analyze-character-continuity-task-v3.schema.json",
    "character_continuity_transition_evidence/1":"character-continuity-transition-evidence-v1.schema.json",
    "character_continuity_observation_set/1":"character-continuity-observation-set-v1.schema.json",
})
COMPATIBILITY = MappingProxyType({
    "analyze_character_continuity/1": "character_continuity_observation_set/1",
    "analyze_character_continuity/2": "character_continuity_observation_set/1",
    "analyze_character_continuity/3": "character_continuity_observation_set/1",
})
def _pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise MovieRegistryError("movie schema has duplicate keys")
        out[k]=v
    return out
def _load(identity, filename):
    path=ROOT/filename
    if path.is_symlink(): raise MovieRegistryError("movie schema symlink rejected")
    try:
        resolved=path.resolve(strict=True)
        if not resolved.is_relative_to(ROOT): raise MovieRegistryError("movie schema escapes root")
        fd=os.open(path, os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode): raise MovieRegistryError("movie schema is not regular")
            raw=os.read(fd, 262145)
        finally:
            os.close(fd)
    except OSError as exc: raise MovieRegistryError("movie schema unavailable") from exc
    if len(raw)>262144: raise MovieRegistryError("movie schema too large")
    try: schema=json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception as exc: raise MovieRegistryError("movie schema invalid") from exc
    if schema.get("$id") != f"vss.movie.{identity}": raise MovieRegistryError("movie schema identity mismatch")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema": raise MovieRegistryError("movie schema dialect invalid")
    try: Draft202012Validator.check_schema(schema)
    except Exception as exc: raise MovieRegistryError("movie schema malformed") from exc
    def walk(node, root=True):
        if isinstance(node, dict):
            if not root and "$id" in node: raise MovieRegistryError("nested schema id rejected")
            if any(k in node for k in ("$dynamicRef", "$recursiveRef", "$anchor", "$dynamicAnchor")):
                raise MovieRegistryError("unsupported schema reference")
            if "$ref" in node and not (isinstance(node["$ref"], str) and node["$ref"].startswith("#")):
                raise MovieRegistryError("remote schema reference rejected")
            for value in node.values(): walk(value, False)
        elif isinstance(node, list):
            for value in node: walk(value, False)
    walk(schema)
    return {"identity":identity,"sha256":hashlib.sha256(raw).hexdigest(),"schema":freeze_json(schema)}

class MovieContractRegistry:
    __slots__=("registrations","schemas","compatibility","digest")
    def __init__(self):
        regs=tuple(
            MovieRegistration(
                i,
                i.rsplit("/", 1)[1],
                f"vss.movie.{i}/1" if i.rsplit("/", 1)[1] == "1" else f"vss.movie.{i}",
            )
            for i in FILES
        )
        schemas={i:_load(i,f) for i,f in FILES.items()}
        self.registrations=regs; self.schemas=freeze_json(schemas)
        self.compatibility=freeze_json(dict(COMPATIBILITY))
        self.digest=canonical_digest({"registry":"movie_domain_contract_registry/1","registrations":[r.__dict__ if hasattr(r,"__dict__") else {"identity":r.identity,"version":r.version,"schema_identity":r.schema_identity,"lifecycle":r.lifecycle,"owner":r.owner} for r in regs],"schemas":{k:v["sha256"] for k,v in sorted(schemas.items())},"compatibility":dict(COMPATIBILITY)})
    @classmethod
    def built_in(cls): return cls()
    def resolve(self, identity, version=None):
        if not isinstance(identity, str) or not identity or "*" in identity or identity.endswith("latest"):
            raise MovieContractError("unknown movie contract")
        qualified = identity if version is None else f"{identity}/{version}"
        for r in self.registrations:
            if r.identity == qualified: return r
        raise MovieContractError("unknown movie contract")
    def resolve_result(self, task_identity, result_identity):
        self.resolve(task_identity)
        self.resolve(result_identity)
        if self.compatibility.get(task_identity) != result_identity:
            raise MovieContractError("movie task/result compatibility is invalid")
        return result_identity
