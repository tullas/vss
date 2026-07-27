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
    def add_execution_options(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--environment", required=True)
        parser.add_argument("--input", type=Path)
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
    subparsers.add_parser("list")
    describe = subparsers.add_parser("describe")
    describe.add_argument("command")
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

    input_data, input_error = _read_input(args.input)
    if input_error is not None:
        print(json.dumps({"error": "input must be valid JSON object"}, sort_keys=True, separators=(",", ":")))
        return int(input_error)
    command_name = args.command if args.action == "run" else f"bootstrap.{args.bootstrap_action}"
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
