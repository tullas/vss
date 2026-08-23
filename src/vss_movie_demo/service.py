from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vss_context import ContextAssembler
from vss_movie_contracts import validate_scene_breakdown, validate_story_fragment
from vss_movie_option_review import prepare_option_review, record_option_review_decision
from vss_reasoning.gateway import ReasoningGateway


@dataclass(frozen=True)
class DemoPrepared:
    story: dict[str, Any]
    scene_breakdown: dict[str, Any]
    option_set: dict[str, Any]
    review_packet: dict[str, Any]


def prepare_demo(story_data: dict[str, Any], *, correlation_id: str) -> DemoPrepared:
    """Run the real pipeline through review preparation without choosing for the user."""
    story = validate_story_fragment(story_data).to_json_value()
    project_id = story["project_id"]
    breakdown_request = {
        "correlation_id": correlation_id,
        "request_id": f"{correlation_id}-breakdown",
        "project_id": project_id,
        "purpose": "scene_breakdown_local_validation",
        "task_identity": "break_down_scenes",
        "task_version": "1",
    }
    breakdown_context = ContextAssembler().assemble_scene_breakdown(
        story, request_id=breakdown_request["request_id"], correlation_id=correlation_id,
        project_id=project_id, environment="development",
    )
    gateway = ReasoningGateway.built_in()
    breakdown = gateway.execute_scene_breakdown(
        breakdown_request, breakdown_context.to_json_value(), environment="development",
        correlation_id=correlation_id,
    )["scene_breakdown"]
    validated_breakdown = validate_scene_breakdown(breakdown)
    scene = breakdown["payload"]["ordered_scenes"][0]
    options_request = {
        "schema_version": "2",
        "task_identity": "generate_scene_production_options",
        "task_version": "2",
        "request_id": f"{correlation_id}-options",
        "correlation_id": correlation_id,
        "project_id": project_id,
        "environment": "development",
        "purpose": "scene_production_options_local_analysis",
        "expected_context_family": "scene_production_options_context",
        "expected_context_version": "2",
        "expected_result_family": "scene_production_option_set",
        "expected_result_version": "2",
        "scene_breakdown_identity": "scene_breakdown",
        "scene_breakdown_version": "1",
        "scene_breakdown_digest": validated_breakdown.digest,
        "scene_id": scene["scene_id"],
        "scene_content_digest": scene["scene_content_digest"],
        "classification": story["classification"],
        "trust": story["trust"],
        "bounds": {"maximum_options": 4, "maximum_result_bytes": 65536, "maximum_duration_ms": 30000},
        "lifecycle": "active",
        "implementation_availability": "required",
    }
    options_context = ContextAssembler().assemble_scene_production_options(
        options_request, breakdown, correlation_id=correlation_id, environment="development",
    ).context.to_json_value()
    option_set = gateway.execute_scene_production_options(
        options_request, options_context, environment="development", correlation_id=correlation_id,
    )["scene_production_option_set"]
    packet = prepare_option_review(
        option_set, request_id=f"{correlation_id}-review", correlation_id=correlation_id,
        environment="development",
    )
    return DemoPrepared(story, breakdown, option_set, packet)


def finish_demo(prepared: DemoPrepared, *, option_id: str, reviewer_id: str,
                rationale: str, correlation_id: str) -> dict[str, Any]:
    """Record an accepted human review choice and create the real deterministic draft."""
    decision = record_option_review_decision(
        prepared.review_packet, prepared.option_set, option_id=option_id,
        reviewer_id=reviewer_id, outcome="accept", rationale=rationale,
        request_id=f"{correlation_id}-decision", correlation_id=correlation_id,
        environment="development",
    )
    draft = ReasoningGateway.built_in().execute_scene_shot_plan_draft(
        decision, prepared.review_packet, prepared.option_set, prepared.scene_breakdown,
        request_id=f"{correlation_id}-shot-plan", environment="development",
        correlation_id=correlation_id,
    )["scene_shot_plan_draft"]
    return {
        "selected_option_id": option_id,
        "scene_breakdown": prepared.scene_breakdown,
        "scene_production_option_set": prepared.option_set,
        "review_packet": prepared.review_packet,
        "review_decision": decision,
        "scene_shot_plan_draft": draft,
    }
