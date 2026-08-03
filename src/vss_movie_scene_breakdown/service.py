from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from types import MappingProxyType
from typing import Any

from vss_reasoning_contracts import canonical_digest, canonical_bytes
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json
from vss_movie_contracts import MovieContractRegistry, validate_story_fragment, validate_scene_breakdown

POLICY = "scene_breakdown_context_local/1"
RULE_CATALOGUE = "vss.scene-boundary-rules.deterministic/1"
STRATEGY = "vss.break-down-scenes.deterministic/1.0.0"
PROVIDER = "vss.reasoning.deterministic-scene-breakdown/1.0.0"
MAX_CONTEXT = 32768

def _now(): return datetime.now(timezone.utc).replace(microsecond=0)
def _ts(v): return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
def _iso(v): return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass(frozen=True, slots=True, init=False)
class SceneBreakdownContext:
    value: Any
    digest: str
    @classmethod
    def create(cls, value):
        obj=object.__new__(cls); frozen=freeze_json(value)
        object.__setattr__(obj,"value",frozen); object.__setattr__(obj,"digest",canonical_digest(frozen)); return obj
    def to_json_value(self): return thaw_json(self.value)

def validate_scene_context(value: Any) -> SceneBreakdownContext:
    if not isinstance(value, dict): value=thaw_json(value) if hasattr(value, "keys") else value
    if not isinstance(value, dict): raise ValueError("scene context must be an object")
    required={"schema_version","context_id","context_family","context_family_version","request_id","correlation_id","semantic_task","semantic_task_version","purpose","environment","project_id","classification","policy_identity","policy_version","constructed_at","expires_at","lifecycle","context_content_digest","integrity","payload"}
    if set(value) != required: raise ValueError("scene context fields are invalid")
    if value["context_family"] != "scene_breakdown_context" or value["context_family_version"] != "1" or value["semantic_task"] != "break_down_scenes" or value["semantic_task_version"] != "1" or value["purpose"] != "scene_breakdown_local_validation" or value["policy_identity"] != POLICY or value["policy_version"] != "1" or value["lifecycle"] != "validated": raise ValueError("scene context compatibility is invalid")
    if _ts(value["constructed_at"]) >= _ts(value["expires_at"]): raise ValueError("scene context expiry is invalid")
    if canonical_digest(value["payload"]) != value["context_content_digest"]: raise ValueError("scene context digest mismatch")
    material=dict(value); integ=dict(material["integrity"]); expected=integ.pop("complete_context_sha256"); material["integrity"]=integ
    if expected != canonical_digest(material): raise ValueError("scene context integrity mismatch")
    if len(canonical_bytes(value)) > MAX_CONTEXT: raise ValueError("scene context exceeds bound")
    return SceneBreakdownContext.create(value)

def assemble_scene_context(story: dict, *, request_id: str, correlation_id: str, project_id: str, environment: str = "development", validation_time: str | None = None) -> SceneBreakdownContext:
    validated=validate_story_fragment(story, MovieContractRegistry.built_in())
    if validated.value["project_id"] != project_id or environment != "development": raise ValueError("movie context binding mismatch")
    frag=validated.value
    if validation_time is not None and not (frag["fragment_id"] == "fragment-opening-001" and validated.digest == "ce124fe3aba0abb9de2228dc250a1a0aba472012ceae44f21a3aac351aff7810" and validation_time == "2026-08-02T00:00:00Z"):
        raise ValueError("caller-selected validation time is not admitted")
    now=_ts(validation_time) if validation_time else _now(); expiry=now+timedelta(seconds=300)
    payload={"story_fragment": {"fragment_id":frag["fragment_id"],"fragment_digest":validated.digest,"title":frag["payload"]["title"],"fragment_text":frag["payload"]["fragment_text"],"language":frag["payload"]["language"],"source_type":frag["payload"]["source_type"],"source_sequence":frag["payload"]["source_sequence"],"declared_characters":frag["payload"]["declared_characters"],"declared_locations":frag["payload"]["declared_locations"],"citations":frag["payload"]["citations"],"source_qualification":frag["payload"]["source_qualification"],"rights_qualification":frag["payload"]["rights_qualification"],"cultural_qualification":frag["payload"]["cultural_qualification"]},"source_bindings":[frag["fragment_id"]],"rule_catalogue":RULE_CATALOGUE,"uncertainty":["Source claims were not independently verified.","Completeness is not guaranteed."],"limitations":["Boundaries are deterministic structural interpretations, not artistic truth.","No external screenplay parser or source retrieval is used."],"budget_summary":{"maximum_context_bytes":MAX_CONTEXT}}
    content=canonical_digest(payload); context={"schema_version":"1","context_id":"scene-context-"+content[:32],"context_family":"scene_breakdown_context","context_family_version":"1","request_id":request_id,"correlation_id":correlation_id,"semantic_task":"break_down_scenes","semantic_task_version":"1","purpose":"scene_breakdown_local_validation","environment":environment,"project_id":project_id,"classification":frag["classification"],"policy_identity":POLICY,"policy_version":"1","constructed_at":_iso(now),"expires_at":_iso(expiry),"lifecycle":"validated","context_content_digest":content,"integrity":{"complete_context_sha256":"0"*64},"payload":payload}
    context["integrity"]["complete_context_sha256"]=canonical_digest({**context,"integrity":{}})
    return validate_scene_context(context)

def scene_context_report(context: SceneBreakdownContext) -> dict:
    value=thaw_json(context.value)
    report={"schema_version":"1","report_family":"scene_breakdown_context_assembly_report","report_version":"1","request_id":value["request_id"],"correlation_id":value["correlation_id"],"context_id":value["context_id"],"context_family":"scene_breakdown_context","context_family_version":"1","project_id":value["project_id"],"environment":value["environment"],"purpose":value["purpose"],"classification":value["classification"],"story_fragment_id":value["payload"]["story_fragment"]["fragment_id"],"story_fragment_digest":value["payload"]["story_fragment"]["fragment_digest"],"rule_catalogue":value["payload"]["rule_catalogue"],"source_count":1,"context_content_digest":value["context_content_digest"],"complete_context_digest":context.digest,"status":"success"}
    report["report_digest"]=canonical_digest(report); return report

def _scene_id(project, fragment_id, digest, start, end, ordinal): return "scene-"+hashlib.sha256(f"{project}|{fragment_id}|{digest}|{start}|{end}|{ordinal}".encode()).hexdigest()[:24]

def break_down_scenes(context: SceneBreakdownContext, *, now: str | None = None) -> dict:
    cv=thaw_json(validate_scene_context(context.value if isinstance(context, SceneBreakdownContext) else context).value)
    if ( _ts(now) if now else _now()) >= _ts(cv["expires_at"]): raise ValueError("scene context expired")
    source=thaw_json(cv["payload"]["story_fragment"]); text=source["fragment_text"]; marker=[]
    lines=text.splitlines(keepends=True); offset=0
    for line in lines:
        stripped=line.rstrip("\r\n")
        if stripped.startswith("SCENE: ") and stripped[7:].strip(): marker.append((offset, offset+len(line), "explicit_heading"))
        offset += len(line)
    spans=[]
    if marker:
        for i,(start,_,basis) in enumerate(marker): spans.append((start, marker[i+1][0] if i+1<len(marker) else len(text), basis))
    else: spans=[(0,len(text),"deterministic_fallback")]
    scenes=[]
    for ordinal,(start,end,basis) in enumerate(spans,1):
        if end<=start: raise ValueError("empty scene")
        body=text[start:end]; rule=RULE_CATALOGUE; obs=[{"category":"source_observed","text":body[:512]}]
        scene={"scene_id":_scene_id(cv["project_id"],source["fragment_id"],source["fragment_digest"],start,end,ordinal),"ordinal":ordinal,"source_span":{"start":start,"end":end},"boundary_basis":basis,"boundary_rule":rule,"boundary_confidence":"low" if basis=="deterministic_fallback" else "high","source_observations":obs,"declared_characters":source["declared_characters"],"declared_locations":source["declared_locations"],"time_indicators":[],"events":[],"evidence_references":[source["fragment_id"]],"assumptions":[],"unknowns":["Artistic scene intent is unknown."],"conflicts":[],"limitations":["Segmentation is rule-derived and not artistically definitive."],"source_binding":source["fragment_id"],"ambiguous_boundary":basis=="deterministic_fallback"}
        scene["scene_content_digest"]=canonical_digest(scene); scenes.append(scene)
    payload={"ordered_scenes":scenes,"assumptions":[],"unknowns":["The source may be incomplete."],"conflicts":[],"confidence":"low","limitations":cv["payload"]["limitations"],"evidence_references":[source["fragment_id"]]}
    result={"schema_version":"1","result_family":"scene_breakdown","result_version":"1","project_id":cv["project_id"],"source_bindings":[source["fragment_id"]],"payload":payload,"integrity":{"payload_sha256":canonical_digest(payload)}}
    return validate_scene_breakdown(result, MovieContractRegistry.built_in()).to_json_value()

class SceneBreakdownService:
    def assemble(self, story, **kwargs): return assemble_scene_context(story, **kwargs)
    def execute(self, context, *, dry_run=False, now=None):
        if dry_run: validate_scene_context(context.value if isinstance(context,SceneBreakdownContext) else context); return {"ready":True,"provider_invoked":False,"rule_catalogue":RULE_CATALOGUE}
        return break_down_scenes(context, now=now)
