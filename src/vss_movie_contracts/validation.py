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
    errors=list(registry.iter_errors(identity, value))
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

def validate_production_options_task_v2(value, registry=None):
    result = _validate(value, "generate_scene_production_options/2", registry or MovieContractRegistry.built_in(), MAX_STORY_BYTES)
    task = result.value
    if task["expected_context_family"] != "scene_production_options_context" or task["expected_context_version"] != "2" or task["expected_result_family"] != "scene_production_option_set" or task["expected_result_version"] != "2":
        raise MovieContractError("production v2 task compatibility is invalid")
    if task["purpose"] != "scene_production_options_local_analysis" or task["environment"] != "development":
        raise MovieContractError("production v2 task policy is invalid")
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
    data = thaw_json(result.value)
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

def validate_production_option_set_v2(value, *, context=None, registry=None):
    result = _validate(value, "scene_production_option_set/2", registry or MovieContractRegistry.built_in(), MAX_RESULT_BYTES)
    data = thaw_json(result.value)
    # Verify every v2 seal over the supplied representation before projecting
    # any common fields into the v1 validator.  v2-only influence/lineage data
    # is part of the semantic result and cannot be stripped before checking.
    if data["integrity"]["payload_sha256"] != canonical_digest(data["payload"]):
        raise MovieContractError("production v2 payload digest mismatch")
    if data["payload"]["semantic_result_digest"] != canonical_digest({**data["payload"], "semantic_result_digest": None}):
        raise MovieContractError("production v2 semantic result digest mismatch")
    for option in data["payload"]["options"]:
        material = dict(option)
        supplied = material.pop("option_content_digest")
        material.pop("option_id", None)
        if supplied != canonical_digest(material):
            raise MovieContractError("production v2 option content digest mismatch")
    if data["integrity"]["complete_result_sha256"] != canonical_digest({**data, "integrity": {"payload_sha256": data["integrity"]["payload_sha256"]}}):
        raise MovieContractError("production v2 complete result digest mismatch")
    if data.get("strategy_identity") != "vss.generate-scene-production-options.deterministic" or data.get("strategy_version") != "1.0.0" or data.get("provider_identity") != "vss.reasoning.deterministic-scene-production-options" or data.get("provider_version") != "1.0.0":
        raise MovieContractError("production v2 implementation identity is invalid")
    if context is not None:
        c = context.to_json_value() if hasattr(context, "to_json_value") else context
        if data["context_content_digest"] != c["context_content_digest"] or data["complete_context_digest"] != canonical_digest(c):
            raise MovieContractError("production v2 Context binding is invalid")
    bindings = data["knowledge_bindings"]
    ids = [item["knowledge_id"] for item in bindings]
    if len(ids) != len(set(ids)): raise MovieContractError("production v2 Knowledge binding is duplicated")
    required_binding = {"knowledge_id","knowledge_content_digest","admission_decision_id","admission_decision_digest","source_candidate","use"}
    if any(set(item) != required_binding or item.get("use") != "informational_context_only" for item in bindings): raise MovieContractError("Knowledge lineage binding is invalid")
    if context is not None:
        c = context.to_json_value() if hasattr(context, "to_json_value") else context
        expected = []
        for item in c["payload"].get("knowledge_bindings", ()):
            k = item["knowledge"]
            expected.append({"knowledge_id":k["knowledge_id"],"knowledge_content_digest":k["knowledge_content_digest"],"admission_decision_id":k["admission_decision_id"],"admission_decision_digest":k["admission_decision_digest"],"source_candidate":k["source_candidate"],"use":"informational_context_only"})
        if bindings != expected: raise MovieContractError("Knowledge lineage does not match Context")
        expected_ids = [item["knowledge"]["knowledge_id"] for item in c["payload"].get("knowledge_bindings", ())]
        expected_attributes = [item["knowledge"]["proposition"]["attribute"] for item in c["payload"].get("knowledge_bindings", ())]
        expected_values = []
        for item in c["payload"].get("knowledge_bindings", ()):
            proposition = item["knowledge"]["proposition"]
            expected_values.extend(proposition.get("values", [proposition.get("value")]))
        for option in data["payload"]["options"]:
            influence = option.get("knowledge_influence")
            expected_influence = {"mode":"informational_context_only","knowledge_ids":expected_ids,"knowledge_attributes":expected_attributes,"knowledge_values":expected_values}
            if expected_ids and influence != expected_influence:
                raise MovieContractError("Knowledge influence does not match Context")
            if not expected_ids and influence is not None:
                raise MovieContractError("unexpected Knowledge influence")
    # Re-run the accepted v1 result validator against an immutable common
    # projection only after the complete v2 representation has been sealed.
    base = dict(data); base.pop("knowledge_bindings", None); base["schema_version"] = "1"; base["result_version"] = "1"; base["context_version"] = "1"; base["policy_version"] = "1"; base["strategy_version"] = "1.0.0"; base["provider_version"] = "1.0.0"; base["context_content_digest"] = data["context_content_digest"]
    base_payload = dict(base["payload"]); base_payload["options"] = []
    for option in data["payload"]["options"]:
        item = dict(option); item.pop("knowledge_influence", None)
        item.pop("option_content_digest")
        digest_material = dict(item); digest_material.pop("option_id", None)
        item["option_content_digest"] = canonical_digest(digest_material)
        base_payload["options"].append(item)
    base_payload["semantic_result_digest"] = canonical_digest({**base_payload, "semantic_result_digest": None})
    base["payload"] = base_payload
    base["integrity"] = {"payload_sha256": canonical_digest(base_payload), "complete_result_sha256": "0"*64}
    base["integrity"]["complete_result_sha256"] = canonical_digest({**base, "integrity": {"payload_sha256": base["integrity"]["payload_sha256"]}})
    try: validate_production_option_set(base, registry=registry or MovieContractRegistry.built_in())
    except Exception as exc: raise MovieContractError("production v2 common result is invalid") from exc
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


def validate_shot_cinematography_observation_set(value, observations=(), registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "shot_cinematography_observation_set/1", registry, MAX_RESULT_BYTES)
    _require_digest(result.value, "content_digest", "shot cinematography observation set")
    data = result.value
    admitted = {}
    for raw in observations:
        artifact = validate_shot_cinematography_observation(raw, registry)
        observation_id = artifact.value["observation_id"]
        if observation_id in admitted:
            raise MovieContractError("shot observation identity is duplicated")
        admitted[observation_id] = artifact
    bindings = data["observations"]
    if [item["observation_id"] for item in bindings] != sorted(item["observation_id"] for item in bindings):
        raise MovieContractError("shot observation set order is not canonical")
    if len(admitted) != len(bindings) or set(admitted) != {item["observation_id"] for item in bindings}:
        raise MovieContractError("shot observation set is not exact")
    if len({item["shot_id"] for item in bindings}) != len(bindings):
        raise MovieContractError("shot observation identity is duplicated")
    for binding in bindings:
        observation = admitted[binding["observation_id"]].value
        expected = (
            observation["contract_identity"], observation["contract_version"],
            observation["observation_content_digest"], observation["shot_id"],
        )
        actual = (
            binding["observation_identity"], binding["observation_version"],
            binding["observation_content_digest"], binding["shot_id"],
        )
        if actual != expected:
            raise MovieContractError("shot observation binding mismatch")
        if (observation["project_id"], observation["scene_id"], observation["classification"]) != (
            data["project_id"], data["scene_id"], data["classification"]
        ):
            raise MovieContractError("shot observation set scope mismatch")
    return result


def validate_shot_cinematography_pattern_task(value, context=None, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "analyze_shot_cinematography_patterns/1", registry, MAX_STORY_BYTES)
    registry.resolve_result("analyze_shot_cinematography_patterns/1", "shot_cinematography_pattern_set/1")
    _require_digest(result.value, "task_content_digest", "shot cinematography pattern task")
    data = result.value
    if context is None or not hasattr(context, "value") or not hasattr(context, "digest"):
        raise MovieContractError("pattern task requires an independently validated Context")
    cv = context.value
    expected = (cv["context_family"], cv["context_family_version"], cv["context_id"], cv["context_content_digest"], context.digest,
                cv["project_id"], cv["scene_id"], cv["classification"])
    actual = (data["expected_context_family"], data["expected_context_version"], data["context_id"], data["context_content_digest"],
              data["complete_context_digest"], data["project_id"], data["scene_id"], data["classification"])
    if actual != expected:
        raise MovieContractError("pattern task Context binding mismatch")
    return result


def validate_shot_cinematography_pattern_set(value, *, task, context, invocation_binding_digest, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "shot_cinematography_pattern_set/1", registry, MAX_RESULT_BYTES)
    data = result.value
    if not isinstance(task, ValidatedMovieArtifact):
        raise MovieContractError("pattern result requires a validated task")
    tv, cv = task.value, context.value
    expected = (tv["request_id"], tv["correlation_id"], tv["project_id"], tv["scene_id"], tv["classification"],
                cv["context_id"], cv["context_content_digest"], context.digest,
                tv["rule_catalogue_identity"], tv["rule_catalogue_version"], tv["rule_catalogue_digest"], invocation_binding_digest)
    actual = (data["request_id"], data["correlation_id"], data["project_id"], data["scene_id"], data["classification"],
              data["context_id"], data["context_content_digest"], data["complete_context_digest"],
              data["rule_catalogue_identity"], data["rule_catalogue_version"], data["rule_catalogue_digest"], data["invocation_binding_digest"])
    if actual != expected:
        raise MovieContractError("pattern result binding mismatch")
    payload = data["payload"]
    if payload["semantic_result_digest"] != canonical_digest({**payload, "semantic_result_digest": None}):
        raise MovieContractError("pattern semantic result digest mismatch")
    if data["integrity"]["payload_sha256"] != canonical_digest(payload):
        raise MovieContractError("pattern payload digest mismatch")
    if data["integrity"]["complete_result_sha256"] != canonical_digest({**data, "integrity": {"payload_sha256": data["integrity"]["payload_sha256"]}}):
        raise MovieContractError("pattern complete result digest mismatch")
    from vss_movie_cinematic_patterns import expected_pattern_payload
    expected_payload = expected_pattern_payload(context)
    if thaw_json(payload) != expected_payload:
        raise MovieContractError("pattern evidence or rule result substitution rejected")
    return result


def validate_shot_cinematography_lesson_candidate_task(value, pattern_set=None, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "derive_shot_cinematography_lesson_candidates/1", registry, MAX_STORY_BYTES)
    registry.resolve_result("derive_shot_cinematography_lesson_candidates/1", "shot_cinematography_lesson_candidate_set/1")
    _require_digest(result.value, "task_content_digest", "shot cinematography lesson candidate task")
    if not isinstance(pattern_set, ValidatedMovieArtifact) or pattern_set.value.get("result_family") != "shot_cinematography_pattern_set":
        raise MovieContractError("lesson candidate task requires an independently validated Pattern Set")
    data, source = result.value, pattern_set.value
    expected = (
        "shot_cinematography_pattern_set", "1", pattern_set.digest, source["integrity"]["complete_result_sha256"],
        source["context_id"], source["context_content_digest"], source["complete_context_digest"],
        source["project_id"], source["scene_id"], source["classification"],
    )
    actual = (
        data["expected_input_family"], data["expected_input_version"], data["pattern_set_digest"],
        data["pattern_set_complete_digest"], data["context_id"], data["context_content_digest"],
        data["complete_context_digest"], data["project_id"], data["scene_id"], data["classification"],
    )
    if actual != expected:
        raise MovieContractError("lesson candidate task Pattern Set binding mismatch")
    return result


def validate_shot_cinematography_lesson_candidate_set(value, *, task, pattern_set,
                                                       invocation_binding_digest, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "shot_cinematography_lesson_candidate_set/1", registry, MAX_RESULT_BYTES)
    if not isinstance(task, ValidatedMovieArtifact) or not isinstance(pattern_set, ValidatedMovieArtifact):
        raise MovieContractError("lesson candidate result requires validated task and Pattern Set")
    data, tv, source = result.value, task.value, pattern_set.value
    expected = (
        tv["request_id"], tv["correlation_id"], tv["project_id"], tv["scene_id"], tv["purpose"], tv["classification"],
        pattern_set.digest, source["integrity"]["complete_result_sha256"], source["context_id"],
        source["context_content_digest"], source["complete_context_digest"], tv["rule_catalogue_identity"],
        tv["rule_catalogue_version"], tv["rule_catalogue_digest"], invocation_binding_digest,
    )
    actual = (
        data["request_id"], data["correlation_id"], data["project_id"], data["scene_id"], data["purpose"],
        data["classification"], data["pattern_set_digest"], data["pattern_set_complete_digest"], data["context_id"],
        data["context_content_digest"], data["complete_context_digest"], data["rule_catalogue_identity"],
        data["rule_catalogue_version"], data["rule_catalogue_digest"], data["invocation_binding_digest"],
    )
    if actual != expected:
        raise MovieContractError("lesson candidate result binding mismatch")
    payload = data["payload"]
    if payload["semantic_result_digest"] != canonical_digest({**payload, "semantic_result_digest": None}):
        raise MovieContractError("lesson candidate semantic result digest mismatch")
    if data["integrity"]["payload_sha256"] != canonical_digest(payload):
        raise MovieContractError("lesson candidate payload digest mismatch")
    if data["integrity"]["complete_result_sha256"] != canonical_digest({**data, "integrity": {"payload_sha256": data["integrity"]["payload_sha256"]}}):
        raise MovieContractError("lesson candidate complete result digest mismatch")
    from vss_movie_cinematic_lessons import expected_lesson_candidate_payload
    if thaw_json(payload) != expected_lesson_candidate_payload(pattern_set):
        raise MovieContractError("lesson candidate evidence, scope, or proposition substitution rejected")
    return result


def validate_shot_cinematography_knowledge_admission(value, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "shot_cinematography_knowledge_admission/1", registry, MAX_STORY_BYTES)
    _require_digest(result.value, "decision_content_digest", "shot knowledge admission decision")
    return result


def validate_shot_cinematography_admitted_knowledge(value, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "shot_cinematography_admitted_knowledge/1", registry, MAX_RESULT_BYTES)
    data = result.value
    if data["effective_from"] > data["admitted_at"] or data["admitted_at"] > data["effective_until"] or data["effective_until"] > data["retention_until"]:
        raise MovieContractError("shot knowledge temporal ordering is invalid")
    content_keys = ("knowledge_type", "project_id", "domain", "purpose", "classification",
                    "source_candidate", "proposition", "scope", "limitations", "lifecycle_status")
    if data["knowledge_content_digest"] != canonical_digest({key: data[key] for key in content_keys}):
        raise MovieContractError("shot knowledge content digest mismatch")
    if data["knowledge_id"] != "shot-knowledge-" + data["knowledge_content_digest"][:32]:
        raise MovieContractError("shot knowledge identity mismatch")
    complete = dict(data)
    complete["complete_knowledge_sha256"] = "0" * 64
    if data["complete_knowledge_sha256"] != canonical_digest(complete):
        raise MovieContractError("shot knowledge complete digest mismatch")
    return result


def validate_shot_cinematography_knowledge_lifecycle_event(value, registry=None):
    registry = registry or MovieContractRegistry.built_in()
    result = _validate(value, "shot_cinematography_knowledge_lifecycle_event/1", registry, MAX_STORY_BYTES)
    material = dict(result.value)
    expected = material.pop("event_content_digest")
    if expected != canonical_digest(material):
        raise MovieContractError("shot knowledge lifecycle event digest mismatch")
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
