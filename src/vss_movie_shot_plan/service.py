from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vss_movie_contracts import (
    ValidatedMovieArtifact,
    validate_production_option_set_v2,
    validate_scene_breakdown,
    validate_scene_option_review_decision,
    validate_scene_option_review_packet,
)
from vss_movie_contracts.errors import MovieContractError
from vss_movie_option_review import create_decision_task, create_review_task
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json, thaw_json

AUTHORITY_BOUNDARY = {
    "scope": "draft_only", "production_approval": False,
    "final_shot_selection": False, "production_plan_authority": False,
    "scheduling_authority": False, "workflow_activation": False,
    "capability_grant": False, "provider_execution_authority": False,
    "runtime_execution_authority": False,
}
PLAN_LIMITATIONS = (
    "This artifact is a deterministic structural draft for human inspection, not a production plan or final shot selection.",
    "Shot feasibility, availability, cost, schedule, rights, safety, and renderability have not been established.",
    "Stable shot order represents narrative structure only; it is not ranking or recommendation.",
)


@dataclass(frozen=True, slots=True)
class ShotPlanProviderView:
    project_id: str
    scene_id: str
    option_id: str
    option_content_digest: str
    profile_identity: str
    approach_category: str
    source_observations: tuple[Any, ...]
    source_events: tuple[Any, ...]
    declared_characters: tuple[str, ...]
    declared_locations: tuple[str, ...]
    time_indicators: tuple[str, ...]
    evidence_references: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    knowledge_influence: Any
    provider_visible_digest: str


def _validate_upstream(decision_data: Any, packet_data: Any, option_set_data: Any,
                       breakdown_data: Any, environment: str):
    if environment != "development":
        raise MovieContractError("shot-plan drafting is development-only")
    option_set = validate_production_option_set_v2(option_set_data)
    review_task = create_review_task(
        option_set, request_id=packet_data.get("request_id", "") if isinstance(packet_data, dict) else "",
        correlation_id=packet_data.get("correlation_id", "") if isinstance(packet_data, dict) else "",
        environment=environment,
    )
    packet = validate_scene_option_review_packet(packet_data, task=review_task, option_set=option_set)
    if not isinstance(decision_data, dict):
        raise MovieContractError("shot-plan decision input must be an object")
    raw_decisions = decision_data.get("payload", {}).get("decisions", [])
    if not isinstance(raw_decisions, list) or len(raw_decisions) != 1 or not isinstance(raw_decisions[0], dict):
        raise MovieContractError("shot-plan input requires exactly one review decision")
    raw = raw_decisions[0]
    decision_task = create_decision_task(
        packet, option_set, option_id=raw.get("option_id", ""), reviewer_id=raw.get("reviewer_id", ""),
        outcome=raw.get("outcome", ""), rationale=raw.get("rationale", ""),
        deferred_review_conditions=raw.get("deferred_review_conditions"),
        request_id=decision_data.get("request_id", ""), correlation_id=decision_data.get("correlation_id", ""),
        environment=environment,
    )
    decision = validate_scene_option_review_decision(
        decision_data, task=decision_task, packet=packet, option_set=option_set
    )
    if decision.value["payload"]["decisions"][0]["outcome"] != "accept":
        raise MovieContractError("shot-plan drafting requires an accepted review-stage decision")
    breakdown = validate_scene_breakdown(breakdown_data)
    if (breakdown.value["project_id"] != option_set.value["project_id"]
            or breakdown.digest != option_set.value["scene_breakdown_digest"]):
        raise MovieContractError("scene breakdown binding mismatch")
    scenes = [s for s in breakdown.value["payload"]["ordered_scenes"]
              if s["scene_id"] == option_set.value["scene_id"]]
    if len(scenes) != 1 or scenes[0]["scene_content_digest"] != option_set.value["scene_content_digest"]:
        raise MovieContractError("selected scene binding mismatch")
    return decision, packet, option_set, breakdown, scenes[0]


def create_shot_plan_task(decision: ValidatedMovieArtifact, packet: ValidatedMovieArtifact,
                          option_set: ValidatedMovieArtifact, breakdown: ValidatedMovieArtifact,
                          *, request_id: str, correlation_id: str,
                          environment: str = "development") -> ValidatedMovieArtifact:
    from vss_movie_contracts import validate_scene_shot_plan_task
    selected = decision.value["payload"]["decisions"][0]
    value = {
        "schema_version": "1", "task_identity": "create_scene_shot_plan_draft", "task_version": "1",
        "request_id": request_id, "correlation_id": correlation_id,
        "project_id": decision.value["project_id"], "scene_id": decision.value["scene_id"],
        "environment": environment, "purpose": "scene_shot_plan_draft_local_development",
        "expected_result_family": "scene_shot_plan_draft", "expected_result_version": "1",
        "decision_digest": decision.digest,
        "decision_complete_digest": decision.value["integrity"]["complete_result_sha256"],
        "review_packet_digest": packet.value["payload"]["review_packet_digest"],
        "review_packet_complete_digest": packet.value["integrity"]["complete_result_sha256"],
        "option_set_digest": option_set.digest,
        "option_set_complete_digest": option_set.value["integrity"]["complete_result_sha256"],
        "selected_option_id": selected["option_id"],
        "selected_option_content_digest": selected["option_content_digest"],
        "scene_breakdown_digest": breakdown.digest,
        "scene_breakdown_payload_digest": breakdown.value["integrity"]["payload_sha256"],
        "bounds": {"maximum_shots": 3, "maximum_result_bytes": 65536},
        "lifecycle": "active", "task_content_digest": "0" * 64,
    }
    value["task_content_digest"] = canonical_digest({k: v for k, v in value.items() if k != "task_content_digest"})
    return validate_scene_shot_plan_task(value, decision=decision, packet=packet,
                                         option_set=option_set, breakdown=breakdown)


def admit_shot_plan_inputs(decision_data: Any, packet_data: Any, option_set_data: Any,
                           breakdown_data: Any, *, request_id: str, correlation_id: str,
                           environment: str = "development"):
    decision, packet, option_set, breakdown, scene = _validate_upstream(
        decision_data, packet_data, option_set_data, breakdown_data, environment
    )
    task = create_shot_plan_task(decision, packet, option_set, breakdown,
                                 request_id=request_id, correlation_id=correlation_id,
                                 environment=environment)
    return task, decision, packet, option_set, breakdown, scene


def shot_plan_provider_view(task: ValidatedMovieArtifact, decision: ValidatedMovieArtifact,
                            option_set: ValidatedMovieArtifact, scene: Any) -> ShotPlanProviderView:
    option_id = task.value["selected_option_id"]
    matches = [o for o in option_set.value["payload"]["options"] if o["option_id"] == option_id]
    if len(matches) != 1:
        raise MovieContractError("accepted option is not present exactly once")
    option = thaw_json(matches[0]); raw_scene = thaw_json(scene)
    evidence = tuple(dict.fromkeys(raw_scene["evidence_references"] + option["evidence_references"]))
    assumptions = tuple(dict.fromkeys(raw_scene["assumptions"] + option["assumptions"]))
    unknowns = tuple(dict.fromkeys(raw_scene["unknowns"] + option["unknowns"] + ["Shot feasibility has not been established."]))
    limitations = tuple(dict.fromkeys(raw_scene["limitations"] + option["limitations"] + list(PLAN_LIMITATIONS)))
    influence = option.get("knowledge_influence")
    material = {
        "project_id": task.value["project_id"], "scene_id": task.value["scene_id"],
        "option_id": option_id, "option_content_digest": option["option_content_digest"],
        "profile_identity": option["profile_identity"], "approach_category": option["approach_category"],
        "source_observations": raw_scene["source_observations"], "source_events": raw_scene["events"],
        "declared_characters": raw_scene["declared_characters"],
        "declared_locations": raw_scene["declared_locations"],
        "time_indicators": raw_scene["time_indicators"],
        "evidence_references": list(evidence), "assumptions": list(assumptions),
        "unknowns": list(unknowns), "limitations": list(limitations),
        "knowledge_influence": influence,
    }
    return ShotPlanProviderView(
        task.value["project_id"], task.value["scene_id"], option_id, option["option_content_digest"],
        option["profile_identity"], option["approach_category"],
        tuple(freeze_json(x) for x in raw_scene["source_observations"]),
        tuple(freeze_json(x) for x in raw_scene["events"]),
        tuple(raw_scene["declared_characters"]), tuple(raw_scene["declared_locations"]),
        tuple(raw_scene["time_indicators"]), evidence, assumptions, unknowns,
        limitations, freeze_json(influence) if influence is not None else None,
        canonical_digest(material),
    )


def _qualification(view: ShotPlanProviderView, attribute: str) -> str:
    influence = thaw_json(view.knowledge_influence) if view.knowledge_influence is not None else None
    if influence and attribute in influence["knowledge_attributes"]:
        values = ", ".join(str(value) for value in influence["knowledge_values"])
        return f"Informational cinematography Knowledge reports {attribute}: {values}; human validation required."
    return "Not specified by validated upstream artifacts; requires human determination."


def create_shot_cards(view: ShotPlanProviderView) -> tuple[Any, ...]:
    if type(view) is not ShotPlanProviderView:
        raise TypeError("shot-plan provider requires the exact provider view")
    observation = thaw_json(view.source_observations[0])["text"]
    event = (thaw_json(view.source_events[0])["text"] if view.source_events
             else observation)
    unresolved = view.unknowns[0]
    locations = ", ".join(view.declared_locations) or "an upstream-unspecified location"
    characters = ", ".join(view.declared_characters) or "upstream-unspecified subjects"
    time = ", ".join(view.time_indicators) or "an upstream-unspecified time"
    roles = (
        ("scene_orientation", "Wide structural coverage draft",
         f"Establish the source-observed scene: {observation}",
         f"Draft composition should establish {locations} at {time}; exact blocking remains undetermined."),
        ("primary_action", "Medium structural coverage draft",
         f"Cover the source event: {event}",
         f"Draft composition should keep {characters} legible during the source event; exact blocking remains undetermined."),
        ("detail_or_transition", "Close detail or transition coverage draft",
         f"Hold space for the unresolved narrative detail: {unresolved}",
         "Draft composition may isolate the unresolved detail, but its meaning and exact visual treatment require human determination."),
    )
    cards = []
    for ordinal, (purpose, scale, focus, composition) in enumerate(roles, 1):
        material = {
            "source_ordinal": ordinal, "shot_purpose": purpose,
            "narrative_focus": focus,
            "option_application": f"Use accepted option profile {view.profile_identity} ({view.approach_category}) only as draft structural context.",
            "shot_scale_qualification": f"{scale} for the accepted {view.approach_category} approach; human validation required.",
            "camera_angle_qualification": _qualification(view, "camera_angle"),
            "camera_elevation_qualification": _qualification(view, "camera_elevation"),
            "camera_movement_qualification": _qualification(view, "camera_movement"),
            "composition_qualification": (_qualification(view, "composition")
                                          if view.knowledge_influence is not None
                                          and "composition" in thaw_json(view.knowledge_influence)["knowledge_attributes"]
                                          else composition),
            "screen_direction_qualification": _qualification(view, "screen_direction"),
            "evidence_references": list(view.evidence_references), "assumptions": list(view.assumptions),
            "unresolved_unknowns": list(view.unknowns), "limitations": list(view.limitations),
            "knowledge_influence": thaw_json(view.knowledge_influence) if view.knowledge_influence is not None else None,
            "derivation_basis": "deterministic_structural_draft",
        }
        shot_id = "shot-" + canonical_digest({"project": view.project_id, "scene": view.scene_id,
                                                "option": view.option_id, "card": material})[:24]
        card = {"shot_id": shot_id, **material}
        card["shot_card_digest"] = canonical_digest(card)
        cards.append(freeze_json(card))
    return tuple(cards)


def expected_shot_plan_payload(view: ShotPlanProviderView, cards: tuple[Any, ...] | None = None,
                               *, knowledge_bindings: tuple[Any, ...] = ()) -> dict[str, Any]:
    authoritative = create_shot_cards(view)
    supplied = cards if cards is not None else authoritative
    if type(supplied) is not tuple or [thaw_json(x) for x in supplied] != [thaw_json(x) for x in authoritative]:
        raise MovieContractError("shot cards do not match deterministic authoritative derivation")
    payload = {
        "draft_status": "draft_only", "stable_order_is_not_ranking": True,
        "ordered_shots": [thaw_json(x) for x in supplied],
        "source_knowledge_bindings": [thaw_json(x) for x in knowledge_bindings],
        "knowledge_influence": thaw_json(view.knowledge_influence) if view.knowledge_influence is not None else None,
        "authority_boundary": dict(AUTHORITY_BOUNDARY), "limitations": list(PLAN_LIMITATIONS),
        "shot_plan_digest": None,
    }
    payload["shot_plan_digest"] = canonical_digest(payload)
    return payload


def create_shot_plan_result(task: ValidatedMovieArtifact, decision: ValidatedMovieArtifact,
                            packet: ValidatedMovieArtifact, option_set: ValidatedMovieArtifact,
                            breakdown: ValidatedMovieArtifact, scene: Any,
                            cards: tuple[Any, ...]) -> dict[str, Any]:
    from vss_movie_contracts import validate_scene_shot_plan_draft
    view = shot_plan_provider_view(task, decision, option_set, scene)
    payload = expected_shot_plan_payload(view, cards, knowledge_bindings=tuple(option_set.value["knowledge_bindings"]))
    tv = task.value
    result = {
        "schema_version": "1", "result_family": "scene_shot_plan_draft", "result_version": "1",
        **{k: tv[k] for k in (
            "request_id", "correlation_id", "project_id", "scene_id", "decision_digest",
            "decision_complete_digest", "review_packet_digest", "review_packet_complete_digest",
            "option_set_digest", "option_set_complete_digest", "selected_option_id",
            "selected_option_content_digest", "scene_breakdown_digest", "scene_breakdown_payload_digest")},
        "payload": payload,
        "integrity": {"payload_sha256": canonical_digest(payload), "complete_result_sha256": "0" * 64},
    }
    result["integrity"]["complete_result_sha256"] = canonical_digest(
        {**result, "integrity": {"payload_sha256": result["integrity"]["payload_sha256"]}}
    )
    return validate_scene_shot_plan_draft(
        result, task=task, decision=decision, packet=packet,
        option_set=option_set, breakdown=breakdown
    ).to_json_value()
