from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from typing import Any

from jsonschema import Draft202012Validator

from vss_context_contracts import ContextContractRegistry
from vss_movie_contracts import (
    MovieContractRegistry, ValidatedMovieArtifact,
    validate_character_continuity_observation_set,
    validate_executable_character_continuity_task,
)
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json, validate_json_value

POLICY_IDENTITY = "character_continuity_context_local"
POLICY_VERSION = "1"
CATALOGUE_IDENTITY = "vss.character-continuity.rules.deterministic"
CATALOGUE_VERSION = "1.0.0"
STRATEGY_IDENTITY = "vss.analyze-character-continuity.deterministic"
STRATEGY_VERSION = "1.0.0"
PROVIDER_IDENTITY = "vss.reasoning.character-continuity.deterministic"
PROVIDER_VERSION = "1.0.0"
PROVIDER_API_VERSION = "1"
MAX_CONTEXT_BYTES = 65536


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class CharacterContinuityRuleCatalogue:
    identity: str = CATALOGUE_IDENTITY
    version: str = CATALOGUE_VERSION
    admitted_categories: tuple[str, ...] = ("presence", "possession", "physical_state")
    transition_categories: tuple[str, ...] = ("possession", "physical_state")
    contradiction_categories: tuple[str, ...] = ("possession", "physical_state")
    chronology_requirement: str = "explicit_linear_positions_only"
    persistence: str = "off"
    maximum_scenes: int = 8
    maximum_characters: int = 8
    maximum_observations: int = 128
    maximum_comparisons: int = 128

    @property
    def digest(self) -> str:
        return canonical_digest({f.name: list(getattr(self, f.name)) if isinstance(getattr(self, f.name), tuple) else getattr(self, f.name) for f in fields(self)})

    @classmethod
    def built_in(cls) -> "CharacterContinuityRuleCatalogue":
        return cls()


@dataclass(frozen=True, slots=True, init=False)
class CharacterContinuityContext:
    value: Any
    digest: str

    @classmethod
    def create(cls, value: dict[str, Any]) -> "CharacterContinuityContext":
        obj = object.__new__(cls)
        frozen = freeze_json(value)
        object.__setattr__(obj, "value", frozen)
        object.__setattr__(obj, "digest", canonical_digest(frozen))
        return obj

    def to_json_value(self) -> dict[str, Any]:
        return thaw_json(self.value)


@dataclass(frozen=True, slots=True)
class CharacterContinuityProviderView:
    project_id: str
    continuity_sequence_id: str
    continuity_sequence_digest: str
    scenes: tuple[Any, ...]
    character_ids: tuple[str, ...]
    categories: tuple[str, ...]
    observations: tuple[Any, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    rule_catalogue_identity: str
    rule_catalogue_version: str
    rule_catalogue_digest: str
    provider_visible_digest: str


def validate_character_continuity_context(value: Any, *, registry: ContextContractRegistry | None = None) -> CharacterContinuityContext:
    registry = registry or ContextContractRegistry.built_in()
    if isinstance(value, CharacterContinuityContext):
        value = value.to_json_value()
    elif hasattr(value, "keys"):
        value = thaw_json(value)
    try:
        validate_json_value(value, maximum_bytes=MAX_CONTEXT_BYTES)
    except Exception as exc:
        raise ValueError("character continuity Context is unsafe") from exc
    if not isinstance(value, dict):
        raise ValueError("character continuity Context must be an object")
    errors = list(Draft202012Validator(thaw_json(registry.schema("vss.character_continuity_context/1").schema)).iter_errors(value))
    if errors:
        raise ValueError("character continuity Context does not match its contract")
    payload = value["payload"]
    catalogue = CharacterContinuityRuleCatalogue.built_in()
    if (payload["rule_catalogue_identity"], payload["rule_catalogue_version"], payload["rule_catalogue_digest"]) != (catalogue.identity, catalogue.version, catalogue.digest):
        raise ValueError("character continuity rule catalogue substitution rejected")
    if value["semantic_task_version"] != "2":
        raise ValueError("validation-only task v1 cannot enter executable Context")
    positions = [scene["continuity_position"] for scene in payload["selected_scenes"]]
    if positions != list(range(1, len(positions) + 1)):
        raise ValueError("Context chronology must be explicit, ordered, and contiguous")
    if len({scene["scene_id"] for scene in payload["selected_scenes"]}) != len(payload["selected_scenes"]):
        raise ValueError("Context scene identity is duplicated")
    if [x["character_id"] for x in payload["selected_characters"]] != sorted(x["character_id"] for x in payload["selected_characters"]):
        raise ValueError("Context character order is not canonical")
    if len({x["character_id"] for x in payload["selected_characters"]}) != len(payload["selected_characters"]):
        raise ValueError("Context character identity is duplicated")
    order = {name: i for i, name in enumerate(catalogue.admitted_categories)}
    if payload["selected_categories"] != sorted(payload["selected_categories"], key=order.__getitem__):
        raise ValueError("Context category order is not canonical")
    expected_obs = sorted(payload["observations"], key=lambda x: (x["sequence_position"], x["character_id"], order[x["category"]], x["observation_id"]))
    if payload["observations"] != expected_obs:
        raise ValueError("Context observation order is not canonical")
    if len({x["observation_id"] for x in payload["observations"]}) != len(payload["observations"]):
        raise ValueError("Context observation identity is duplicated")
    scene_map = {x["scene_id"]: x for x in payload["selected_scenes"]}
    character_ids = {x["character_id"] for x in payload["selected_characters"]}
    categories = set(payload["selected_categories"])
    for obs in payload["observations"]:
        scene = scene_map.get(obs["scene_id"])
        if obs["character_id"] not in character_ids or obs["category"] not in categories or scene is None or (obs["scene_content_digest"], obs["sequence_position"]) != (scene["scene_content_digest"], scene["continuity_position"]):
            raise ValueError("Context observation binding is invalid")
    if canonical_digest(payload) != value["context_content_digest"]:
        raise ValueError("character continuity Context content digest mismatch")
    if _ts(value["constructed_at"]) >= _ts(value["expires_at"]):
        raise ValueError("character continuity Context expiry is invalid")
    material = dict(value); integrity = dict(material["integrity"]); expected = integrity.pop("complete_context_sha256"); material["integrity"] = integrity
    if expected != canonical_digest(material):
        raise ValueError("character continuity Context integrity mismatch")
    return CharacterContinuityContext.create(value)


def _require_artifact(value: Any, identity: str) -> ValidatedMovieArtifact:
    if not isinstance(value, ValidatedMovieArtifact):
        raise ValueError("Context Assembly requires independently validated movie artifacts")
    if value.value.get("contract_identity") != identity:
        raise ValueError("Context Assembly artifact family is invalid")
    return value


def assemble_character_continuity_context(task: ValidatedMovieArtifact, sequence: ValidatedMovieArtifact, identities: tuple[ValidatedMovieArtifact, ...], observations: tuple[ValidatedMovieArtifact, ...], *, classification: str = "public", validation_time: str | None = None) -> CharacterContinuityContext:
    sequence = _require_artifact(sequence, "continuity_sequence")
    identities = tuple(_require_artifact(x, "character_identity") for x in identities)
    observations = tuple(_require_artifact(x, "character_observation") for x in observations)
    if not isinstance(task, ValidatedMovieArtifact):
        raise ValueError("Context Assembly requires an independently validated executable task")
    validated_task = validate_executable_character_continuity_task(task.to_json_value(), sequence, identities, MovieContractRegistry.built_in())
    if validated_task.digest != task.digest:
        raise ValueError("executable task substitution rejected")
    tv = task.value; sv = sequence.value
    if validation_time is not None and not (
        tv["project_id"] == "continuity-local"
        and task.digest == "f49dd8fb2045ace76cc5af3c3350d07905c4f79581bc58c9ee054cda21de93c0"  # pragma: allowlist secret
        and validation_time == "2026-08-08T00:00:00Z"
    ):
        raise ValueError("caller-selected character continuity clock is not admitted")
    if classification not in {"public", "internal"} or tv["purpose"] != "character_continuity_local_validation" or tv["environment"] != "development":
        raise ValueError("character continuity Context policy is invalid")
    expected_ids = set(tv["selected_character_ids"]); expected_categories = set(tv["selected_observation_categories"])
    if {x.value["character_id"] for x in identities} != expected_ids:
        raise ValueError("Context selected character set is not exact")
    if len(observations) > tv["bounds"]["maximum_observations"]:
        raise ValueError("Context observation bound exceeded")
    for obs in observations:
        ov = obs.value
        if ov["project_id"] != tv["project_id"] or ov["continuity_sequence_digest"] != sv["content_digest"] or ov["character_id"] not in expected_ids or ov["category"] not in expected_categories:
            raise ValueError("Context observation selection is invalid")
    for field in ("character_id", "scene_id"):
        counts: dict[str, int] = {}
        for artifact in observations:
            key = artifact.value[field]; counts[key] = counts.get(key, 0) + 1
        if any(count > 32 for count in counts.values()):
            raise ValueError("Context per-identity observation bound exceeded")
    if len({ref for artifact in observations for ref in artifact.value["evidence_references"]}) > 64:
        raise ValueError("Context aggregate evidence-reference bound exceeded")
    catalogue = CharacterContinuityRuleCatalogue.built_in()
    scenes = [thaw_json(x) for x in sv["selected_scenes"]]
    characters = sorted(({"character_id": x.value["character_id"], "identity_digest": x.value["content_digest"]} for x in identities), key=lambda x: x["character_id"])
    category_order = {name: i for i, name in enumerate(catalogue.admitted_categories)}
    selected_observations = []
    for artifact in observations:
        value = artifact.to_json_value()
        selected_observations.append({key: value[key] for key in ("observation_id", "observation_content_digest", "character_id", "scene_id", "scene_content_digest", "sequence_position", "category", "payload", "provenance_category", "evidence_references", "confidence", "assumptions", "unknowns", "limitations")})
    selected_observations.sort(key=lambda x: (x["sequence_position"], x["character_id"], category_order[x["category"]], x["observation_id"]))
    unknowns = ["No state is inferred for scenes without an explicit observation.", "Identity and chronology are exact supplied bindings, not inferred claims."]
    limitations = ["Persistence is off; every observation is scene-local.", "M5.2 does not discover transitions or contradictions.", "This Context and its evidence are inert and non-authorizing."]
    payload = {"task_digest": task.digest, "continuity_sequence_id": sv["continuity_sequence_id"], "continuity_sequence_digest": sv["content_digest"], "scene_breakdown_digest": sv["scene_breakdown_digest"], "selected_scenes": scenes, "selected_characters": characters, "selected_categories": list(tv["selected_observation_categories"]), "observations": selected_observations, "rule_catalogue_identity": catalogue.identity, "rule_catalogue_version": catalogue.version, "rule_catalogue_digest": catalogue.digest, "unknowns": unknowns, "limitations": limitations, "budget_summary": {"maximum_context_bytes": MAX_CONTEXT_BYTES, "maximum_scenes": 8, "maximum_characters": 8, "maximum_observations": 128, "maximum_comparisons": 128}}
    input_set_digest = canonical_digest({"task": task.digest, "sequence": sequence.digest, "identities": sorted(x.digest for x in identities), "observations": sorted(x.digest for x in observations)})
    selection_digest = canonical_digest({"project": tv["project_id"], "sequence": sv["content_digest"], "characters": list(tv["selected_character_ids"]), "categories": list(tv["selected_observation_categories"]), "scenes": scenes, "observations": [x["observation_content_digest"] for x in selected_observations]})
    now = _ts(validation_time) if validation_time else datetime.now(timezone.utc).replace(microsecond=0)
    content = canonical_digest(payload)
    context = {"schema_version":"1", "context_id":"continuity-context-"+content[:32], "context_family":"character_continuity_context", "context_family_version":"1", "request_id":tv["request_id"], "correlation_id":tv["correlation_id"], "semantic_task":"analyze_character_continuity", "semantic_task_version":"2", "result_family":"character_continuity_observation_set", "result_version":"1", "purpose":tv["purpose"], "environment":tv["environment"], "project_id":tv["project_id"], "classification":classification, "policy_identity":POLICY_IDENTITY, "policy_version":POLICY_VERSION, "constructed_at":_iso(now), "expires_at":_iso(now+timedelta(seconds=300)), "lifecycle":"validated", "input_set_digest":input_set_digest, "selection_digest":selection_digest, "context_content_digest":content, "integrity":{"complete_context_sha256":"0"*64}, "payload":payload}
    context["integrity"]["complete_context_sha256"] = canonical_digest({**context, "integrity":{}})
    return validate_character_continuity_context(context)


def character_continuity_context_report(context: CharacterContinuityContext) -> Any:
    c = validate_character_continuity_context(context).to_json_value(); p = c["payload"]
    report = {"schema_version":"1", "report_family":"character_continuity_context_assembly_report", "report_version":"1", "request_id":c["request_id"], "correlation_id":c["correlation_id"], "context_id":c["context_id"], "context_family":"character_continuity_context", "context_version":"1", "project_id":c["project_id"], "purpose":c["purpose"], "classification":c["classification"], "scene_count":len(p["selected_scenes"]), "character_count":len(p["selected_characters"]), "observation_count":len(p["observations"]), "input_set_digest":c["input_set_digest"], "selection_digest":c["selection_digest"], "context_content_digest":c["context_content_digest"], "complete_context_digest":context.digest, "rule_catalogue_digest":p["rule_catalogue_digest"], "expires_at":c["expires_at"], "revocation_result":"eligible", "status":"success"}
    report["report_digest"] = canonical_digest(report)
    return freeze_json(report)


def character_continuity_provider_view(context: Any) -> CharacterContinuityProviderView:
    c = validate_character_continuity_context(context).to_json_value(); p = c["payload"]
    material = {"project_id":c["project_id"], "continuity_sequence_id":p["continuity_sequence_id"], "continuity_sequence_digest":p["continuity_sequence_digest"], "scenes":p["selected_scenes"], "character_ids":[x["character_id"] for x in p["selected_characters"]], "categories":p["selected_categories"], "observations":p["observations"], "unknowns":p["unknowns"], "limitations":p["limitations"], "rule_catalogue_identity":p["rule_catalogue_identity"], "rule_catalogue_version":p["rule_catalogue_version"], "rule_catalogue_digest":p["rule_catalogue_digest"]}
    return CharacterContinuityProviderView(material["project_id"], material["continuity_sequence_id"], material["continuity_sequence_digest"], tuple(freeze_json(x) for x in material["scenes"]), tuple(material["character_ids"]), tuple(material["categories"]), tuple(freeze_json(x) for x in material["observations"]), tuple(material["unknowns"]), tuple(material["limitations"]), material["rule_catalogue_identity"], material["rule_catalogue_version"], material["rule_catalogue_digest"], canonical_digest(material))


def analyze_explicit_observations(view: CharacterContinuityProviderView) -> tuple[str, ...]:
    if type(view) is not CharacterContinuityProviderView:
        raise TypeError("provider requires exact CharacterContinuityProviderView")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for frozen in view.observations:
        obs = thaw_json(frozen)
        groups.setdefault((obs["character_id"], obs["category"]), []).append(obs)
    notes: list[str] = []
    comparisons = 0
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda x: (x["sequence_position"], x["observation_id"]))
        repeated = False; changed = False
        for left, right in zip(group, group[1:]):
            comparisons += 1
            if comparisons > 128:
                raise ValueError("continuity comparison bound exceeded")
            if left["payload"] == right["payload"]:
                repeated = True
            else:
                changed = True
        if changed:
            notes.append(f"Different explicit {key[1]} observations for {key[0]} are not generically contradictory in M5.2.")
        elif repeated:
            notes.append(f"Repeated explicit {key[1]} observations for {key[0]} do not prove persistence.")
    if not notes:
        notes.append("Available explicit observations provide no supported cross-scene comparison; missing evidence remains unknown.")
    return tuple(notes)


def create_character_continuity_result(view: CharacterContinuityProviderView, binding: Any, comparison_notes: tuple[str, ...]) -> dict[str, Any]:
    if type(view) is not CharacterContinuityProviderView or type(comparison_notes) is not tuple:
        raise TypeError("continuity result inputs are invalid")
    observations = [{key: obs[key] for key in ("observation_id", "observation_content_digest", "character_id", "scene_id", "scene_content_digest", "sequence_position", "category")} for obs in map(thaw_json, view.observations)]
    evidence = sorted({ref for obs in map(thaw_json, view.observations) for ref in obs["evidence_references"]})
    unknowns = list(dict.fromkeys(list(view.unknowns) + list(comparison_notes)))
    limitations = list(dict.fromkeys(list(view.limitations) + ["Deterministic comparison uses explicit structured observations only; it grants no authority."]))
    payload = {"observations":observations, "explicit_transitions":[], "contradictions":[], "unknowns":unknowns, "evidence_references":evidence, "confidence":{"level":"low", "basis":"Bounded deterministic comparison of explicit structured evidence.", "qualifications":["Confidence is qualified, does not establish truth, and grants no authority."]}, "limitations":limitations, "review_suggested":False, "semantic_result_digest":None}
    payload["semantic_result_digest"] = canonical_digest(payload)
    result = {"schema_version":"1", "result_family":"character_continuity_observation_set", "result_version":"1", "request_id":binding["request_id"], "correlation_id":binding["correlation_id"], "project_id":view.project_id, "continuity_sequence_id":view.continuity_sequence_id, "continuity_sequence_digest":view.continuity_sequence_digest, "selected_character_ids":list(view.character_ids), "selected_observation_categories":list(view.categories), "payload":payload, "integrity":{"payload_sha256":canonical_digest(payload), "complete_result_sha256":"0"*64}}
    result["integrity"]["complete_result_sha256"] = canonical_digest({**result, "integrity":{"payload_sha256":result["integrity"]["payload_sha256"]}})
    return result
