from __future__ import annotations

import argparse
import sys

from .loader import ConfigError, SUPPORTED_ENVIRONMENTS, load_configuration, render_configuration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vss_config")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "render"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--environment", required=True, choices=SUPPORTED_ENVIRONMENTS)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            load_configuration(args.environment)
            print(f"valid configuration: {args.environment}")
        else:
            print(render_configuration(args.environment), end="")
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    return 0
