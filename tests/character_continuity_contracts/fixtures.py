from copy import deepcopy

from vss_reasoning_contracts import canonical_digest


def seal(value, field):
    value[field] = canonical_digest({key: item for key, item in value.items() if key != field})
    return value


def story_digest():
    return "1" * 64


def reference(reference_id="character-ref-arin", display_label="Arin"):
    return seal({
        "schema_version":"1", "contract_identity":"character_reference", "contract_version":"1",
        "reference_id":reference_id, "project_id":"continuity-local", "display_label":display_label,
        "source_binding":{"identity":"story_fragment","version":"1","digest":story_digest(),"source_sequence":1},
        "declaration_evidence":["continuity-fragment-001:character-arin"],
        "qualification":"Explicit fictional source declaration; the label is presentation only.",
        "content_digest":""
    }, "content_digest")


def identity(reference_values=None):
    reference_values = list(reference_values or (reference(),))
    return seal({
        "schema_version":"1", "contract_identity":"character_identity", "contract_version":"1",
        "character_id":"character-arin", "project_id":"continuity-local",
        "bound_reference_ids":[item["reference_id"] for item in reference_values],
        "bound_reference_content_digests":[item["content_digest"] for item in reference_values], "identity_basis":"explicit_source_identity",
        "ambiguity":[], "evidence_references":["continuity-fragment-001:character-arin"],
        "qualification":"Exact governed binding; no alias or name inference was used.", "content_digest":""
    }, "content_digest")


def scene_breakdown():
    scenes=[]
    facts=(
        ("scene-continuity-001", "Arin explicitly carries a lantern.", "dawn"),
        ("scene-continuity-002", "Arin enters; the lantern is not mentioned.", "later"),
        ("scene-continuity-003", "Arin is explicitly injured after a fall.", "night"),
    )
    for ordinal,(scene_id,text,time) in enumerate(facts,1):
        scene={
            "assumptions":[], "boundary_basis":"explicit_sequence_marker", "boundary_confidence":"high",
            "boundary_rule":"explicit_sequence_marker/1", "conflicts":[], "declared_characters":["arin"],
            "declared_locations":[], "events":[{"category":"source_observed","text":text}],
            "evidence_references":["continuity-fragment-001"],
            "limitations":["Structured fictional fixture evidence only."], "ordinal":ordinal,
            "scene_id":scene_id, "source_observations":[{"category":"source_observed","text":text}],
            "source_span":{"start":ordinal*100,"end":ordinal*100+50}, "time_indicators":[time],
            "unknowns":[], "source_binding":"continuity-fragment-001", "ambiguous_boundary":False,
        }
        scene["scene_content_digest"]=canonical_digest(scene)
        scenes.append(scene)
    payload={"assumptions":[],"confidence":"high","conflicts":[],"evidence_references":["continuity-fragment-001"],"limitations":["Fictional deterministic fixture only."],"ordered_scenes":scenes,"unknowns":["No facts beyond the explicit structured fixture are established."]}
    return {"schema_version":"1","result_family":"scene_breakdown","result_version":"1","project_id":"continuity-local","source_bindings":["continuity-fragment-001"],"payload":payload,"integrity":{"payload_sha256":canonical_digest(payload)}}


def sequence(breakdown_artifact):
    scenes=breakdown_artifact.value["payload"]["ordered_scenes"]
    return seal({
        "schema_version":"1","contract_identity":"continuity_sequence","contract_version":"1",
        "continuity_sequence_id":"continuity-sequence-primary","project_id":"continuity-local",
        "sequence_kind":"explicit_linear","scene_breakdown_identity":"scene_breakdown","scene_breakdown_version":"1",
        "scene_breakdown_digest":breakdown_artifact.digest,
        "selected_scenes":[{"scene_id":scene["scene_id"],"scene_content_digest":scene["scene_content_digest"],"continuity_position":position} for position,scene in enumerate(scenes,1)],
        "qualification":"Explicit fixture chronology; Scene Breakdown ordinals were not used as chronology.",
        "unknowns":[],"limitations":["Only this declared linear continuity scope is represented."],"content_digest":""
    }, "content_digest")


def observation(sequence_value, category="presence", ordinal=1):
    scene=sequence_value["selected_scenes"][ordinal-1]
    payloads={
        "presence":{"kind":"presence","state":"present"},
        "possession":{"kind":"possession","object_reference":"lantern","state":"possesses"},
        "physical_state":{"kind":"physical_state","state":"injured"},
    }
    return seal({
        "schema_version":"1","contract_identity":"character_observation","contract_version":"1",
        "observation_id":f"character-observation-{category}-{ordinal}","project_id":"continuity-local","character_id":"character-arin",
        "scene_breakdown_digest":sequence_value["scene_breakdown_digest"],"scene_id":scene["scene_id"],"scene_content_digest":scene["scene_content_digest"],
        "continuity_sequence_id":sequence_value["continuity_sequence_id"],"continuity_sequence_digest":sequence_value["content_digest"],"sequence_position":ordinal,
        "category":category,"payload":payloads[category],"provenance_category":"source_observed",
        "evidence_references":[f"continuity-fragment-001:{scene['scene_id']}"],
        "confidence":{"level":"high","basis":"Explicit structured fictional fixture claim.","qualifications":["Traceability does not establish truth."]},
        "assumptions":[],"unknowns":[],"limitations":["No persistence or contradiction inference is performed."],"observation_content_digest":""
    }, "observation_content_digest")


def task(sequence_value):
    return seal({
        "schema_version":"1","task_identity":"analyze_character_continuity","task_version":"1",
        "request_id":"continuity-request-001","correlation_id":"continuity-correlation-001","project_id":"continuity-local",
        "environment":"development","purpose":"character_continuity_local_validation",
        "expected_context_family":"character_continuity_context","expected_context_version":"1",
        "expected_result_family":"character_continuity_observation_set","expected_result_version":"1",
        "continuity_sequence_id":sequence_value["continuity_sequence_id"],"continuity_sequence_digest":sequence_value["content_digest"],
        "selected_character_ids":["character-arin"],"selected_observation_categories":["presence","possession","physical_state"],
        "bounds":{"maximum_scenes":8,"maximum_characters":8,"maximum_observations":128,"maximum_result_bytes":65536},
        "lifecycle":"defined_validation_only","implementation_availability":"not_implemented","task_content_digest":""
    }, "task_content_digest")


def result(sequence_value, observations):
    bindings=[{key:item[key] for key in ("observation_id","observation_content_digest","character_id","scene_id","scene_content_digest","sequence_position","category")} for item in observations]
    payload={"observations":bindings,"explicit_transitions":[],"contradictions":[],"unknowns":["No continuity analysis or persistence inference exists in M5.1."],"evidence_references":["continuity-fragment-001"],"confidence":{"level":"low","basis":"Validation-only fixture; no analysis was performed.","qualifications":["Confidence grants no authority."]},"limitations":["This result demonstrates contract validation only."],"review_suggested":False,"semantic_result_digest":None}
    payload["semantic_result_digest"]=canonical_digest(payload)
    value={"schema_version":"1","result_family":"character_continuity_observation_set","result_version":"1","request_id":"continuity-request-001","correlation_id":"continuity-correlation-001","project_id":"continuity-local","continuity_sequence_id":sequence_value["continuity_sequence_id"],"continuity_sequence_digest":sequence_value["content_digest"],"selected_character_ids":["character-arin"],"selected_observation_categories":["presence","possession","physical_state"],"payload":payload,"integrity":{"payload_sha256":canonical_digest(payload)}}
    value["integrity"]["complete_result_sha256"]=canonical_digest(value)
    return value


def copied(value):
    return deepcopy(value)
