from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from vss_reasoning_contracts import canonical_digest, canonical_bytes
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_movie_contracts import MovieContractRegistry, validate_scene_breakdown

POLICY="scene_production_options_context_local/1"; CATALOGUE="vss.scene-production-profiles.deterministic/1.0.0"
PROFILES=("minimal_stage","location_live_action","stylized_2d","stylized_3d")
@dataclass(frozen=True,slots=True)
class ProductionProfile:
    identity:str; version:str; approach:str; complexity:str; limitations:tuple
class ProductionProfileCatalogue:
    identity=CATALOGUE; version="1.0.0"
    def __init__(self): self.profiles=tuple(ProductionProfile(p,"1.0.0",p,"qualified",("Feasibility, cost, duration, quality, and availability are unknown.",)) for p in PROFILES)
    @classmethod
    def built_in(cls): return cls()
    @property
    def digest(self): return canonical_digest([{"identity":p.identity,"version":p.version,"approach":p.approach,"complexity":p.complexity,"limitations":list(p.limitations)} for p in self.profiles])
@dataclass(frozen=True,slots=True,init=False)
class SceneProductionOptionsContext:
    value:object; digest:str
    @classmethod
    def create(cls,value):
        obj=object.__new__(cls); frozen=freeze_json(value); object.__setattr__(obj,"value",frozen); object.__setattr__(obj,"digest",canonical_digest(frozen)); return obj
    def to_json_value(self): return thaw_json(self.value)
def _ts(v): return datetime.strptime(v,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
def _iso(v): return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def validate_production_options_context(value):
    if isinstance(value, SceneProductionOptionsContext): value=value.value
    value=thaw_json(value) if hasattr(value,"keys") else value
    required={"schema_version","context_id","context_family","context_family_version","request_id","correlation_id","semantic_task","semantic_task_version","purpose","environment","project_id","classification","policy_identity","policy_version","constructed_at","expires_at","lifecycle","context_content_digest","integrity","payload"}
    if not isinstance(value,dict) or set(value)!=required: raise ValueError("production Context is invalid")
    if value["context_family"]!="scene_production_options_context" or value["semantic_task"]!="generate_scene_production_options" or value["purpose"]!="scene_production_options_local_validation" or value["lifecycle"]!="validated": raise ValueError("production Context compatibility is invalid")
    if _ts(value["constructed_at"])>=_ts(value["expires_at"]): raise ValueError("production Context expiry is invalid")
    if canonical_digest(value["payload"])!=value["context_content_digest"]: raise ValueError("production Context digest mismatch")
    material=dict(value); integ=dict(material["integrity"]); expected=integ.pop("complete_context_sha256"); material["integrity"]=integ
    if expected!=canonical_digest(material): raise ValueError("production Context integrity mismatch")
    return SceneProductionOptionsContext.create(value)
def assemble_production_options_context(scene_breakdown, *, request_id, correlation_id, project_id, scene_id, scene_content_digest, environment="development", validation_time=None):
    result=validate_scene_breakdown(scene_breakdown,MovieContractRegistry.built_in()); value=thaw_json(result.value)
    if value["project_id"]!=project_id: raise ValueError("project mismatch")
    matches=[s for s in value["payload"]["ordered_scenes"] if s["scene_id"]==scene_id and s["scene_content_digest"]==scene_content_digest]
    if len(matches)!=1: raise ValueError("exact scene selection failed")
    scene=matches[0]; now=_ts(validation_time) if validation_time else datetime.now(timezone.utc).replace(microsecond=0); expiry=now+timedelta(seconds=300)
    payload={"scene_breakdown_digest":result.digest,"scene_id":scene_id,"scene_content_digest":scene_content_digest,"scene":scene,"profile_catalogue":CATALOGUE,"option_limit":len(PROFILES),"limitations":["Options are alternatives, not recommendations or plans."],"unknowns":["Feasibility, cost, duration, quality, rights, permits, performers, and assets are unknown."],"conflicts":scene["conflicts"],"evidence_references":scene["evidence_references"]}
    content=canonical_digest(payload); context={"schema_version":"1","context_id":"production-context-"+content[:32],"context_family":"scene_production_options_context","context_family_version":"1","request_id":request_id,"correlation_id":correlation_id,"semantic_task":"generate_scene_production_options","semantic_task_version":"1","purpose":"scene_production_options_local_validation","environment":environment,"project_id":project_id,"classification":"public","policy_identity":POLICY,"policy_version":"1","constructed_at":_iso(now),"expires_at":_iso(expiry),"lifecycle":"validated","context_content_digest":content,"integrity":{"complete_context_sha256":"0"*64},"payload":payload}
    context["integrity"]["complete_context_sha256"]=canonical_digest({**context,"integrity":{}}); return validate_production_options_context(context)
def production_provider_view(context):
    c=thaw_json(validate_production_options_context(context.value if isinstance(context,SceneProductionOptionsContext) else context).value); p=c["payload"]; material={"project_id":c["project_id"],"scene_breakdown_digest":p["scene_breakdown_digest"],"scene_id":p["scene_id"],"scene_content_digest":p["scene_content_digest"],"scene":p["scene"],"profile_catalogue":p["profile_catalogue"],"option_limit":p["option_limit"],"limitations":p["limitations"],"unknowns":p["unknowns"],"conflicts":p["conflicts"],"evidence_references":p["evidence_references"]}; return freeze_json({**material,"provider_visible_digest":canonical_digest(material)})
def generate_production_options(context, *, now=None):
    c=validate_production_options_context(context); v=production_provider_view(c); now=_ts(now) if now else datetime.now(timezone.utc)
    if now>=_ts(v["constructed_at"] if "constructed_at" in v else thaw_json(c.value)["expires_at"]): pass
    catalogue=ProductionProfileCatalogue.built_in(); options=[]
    for i,p in enumerate(catalogue.profiles,1):
        material={"project_id":v["project_id"],"scene_breakdown_digest":v["scene_breakdown_digest"],"scene_id":v["scene_id"],"scene_content_digest":v["scene_content_digest"],"profile_identity":p.identity,"profile_version":p.version,"catalogue":catalogue.identity}
        options.append({"option_id":"option-"+canonical_digest(material)[:24],"ordinal":i,"profile_identity":p.identity,"profile_version":p.version,"approach":p.approach,"rationale":"A bounded alternative requiring external validation; not a recommendation.","unknowns":list(p.limitations),"limitations":["No feasibility, cost, duration, quality, rights, or availability was verified."],"evidence_references":list(v["evidence_references"]),"confidence":"low","option_content_digest":canonical_digest(material)})
    payload={"scene_breakdown_digest":v["scene_breakdown_digest"],"scene_id":v["scene_id"],"scene_content_digest":v["scene_content_digest"],"profile_catalogue":catalogue.identity,"profile_catalogue_digest":catalogue.digest,"options":options,"confidence":"low","limitations":["Stable catalogue order is not ranking.","Options are inert alternatives, not plans or recommendations."],"unknowns":v["unknowns"],"conflicts":v["conflicts"],"evidence_references":v["evidence_references"]}
    return {"schema_version":"1","result_family":"scene_production_option_set","result_version":"1","project_id":v["project_id"],"payload":payload,"integrity":{"payload_sha256":canonical_digest(payload)}}
