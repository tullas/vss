from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from .exit_codes import ExitCode
from .registry import get_command, list_commands
from .runner import CommandRunner, response_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vss")
    subparsers = parser.add_subparsers(dest="action", required=True)
    def add_execution_options(parser: argparse.ArgumentParser, *, input_required: bool = False) -> None:
        parser.add_argument("--environment", required=True)
        parser.add_argument("--input", type=Path, required=input_required)
        parser.add_argument("--correlation-id")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--timeout", type=float)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--ask-become-pass", action="store_true")

    run = subparsers.add_parser("run")
    run.add_argument("command")
    add_execution_options(run)
    bootstrap = subparsers.add_parser("bootstrap")
    bootstrap_actions = bootstrap.add_subparsers(dest="bootstrap_action", required=True)
    for action in ("check", "local", "verify"):
        action_parser = bootstrap_actions.add_parser(action)
        add_execution_options(action_parser)
    secrets = subparsers.add_parser("secrets")
    secrets_actions = secrets.add_subparsers(dest="secrets_action", required=True)
    secrets_init = secrets_actions.add_parser("init")
    add_execution_options(secrets_init)
    secrets_init.add_argument("--rotate", action="store_true")
    secrets_init.add_argument("--yes", action="store_true")
    secrets_status = secrets_actions.add_parser("status")
    add_execution_options(secrets_status)
    platform = subparsers.add_parser("platform")
    platform_actions = platform.add_subparsers(dest="platform_action", required=True)
    for action in ("plan", "up", "status", "verify", "down"):
        action_parser = platform_actions.add_parser(action)
        add_execution_options(action_parser)
        if action in ("up", "down"):
            action_parser.add_argument("--non-interactive", action="store_true")
        if action == "down":
            action_parser.add_argument("--yes", action="store_true")
    subparsers.add_parser("list")
    describe = subparsers.add_parser("describe")
    describe.add_argument("command")
    workflow = subparsers.add_parser("workflow")
    workflow_actions = workflow.add_subparsers(dest="workflow_action", required=True)
    workflow_actions.add_parser("list")
    workflow_describe = workflow_actions.add_parser("describe")
    workflow_describe.add_argument("workflow_name")
    workflow_run = workflow_actions.add_parser("run")
    workflow_run.add_argument("workflow_name")
    workflow_run.add_argument("--environment", required=True)
    workflow_run.add_argument("--correlation-id")
    reasoning = subparsers.add_parser("reasoning")
    reasoning_actions = reasoning.add_subparsers(dest="reasoning_action", required=True)
    generate_options = reasoning_actions.add_parser("generate-options")
    add_execution_options(generate_options, input_required=True)
    generate_options.add_argument("--context", type=Path)
    performance = subparsers.add_parser("performance")
    performance_actions = performance.add_subparsers(dest="performance_action", required=True)
    performance_reasoning = performance_actions.add_parser("reasoning")
    performance_reasoning.add_argument("--profile", required=True)
    performance_reasoning.add_argument("--environment", required=True)
    performance_reasoning.add_argument("--no-endurance", action="store_true")
    performance_reasoning.add_argument("--dry-run", action="store_true")
    knowledge = subparsers.add_parser("knowledge")
    knowledge_actions = knowledge.add_subparsers(dest="knowledge_action", required=True)
    package = knowledge_actions.add_parser("package")
    package_actions = package.add_subparsers(dest="package_action", required=True)
    package_build = package_actions.add_parser("build")
    package_build.add_argument("--source", required=True)
    package_build.add_argument("--purpose", required=True)
    package_build.add_argument("--environment", required=True)
    package_build.add_argument("--correlation-id")
    package_validate = package_actions.add_parser("validate")
    package_validate.add_argument("--input", type=Path, required=True)
    package_validate.add_argument("--environment", required=True)
    package_validate.add_argument("--correlation-id")
    context = subparsers.add_parser("context")
    context_actions = context.add_subparsers(dest="context_action", required=True)
    context_assemble = context_actions.add_parser("assemble")
    context_assemble.add_argument("--request", type=Path, required=True)
    context_assemble.add_argument("--package", type=Path, action="append", required=True)
    context_assemble.add_argument("--environment", required=True)
    context_assemble.add_argument("--correlation-id")
    context_assemble.add_argument("--dry-run", action="store_true")
    context_validate = context_actions.add_parser("validate")
    context_validate.add_argument("--input", type=Path, required=True)
    context_validate.add_argument("--environment", required=True)
    context_validate.add_argument("--correlation-id")
    movie = subparsers.add_parser("movie")
    movie_actions = movie.add_subparsers(dest="movie_action", required=True)
    movie_demo = movie_actions.add_parser("demo")
    movie_demo.add_argument("--story", type=Path, required=True)
    movie_demo.add_argument("--reviewer-id", required=True)
    movie_demo.add_argument("--correlation-id", default="local-movie-demo")
    movie_demo.add_argument("--option-id")
    movie_demo.add_argument("--rationale", default="Accepted at human review for a local shot-plan draft demo.")
    movie_demo.add_argument("--storyboard-specification", action="store_true")
    movie_demo.add_argument("--render-storyboard", action="store_true")
    movie_break = movie_actions.add_parser("break-down-scenes")
    movie_break.add_argument("--request", type=Path, required=True)
    movie_break.add_argument("--context", type=Path, required=True)
    movie_break.add_argument("--environment", required=True)
    movie_break.add_argument("--correlation-id", required=True)
    movie_break.add_argument("--dry-run", action="store_true")
    movie_assemble = movie_actions.add_parser("context-assemble-scene-breakdown")
    movie_assemble.add_argument("--request", type=Path, required=True)
    movie_assemble.add_argument("--story", type=Path, required=True)
    movie_assemble.add_argument("--environment", required=True)
    movie_assemble.add_argument("--correlation-id", required=True)
    movie_prod = movie_actions.add_parser("context-assemble-scene-production-options")
    movie_prod.add_argument("--request", type=Path, required=True); movie_prod.add_argument("--scene-breakdown", type=Path, required=True); movie_prod.add_argument("--environment", required=True); movie_prod.add_argument("--correlation-id", required=True)
    movie_gen = movie_actions.add_parser("generate-scene-production-options")
    movie_gen.add_argument("--request", type=Path, required=True); movie_gen.add_argument("--context", type=Path, required=True); movie_gen.add_argument("--environment", required=True); movie_gen.add_argument("--correlation-id", required=True); movie_gen.add_argument("--dry-run",action="store_true")
    movie_review = movie_actions.add_parser("prepare-option-review")
    movie_review.add_argument("--input", type=Path, required=True); movie_review.add_argument("--environment", required=True); movie_review.add_argument("--correlation-id", required=True); movie_review.add_argument("--request-id", required=True)
    movie_decision = movie_actions.add_parser("record-option-review-decision")
    movie_decision.add_argument("--review-packet", type=Path, required=True)
    movie_decision.add_argument("--option-set", type=Path, required=True)
    movie_decision.add_argument("--option-id", required=True); movie_decision.add_argument("--reviewer-id", required=True)
    movie_decision.add_argument("--outcome", required=True); movie_decision.add_argument("--rationale", required=True)
    movie_decision.add_argument("--deferred-condition", action="append", default=[])
    movie_decision.add_argument("--request-id", required=True); movie_decision.add_argument("--environment", required=True); movie_decision.add_argument("--correlation-id", required=True)
    movie_shots = movie_actions.add_parser("create-shot-plan-draft")
    movie_shots.add_argument("--decision", type=Path, required=True)
    movie_shots.add_argument("--review-packet", type=Path, required=True)
    movie_shots.add_argument("--option-set", type=Path, required=True)
    movie_shots.add_argument("--scene-breakdown", type=Path, required=True)
    movie_shots.add_argument("--request-id", required=True); movie_shots.add_argument("--environment", required=True); movie_shots.add_argument("--correlation-id", required=True); movie_shots.add_argument("--dry-run", action="store_true")
    movie_storyboard = movie_actions.add_parser("create-storyboard-specification")
    movie_storyboard.add_argument("--decision", type=Path, required=True)
    movie_storyboard.add_argument("--review-packet", type=Path, required=True)
    movie_storyboard.add_argument("--option-set", type=Path, required=True)
    movie_storyboard.add_argument("--scene-breakdown", type=Path, required=True)
    movie_storyboard.add_argument("--shot-plan", type=Path, required=True)
    movie_storyboard.add_argument("--request-id", required=True); movie_storyboard.add_argument("--environment", required=True); movie_storyboard.add_argument("--correlation-id", required=True); movie_storyboard.add_argument("--dry-run", action="store_true")
    movie_render = movie_actions.add_parser("render-storyboard")
    movie_render.add_argument("--decision", type=Path, required=True)
    movie_render.add_argument("--review-packet", type=Path, required=True)
    movie_render.add_argument("--option-set", type=Path, required=True)
    movie_render.add_argument("--scene-breakdown", type=Path, required=True)
    movie_render.add_argument("--shot-plan", type=Path, required=True)
    movie_render.add_argument("--storyboard", type=Path, required=True)
    movie_render.add_argument("--environment", required=True)
    movie_render.add_argument("--correlation-id", required=True)
    movie_render.add_argument("--dry-run", action="store_true")
    movie_render.add_argument("--timeout", type=float)
    movie_pictorial = movie_actions.add_parser("generate-pictorial-frame")
    for flag in ("decision", "review-packet", "option-set", "scene-breakdown", "shot-plan", "storyboard"):
        movie_pictorial.add_argument(f"--{flag}", type=Path, required=True)
    movie_pictorial.add_argument("--frame-id", required=True)
    movie_pictorial.add_argument("--environment", required=True)
    movie_pictorial.add_argument("--correlation-id", required=True)
    movie_pictorial.add_argument("--dry-run", action="store_true")
    movie_pictorial.add_argument("--timeout", type=float)
    movie_smoke = movie_actions.add_parser("m8-3-real-provider-smoke-2")
    for flag in ("decision", "review-packet", "option-set", "scene-breakdown", "shot-plan", "storyboard"):
        movie_smoke.add_argument(f"--{flag}", type=Path, required=True)
    movie_smoke.add_argument("--environment", required=True)
    movie_smoke.add_argument("--correlation-id", required=True)
    movie_smoke.add_argument("--dry-run", action="store_true")
    movie_smoke_3 = movie_actions.add_parser("m8-3-real-provider-smoke-3")
    for flag in ("decision", "review-packet", "option-set", "scene-breakdown", "shot-plan", "storyboard"):
        movie_smoke_3.add_argument(f"--{flag}", type=Path, required=True)
    movie_smoke_3.add_argument("--environment", required=True)
    movie_smoke_3.add_argument("--correlation-id", required=True)
    smoke_3_mode = movie_smoke_3.add_mutually_exclusive_group(required=True)
    smoke_3_mode.add_argument("--preflight", dest="smoke_mode", action="store_const", const="preflight")
    smoke_3_mode.add_argument("--generate", dest="smoke_mode", action="store_const", const="generate")
    for action in ("context-assemble-character-continuity", "analyze-character-continuity"):
        continuity = movie_actions.add_parser(action)
        continuity.add_argument("--input", type=Path, required=True)
        continuity.add_argument("--environment", required=True)
        continuity.add_argument("--correlation-id", required=True)
        if action == "analyze-character-continuity": continuity.add_argument("--dry-run", action="store_true")
    return parser


def _read_input(path: Path | None) -> tuple[dict | None, ExitCode | None]:
    if path is None:
        return {}, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, ExitCode.INVALID_INPUT
    if not isinstance(value, dict):
        return None, ExitCode.INVALID_INPUT
    return value, None


def _read_reasoning_input(path: Path | None) -> tuple[dict | None, ExitCode | None]:
    if path is None:
        return None, ExitCode.INVALID_INPUT
    try:
        from vss_reasoning_contracts import SemanticContractError, load_json_document
        from vss_reasoning_contracts.constants import MAX_REQUEST_BYTES

        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None, ExitCode.INVALID_INPUT
            chunks: list[bytes] = []
            remaining = MAX_REQUEST_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 4096))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            document = b"".join(chunks)
            if len(document) > MAX_REQUEST_BYTES:
                return None, ExitCode.INVALID_INPUT
        finally:
            os.close(descriptor)
        value = load_json_document(document)
    except (OSError, SemanticContractError):
        # Contract failures are deliberately collapsed at the CLI boundary.
        return None, ExitCode.INVALID_INPUT
    if not isinstance(value, dict):
        return None, ExitCode.INVALID_INPUT
    return value, None


def _read_knowledge_input(path: Path | None) -> tuple[dict | None, ExitCode | None]:
    if path is None:
        return None, ExitCode.INVALID_INPUT
    try:
        from vss_knowledge_contracts import MAX_PACKAGE_BYTES, load_json_document

        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None, ExitCode.INVALID_INPUT
            document = os.read(descriptor, MAX_PACKAGE_BYTES + 1)
            if len(document) > MAX_PACKAGE_BYTES:
                return None, ExitCode.INVALID_INPUT
        finally:
            os.close(descriptor)
        value = load_json_document(document)
    except Exception:
        return None, ExitCode.INVALID_INPUT
    return (value, None) if isinstance(value, dict) else (None, ExitCode.INVALID_INPUT)


def _read_context_file(path: Path) -> tuple[dict | None, ExitCode | None]:
    # Context files are data inputs; no caller-selected implementation or schema
    # root is accepted. The Context subsystem performs the contract checks.
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None, ExitCode.INVALID_INPUT
            chunks: list[bytes] = []
            remaining = 64 * 1024 + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 4096))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > 64 * 1024:
                return None, ExitCode.INVALID_INPUT
        finally:
            os.close(descriptor)
        from vss_reasoning_contracts import load_json_document
        value = load_json_document(raw)
    except Exception:
        return None, ExitCode.INVALID_INPUT
    return (value, None) if isinstance(value, dict) else (None, ExitCode.INVALID_INPUT)


def _read_continuity_bundle(path: Path) -> tuple[dict | None, ExitCode | None]:
    """Load one bounded regular-file bundle; semantic validation remains domain-owned."""
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None, ExitCode.INVALID_INPUT
            raw = os.read(descriptor, 256 * 1024 + 1)
            if len(raw) > 256 * 1024:
                return None, ExitCode.INVALID_INPUT
        finally:
            os.close(descriptor)
        from vss_reasoning_contracts import load_json_document
        value = load_json_document(raw)
    except Exception:
        return None, ExitCode.INVALID_INPUT
    return (value, None) if isinstance(value, dict) else (None, ExitCode.INVALID_INPUT)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    if args.action == "list":
        print(json.dumps([metadata.__dict__ for metadata in list_commands()], sort_keys=True, separators=(",", ":")))
        return int(ExitCode.SUCCESS)
    if args.action == "describe":
        command = get_command(args.command)
        if command is None:
            print(json.dumps({"error": f"unknown command: {args.command}"}, sort_keys=True, separators=(",", ":")))
            return int(ExitCode.UNKNOWN_COMMAND)
        print(json.dumps(command.metadata.__dict__, sort_keys=True, separators=(",", ":")))
        return int(ExitCode.SUCCESS)
    if args.action == "workflow":
        from vss_workflows import WorkflowController
        from vss_workflows.errors import WorkflowFailure

        controller = WorkflowController()
        try:
            if args.workflow_action == "list":
                print(json.dumps(controller.list_workflows(), sort_keys=True, separators=(",", ":")))
                return int(ExitCode.SUCCESS)
            if args.workflow_action == "describe":
                description = controller.describe_workflow(args.workflow_name)
                print(json.dumps(description, sort_keys=True, separators=(",", ":")))
                return int(ExitCode.SUCCESS)
            result, exit_code = controller.run(args.workflow_name, args.environment, args.correlation_id)
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
            return int(exit_code)
        except WorkflowFailure as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True, separators=(",", ":")))
            return int(exc.exit_code)

    if args.action == "movie":
        if args.movie_action == "demo":
            story, input_error = _read_context_file(args.story)
            if input_error is not None:
                print(json.dumps({"error": "story must be a valid JSON object"}, sort_keys=True, separators=(",", ":")))
                return int(input_error)
            try:
                from vss_movie_demo import finish_demo, prepare_demo

                prepared = prepare_demo(story, correlation_id=args.correlation_id)
                entries = prepared.review_packet["payload"]["review_entries"]
                option_ids = [entry["option_id"] for entry in entries]
                option_id = args.option_id
                if option_id is None:
                    print("Production options:", file=sys.stderr)
                    for index, (entry, option) in enumerate(zip(entries, prepared.option_set["payload"]["options"]), 1):
                        print(f"  {index}. {option['profile_identity']} ({entry['option_id']})", file=sys.stderr)
                        print(f"     {option['qualified_rationale']}", file=sys.stderr)
                    print(f"Choose an option [1-{len(entries)}]: ", end="", file=sys.stderr, flush=True)
                    choice = input().strip()
                    if not choice.isdigit() or not 1 <= int(choice) <= len(entries):
                        raise ValueError("option choice is invalid")
                    option_id = option_ids[int(choice) - 1]
                if option_id not in option_ids:
                    raise ValueError("option choice is invalid")
                result = finish_demo(
                    prepared, option_id=option_id, reviewer_id=args.reviewer_id,
                    rationale=args.rationale, correlation_id=args.correlation_id,
                    include_storyboard=args.storyboard_specification or args.render_storyboard,
                )
                if args.render_storyboard:
                    render_response, render_code = CommandRunner().run(
                        "movie.render-storyboard", "development",
                        {"decision": result["review_decision"], "review_packet": result["review_packet"],
                         "option_set": result["scene_production_option_set"],
                         "scene_breakdown": result["scene_breakdown"],
                         "shot_plan": result["scene_shot_plan_draft"],
                         "storyboard": result["scene_storyboard_specification"]},
                        args.correlation_id,
                    )
                    if render_code != int(ExitCode.SUCCESS):
                        print(response_json(render_response))
                        return int(render_code)
                    result["storyboard_render"] = render_response["output"]
                print(json.dumps(result, sort_keys=True, separators=(",", ":")))
                return int(ExitCode.SUCCESS)
            except (EOFError, KeyboardInterrupt):
                print(json.dumps({"error": "movie demo input or selection is invalid"}, sort_keys=True, separators=(",", ":")))
                return int(ExitCode.INVALID_INPUT)
            except Exception:
                print(json.dumps({"error": "movie demo input or selection is invalid"}, sort_keys=True, separators=(",", ":")))
                return int(ExitCode.INVALID_INPUT)
        if args.movie_action == "prepare-option-review":
            input_data, input_error = _read_context_file(args.input)
            if input_error is None:
                input_data = {"option_set": input_data, "request_id": args.request_id}
        elif args.movie_action == "record-option-review-decision":
            review_packet, input_error = _read_context_file(args.review_packet)
            option_set, option_error = _read_context_file(args.option_set)
            input_error = input_error or option_error
            if input_error is None:
                input_data = {
                    "review_packet": review_packet, "option_set": option_set, "option_id": args.option_id,
                    "reviewer_id": args.reviewer_id, "outcome": args.outcome, "rationale": args.rationale,
                    "deferred_review_conditions": args.deferred_condition, "request_id": args.request_id,
                }
        elif args.movie_action in {"create-shot-plan-draft", "create-storyboard-specification", "render-storyboard", "generate-pictorial-frame", "m8-3-real-provider-smoke-2", "m8-3-real-provider-smoke-3"}:
            decision, input_error = _read_context_file(args.decision)
            packet, packet_error = _read_context_file(args.review_packet)
            option_set, option_error = _read_context_file(args.option_set)
            breakdown, breakdown_error = _read_context_file(args.scene_breakdown)
            input_error = input_error or packet_error or option_error or breakdown_error
            shot_plan = None
            if args.movie_action in {"create-storyboard-specification", "render-storyboard", "generate-pictorial-frame", "m8-3-real-provider-smoke-2", "m8-3-real-provider-smoke-3"}:
                shot_plan, shot_error = _read_context_file(args.shot_plan)
                input_error = input_error or shot_error
            storyboard = None
            if args.movie_action in {"render-storyboard", "generate-pictorial-frame", "m8-3-real-provider-smoke-2", "m8-3-real-provider-smoke-3"}:
                storyboard, storyboard_error = _read_context_file(args.storyboard)
                input_error = input_error or storyboard_error
            if input_error is None:
                input_data = {"decision": decision, "review_packet": packet, "option_set": option_set,
                              "scene_breakdown": breakdown}
                if args.movie_action not in {"render-storyboard", "generate-pictorial-frame", "m8-3-real-provider-smoke-2", "m8-3-real-provider-smoke-3"}: input_data["request_id"] = args.request_id
                if shot_plan is not None: input_data["shot_plan"] = shot_plan
                if storyboard is not None: input_data["storyboard"] = storyboard
                if args.movie_action == "generate-pictorial-frame": input_data["frame_id"] = args.frame_id
                if args.movie_action == "m8-3-real-provider-smoke-3": input_data["mode"] = args.smoke_mode
        elif args.movie_action in {"context-assemble-character-continuity", "analyze-character-continuity"}:
            input_data, input_error = _read_continuity_bundle(args.input)
        else:
            request, input_error = _read_context_file(args.request)
        if args.movie_action in {"context-assemble-character-continuity", "analyze-character-continuity", "prepare-option-review", "record-option-review-decision", "create-shot-plan-draft", "create-storyboard-specification", "render-storyboard", "generate-pictorial-frame", "m8-3-real-provider-smoke-2", "m8-3-real-provider-smoke-3"}:
            pass
        elif args.movie_action in {"break-down-scenes","generate-scene-production-options"}:
            context, context_error = _read_context_file(args.context)
            input_error = input_error or context_error
            input_data = {"request": request, "context": context} if input_error is None else None
        elif args.movie_action == "context-assemble-scene-production-options":
            scene_breakdown, scene_error = _read_context_file(args.scene_breakdown); input_error=input_error or scene_error
            input_data={"request":request,"scene_breakdown":scene_breakdown} if input_error is None else None
        else:
            story, story_error = _read_context_file(args.story)
            input_error = input_error or story_error
            input_data = {"request": request, "story": story} if input_error is None else None
    elif args.action == "reasoning":
        input_data, input_error = _read_reasoning_input(args.input)
    elif args.action == "performance":
        input_data, input_error = {
            "profile": args.profile,
            "include_endurance": not args.no_endurance,
        }, None
    elif args.action == "knowledge":
        if args.package_action == "build":
            input_data, input_error = {"source": args.source, "purpose": args.purpose}, None
        else:
            input_data, input_error = _read_knowledge_input(args.input)
    elif args.action == "context":
        if args.context_action == "assemble":
            request, request_error = _read_context_file(args.request)
            packages: list[dict] = []
            input_error = request_error
            if input_error is None:
                for package_path in args.package:
                    package, package_error = _read_context_file(package_path)
                    if package_error is not None:
                        input_error = package_error
                        break
                    packages.append(package)
                input_data = {"request": request, "packages": packages}
        else:
            input_data, input_error = _read_context_file(args.input)
    else:
        input_data, input_error = _read_input(args.input)
    if input_error is not None:
        print(json.dumps({"error": "input must be valid JSON object"}, sort_keys=True, separators=(",", ":")))
        return int(input_error)
    if args.action == "reasoning" and args.context is not None:
        context_value, context_error = _read_context_file(args.context)
        if context_error is not None:
            print(json.dumps({"error": "context input must be valid JSON object"}, sort_keys=True, separators=(",", ":")))
            return int(context_error)
        input_data = {"semantic_request": input_data, "context": context_value}
    if args.action == "run":
        command_name = args.command
    elif args.action == "bootstrap":
        command_name = f"bootstrap.{args.bootstrap_action}"
    elif args.action == "reasoning":
        command_name = "reasoning.generate-options"
    elif args.action == "performance":
        command_name = "performance.reasoning"
    elif args.action == "knowledge":
        command_name = f"knowledge.package.{args.package_action}"
    elif args.action == "context":
        command_name = f"context.{args.context_action}"
    elif args.action == "movie":
        command_name = {"break-down-scenes":"movie.break-down-scenes","context-assemble-scene-breakdown":"movie.context-assemble-scene-breakdown","context-assemble-scene-production-options":"movie.context-assemble-scene-production-options","generate-scene-production-options":"movie.generate-scene-production-options","prepare-option-review":"movie.prepare-option-review","record-option-review-decision":"movie.record-option-review-decision","create-shot-plan-draft":"movie.create-shot-plan-draft","create-storyboard-specification":"movie.create-storyboard-specification","render-storyboard":"movie.render-storyboard","generate-pictorial-frame":"movie.generate-pictorial-frame","m8-3-real-provider-smoke-2":"movie.m8-3-real-provider-smoke-2","m8-3-real-provider-smoke-3":"movie.m8-3-real-provider-smoke-3","context-assemble-character-continuity":"movie.context-assemble-character-continuity","analyze-character-continuity":"movie.analyze-character-continuity"}[args.movie_action]
    else:
        command_name = f"{args.action}.{getattr(args, f'{args.action}_action')}"
    if args.action == "secrets" and args.secrets_action == "init":  # pragma: allowlist secret
        input_data = {"rotate": args.rotate, "confirmed": args.yes}
    elif args.action == "platform" and args.platform_action in ("up", "down"):
        input_data = {"non_interactive": args.non_interactive}
        if args.platform_action == "down":
            input_data["confirmed"] = args.yes
    dry_run = getattr(args, "dry_run", False)
    if args.action == "movie" and args.movie_action == "m8-3-real-provider-smoke-3":
        dry_run = args.smoke_mode == "preflight"
    response, exit_code = CommandRunner().run(
        command_name,
        args.environment,
        input_data,
        getattr(args, "correlation_id", None),
        dry_run,
        getattr(args, "timeout", None),
        getattr(args, "verbose", False),
        getattr(args, "ask_become_pass", False),
    )
    print(response_json(response))
    return int(exit_code)
