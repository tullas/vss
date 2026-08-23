from __future__ import annotations

import concurrent.futures
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from vss_config import ConfigError, load_configuration
from vss_reasoning_contracts import canonical_digest

from .exit_codes import ExitCode
from .models import CommandContext, SafeCommandError
from .registry import get_command

RUNTIME_CAPABILITY_COMMANDS = frozenset({"system.info", "runtime.echo", "runtime.time", "bootstrap.check"})
REASONING_COMMAND = "reasoning.generate-options"
PERFORMANCE_COMMAND = "performance.reasoning"
KNOWLEDGE_BUILD_COMMAND = "knowledge.package.build"
KNOWLEDGE_VALIDATE_COMMAND = "knowledge.package.validate"
CONTEXT_ASSEMBLE_COMMAND = "context.assemble"
CONTEXT_VALIDATE_COMMAND = "context.validate"
MOVIE_BREAKDOWN_COMMAND = "movie.break-down-scenes"
MOVIE_CONTEXT_COMMAND = "movie.context-assemble-scene-breakdown"
MOVIE_PROD_CONTEXT_COMMAND = "movie.context-assemble-scene-production-options"
MOVIE_PROD_COMMAND = "movie.generate-scene-production-options"
MOVIE_REVIEW_COMMAND = "movie.prepare-option-review"
MOVIE_REVIEW_DECISION_COMMAND = "movie.record-option-review-decision"
MOVIE_SHOT_PLAN_COMMAND = "movie.create-shot-plan-draft"
MOVIE_CONTINUITY_CONTEXT_COMMAND = "movie.context-assemble-character-continuity"
MOVIE_CONTINUITY_COMMAND = "movie.analyze-character-continuity"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def _safe_error(message: str) -> str:
    # Error text is deliberately limited to schema paths and fixed framework messages.
    return " ".join(str(message).replace("\n", " ").split())[:500]


class CommandRunner:
    def __init__(self, runtime_controller=None, reasoning_gateway=None, performance_harness=None, knowledge_builder=None) -> None:
        self._runtime_controller = runtime_controller
        self._reasoning_gateway = reasoning_gateway
        self._performance_harness = performance_harness
        self._knowledge_builder = knowledge_builder

    def run(
        self,
        command: str,
        environment: str,
        input_data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        dry_run: bool = False,
        timeout_seconds: float | None = None,
        verbose: bool = False,
        ask_become_pass: bool = False,
    ) -> tuple[dict[str, Any], int]:
        started_at = utc_now()
        started_clock = time.monotonic()
        correlation = correlation_id or new_correlation_id()
        response_base = {
            "schema_version": "1",
            "command": command,
            "correlation_id": correlation,
            "started_at": started_at,
        }

        def finish(status: str, exit_code: int, output: dict[str, Any], errors: list[str]):
            completed_at = utc_now()
            response = {
                **response_base,
                "status": status,
                "exit_code": int(exit_code),
                "completed_at": completed_at,
                "duration_ms": int((time.monotonic() - started_clock) * 1000),
                "output": output,
                "errors": [_safe_error(error) for error in errors],
            }
            return response, exit_code

        try:
            registered = get_command(command)
        except Exception:
            return finish("error", ExitCode.INTERNAL_ERROR, {}, ["command registry unavailable"])
        if registered is None and command not in RUNTIME_CAPABILITY_COMMANDS and command not in {REASONING_COMMAND, PERFORMANCE_COMMAND, KNOWLEDGE_BUILD_COMMAND, KNOWLEDGE_VALIDATE_COMMAND, CONTEXT_ASSEMBLE_COMMAND, CONTEXT_VALIDATE_COMMAND, MOVIE_BREAKDOWN_COMMAND, MOVIE_CONTEXT_COMMAND, MOVIE_PROD_CONTEXT_COMMAND, MOVIE_PROD_COMMAND, MOVIE_REVIEW_COMMAND, MOVIE_REVIEW_DECISION_COMMAND, MOVIE_SHOT_PLAN_COMMAND, MOVIE_CONTINUITY_CONTEXT_COMMAND, MOVIE_CONTINUITY_COMMAND}:
            return finish("error", ExitCode.UNKNOWN_COMMAND, {}, [f"unknown command: {command}"])
        try:
            configuration = load_configuration(environment)
        except ConfigError as exc:
            return finish("error", ExitCode.INVALID_CONFIGURATION, {}, [str(exc)])

        payload = input_data if input_data is not None else {}
        if not isinstance(payload, dict):
            return finish("error", ExitCode.INVALID_INPUT, {}, ["input must be a JSON object"])
        if command in {MOVIE_BREAKDOWN_COMMAND, MOVIE_CONTEXT_COMMAND, MOVIE_PROD_CONTEXT_COMMAND, MOVIE_PROD_COMMAND, MOVIE_REVIEW_COMMAND, MOVIE_REVIEW_DECISION_COMMAND, MOVIE_SHOT_PLAN_COMMAND, MOVIE_CONTINUITY_CONTEXT_COMMAND, MOVIE_CONTINUITY_COMMAND}:
            try:
                if command in {MOVIE_CONTINUITY_CONTEXT_COMMAND, MOVIE_CONTINUITY_COMMAND}:
                    required = {"task","scene_breakdown","continuity_sequence","character_references","character_identities","character_observations"}
                    if command == MOVIE_CONTINUITY_COMMAND: required.add("context")
                    allowed = required | {"transition_evidence"}
                    if not required.issubset(payload) or not set(payload).issubset(allowed) or not all(isinstance(payload.get(name, []), list) for name in ("character_references","character_identities","character_observations","transition_evidence")):
                        return finish("error", ExitCode.INVALID_INPUT, {}, ["character continuity input is invalid"])
                    from vss_movie_contracts import (validate_scene_breakdown, validate_character_reference, validate_character_identity, validate_continuity_sequence, validate_character_observation, validate_executable_character_continuity_task, validate_character_continuity_transition_evidence)
                    breakdown = validate_scene_breakdown(payload["scene_breakdown"])
                    references = tuple(validate_character_reference(x) for x in payload["character_references"])
                    identities = tuple(validate_character_identity(raw, tuple(x for x in references if x.value["reference_id"] in raw["bound_reference_ids"])) for raw in payload["character_identities"])
                    sequence = validate_continuity_sequence(payload["continuity_sequence"], breakdown)
                    identity_map = {x.value["character_id"]:x for x in identities}
                    observations = tuple(validate_character_observation(raw, identity_map.get(raw.get("character_id")), sequence) for raw in payload["character_observations"])
                    task = validate_executable_character_continuity_task(payload["task"], sequence, identities)
                    transitions = tuple(validate_character_continuity_transition_evidence(raw, observations, sequence) for raw in payload.get("transition_evidence", ()))
                    if command == MOVIE_CONTINUITY_CONTEXT_COMMAND:
                        from vss_context import ContextAssembler
                        outcome = ContextAssembler().assemble_character_continuity(task, sequence, identities, observations, transition_evidence=transitions, correlation_id=correlation, environment=environment)
                        from vss_reasoning_contracts.canonicalization import thaw_json
                        return finish("success", ExitCode.SUCCESS, {"context":outcome.context.to_json_value(), "assembly_report":thaw_json(outcome.report), "summary":dict(outcome.summary)}, [])
                    gateway = self._reasoning_gateway
                    if gateway is None:
                        from vss_reasoning.gateway import ReasoningGateway
                        gateway = ReasoningGateway.built_in()
                    result = gateway.execute_character_continuity(task, payload["context"], continuity_sequence=sequence, character_identities=identities, observations=observations, transition_evidence=transitions, environment=environment, correlation_id=correlation, dry_run=dry_run)
                    return finish("success", ExitCode.SUCCESS, result, [])
                if command == MOVIE_CONTEXT_COMMAND:
                    if frozenset(payload) != {"request", "story"}: return finish("error", ExitCode.INVALID_INPUT, {}, ["movie context input is invalid"])
                    req, story = payload["request"], payload["story"]
                    from vss_context import ContextAssembler
                    context = ContextAssembler().assemble_scene_breakdown(story, request_id=req.get("request_id"), correlation_id=correlation, project_id=req.get("project_id"), environment=environment)
                    from vss_movie_scene_breakdown import scene_context_report
                    report=scene_context_report(context)
                    return finish("success", ExitCode.SUCCESS, {"context": context.to_json_value(), "assembly_report": report, "context_digest": context.digest}, [])
                if command == MOVIE_PROD_CONTEXT_COMMAND:
                    if frozenset(payload) != {"request","scene_breakdown"}: return finish("error",ExitCode.INVALID_INPUT,{},["production Context input is invalid"])
                    from vss_context import ContextAssembler
                    outcome=ContextAssembler().assemble_scene_production_options(payload["request"],payload["scene_breakdown"],correlation_id=correlation,environment=environment)
                    from vss_reasoning_contracts.canonicalization import thaw_json
                    return finish("success",ExitCode.SUCCESS,{"context":outcome.context.to_json_value(),"assembly_report":thaw_json(outcome.report),"summary":dict(outcome.summary)},[])
                if command == MOVIE_PROD_COMMAND:
                    if frozenset(payload) != {"request","context"}: return finish("error",ExitCode.INVALID_INPUT,{},["production request input is invalid"])
                    req, context=payload["request"],payload["context"]
                    gateway = self._reasoning_gateway
                    if gateway is None:
                        from vss_reasoning.gateway import ReasoningGateway
                        gateway = ReasoningGateway.built_in()
                    result=gateway.execute_scene_production_options(req,context,environment=environment,correlation_id=correlation,dry_run=dry_run)
                    return finish("success",ExitCode.SUCCESS,result,[])
                if command == MOVIE_REVIEW_COMMAND:
                    if frozenset(payload) != {"option_set", "request_id"}:
                        return finish("error", ExitCode.INVALID_INPUT, {}, ["option review input is invalid"])
                    from vss_movie_option_review import prepare_option_review
                    packet = prepare_option_review(payload["option_set"], request_id=payload["request_id"],
                                                   correlation_id=correlation, environment=environment)
                    return finish("success", ExitCode.SUCCESS, {"review_packet": packet}, [])
                if command == MOVIE_REVIEW_DECISION_COMMAND:
                    required = {"review_packet", "option_set", "option_id", "reviewer_id", "outcome", "rationale", "deferred_review_conditions", "request_id"}
                    if frozenset(payload) != required or not isinstance(payload["deferred_review_conditions"], list):
                        return finish("error", ExitCode.INVALID_INPUT, {}, ["option review decision input is invalid"])
                    from vss_movie_option_review import record_option_review_decision
                    decision = record_option_review_decision(
                        payload["review_packet"], payload["option_set"], option_id=payload["option_id"],
                        reviewer_id=payload["reviewer_id"], outcome=payload["outcome"], rationale=payload["rationale"],
                        deferred_review_conditions=payload["deferred_review_conditions"], request_id=payload["request_id"],
                        correlation_id=correlation, environment=environment,
                    )
                    return finish("success", ExitCode.SUCCESS, {"review_decision": decision}, [])
                if command == MOVIE_SHOT_PLAN_COMMAND:
                    required = {"decision", "review_packet", "option_set", "scene_breakdown", "request_id"}
                    if frozenset(payload) != required:
                        return finish("error", ExitCode.INVALID_INPUT, {}, ["shot-plan input is invalid"])
                    gateway = self._reasoning_gateway
                    if gateway is None:
                        from vss_reasoning.gateway import ReasoningGateway
                        gateway = ReasoningGateway.built_in()
                    result = gateway.execute_scene_shot_plan_draft(
                        payload["decision"], payload["review_packet"], payload["option_set"],
                        payload["scene_breakdown"], request_id=payload["request_id"],
                        environment=environment, correlation_id=correlation, dry_run=dry_run,
                    )
                    return finish("success", ExitCode.SUCCESS, result, [])
                if frozenset(payload) != {"request", "context"}: return finish("error", ExitCode.INVALID_INPUT, {}, ["movie breakdown input is invalid"])
                req, context = payload["request"], payload["context"]
                gateway = self._reasoning_gateway
                if gateway is None:
                    from vss_reasoning.gateway import ReasoningGateway
                    gateway = ReasoningGateway.built_in()
                result = gateway.execute_scene_breakdown(req, context, environment=environment, correlation_id=correlation, dry_run=dry_run)
                return finish("success", ExitCode.SUCCESS, result, [])
            except Exception as exc:
                from vss_context.audit import ContextAuditFailure
                from vss_movie_contracts.errors import MovieContractError
                from vss_reasoning import InvalidReasoningRequest, ReasoningAuditFailure, ReasoningBudgetExceeded, ReasoningUnavailable
                if isinstance(exc, (InvalidReasoningRequest, ReasoningBudgetExceeded, MovieContractError)): return finish("error",ExitCode.INVALID_INPUT,{},["movie input is invalid"])
                if isinstance(exc, ReasoningUnavailable): return finish("error",ExitCode.NOT_READY,{},["movie implementation is unavailable"])
                if isinstance(exc, (ContextAuditFailure, ReasoningAuditFailure)): return finish("error",ExitCode.INTERNAL_ERROR,{},["movie audit failed"])
                return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["movie operation failed"])
        if command == PERFORMANCE_COMMAND:
            from vss_performance import (
                InvalidPerformanceProfile,
                PerformanceCorrectnessFailure,
                PerformanceHarness,
                PerformanceReportFailure,
                PerformanceTimeout,
            )

            if frozenset(payload) != {"profile", "include_endurance"}:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["performance input is invalid"])
            harness = self._performance_harness or PerformanceHarness()
            try:
                summary, _ = harness.run(
                    payload["profile"], environment=environment, dry_run=dry_run,
                    include_endurance=payload["include_endurance"],
                )
                return finish("success", ExitCode.SUCCESS, summary, [])
            except InvalidPerformanceProfile:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["performance profile is invalid"])
            except PerformanceTimeout:
                return finish("error", ExitCode.TIMEOUT, {}, ["performance run timed out"])
            except PerformanceCorrectnessFailure:
                return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["performance correctness validation failed"])
            except PerformanceReportFailure:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["performance report failed"])
            except Exception:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["performance run failed"])
        if command in {KNOWLEDGE_BUILD_COMMAND, KNOWLEDGE_VALIDATE_COMMAND}:
            from vss_knowledge import KnowledgePackageBuilder
            from vss_knowledge.errors import KnowledgeAuditFailure, KnowledgePolicyDenied, UnknownKnowledgeSource
            from vss_knowledge_contracts import KnowledgeContractError

            builder = self._knowledge_builder or KnowledgePackageBuilder()
            try:
                if command == KNOWLEDGE_BUILD_COMMAND:
                    if frozenset(payload) != {"source", "purpose"}:
                        return finish("error", ExitCode.INVALID_INPUT, {}, ["knowledge build input is invalid"])
                    outcome = builder.build(payload["source"], payload["purpose"], environment, correlation)
                    return finish("success", ExitCode.SUCCESS, {"knowledge_package": outcome.package.to_json_value(), "summary": dict(outcome.summary)}, [])
                outcome = builder.validate(payload, environment, correlation)
                return finish("success", ExitCode.SUCCESS, {"valid": True, "summary": dict(outcome.summary)}, [])
            except UnknownKnowledgeSource:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["knowledge source is invalid"])
            except KnowledgePolicyDenied:
                return finish("error", ExitCode.PERMISSION_DENIED, {}, ["knowledge operation is not permitted"])
            except KnowledgeContractError:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["knowledge package is invalid"])
            except KnowledgeAuditFailure:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["knowledge audit failed"])
            except Exception:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["knowledge operation failed"])
        if command in {CONTEXT_ASSEMBLE_COMMAND, CONTEXT_VALIDATE_COMMAND}:
            from vss_context import ContextAssembler
            from vss_context.audit import ContextAuditFailure
            from vss_context_contracts import ContextContractError, validate_context

            assembler = ContextAssembler()
            try:
                if command == CONTEXT_ASSEMBLE_COMMAND:
                    if frozenset(payload) != {"request", "packages"} or not isinstance(payload["request"], dict) or not isinstance(payload["packages"], list):
                        return finish("error", ExitCode.INVALID_INPUT, {}, ["context assembly input is invalid"])
                    outcome = assembler.assemble(payload["request"], payload["packages"], correlation_id=correlation, dry_run=dry_run)
                    if dry_run:
                        return finish("success", ExitCode.SUCCESS, outcome, [])
                    return finish("success", ExitCode.SUCCESS, {"context": outcome.context.to_json_value(), "assembly_report": outcome.report.to_json_value(), "summary": dict(outcome.summary)}, [])
                if payload.get("context_family") in {"scene_production_options_context", "character_continuity_context"} and (payload.get("correlation_id") != correlation or payload.get("environment") != environment):
                    return finish("error", ExitCode.INVALID_INPUT, {}, ["context binding is invalid"])
                validated = validate_context(payload, assembler.registry)
                return finish("success", ExitCode.SUCCESS, {"valid": True, "summary": {"context_id": validated.value["context_id"], "context_content_digest": validated.value["context_content_digest"], "complete_context_digest": validated.digest}}, [])
            except ContextAuditFailure:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["context audit failed"])
            except ContextContractError:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["context is invalid"])
            except Exception:
                return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["context assembly failed"])
        if command == REASONING_COMMAND:
            from vss_reasoning import (
                CandidateGenerationFailure,
                InvalidReasoningRequest,
                InvalidReasoningResult,
                ReasoningAuditFailure,
                ReasoningBudgetExceeded,
                ReasoningDeadlineExceeded,
                ReasoningUnauthorized,
                ReasoningUnavailable,
            )
            from vss_reasoning.gateway import ReasoningGateway

            gateway = self._reasoning_gateway or ReasoningGateway.built_in()
            try:
                outcome = gateway.execute(
                    payload.get("semantic_request", payload),
                    environment=environment,
                    correlation_id=correlation,
                    dry_run=dry_run,
                    timeout_seconds=timeout_seconds,
                    context_data=payload.get("context") if "semantic_request" in payload else None,
                )
                return finish("success", ExitCode.SUCCESS, dict(outcome.output), [])
            except InvalidReasoningRequest:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["semantic request is invalid"])
            except ReasoningUnauthorized:
                return finish("error", ExitCode.PERMISSION_DENIED, {}, ["reasoning request is not authorized"])
            except ReasoningDeadlineExceeded:
                return finish("error", ExitCode.TIMEOUT, {}, ["reasoning deadline exceeded"])
            except ReasoningBudgetExceeded:
                return finish("error", ExitCode.INVALID_INPUT, {}, ["reasoning budget exceeded"])
            except ReasoningUnavailable:
                return finish("error", ExitCode.NOT_READY, {}, ["reasoning implementation is unavailable"])
            except (CandidateGenerationFailure, InvalidReasoningResult):
                return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["reasoning generation failed"])
            except ReasoningAuditFailure:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["reasoning audit failed"])
            except Exception:
                return finish("error", ExitCode.INTERNAL_ERROR, {}, ["reasoning operation failed"])
        if command in RUNTIME_CAPABILITY_COMMANDS:
            from vss_runtime import RuntimeController

            runtime_controller = self._runtime_controller or RuntimeController()
            return runtime_controller.run(
                command=command,
                environment=environment,
                configuration=configuration,
                input_data=payload,
                correlation_id=correlation,
                started_at=started_at,
                started_clock=started_clock,
                dry_run=dry_run,
                timeout_seconds=timeout_seconds,
                verbose=verbose,
                ask_become_pass=ask_become_pass,
            )
        errors = sorted(Draft202012Validator(registered.metadata.input_schema).iter_errors(payload), key=lambda e: list(e.path))
        if errors:
            return finish("error", ExitCode.INVALID_INPUT, {}, [f"invalid input: {errors[0].message}"])
        if dry_run and not registered.metadata.supports_dry_run:
            return finish("error", ExitCode.INVALID_INPUT, {}, ["command does not support dry-run"])

        context = CommandContext(environment, configuration, correlation, verbose, ask_become_pass)
        # Interactive children must remain on the main thread so terminal
        # signals such as Ctrl+C reach subprocess.run and its foreground child.
        terminal_bootstrap = command == "bootstrap.local" and all(
            stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)
        )
        if ask_become_pass or terminal_bootstrap:
            try:
                output = registered.handler(context, payload, dry_run)
                return finish("success", ExitCode.SUCCESS, output, [])
            except KeyboardInterrupt:
                return finish("error", ExitCode.INTERRUPTED, {}, ["command interrupted"])
            except SafeCommandError as exc:
                return finish("error", exc.exit_code, exc.output, [str(exc)])
            except Exception:
                return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["command execution failed"])

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(registered.handler, context, payload, dry_run)
        try:
            output = future.result(timeout=timeout_seconds)
            return finish("success", ExitCode.SUCCESS, output, [])
        except concurrent.futures.TimeoutError:
            return finish("error", ExitCode.TIMEOUT, {}, ["command timed out"])
        except KeyboardInterrupt:
            return finish("error", ExitCode.INTERRUPTED, {}, ["command interrupted"])
        except SafeCommandError as exc:
            return finish("error", exc.exit_code, exc.output, [str(exc)])
        except Exception:
            return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["command execution failed"])
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def response_json(response: dict[str, Any]) -> str:
    return json.dumps(response, sort_keys=True, separators=(",", ":"))
