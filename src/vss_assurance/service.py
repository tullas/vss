from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vss_dev.milestone import MilestoneController
from vss_movie_canon import assess_production_binding_impact, create_dependency_impact_request
from vss_movie_contracts import MovieContractRegistry
from vss_movie_shot_plan import admit_shot_plan_inputs
from vss_reasoning_contracts import canonical_digest
from vss_resource_contracts import ResourceContractRegistry, validate_dependency_impact_result


ROOT = Path(__file__).resolve().parents[2]
REQUEST_SCHEMA = ROOT / "schemas/assurance-assessment-request-v1.schema.json"
RESULT_SCHEMA = ROOT / "schemas/assurance-assessment-result-v1.schema.json"
TASK_IDENTITY = "create_scene_shot_plan_draft/1"
RESULT_IDENTITY = "scene_shot_plan_draft/1"
BASE_OBLIGATIONS = {
    "repo.impact_union", "milestone.validation", "mission.alignment",
    "mission.review_receipts", "ci.exact_head",
}
AUTHORITY = {
    "runtime_execution": False, "provider_execution": False,
    "workflow_activation": False, "merge": False, "publication": False,
    "production": False, "security_exception": False,
}
LIMITATIONS = [
    "inert_assessment", "no_historical_invalidation", "no_autonomous_remediation",
    "no_runtime_or_provider_execution", "no_workflow_or_merge_authority",
    "no_production_or_publication_authority",
]
DEPENDENCY_ARGUMENTS = {
    "prior_decision_data", "prior_packet_data", "prior_option_set_data", "prior_breakdown_data",
    "prior_decision_revision", "prior_canon_snapshot", "prior_binding",
    "candidate_decision_data", "candidate_packet_data", "candidate_option_set_data",
    "candidate_breakdown_data", "candidate_decision_revision", "candidate_canon_snapshot",
    "prior_previous_revision", "candidate_previous_revision",
}
LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


class AssuranceAssessmentError(ValueError):
    """The request is not the one registered bounded assessment operation."""


def _schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(value)
    except Exception as exc:
        raise AssuranceAssessmentError("assurance schema is unavailable or malformed") from exc
    return value


def _dependency_input_value(value: Any) -> Any:
    serializer = getattr(value, "to_json_value", None)
    if callable(serializer):
        return serializer()
    if value is None or type(value) in {str, int, float, bool, dict, list}:
        return value
    raise AssuranceAssessmentError("dependency evidence is not a canonical JSON value")


def _impact(root: Path, base: str, map_revision: str | None = None) -> dict[str, Any]:
    command = [str(root / "scripts/vss-agent"), "impact", "--base", base,
               "--include-assurance-coverage"]
    if map_revision is not None:
        command.extend(["--map-revision", map_revision])
    try:
        result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, check=False, timeout=10)
        if result.returncode != 0 or len(result.stdout) > 65_536:
            raise AssuranceAssessmentError("authoritative repository impact is unavailable")
        value = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise AssuranceAssessmentError("authoritative repository impact is unavailable") from exc
    if (type(value) is not dict or value.get("schema_version") != "2"
            or value.get("authority") != {"runtime_execution": False, "provider_execution": False,
                                          "merge": False, "push": False}):
        raise AssuranceAssessmentError("authoritative repository impact is malformed")
    return value


def _result(*, request_digest: str, repository: dict[str, str], changed_paths: list[str],
            policy: dict[str, str], coverage: dict[str, Any], fitness: str, impact: str,
            reasons: set[str], evidence: list[dict[str, str]]) -> dict[str, Any]:
    value = {
        "schema_version": "1", "protocol": "vss.assurance-assessment-result",
        "request_sha256": request_digest, "repository": repository,
        "changed_paths": sorted(set(changed_paths)), "policy": policy,
        "coverage": coverage, "assurance_fitness": fitness, "change_impact": impact,
        "reason_codes": sorted(reasons),
        "evidence": sorted(evidence, key=lambda item: (item["kind"], item["identity"])),
        "limitations": LIMITATIONS, "authority": AUTHORITY,
    }
    errors = list(Draft202012Validator(_schema(RESULT_SCHEMA)).iter_errors(value))
    if errors:
        raise AssuranceAssessmentError("assessment result violated its closed schema")
    return value


def _incomplete(*, request_digest: str, repository: dict[str, str], policy: dict[str, str],
                changed_paths: list[str], coverage: dict[str, Any], reasons: set[str],
                evidence: list[dict[str, str]] | None = None) -> dict[str, Any]:
    reasons.add("evidence_incomplete")
    return _result(request_digest=request_digest, repository=repository,
                   changed_paths=changed_paths, policy=policy, coverage=coverage,
                   fitness="incomplete_fail_closed", impact="incomplete_fail_closed",
                   reasons=reasons, evidence=evidence or [])


def assess_registered_shot_plan(
    request_data: dict[str, Any], *, dependency_arguments: dict[str, Any],
    repository_root: Path | str = ROOT, milestone_id: str | None = None,
) -> dict[str, Any]:
    """Compose current repository assurance with the exact registered shot-plan dependency chain.

    The request intentionally has no scope, action, dependency subset, or policy selector. Repository
    identity, changed-path obligations, and milestone evidence come from the live controller and
    harness; creative dependency scope is reconstructed from the registered movie/resource contracts.
    """
    request_schema = _schema(REQUEST_SCHEMA)
    if list(Draft202012Validator(request_schema).iter_errors(request_data)):
        raise AssuranceAssessmentError("request is not the registered shot-plan assessment")
    registry = MovieContractRegistry.built_in()
    registry.resolve_result(TASK_IDENTITY, RESULT_IDENTITY)
    arguments_complete = (type(dependency_arguments) is dict
                          and set(dependency_arguments) == DEPENDENCY_ARGUMENTS)
    if not isinstance(dependency_arguments, dict):
        dependency_arguments = {}

    root = Path(repository_root).resolve()
    controller = MilestoneController(root)
    try:
        state = controller.load(milestone_id)
    except Exception as exc:
        raise AssuranceAssessmentError("current milestone identity is unavailable") from exc
    repository = state["repository"]
    if state["status"] == "CONFLICT":
        raise AssuranceAssessmentError("current milestone source identity conflicts")

    candidate_plan = _impact(root, repository["base_sha"])
    base_plan = _impact(root, repository["base_sha"], repository["base_sha"])
    try:
        dependency_commitment = {key: _dependency_input_value(value)
                                 for key, value in sorted(dependency_arguments.items())}
    except Exception:
        dependency_commitment = {"invalid_input_fields": sorted(dependency_arguments)}
    candidate_coverage = candidate_plan["coverage"]
    base_coverage = base_plan["coverage"]
    obligations = sorted(set(candidate_coverage["obligations"] + base_coverage["obligations"]
                            + ["resource.canon_decisions", "schema.consumer_closure"]))
    effect_scope = ("all_affected_subjects"
                    if "all_affected_subjects" in {
                        candidate_coverage["effect_scope"], base_coverage["effect_scope"]}
                    else candidate_coverage["effect_scope"])
    coverage = {
        "rule_patterns": sorted(set(candidate_coverage["rule_patterns"] + base_coverage["rule_patterns"])),
        "obligations": obligations,
        "effect_scope": effect_scope,
    }
    policy = {
        "base_harness_sha256": base_plan["map_sha256"],
        "candidate_harness_sha256": candidate_plan["map_sha256"],
        "controller_policy_sha256": controller.policy_digest,
        "active_decision_index_sha256": controller._active_decisions()[1],
        "assessment_sha256": state["mission_gate"]["assessment_sha256"],
        "resource_registry_sha256": ResourceContractRegistry.built_in().digest,
        "movie_registry_sha256": registry.digest,
    }
    request_digest = canonical_digest({
        "request": request_data, "task_identity": TASK_IDENTITY,
        "result_identity": RESULT_IDENTITY, "dependency_inputs": dependency_commitment,
        "repository": repository, "policy": policy,
    })
    paths = sorted(set(candidate_plan["changed_paths"] + base_plan["changed_paths"]))
    reasons: set[str] = set()
    evidence: list[dict[str, str]] = [
        {"kind": "controller", "identity": state["history_tail"]["sha256"]},
        {"kind": "operation", "identity": canonical_digest({"task": TASK_IDENTITY, "result": RESULT_IDENTITY})},
    ]
    if state["validation"].get("evidence_sha256"):
        evidence.append({"kind": "validation", "identity": state["validation"]["evidence_sha256"]})
    evidence.append({"kind": "ci", "identity": canonical_digest(state["ci"])})
    if candidate_plan["unknown_paths"] or base_plan["unknown_paths"]:
        reasons.add("unknown_path")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage={**coverage, "effect_scope": "incomplete_fail_closed"},
                           reasons=reasons, evidence=evidence)
    if candidate_coverage["missing_rules"]:
        reasons.add("coverage_rule_missing")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage={**coverage, "effect_scope": "incomplete_fail_closed"},
                           reasons=reasons, evidence=evidence)
    if not BASE_OBLIGATIONS.issubset(set(coverage["obligations"])):
        reasons.add("assurance_obligation_missing")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)
    if state["mission_gate"]["outcome"] != "PROCEED":
        reasons.update({"authority_alignment_unresolved", "review_required"})
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)
    if not arguments_complete:
        reasons.add("authoritative_chain_incomplete")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)

    try:
        task, *_ = admit_shot_plan_inputs(
            dependency_arguments["candidate_decision_data"],
            dependency_arguments["candidate_packet_data"],
            dependency_arguments["candidate_option_set_data"],
            dependency_arguments["candidate_breakdown_data"],
            request_id=dependency_arguments["candidate_decision_data"]["request_id"],
            correlation_id=dependency_arguments["candidate_decision_data"]["correlation_id"],
            environment="development",
        )
        if task.value["task_identity"] != "create_scene_shot_plan_draft":
            raise AssuranceAssessmentError("shot-plan operation identity mismatch")
        dependency_request = create_dependency_impact_request(
            prior_binding=dependency_arguments["prior_binding"],
            prior_canon_snapshot=dependency_arguments["prior_canon_snapshot"],
            prior_decision_revision=dependency_arguments["prior_decision_revision"],
            candidate_canon_snapshot=dependency_arguments["candidate_canon_snapshot"],
            candidate_decision_revision=dependency_arguments["candidate_decision_revision"],
        )
        dependency_result = assess_production_binding_impact(
            dependency_request.to_json_value(), **dependency_arguments)
        checked_dependency = validate_dependency_impact_result(dependency_result.to_json_value())
    except Exception:
        reasons.add("authoritative_chain_incomplete")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage={**coverage, "effect_scope": "incomplete_fail_closed"},
                           reasons=reasons, evidence=evidence)
    evidence.extend([
        {"kind": "dependency", "identity": checked_dependency.value["result_sha256"]},
        {"kind": "operation", "identity": task.digest},
    ])

    if ("dependency.subject_enumeration" in coverage["obligations"]
            or coverage["effect_scope"] != "exact_registered_subject"):
        reasons.add("authoritative_chain_incomplete")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)
    if "resource.rights_eligibility" in coverage["obligations"]:
        reasons.add("candidate_rights_unknown")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)
    if "security.l3_review" in coverage["obligations"]:
        reasons.add("unsupported_authority_transition")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)
    pending_assurance = False
    if "policy.controller_self_change" in coverage["obligations"]:
        reasons.add("policy_or_controller_change")

    required = max(LEVELS[base_plan["minimum_level"]], LEVELS[candidate_plan["minimum_level"]])
    if "policy.controller_self_change" in coverage["obligations"]:
        required = max(required, LEVELS["L3"])
    current_level = LEVELS.get(state["validation"]["level"], -1)
    if current_level < required:
        reasons.add("validation_level_insufficient")
        pending_assurance = True
    current_ci = state["ci"]
    if (current_ci["status"] != "passed" or current_ci["head_sha"] != repository["head_sha"]):
        reasons.add("ci_required")
        if current_ci["status"] == "stale" or current_ci["head_sha"] not in {None, repository["head_sha"]}:
            reasons.add("evidence_stale")
        pending_assurance = True
    if checked_dependency.value["classification"] == "incomplete_fail_closed":
        reasons.add("authoritative_chain_incomplete")
        return _incomplete(request_digest=request_digest, repository=repository, policy=policy,
                           changed_paths=paths, coverage=coverage, reasons=reasons, evidence=evidence)
    if checked_dependency.value["classification"] == "affected_reassessment_required":
        reasons.add("selected_dependency_changed")
        return _result(request_digest=request_digest, repository=repository, changed_paths=paths,
                       policy=policy, coverage=coverage,
                       fitness="additional_assurance_required",
                       impact="affected_reassessment_required", reasons=reasons, evidence=evidence)
    if pending_assurance:
        return _result(request_digest=request_digest, repository=repository, changed_paths=paths,
                       policy=policy, coverage=coverage,
                       fitness="additional_assurance_required", impact="unaffected",
                       reasons=reasons, evidence=evidence)
    reasons.add("exact_identity_and_required_evidence_fresh")
    reasons.add("exact_dependencies_unchanged")
    return _result(request_digest=request_digest, repository=repository, changed_paths=paths,
                   policy=policy, coverage=coverage, fitness="fit", impact="unaffected",
                   reasons=reasons, evidence=evidence)
