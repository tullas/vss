from jsonschema import Draft202012Validator
import re
from vss_reasoning_contracts.canonicalization import validate_json_value, thaw_json
from .errors import MovieContractError
from .limits import MAX_STORY_BYTES, MAX_RESULT_BYTES
from .models import ValidatedMovieArtifact
from .registry import MovieContractRegistry
from vss_reasoning_contracts import canonical_digest

def _content_digest(value, field):
    material = dict(value)
    material.pop(field, None)
    return canonical_digest(material)

def _require_digest(value, field, label):
    if value[field] != _content_digest(value, field):
        raise MovieContractError(f"{label} content digest mismatch")

def _validate(value, identity, registry, maximum):
    try: validate_json_value(value, maximum_bytes=maximum)
    except Exception as exc: raise MovieContractError("movie artifact is unsafe") from exc
    if not isinstance(value,dict): raise MovieContractError("movie artifact must be an object")
    registry.resolve(identity)
    errors=list(Draft202012Validator(thaw_json(registry.schemas[identity]["schema"])).iter_errors(value))
    if errors: raise MovieContractError("movie artifact does not match its contract")
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
    affirmative_claims = (
        r"\b(?:is|are|was|were)\s+(?:the\s+)?(?:best|recommended|preferred|selected|feasible)\b",
        r"\b(?:cost|duration)\s+(?:is|was)\s+verified\b",
        r"\bquality\s+(?:is|was)\s+guaranteed\b",
        r"\b(?:performers?|locations?|assets?)\s+(?:are|were)\s+available\b",
        r"\b(?:rights?|permits?)\s+(?:are|were)\s+cleared\b",
        r"\b(?:conflicts?|ambiguity)\s+(?:is|are|was|were)\s+resolved\b",
        r"\bartistic intent\s+(?:is|was)\s+(?:understood|known)\b",
    )
    honesty_fields = (
        "qualified_rationale", "source_supported_considerations",
        "rule_derived_considerations", "assumptions", "unknowns", "conflicts",
        "limitations", "external_validation_requirements",
    )
    def strings(node):
        if isinstance(node, str): yield node
        elif isinstance(node, (list, tuple)):
            for child in node: yield from strings(child)
    for option in options:
        material = dict(option); digest = material.pop("option_content_digest"); material.pop("option_id")
        if digest != canonical_digest(material): raise MovieContractError("production option content digest mismatch")
        if not option["unknowns"] or not option["limitations"] or not option["external_validation_requirements"]:
            raise MovieContractError("production option qualifications are incomplete")
        text = " ".join(text for field in honesty_fields for text in strings(option[field])).lower()
        if any(re.search(pattern, text) for pattern in affirmative_claims):
            raise MovieContractError("production option makes a prohibited semantic claim")
    return result

def validate_character_reference(value, registry=None):
    result = _validate(value, "character_reference/1", registry or MovieContractRegistry.built_in(), MAX_STORY_BYTES)
    _require_digest(result.value, "content_digest", "character reference")
    return result

def validate_character_identity(value, references=None, registry=None):
    result = _validate(value, "character_identity/1", registry or MovieContractRegistry.built_in(), MAX_STORY_BYTES)
    _require_digest(result.value, "content_digest", "character identity")
    if result.value["ambiguity"]:
        raise MovieContractError("ambiguous references cannot claim an exact character identity")
    if list(result.value["bound_reference_ids"]) != sorted(result.value["bound_reference_ids"]):
        raise MovieContractError("character identity reference order is not canonical")
    if len(result.value["bound_reference_ids"]) != len(result.value["bound_reference_content_digests"]):
        raise MovieContractError("character identity reference digest binding is incomplete")
    if not references:
        raise MovieContractError("character identity requires independently validated references")
    supplied = {}
    for artifact in references:
        if not isinstance(artifact, ValidatedMovieArtifact) or artifact.value.get("contract_identity") != "character_reference":
            raise MovieContractError("character identity requires independently validated references")
        ref = artifact.value
        if ref["reference_id"] in supplied:
            raise MovieContractError("supplied character reference identity is duplicated")
        supplied[ref["reference_id"]] = ref
    if set(supplied) != set(result.value["bound_reference_ids"]):
        raise MovieContractError("character identity reference set is not exact")
    for reference_id, reference_digest in zip(result.value["bound_reference_ids"], result.value["bound_reference_content_digests"]):
        if supplied[reference_id]["project_id"] != result.value["project_id"]:
            raise MovieContractError("character identity project binding mismatch")
        if supplied[reference_id]["content_digest"] != reference_digest:
            raise MovieContractError("character identity reference content substitution detected")
    return result

def validate_continuity_sequence(value, scene_breakdown=None, registry=None):
    result = _validate(value, "continuity_sequence/1", registry or MovieContractRegistry.built_in(), MAX_RESULT_BYTES)
    _require_digest(result.value, "content_digest", "continuity sequence")
    scenes = result.value["selected_scenes"]
    positions = [scene["continuity_position"] for scene in scenes]
    if positions != list(range(1, len(scenes) + 1)):
        raise MovieContractError("continuity positions must be unique, contiguous, and explicitly ordered")
    if len({scene["scene_id"] for scene in scenes}) != len(scenes):
        raise MovieContractError("continuity sequence contains a duplicate scene")
    if not isinstance(scene_breakdown, ValidatedMovieArtifact) or scene_breakdown.value.get("result_family") != "scene_breakdown":
        raise MovieContractError("continuity sequence requires an independently validated Scene Breakdown")
    breakdown = scene_breakdown
    data = breakdown.value
    if data["project_id"] != result.value["project_id"] or breakdown.digest != result.value["scene_breakdown_digest"]:
        raise MovieContractError("continuity sequence Scene Breakdown binding mismatch")
    admitted = {scene["scene_id"]: scene["scene_content_digest"] for scene in data["payload"]["ordered_scenes"]}
    if any(admitted.get(scene["scene_id"]) != scene["scene_content_digest"] for scene in scenes):
        raise MovieContractError("continuity sequence scene binding mismatch")
    return result

def validate_character_observation(value, character_identity=None, continuity_sequence=None, registry=None):
    result = _validate(value, "character_observation/1", registry or MovieContractRegistry.built_in(), MAX_STORY_BYTES)
    _require_digest(result.value, "observation_content_digest", "character observation")
    data = result.value
    if data["category"] != data["payload"]["kind"]:
        raise MovieContractError("character observation category and payload mismatch")
    if not isinstance(character_identity, ValidatedMovieArtifact) or character_identity.value.get("contract_identity") != "character_identity":
        raise MovieContractError("character observation requires an independently validated character identity")
    if not isinstance(continuity_sequence, ValidatedMovieArtifact) or continuity_sequence.value.get("contract_identity") != "continuity_sequence":
        raise MovieContractError("character observation requires an independently validated continuity sequence")
    identity = character_identity; sequence = continuity_sequence
    if data["character_id"] != identity.value["character_id"] or data["project_id"] != identity.value["project_id"]:
        raise MovieContractError("character observation identity binding mismatch")
    if data["project_id"] != sequence.value["project_id"] or data["continuity_sequence_id"] != sequence.value["continuity_sequence_id"] or data["continuity_sequence_digest"] != sequence.value["content_digest"]:
        raise MovieContractError("character observation sequence binding mismatch")
    scenes = {scene["scene_id"]: scene for scene in sequence.value["selected_scenes"]}
    scene = scenes.get(data["scene_id"])
    if scene is None or scene["scene_content_digest"] != data["scene_content_digest"] or scene["continuity_position"] != data["sequence_position"] or data["scene_breakdown_digest"] != sequence.value["scene_breakdown_digest"]:
        raise MovieContractError("character observation scene binding mismatch")
    return result

def validate_shot_cinematography_observation(value, registry=None):
    result = _validate(value, "shot_cinematography_observation/1", registry or MovieContractRegistry.built_in(), MAX_STORY_BYTES)
    _require_digest(result.value, "observation_content_digest", "shot cinematography observation")
    return result

def validate_character_continuity_task(value, continuity_sequence=None, character_identities=None, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    version = value.get("task_version") if isinstance(value, dict) else None
    if version not in {"1", "2", "3"}:
        raise MovieContractError("unknown character continuity task version")
    task_contract = f"analyze_character_continuity/{version}"
    result = _validate(value, task_contract, registry, MAX_STORY_BYTES)
    registry.resolve_result(task_contract, "character_continuity_observation_set/1")
    _require_digest(result.value, "task_content_digest", "character continuity task")
    order = {name: index for index, name in enumerate(("presence", "possession", "physical_state"))}
    if list(result.value["selected_character_ids"]) != sorted(result.value["selected_character_ids"]) or list(result.value["selected_observation_categories"]) != sorted(result.value["selected_observation_categories"], key=order.__getitem__):
        raise MovieContractError("character continuity task selection order is not canonical")
    if not isinstance(continuity_sequence, ValidatedMovieArtifact) or continuity_sequence.value.get("contract_identity") != "continuity_sequence":
        raise MovieContractError("character continuity task requires an independently validated continuity sequence")
    if not character_identities or any(not isinstance(artifact, ValidatedMovieArtifact) or artifact.value.get("contract_identity") != "character_identity" for artifact in character_identities):
        raise MovieContractError("character continuity task requires independently validated character identities")
    sequence = continuity_sequence
    if result.value["project_id"] != sequence.value["project_id"] or result.value["continuity_sequence_id"] != sequence.value["continuity_sequence_id"] or result.value["continuity_sequence_digest"] != sequence.value["content_digest"] or result.value["bounds"]["maximum_scenes"] < len(sequence.value["selected_scenes"]):
        raise MovieContractError("character continuity task sequence binding mismatch")
    identities = list(character_identities)
    ids = [artifact.value["character_id"] for artifact in identities]
    if len(ids) != len(set(ids)) or set(ids) != set(result.value["selected_character_ids"]) or any(artifact.value["project_id"] != result.value["project_id"] for artifact in identities) or result.value["bounds"]["maximum_characters"] < len(ids):
        raise MovieContractError("character continuity task character binding mismatch")
    return result

def validate_executable_character_continuity_task(value, continuity_sequence=None, character_identities=None, registry=None):
    result = validate_character_continuity_task(value, continuity_sequence, character_identities, registry)
    if result.value["task_version"] not in {"2", "3"} or result.value["lifecycle"] != "active" or result.value["implementation_availability"] != "required":
        raise MovieContractError("character continuity task is not executable")
    return result

def validate_character_continuity_transition_evidence(value, observations=(), continuity_sequence=None, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "character_continuity_transition_evidence/1", registry, MAX_STORY_BYTES)
    _require_digest(result.value, "content_digest", "character continuity transition evidence")
    data = result.value
    if not isinstance(continuity_sequence, ValidatedMovieArtifact) or continuity_sequence.value.get("contract_identity") != "continuity_sequence":
        raise MovieContractError("transition evidence requires an independently validated continuity sequence")
    sequence = continuity_sequence.value
    if (data["project_id"], data["continuity_sequence_id"], data["continuity_sequence_digest"]) != (sequence["project_id"], sequence["continuity_sequence_id"], sequence["content_digest"]):
        raise MovieContractError("transition evidence sequence binding mismatch")
    supplied = {}
    for artifact in observations:
        if not isinstance(artifact, ValidatedMovieArtifact) or artifact.value.get("contract_identity") != "character_observation":
            raise MovieContractError("transition evidence requires independently validated observations")
        if artifact.value["observation_id"] in supplied:
            raise MovieContractError("transition evidence observation identity is duplicated")
        supplied[artifact.value["observation_id"]] = artifact.value
    first = supplied.get(data["from_observation_id"]); second = supplied.get(data["to_observation_id"])
    if first is None or second is None or first is second:
        raise MovieContractError("transition evidence observation is unresolved")
    if (data["from_observation_digest"], data["to_observation_digest"]) != (first["observation_content_digest"], second["observation_content_digest"]):
        raise MovieContractError("transition evidence observation digest mismatch")
    if any(item["character_id"] != data["character_id"] or item["category"] != data["category"] for item in (first, second)):
        raise MovieContractError("transition evidence character or category binding mismatch")
    if (data["from_sequence_position"], data["to_sequence_position"]) != (first["sequence_position"], second["sequence_position"]) or data["from_sequence_position"] >= data["to_sequence_position"]:
        raise MovieContractError("transition evidence chronology binding mismatch")
    return result

def validate_character_continuity_observation_set(value, observations=(), continuity_sequence=None, task=None, registry=None, transition_evidence=()):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "character_continuity_observation_set/1", registry, MAX_RESULT_BYTES)
    data = result.value
    payload = data["payload"]
    order = {name: index for index, name in enumerate(("presence", "possession", "physical_state"))}
    if list(data["selected_character_ids"]) != sorted(data["selected_character_ids"]) or list(data["selected_observation_categories"]) != sorted(data["selected_observation_categories"], key=order.__getitem__):
        raise MovieContractError("continuity result selection order is not canonical")
    if data["integrity"]["payload_sha256"] != canonical_digest(payload):
        raise MovieContractError("continuity result payload digest mismatch")
    if payload["semantic_result_digest"] != canonical_digest({**payload, "semantic_result_digest": None}):
        raise MovieContractError("continuity semantic result digest mismatch")
    if data["integrity"]["complete_result_sha256"] != canonical_digest({**data, "integrity": {"payload_sha256": data["integrity"]["payload_sha256"]}}):
        raise MovieContractError("continuity complete result digest mismatch")
    bindings = payload["observations"]
    if len({item["observation_id"] for item in bindings}) != len(bindings):
        raise MovieContractError("continuity result observation identity is duplicated")
    canonical_bindings = sorted(bindings, key=lambda item: (item["sequence_position"], item["character_id"], order[item["category"]], item["observation_id"]))
    if list(bindings) != canonical_bindings:
        raise MovieContractError("continuity result observation order is not canonical")
    if list(payload["explicit_transitions"]) != sorted(payload["explicit_transitions"], key=lambda item: item["transition_id"]) or list(payload["contradictions"]) != sorted(payload["contradictions"], key=lambda item: item["contradiction_id"]):
        raise MovieContractError("continuity structural record order is not canonical")
    supplied = {}
    for artifact in observations:
        if not isinstance(artifact, ValidatedMovieArtifact) or artifact.value.get("contract_identity") != "character_observation":
            raise MovieContractError("continuity result requires independently validated observations")
        observation = artifact
        if observation.value["observation_id"] in supplied:
            raise MovieContractError("supplied character observation identity is duplicated")
        supplied[observation.value["observation_id"]] = observation
    if bindings and not supplied:
        raise MovieContractError("continuity result observations require independently validated artifacts")
    if set(supplied) != {item["observation_id"] for item in bindings}:
        raise MovieContractError("continuity result observation set is not exact")
    selected_characters = set(data["selected_character_ids"])
    selected_categories = set(data["selected_observation_categories"])
    for binding in bindings:
        observation = supplied.get(binding["observation_id"])
        if observation is None or binding["observation_content_digest"] != observation.value["observation_content_digest"]:
            raise MovieContractError("continuity result observation resolution failed")
        item = observation.value
        if item["character_id"] not in selected_characters or item["category"] not in selected_categories or item["project_id"] != data["project_id"] or item["continuity_sequence_id"] != data["continuity_sequence_id"] or item["continuity_sequence_digest"] != data["continuity_sequence_digest"]:
            raise MovieContractError("continuity result observation binding mismatch")
        for field in ("character_id", "scene_id", "scene_content_digest", "sequence_position", "category"):
            if binding[field] != item[field]: raise MovieContractError("continuity result observation substitution detected")
    for field in ("character_id", "scene_id"):
        counts = {}
        for item in bindings: counts[item[field]] = counts.get(item[field], 0) + 1
        if any(count > 32 for count in counts.values()):
            raise MovieContractError("continuity result per-identity observation bound exceeded")
    if not isinstance(continuity_sequence, ValidatedMovieArtifact) or continuity_sequence.value.get("contract_identity") != "continuity_sequence":
        raise MovieContractError("continuity result requires an independently validated continuity sequence")
    if not isinstance(task, ValidatedMovieArtifact) or task.value.get("task_identity") != "analyze_character_continuity":
        raise MovieContractError("continuity result requires an independently validated task")
    registry.resolve_result(f"analyze_character_continuity/{task.value.get('task_version')}", "character_continuity_observation_set/1")
    sequence = continuity_sequence; admitted_task = task
    if data["continuity_sequence_id"] != sequence.value["continuity_sequence_id"] or data["continuity_sequence_digest"] != sequence.value["content_digest"] or data["project_id"] != sequence.value["project_id"]:
        raise MovieContractError("continuity result sequence binding mismatch")
    for field in ("request_id", "correlation_id", "project_id", "continuity_sequence_id", "continuity_sequence_digest", "selected_character_ids", "selected_observation_categories"):
        if data[field] != admitted_task.value[field]:
            raise MovieContractError("continuity result task binding mismatch")
    if len(bindings) > admitted_task.value["bounds"]["maximum_observations"]:
        raise MovieContractError("continuity result task observation bound exceeded")
    by_id = {item["observation_id"]: supplied[item["observation_id"]] for item in bindings}
    for transition in payload["explicit_transitions"]:
        material = dict(transition); digest = material.pop("transition_content_digest")
        if digest != canonical_digest(material): raise MovieContractError("continuity transition digest mismatch")
        first = by_id.get(transition["from_observation_id"]); second = by_id.get(transition["to_observation_id"])
        if first is None or second is None or first is second or transition["from_observation_digest"] != first.value["observation_content_digest"] or transition["to_observation_digest"] != second.value["observation_content_digest"] or first.value["character_id"] != transition["character_id"] or second.value["character_id"] != transition["character_id"] or first.value["category"] != transition["category"] or second.value["category"] != transition["category"] or first.value["sequence_position"] >= second.value["sequence_position"]:
            raise MovieContractError("continuity transition binding is invalid")
    if admitted_task.value["task_version"] == "3":
        transition_ids = [item["transition_id"] for item in payload["explicit_transitions"]]
        contradiction_ids = [item["contradiction_id"] for item in payload["contradictions"]]
        if len(transition_ids) != len(set(transition_ids)) or len(contradiction_ids) != len(set(contradiction_ids)):
            raise MovieContractError("continuity analysis structural identity is duplicated")
        evidence = {}
        for artifact in transition_evidence:
            validated = validate_character_continuity_transition_evidence(artifact.to_json_value() if isinstance(artifact, ValidatedMovieArtifact) else artifact, observations, continuity_sequence, registry)
            if validated.value["transition_evidence_id"] in evidence:
                raise MovieContractError("transition evidence identity is duplicated")
            evidence[validated.value["transition_evidence_id"]] = validated.value
        if len(evidence) != len(payload["explicit_transitions"]):
            raise MovieContractError("continuity result transition evidence set is not exact")
        for transition in payload["explicit_transitions"]:
            source_id = transition["transition_id"].removeprefix("continuity-transition-")
            source = evidence.get("continuity-transition-evidence-" + source_id)
            if source is None or any(transition[field] != source[source_field] for field, source_field in (("character_id","character_id"),("category","category"),("from_observation_id","from_observation_id"),("from_observation_digest","from_observation_digest"),("to_observation_id","to_observation_id"),("to_observation_digest","to_observation_digest"))):
                raise MovieContractError("continuity result transition evidence binding is invalid")
            required_provenance = {source["transition_evidence_id"], "sha256:" + source["content_digest"]}
            if not required_provenance.issubset(transition["evidence_references"]):
                raise MovieContractError("continuity result transition provenance binding is incomplete")
            if transition["qualification"] != "Independently validated explicit transition evidence; rule explicit_transition/1.1.0 does not infer persistence or causality." or thaw_json(transition["confidence"]) != {"level":"low", "basis":"Exact independently validated transition-evidence binding.", "qualifications":["Qualification establishes neither truth, persistence, causality, severity, nor authority."]} or thaw_json(transition["limitations"]) != ["Only the explicit endpoints are qualified; intervening state and causality remain unknown."]:
                raise MovieContractError("continuity result transition qualification is invalid")
    for contradiction in payload["contradictions"]:
        material = dict(contradiction); digest = material.pop("contradiction_content_digest")
        if digest != canonical_digest(material): raise MovieContractError("continuity contradiction digest mismatch")
        refs = contradiction["observation_bindings"]
        if refs[0]["observation_id"] == refs[1]["observation_id"]: raise MovieContractError("continuity contradiction observations must be distinct")
        resolved = [by_id.get(ref["observation_id"]) for ref in refs]
        if any(item is None for item in resolved): raise MovieContractError("continuity contradiction observation is unknown")
        for ref, item in zip(refs, resolved):
            if ref["observation_digest"] != item.value["observation_content_digest"] or item.value["character_id"] != contradiction["character_id"] or item.value["category"] != contradiction["category"]:
                raise MovieContractError("continuity contradiction binding is invalid")
    if bool(payload["contradictions"]) and not payload["review_suggested"]:
        raise MovieContractError("unresolved contradictions require semantic review suggestion")
    if admitted_task.value["task_version"] == "3" and payload["contradictions"]:
        raise MovieContractError("catalogue 1.1.0 admits no contradiction output")
    if admitted_task.value["task_version"] == "3" and payload["review_suggested"]:
        raise MovieContractError("catalogue 1.1.0 has no review-suggested condition")
    return result
