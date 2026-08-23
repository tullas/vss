import hashlib, json, os, stat
from threading import Lock
from pathlib import Path
from types import MappingProxyType
from jsonschema import Draft202012Validator
from vss_reasoning_contracts import canonical_digest
from .errors import MovieRegistryError, MovieContractError
from .models import MovieRegistration
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json

ROOT = Path(__file__).resolve().parents[2] / "schemas"
FILES = MappingProxyType({
    "story_fragment/1":"story-fragment-v1.schema.json",
    "break_down_scenes/1":"break-down-scenes-task-v1.schema.json",
    "scene_breakdown/1":"scene-breakdown-v1.schema.json",
    "generate_scene_production_options/1":"generate-scene-production-options-task-v1.schema.json",
    "generate_scene_production_options/2":"generate-scene-production-options-task-v2.schema.json",
    "scene_production_option_set/1":"scene-production-option-set-v1.schema.json",
    "scene_production_option_set/2":"scene-production-option-set-v2.schema.json",
    "prepare_scene_option_review/1":"prepare-scene-option-review-task-v1.schema.json",
    "scene_option_review_packet/1":"scene-option-review-packet-v1.schema.json",
    "character_reference/1":"character-reference-v1.schema.json",
    "character_identity/1":"character-identity-v1.schema.json",
    "continuity_sequence/1":"continuity-sequence-v1.schema.json",
    "character_observation/1":"character-observation-v1.schema.json",
    "analyze_character_continuity/1":"analyze-character-continuity-task-v1.schema.json",
    "analyze_character_continuity/2":"analyze-character-continuity-task-v2.schema.json",
    "analyze_character_continuity/3":"analyze-character-continuity-task-v3.schema.json",
    "character_continuity_transition_evidence/1":"character-continuity-transition-evidence-v1.schema.json",
    "character_continuity_observation_set/1":"character-continuity-observation-set-v1.schema.json",
    "shot_cinematography_observation/1":"shot-cinematography-observation-v1.schema.json",
    "shot_cinematography_observation_set/1":"shot-cinematography-observation-set-v1.schema.json",
    "analyze_shot_cinematography_patterns/1":"analyze-shot-cinematography-patterns-task-v1.schema.json",
    "shot_cinematography_pattern_set/1":"shot-cinematography-pattern-set-v1.schema.json",
    "derive_shot_cinematography_lesson_candidates/1":"derive-shot-cinematography-lesson-candidates-task-v1.schema.json",
    "shot_cinematography_lesson_candidate_set/1":"shot-cinematography-lesson-candidate-set-v1.schema.json",
    "shot_cinematography_knowledge_admission/1":"shot-cinematography-knowledge-admission-v1.schema.json",
    "shot_cinematography_admitted_knowledge/1":"shot-cinematography-admitted-knowledge-v1.schema.json",
    "shot_cinematography_knowledge_lifecycle_event/1":"shot-cinematography-knowledge-lifecycle-event-v1.schema.json",
})
COMPATIBILITY = MappingProxyType({
    "generate_scene_production_options/1": "scene_production_option_set/1",
    "generate_scene_production_options/2": "scene_production_option_set/2",
    "prepare_scene_option_review/1": "scene_option_review_packet/1",
    "analyze_character_continuity/1": "character_continuity_observation_set/1",
    "analyze_character_continuity/2": "character_continuity_observation_set/1",
    "analyze_character_continuity/3": "character_continuity_observation_set/1",
    "analyze_shot_cinematography_patterns/1": "shot_cinematography_pattern_set/1",
    "derive_shot_cinematography_lesson_candidates/1": "shot_cinematography_lesson_candidate_set/1",
})
def _pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise MovieRegistryError("movie schema has duplicate keys")
        out[k]=v
    return out
_BUILT_IN = {}
_BUILT_IN_LOCK = Lock()


def _schema_metadata_fingerprint():
    fingerprint = []
    for filename in FILES.values():
        path = ROOT / filename
        try:
            item = os.lstat(path)
            fingerprint.append((filename, item.st_mode, item.st_ino, item.st_size, item.st_mtime_ns))
        except OSError:
            fingerprint.append((filename, None))
    return tuple(fingerprint)

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
    __slots__=("registrations","schemas","compatibility","digest","_validators")
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
        # Schema validation above is repository-metadata validation. Compile
        # each immutable schema once per registry; artifact validation still
        # runs for every caller/provider value through these validators.
        self._validators=MappingProxyType({
            identity: Draft202012Validator(thaw_json(record["schema"]))
            for identity, record in schemas.items()
        })
        self.compatibility=freeze_json(dict(COMPATIBILITY))
        self.digest=canonical_digest({"registry":"movie_domain_contract_registry/1","registrations":[r.__dict__ if hasattr(r,"__dict__") else {"identity":r.identity,"version":r.version,"schema_identity":r.schema_identity,"lifecycle":r.lifecycle,"owner":r.owner} for r in regs],"schemas":{k:v["sha256"] for k,v in sorted(schemas.items())},"compatibility":dict(COMPATIBILITY)})
    @classmethod
    def built_in(cls):
        key = (cls, str(ROOT), _schema_metadata_fingerprint())
        registry = _BUILT_IN.get(key)
        if registry is None:
            with _BUILT_IN_LOCK:
                registry = _BUILT_IN.get(key)
                if registry is None:
                    registry = cls()
                    _BUILT_IN[key] = registry
        return registry

    def iter_errors(self, identity, value):
        try:
            return self._validators[identity].iter_errors(value)
        except KeyError as exc:
            raise MovieContractError("unknown movie contract") from exc
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
