from __future__ import annotations

import concurrent.futures
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from vss_config import ConfigError, load_configuration

from .exit_codes import ExitCode
from .models import CommandContext, SafeCommandError
from .registry import get_command


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def _safe_error(message: str) -> str:
    # Error text is deliberately limited to schema paths and fixed framework messages.
    return " ".join(str(message).replace("\n", " ").split())[:500]


class CommandRunner:
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
        if registered is None:
            return finish("error", ExitCode.UNKNOWN_COMMAND, {}, [f"unknown command: {command}"])
        try:
            configuration = load_configuration(environment)
        except ConfigError as exc:
            return finish("error", ExitCode.INVALID_CONFIGURATION, {}, [str(exc)])

        payload = input_data if input_data is not None else {}
        if not isinstance(payload, dict):
            return finish("error", ExitCode.INVALID_INPUT, {}, ["input must be a JSON object"])
        errors = sorted(Draft202012Validator(registered.metadata.input_schema).iter_errors(payload), key=lambda e: list(e.path))
        if errors:
            return finish("error", ExitCode.INVALID_INPUT, {}, [f"invalid input: {errors[0].message}"])
        if dry_run and not registered.metadata.supports_dry_run:
            return finish("error", ExitCode.INVALID_INPUT, {}, ["command does not support dry-run"])

        context = CommandContext(environment, configuration, correlation, verbose, ask_become_pass)
        # Interactive children must remain on the main thread so terminal
        # signals such as Ctrl+C reach subprocess.run and its foreground child.
        if ask_become_pass:
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
