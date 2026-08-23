from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any

from jsonschema import Draft202012Validator

from vss_context_contracts import ContextContractRegistry
from vss_movie_contracts import MovieContractRegistry, validate_production_option_set, validate_scene_breakdown
from vss_reasoning_contracts import canonical_bytes, canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json, validate_json_value

POLICY_IDENTITY = "scene_production_options_context_local"
POLICY_VERSION = "1"
POLICY = f"{POLICY_IDENTITY}/{POLICY_VERSION}"
CATALOGUE_IDENTITY = "vss.scene-production-profiles.deterministic"
CATALOGUE_VERSION = "1.0.0"
CATALOGUE = f"{CATALOGUE_IDENTITY}/{CATALOGUE_VERSION}"
STRATEGY_IDENTITY = "vss.generate-scene-production-options.deterministic"
STRATEGY_VERSION = "1.0.0"
PROVIDER_IDENTITY = "vss.reasoning.deterministic-scene-production-options"
PROVIDER_VERSION = "1.0.0"
PROVIDER_API_VERSION = "1"
MAX_CONTEXT_BYTES = 32768
MAX_KNOWLEDGE_BINDINGS = 2
V2_POLICY_VERSION = "2"
V2_STRATEGY_VERSION = "1.0.0"
V2_PROVIDER_VERSION = "1.0.0"

def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass(frozen=True, slots=True)
class ProductionProfile:
    identity: str
    version: str
    ordinal: int
    approach_category: str
    complexity_qualification: str
    performer_implications: tuple[str, ...]
    location_implications: str
    asset_implications: tuple[str, ...]
    effects_qualification: str
    audio_considerations: tuple[str, ...]
    prototype_suitability: str
    mandatory_unknowns: tuple[str, ...]
    mandatory_external_validation: tuple[str, ...]
    mandatory_limitations: tuple[str, ...]

    def material(self) -> dict[str, Any]:
        return {field.name: list(getattr(self, field.name)) if isinstance(getattr(self, field.name), tuple) else getattr(self, field.name) for field in fields(self)}

class ProductionProfileCatalogue:
    __slots__ = ("profiles", "digest")
    identity = CATALOGUE_IDENTITY
    version = CATALOGUE_VERSION

    def __init__(self) -> None:
        common_unknowns = ("Feasibility, cost, duration, quality, availability, rights, permits, and artistic suitability are unknown.",)
        common_validation = ("Validate feasibility, people, locations, assets, effects, audio, rights, permits, cost, duration, and quality externally.",)
        common_limits = ("This profile is an inert structural alternative, not a plan, ranking, recommendation, approval, or execution instruction.",)
        profiles = (
            ProductionProfile("minimal_stage", CATALOGUE_VERSION, 1, "bounded_minimal_stage", "qualified_low_relative_complexity", ("performer categories remain unverified",), "controlled local setting category", ("minimal representational asset categories",), "bounded practical effects category", ("dialogue and ambient audio remain unverified",), "qualified local prototype candidate", common_unknowns, common_validation, common_limits),
            ProductionProfile("location_live_action", CATALOGUE_VERSION, 2, "location_live_action", "qualified_context_dependent_complexity", ("performer categories and availability remain unverified",), "source-indicated location category; availability unverified", ("location and practical asset categories",), "context-dependent effects category", ("location audio conditions remain unverified",), "qualified only after external location validation", common_unknowns, common_validation, common_limits),
            ProductionProfile("stylized_2d", CATALOGUE_VERSION, 3, "stylized_2d_representation", "qualified_medium_structural_complexity", ("voice/performance categories remain unverified",), "represented location category", ("2D design and animation asset categories",), "stylized visual effects category", ("voice, sound design, and music requirements remain unverified",), "qualified visualization prototype candidate", common_unknowns, common_validation, common_limits),
            ProductionProfile("stylized_3d", CATALOGUE_VERSION, 4, "stylized_3d_representation", "qualified_high_structural_complexity", ("voice/motion performance categories remain unverified",), "represented 3D location category", ("3D model, rig, material, and animation asset categories",), "stylized 3D effects category", ("voice, sound design, and music requirements remain unverified",), "qualified technical prototype candidate", common_unknowns, common_validation, common_limits),
        )
        if [p.ordinal for p in profiles] != [1, 2, 3, 4] or len({(p.identity, p.version) for p in profiles}) != 4:
            raise ValueError("production profile catalogue is invalid")
        object.__setattr__(self, "profiles", profiles)
        object.__setattr__(self, "digest", canonical_digest({"identity": self.identity, "version": self.version, "stable_order_is_not_ranking": True, "profiles": [p.material() for p in profiles]}))

    def __setattr__(self, name, value):
        raise TypeError("production profile catalogue is immutable")

    @classmethod
    def built_in(cls) -> "ProductionProfileCatalogue": return cls()

@dataclass(frozen=True, slots=True, init=False)
class SceneProductionOptionsContext:
    value: Any
    digest: str
    @classmethod
    def create(cls, value: dict[str, Any]) -> "SceneProductionOptionsContext":
        obj = object.__new__(cls); frozen = freeze_json(value)
        object.__setattr__(obj, "value", frozen); object.__setattr__(obj, "digest", canonical_digest(frozen)); return obj
    def to_json_value(self) -> dict[str, Any]: return thaw_json(self.value)

@dataclass(frozen=True, slots=True)
class SceneProductionOptionsProviderView:
    project_id: str
    scene_breakdown_digest: str
    scene_id: str
    scene_content_digest: str
    source_observations: tuple[Any, ...]
    source_claims: tuple[Any, ...]
    boundary_basis: str
    boundary_rule_identity: str
    ambiguity: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    conflicts: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_references: tuple[str, ...]
    rights_qualification: str
    cultural_qualification: str
    local_resource_constraints: tuple[str, ...]
    profiles: tuple[ProductionProfile, ...]
    option_limit: int
    provider_visible_digest: str
    knowledge_bindings: tuple[Any, ...] = ()

def validate_production_options_context(value: Any, *, registry: ContextContractRegistry | None = None) -> SceneProductionOptionsContext:
    if isinstance(value, SceneProductionOptionsContext): value = value.value
    value = thaw_json(value) if hasattr(value, "keys") else value
    try: validate_json_value(value, maximum_bytes=MAX_CONTEXT_BYTES)
    except Exception as exc: raise ValueError("production Context is unsafe") from exc
    required = {"schema_version","context_id","context_family","context_family_version","request_id","correlation_id","semantic_task","semantic_task_version","result_family","result_version","purpose","environment","project_id","classification","trust","policy_identity","policy_version","constructed_at","expires_at","lifecycle","context_content_digest","integrity","payload"}
    if not isinstance(value, dict) or set(value) != required: raise ValueError("production Context fields are invalid")
    expected = ("scene_production_options_context","1","generate_scene_production_options","1","scene_production_option_set","1","scene_production_options_local_validation","development",POLICY_IDENTITY,POLICY_VERSION,"validated")
    actual = (value["context_family"],value["context_family_version"],value["semantic_task"],value["semantic_task_version"],value["result_family"],value["result_version"],value["purpose"],value["environment"],value["policy_identity"],value["policy_version"],value["lifecycle"])
    if actual != expected or value["classification"] not in {"public","internal"} or value["trust"] != "approved_fixture": raise ValueError("production Context compatibility is invalid")
    reg = registry or ContextContractRegistry.built_in()
    schema = reg.schema("vss.scene_production_options_context/1").schema
    if list(Draft202012Validator(schema).iter_errors(value["payload"])): raise ValueError("production Context payload is invalid")
    payload = value["payload"]; catalogue = ProductionProfileCatalogue.built_in()
    if (payload["profile_catalogue_identity"], payload["profile_catalogue_version"], payload["profile_catalogue_digest"], payload["option_count_limit"]) != (catalogue.identity, catalogue.version, catalogue.digest, len(catalogue.profiles)):
        raise ValueError("production catalogue substitution rejected")
    if payload["selected_scene_id"] == "" or payload["selected_scene_digest"] == "0"*64 or payload["scene_breakdown_digest"] == "0"*64: raise ValueError("selected scene binding is invalid")
    if _ts(value["constructed_at"]) >= _ts(value["expires_at"]): raise ValueError("production Context expiry is invalid")
    if canonical_digest(payload) != value["context_content_digest"]: raise ValueError("production Context content digest mismatch")
    material = dict(value); integrity = dict(material["integrity"]); expected_digest = integrity.pop("complete_context_sha256"); material["integrity"] = integrity
    if expected_digest != canonical_digest(material): raise ValueError("production Context integrity mismatch")
    return SceneProductionOptionsContext.create(value)

def _knowledge_binding(value: Any, *, project_id: str, classification: str, validation_time: str) -> dict[str, Any]:
    """Revalidate one hostile M6.5 binding; no eligibility result is cached."""
    if not isinstance(value, dict) or set(value) != {"knowledge", "lifecycle_events", "replacements"}:
        raise ValueError("Knowledge binding fields are invalid")
    from vss_movie_cinematic_knowledge import current_use_eligible
    knowledge = value["knowledge"]
    if not isinstance(knowledge, dict) or knowledge.get("project_id") != project_id or knowledge.get("domain") != "shot_cinematography":
        raise ValueError("Knowledge scope is invalid")
    eligible = current_use_eligible(knowledge, lifecycle_events=value["lifecycle_events"], replacements=value["replacements"], validation_time=validation_time)
    if eligible.value.get("classification") != classification:
        raise ValueError("Knowledge classification is not compatible")
    return {"knowledge": eligible.to_json_value(), "lifecycle_events": value["lifecycle_events"], "replacements": value["replacements"]}

def validate_production_options_context_v2(value: Any, *, registry: ContextContractRegistry | None = None, validation_time: str | None = None) -> SceneProductionOptionsContext:
    value = thaw_json(value.value) if isinstance(value, SceneProductionOptionsContext) else thaw_json(value) if hasattr(value, "keys") else value
    if not isinstance(value, dict) or value.get("schema_version") != "2" or value.get("context_family") != "scene_production_options_context" or value.get("context_family_version") != "2" or value.get("semantic_task") != "generate_scene_production_options" or value.get("semantic_task_version") != "2" or value.get("result_family") != "scene_production_option_set" or value.get("result_version") != "2" or value.get("purpose") != "scene_production_options_local_analysis" or value.get("environment") != "development" or value.get("policy_identity") != POLICY_IDENTITY or value.get("policy_version") != V2_POLICY_VERSION or value.get("lifecycle") != "validated" or value.get("trust") != "approved_fixture":
        raise ValueError("production Context v2 is required")
    reg = registry or ContextContractRegistry.built_in()
    errors = list(reg.iter_errors("vss.scene_production_options_context/2", value["payload"]))
    if errors: raise ValueError("production Context v2 schema is invalid")
    payload = value["payload"]
    # Verify the caller-supplied v2 seals before projecting to the accepted v1
    # common Context.  Never normalize/reseal hostile content on its behalf.
    if value["context_content_digest"] != canonical_digest(payload):
        raise ValueError("production Context v2 content digest mismatch")
    supplied_integrity = value["integrity"]
    complete_material = dict(value)
    complete_material["integrity"] = {}
    if supplied_integrity["complete_context_sha256"] != canonical_digest(complete_material):
        raise ValueError("production Context v2 integrity mismatch")
    if len(payload["knowledge_bindings"]) > MAX_KNOWLEDGE_BINDINGS:
        raise ValueError("Knowledge binding bound exceeded")
    base = dict(value); base_payload = dict(payload); bindings = base_payload.pop("knowledge_bindings")
    base_payload_digest = canonical_digest(base_payload)
    base["schema_version"] = "1"; base["context_family_version"] = "1"; base["result_version"] = "1"; base["semantic_task_version"] = "1"; base["purpose"] = "scene_production_options_local_validation"; base["policy_version"] = "1"; base["context_content_digest"] = base_payload_digest
    base["payload"] = base_payload; base["integrity"] = {"complete_context_sha256":"0"*64}; base["integrity"]["complete_context_sha256"] = canonical_digest({**base, "integrity": {}})
    base_context = validate_production_options_context(base, registry=reg)
    when = validation_time or value.get("constructed_at")
    if _ts(when) >= _ts(value["expires_at"]):
        raise ValueError("production Context v2 is expired")
    normalized = [_knowledge_binding(item, project_id=value["project_id"], classification=value["classification"], validation_time=when) for item in bindings]
    ids = [item["knowledge"]["knowledge_id"] for item in normalized]
    if len(ids) != len(set(ids)): raise ValueError("duplicate Knowledge binding")
    out = dict(value); out["payload"] = dict(payload); out["payload"]["knowledge_bindings"] = normalized
    if canonical_digest(out["payload"]) != value["context_content_digest"]:
        raise ValueError("production Context v2 binding normalization changed sealed content")
    out["context_content_digest"] = value["context_content_digest"]
    out["integrity"] = dict(value["integrity"])
    # Preserve the immutable Context artifact shape while retaining the v2 value.
    return SceneProductionOptionsContext.create(out)

def assemble_production_options_context(scene_breakdown: Any, *, request_id: str, correlation_id: str, project_id: str, scene_id: str, scene_content_digest: str, environment: str = "development", validation_time: str | None = None) -> SceneProductionOptionsContext:
    result = validate_scene_breakdown(scene_breakdown, MovieContractRegistry.built_in()); breakdown = result.to_json_value()
    if breakdown["project_id"] != project_id or environment != "development": raise ValueError("production Context project or environment mismatch")
    by_id = [scene for scene in breakdown["payload"]["ordered_scenes"] if scene["scene_id"] == scene_id]
    if len(by_id) != 1 or by_id[0]["scene_content_digest"] != scene_content_digest: raise ValueError("exact scene selection failed")
    scene = by_id[0]; catalogue = ProductionProfileCatalogue.built_in()
    now = _ts(validation_time) if validation_time else datetime.now(timezone.utc).replace(microsecond=0)
    observations = list(scene["source_observations"]); claims = list(scene["events"])
    payload = {
        "scene_breakdown_identity":"scene_breakdown","scene_breakdown_version":"1","scene_breakdown_digest":result.digest,
        "selected_scene_id":scene_id,"selected_scene_digest":scene_content_digest,
        "selected_scene":{"source_observations":observations,"declared_characters":scene["declared_characters"],"declared_locations":scene["declared_locations"],"time_indicators":scene["time_indicators"],"events":claims},
        "source_binding_identity":scene["source_binding"],"source_binding_digest":canonical_digest({"identity":scene["source_binding"],"breakdown":result.digest}),
        "source_observations":observations,"source_claims":claims,"boundary_basis":scene["boundary_basis"],"boundary_rule_identity":scene["boundary_rule"],
        "ambiguity":["Scene boundary is ambiguous."] if scene["ambiguous_boundary"] else [],"assumptions":scene["assumptions"] + breakdown["payload"]["assumptions"],"unknowns":scene["unknowns"] + breakdown["payload"]["unknowns"],"conflicts":scene["conflicts"] + breakdown["payload"]["conflicts"],"limitations":scene["limitations"] + breakdown["payload"]["limitations"] + ["Production options are inert alternatives; stable order is not ranking."],"evidence_references":scene["evidence_references"],
        "rights_qualification":"not available in scene_breakdown/1; external validation required","cultural_qualification":"not available in scene_breakdown/1; external validation required","local_resource_constraints":["Local deterministic validation only; no external retrieval or execution."],
        "profile_catalogue_identity":catalogue.identity,"profile_catalogue_version":catalogue.version,"profile_catalogue_digest":catalogue.digest,"option_count_limit":len(catalogue.profiles),"budget_summary":{"maximum_context_bytes":MAX_CONTEXT_BYTES,"maximum_nodes":1024,"maximum_depth":12},
    }
    content = canonical_digest(payload)
    context = {"schema_version":"1","context_id":"production-context-"+content[:32],"context_family":"scene_production_options_context","context_family_version":"1","request_id":request_id,"correlation_id":correlation_id,"semantic_task":"generate_scene_production_options","semantic_task_version":"1","result_family":"scene_production_option_set","result_version":"1","purpose":"scene_production_options_local_validation","environment":environment,"project_id":project_id,"classification":"public","trust":"approved_fixture","policy_identity":POLICY_IDENTITY,"policy_version":POLICY_VERSION,"constructed_at":_iso(now),"expires_at":_iso(now+timedelta(seconds=300)),"lifecycle":"validated","context_content_digest":content,"integrity":{"complete_context_sha256":"0"*64},"payload":payload}
    context["integrity"]["complete_context_sha256"] = canonical_digest({**context,"integrity":{}})
    return validate_production_options_context(context)

def production_context_report(context: SceneProductionOptionsContext) -> dict[str, Any]:
    c = validate_production_options_context(context).to_json_value(); p = c["payload"]
    report = {"schema_version":"1","report_family":"scene_production_options_context_assembly_report","report_version":"1","request_id":c["request_id"],"correlation_id":c["correlation_id"],"scene_breakdown_identity":p["scene_breakdown_identity"],"scene_breakdown_digest":p["scene_breakdown_digest"],"selected_scene_id":p["selected_scene_id"],"selected_scene_digest":p["selected_scene_digest"],"context_id":c["context_id"],"context_family":c["context_family"],"context_version":"1","context_content_digest":c["context_content_digest"],"complete_context_digest":canonical_digest(c),"project_id":c["project_id"],"environment":c["environment"],"purpose":c["purpose"],"classification":c["classification"],"trust":c["trust"],"rights_qualification_status":"claim_preserved","cultural_qualification_status":"claim_preserved","profile_catalogue_identity":p["profile_catalogue_identity"],"profile_catalogue_version":p["profile_catalogue_version"],"included_count":1,"omitted_count":0,"ambiguity_count":len(p["ambiguity"]),"conflict_count":len(p["conflicts"]),"unknown_count":len(p["unknowns"]),"limitation_count":len(p["limitations"]),"budget_use":{"context_bytes":len(canonical_bytes(c)),"maximum_context_bytes":MAX_CONTEXT_BYTES},"constructed_at":c["constructed_at"],"expires_at":c["expires_at"],"status":"success"}
    report["report_digest"] = canonical_digest(report); return freeze_json(report)

def production_provider_view(context: Any) -> SceneProductionOptionsProviderView:
    c = validate_production_options_context(context).to_json_value(); p = c["payload"]; catalogue = ProductionProfileCatalogue.built_in()
    material = {"project_id":c["project_id"],"scene_breakdown_digest":p["scene_breakdown_digest"],"scene_id":p["selected_scene_id"],"scene_content_digest":p["selected_scene_digest"],"source_observations":p["source_observations"],"source_claims":p["source_claims"],"boundary_basis":p["boundary_basis"],"boundary_rule_identity":p["boundary_rule_identity"],"ambiguity":p["ambiguity"],"assumptions":p["assumptions"],"unknowns":p["unknowns"],"conflicts":p["conflicts"],"limitations":p["limitations"],"evidence_references":p["evidence_references"],"rights_qualification":p["rights_qualification"],"cultural_qualification":p["cultural_qualification"],"local_resource_constraints":p["local_resource_constraints"],"profiles":[profile.material() for profile in catalogue.profiles],"option_limit":p["option_count_limit"]}
    return SceneProductionOptionsProviderView(c["project_id"],p["scene_breakdown_digest"],p["selected_scene_id"],p["selected_scene_digest"],tuple(freeze_json(x) for x in p["source_observations"]),tuple(freeze_json(x) for x in p["source_claims"]),p["boundary_basis"],p["boundary_rule_identity"],tuple(p["ambiguity"]),tuple(p["assumptions"]),tuple(p["unknowns"]),tuple(p["conflicts"]),tuple(p["limitations"]),tuple(p["evidence_references"]),p["rights_qualification"],p["cultural_qualification"],tuple(p["local_resource_constraints"]),catalogue.profiles,p["option_count_limit"],canonical_digest(material))

def production_provider_view_v2(context: Any, *, validation_time: str | None = None) -> SceneProductionOptionsProviderView:
    from vss_movie_production_options import validate_production_options_context_v2
    v2 = validate_production_options_context_v2(context, validation_time=validation_time)
    c = v2.to_json_value(); payload = dict(c["payload"]); bindings = tuple(payload.pop("knowledge_bindings"))
    base = dict(c); base["schema_version"] = "1"; base["context_family_version"] = "1"; base["result_version"] = "1"; base["semantic_task_version"] = "1"; base["purpose"] = "scene_production_options_local_validation"; base["policy_version"] = "1"; base["payload"] = payload; base["context_content_digest"] = canonical_digest(payload); base["integrity"] = {"complete_context_sha256":"0"*64}; base["integrity"]["complete_context_sha256"] = canonical_digest({**base, "integrity": {}})
    view = production_provider_view(validate_production_options_context(base))
    projected = tuple(freeze_json({"knowledge_id": b["knowledge"]["knowledge_id"], "knowledge_content_digest": b["knowledge"]["knowledge_content_digest"], "admission_decision_id": b["knowledge"]["admission_decision_id"], "admission_decision_digest": b["knowledge"]["admission_decision_digest"], "source_candidate": b["knowledge"]["source_candidate"], "proposition": b["knowledge"]["proposition"], "use": "informational_context_only"}) for b in bindings)
    material = {"base": view.provider_visible_digest, "knowledge_bindings": list(projected)}
    return replace(view, provider_visible_digest=canonical_digest(material), knowledge_bindings=projected)

def create_production_option_candidates(view: SceneProductionOptionsProviderView) -> tuple[Any, ...]:
    if type(view) is not SceneProductionOptionsProviderView: raise TypeError("provider requires SceneProductionOptionsProviderView")
    options = []
    for profile in view.profiles[:view.option_limit]:
        option = {"ordinal":profile.ordinal,"profile_identity":profile.identity,"profile_version":profile.version,"scene_id":view.scene_id,"scene_content_digest":view.scene_content_digest,"approach_category":profile.approach_category,"complexity_qualification":profile.complexity_qualification,"qualified_rationale":"A deterministic profile-derived alternative requiring external validation; not a recommendation.","source_supported_considerations":[x["text"] for x in map(thaw_json, view.source_observations)],"rule_derived_considerations":[f"Boundary basis: {view.boundary_basis}; rule: {view.boundary_rule_identity}."],"performer_requirement_categories":list(profile.performer_implications),"location_approach_category":profile.location_implications,"asset_requirement_categories":list(profile.asset_implications),"effects_intensity_category":profile.effects_qualification,"audio_considerations":list(profile.audio_considerations),"prototype_suitability":profile.prototype_suitability,"assumptions":list(view.assumptions),"unknowns":list(dict.fromkeys(view.unknowns+profile.mandatory_unknowns)),"conflicts":list(view.conflicts),"limitations":list(dict.fromkeys(view.limitations+profile.mandatory_limitations)),"external_validation_requirements":list(profile.mandatory_external_validation),"evidence_references":list(view.evidence_references),"qualified_confidence":"low"}
        options.append(freeze_json(option))
    return tuple(options)

def create_production_option_set(view: SceneProductionOptionsProviderView, binding: dict[str, Any], candidates: tuple[Any, ...] | None = None) -> dict[str, Any]:
    if type(view) is not SceneProductionOptionsProviderView: raise TypeError("provider requires SceneProductionOptionsProviderView")
    raw_candidates = candidates if candidates is not None else create_production_option_candidates(view)
    if type(raw_candidates) is not tuple or len(raw_candidates) != min(view.option_limit, len(view.profiles)):
        raise ValueError("provider candidate count is invalid")
    options = []
    for position, candidate in enumerate(raw_candidates):
        option = thaw_json(candidate)
        profile = view.profiles[position]
        if (option.get("ordinal"), option.get("profile_identity"), option.get("profile_version")) != (profile.ordinal, profile.identity, profile.version):
            raise ValueError("provider candidate catalogue binding is invalid")
        content_material = dict(option)
        option["option_content_digest"] = canonical_digest(content_material)
        id_material = {"project":view.project_id,"scene_breakdown":view.scene_breakdown_digest,"scene_id":view.scene_id,"scene_digest":view.scene_content_digest,"profile":[profile.identity,profile.version],"context_content":binding["context_content_digest"],"policy":[POLICY_IDENTITY,POLICY_VERSION],"option_content":option["option_content_digest"]}
        option["option_id"] = "option-"+canonical_digest(id_material)[:24]
        options.append(option)
    payload = {"options":options,"stable_order_is_not_ranking":True,"ambiguity":list(view.ambiguity),"assumptions":list(view.assumptions),"unknowns":list(view.unknowns),"conflicts":list(view.conflicts),"limitations":list(view.limitations),"rights_qualification":view.rights_qualification,"cultural_qualification":view.cultural_qualification,"evidence_references":list(view.evidence_references),"semantic_result_digest":"0"*64}
    payload["semantic_result_digest"] = canonical_digest({**payload,"semantic_result_digest":None})
    result = {"schema_version":"1","result_family":"scene_production_option_set","result_version":"1","request_id":binding["request_id"],"correlation_id":binding["correlation_id"],"project_id":view.project_id,"scene_breakdown_identity":"scene_breakdown","scene_breakdown_version":"1","scene_breakdown_digest":view.scene_breakdown_digest,"scene_id":view.scene_id,"scene_content_digest":view.scene_content_digest,"context_identity":binding["context_id"],"context_family":"scene_production_options_context","context_version":"1","context_content_digest":binding["context_content_digest"],"complete_context_digest":binding["complete_context_digest"],"profile_catalogue_identity":CATALOGUE_IDENTITY,"profile_catalogue_version":CATALOGUE_VERSION,"profile_catalogue_digest":ProductionProfileCatalogue.built_in().digest,"policy_identity":POLICY_IDENTITY,"policy_version":POLICY_VERSION,"strategy_identity":STRATEGY_IDENTITY,"strategy_version":STRATEGY_VERSION,"provider_identity":PROVIDER_IDENTITY,"provider_version":PROVIDER_VERSION,"provider_api_version":PROVIDER_API_VERSION,"payload":payload,"integrity":{"payload_sha256":canonical_digest(payload),"complete_result_sha256":"0"*64}}
    result["integrity"]["complete_result_sha256"] = canonical_digest({**result,"integrity":{"payload_sha256":result["integrity"]["payload_sha256"]}})
    return validate_production_option_set(result).to_json_value()

def create_production_option_set_v2(view: SceneProductionOptionsProviderView, binding: dict[str, Any], candidates: tuple[Any, ...] | None = None) -> dict[str, Any]:
    base_view = replace(view, knowledge_bindings=())
    common = create_production_option_set(base_view, {**binding, "context_content_digest": binding["context_content_digest"]}, candidates)
    options = []
    ids = [item["knowledge_id"] for item in view.knowledge_bindings]
    attributes = [item["proposition"]["attribute"] for item in view.knowledge_bindings]
    values = []
    for item in view.knowledge_bindings:
        proposition = item["proposition"]
        supplied = proposition.get("values", (proposition.get("value"),))
        values.extend(thaw_json(supplied))
    for original in common["payload"]["options"]:
        option = dict(original)
        if ids:
            option["knowledge_influence"] = {"mode": "informational_context_only", "knowledge_ids": ids, "knowledge_attributes": attributes, "knowledge_values": values}
        if ids:
            material = dict(option); material.pop("option_id", None); material.pop("option_content_digest", None)
            option["option_content_digest"] = canonical_digest(material)
            option["option_id"] = "option-" + canonical_digest({"base": original["option_id"], "knowledge": ids, "content": option["option_content_digest"]})[:24]
        options.append(option)
    payload = dict(common["payload"]); payload["options"] = options
    payload["semantic_result_digest"] = canonical_digest({**payload, "semantic_result_digest": None})
    lineage = [{key: thaw_json(item[key]) for key in ("knowledge_id", "knowledge_content_digest", "admission_decision_id", "admission_decision_digest", "source_candidate", "use")} for item in view.knowledge_bindings]
    result = dict(common); result.update({"schema_version":"2","result_version":"2","context_version":"2","policy_version":"2","strategy_version":V2_STRATEGY_VERSION,"provider_version":V2_PROVIDER_VERSION,"knowledge_bindings":lineage,"payload":payload})
    result["integrity"] = {"payload_sha256":canonical_digest(payload),"complete_result_sha256":"0"*64}
    result["integrity"]["complete_result_sha256"] = canonical_digest({**result, "integrity":{"payload_sha256":result["integrity"]["payload_sha256"]}})
    from vss_movie_contracts import validate_production_option_set_v2
    return validate_production_option_set_v2(result).to_json_value()

def generate_production_options(context: Any, *, now: str | None = None) -> dict[str, Any]:
    """Compatibility helper; the public command uses the Reasoning Gateway."""
    c = validate_production_options_context(context); value = c.to_json_value()
    if ( _ts(now) if now else datetime.now(timezone.utc)) >= _ts(value["expires_at"]): raise ValueError("production Context expired")
    binding = {"request_id":value["request_id"],"correlation_id":value["correlation_id"],"context_id":value["context_id"],"context_content_digest":value["context_content_digest"],"complete_context_digest":c.digest}
    return create_production_option_set(production_provider_view(c), binding)
