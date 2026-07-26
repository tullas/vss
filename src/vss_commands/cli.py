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
    run = subparsers.add_parser("run")
    run.add_argument("command")
    run.add_argument("--environment", required=True)
    run.add_argument("--input", type=Path)
    run.add_argument("--correlation-id")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--timeout", type=float)
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
    response, exit_code = CommandRunner().run(
        args.command,
        args.environment,
        input_data,
        args.correlation_id,
        args.dry_run,
        args.timeout,
    )
    print(response_json(response))
    return int(exit_code)
