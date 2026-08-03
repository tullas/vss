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
        if registered is None and command not in RUNTIME_CAPABILITY_COMMANDS and command not in {REASONING_COMMAND, PERFORMANCE_COMMAND, KNOWLEDGE_BUILD_COMMAND, KNOWLEDGE_VALIDATE_COMMAND, CONTEXT_ASSEMBLE_COMMAND, CONTEXT_VALIDATE_COMMAND, MOVIE_BREAKDOWN_COMMAND, MOVIE_CONTEXT_COMMAND}:
            return finish("error", ExitCode.UNKNOWN_COMMAND, {}, [f"unknown command: {command}"])
        try:
            configuration = load_configuration(environment)
        except ConfigError as exc:
            return finish("error", ExitCode.INVALID_CONFIGURATION, {}, [str(exc)])

        payload = input_data if input_data is not None else {}
        if not isinstance(payload, dict):
            return finish("error", ExitCode.INVALID_INPUT, {}, ["input must be a JSON object"])
        if command in {MOVIE_BREAKDOWN_COMMAND, MOVIE_CONTEXT_COMMAND}:
            from vss_movie_scene_breakdown import SceneBreakdownService
            try:
                if command == MOVIE_CONTEXT_COMMAND:
                    if frozenset(payload) != {"request", "story"}: return finish("error", ExitCode.INVALID_INPUT, {}, ["movie context input is invalid"])
                    req, story = payload["request"], payload["story"]
                    if req.get("correlation_id") != correlation or req.get("project_id") != story.get("project_id") or req.get("purpose") != "scene_breakdown_local_validation": return finish("error", ExitCode.INVALID_INPUT, {}, ["movie request binding mismatch"])
                    context = SceneBreakdownService().assemble(story, request_id=req["request_id"], correlation_id=correlation, project_id=story["project_id"])
                    return finish("success", ExitCode.SUCCESS, {"context": context.to_json_value(), "context_digest": context.digest}, [])
                if frozenset(payload) != {"request", "context"}: return finish("error", ExitCode.INVALID_INPUT, {}, ["movie breakdown input is invalid"])
                req, context = payload["request"], payload["context"]
                if req.get("correlation_id") != correlation or context.get("correlation_id") != correlation or context.get("request_id") != req.get("request_id"):
                    return finish("error", ExitCode.INVALID_INPUT, {}, ["movie correlation or request binding mismatch"])
                service=SceneBreakdownService()
                if dry_run: return finish("success", ExitCode.SUCCESS, service.execute(context, dry_run=True), [])
                result=service.execute(context)
                return finish("success", ExitCode.SUCCESS, {"scene_breakdown": result, "result_digest": canonical_digest(result)}, [])
            except Exception:
                return finish("error", ExitCode.EXECUTION_FAILURE, {}, ["movie scene breakdown failed"])
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
