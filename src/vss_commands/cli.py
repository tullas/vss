from __future__ import annotations

import argparse
import json
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

        value = load_json_document(path.read_bytes())
    except (OSError, SemanticContractError):
        # Contract failures are deliberately collapsed at the CLI boundary.
        return None, ExitCode.INVALID_INPUT
    if not isinstance(value, dict):
        return None, ExitCode.INVALID_INPUT
    return value, None


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

    if args.action == "reasoning":
        input_data, input_error = _read_reasoning_input(args.input)
    else:
        input_data, input_error = _read_input(args.input)
    if input_error is not None:
        print(json.dumps({"error": "input must be valid JSON object"}, sort_keys=True, separators=(",", ":")))
        return int(input_error)
    if args.action == "run":
        command_name = args.command
    elif args.action == "bootstrap":
        command_name = f"bootstrap.{args.bootstrap_action}"
    elif args.action == "reasoning":
        command_name = "reasoning.generate-options"
    else:
        command_name = f"{args.action}.{getattr(args, f'{args.action}_action')}"
    if args.action == "secrets" and args.secrets_action == "init":  # pragma: allowlist secret
        input_data = {"rotate": args.rotate, "confirmed": args.yes}
    elif args.action == "platform" and args.platform_action in ("up", "down"):
        input_data = {"non_interactive": args.non_interactive}
        if args.platform_action == "down":
            input_data["confirmed"] = args.yes
    response, exit_code = CommandRunner().run(
        command_name,
        args.environment,
        input_data,
        args.correlation_id,
        args.dry_run,
        args.timeout,
        args.verbose,
        args.ask_become_pass,
    )
    print(response_json(response))
    return int(exit_code)
