from __future__ import annotations

from typing import Any

from vss_commands import CommandRunner, ExitCode

ALLOWED_OPERATIONS = frozenset({"system.info", "bootstrap.check"})


class OperationRegistry:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self.command_runner = command_runner or CommandRunner()

    def execute(
        self,
        operation: str,
        environment: str,
        input_data: dict[str, Any],
        correlation_id: str,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], int]:
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError("operation is not allowlisted")
        try:
            return self.command_runner.run(
                command=operation,
                environment=environment,
                input_data=input_data,
                correlation_id=correlation_id,
                timeout_seconds=timeout_seconds,
            )
        except Exception:
            return {
                "status": "error",
                "output": {},
                "errors": ["workflow operation execution failed"],
            }, int(ExitCode.EXECUTION_FAILURE)

    def summarize(self, operation: str, output: dict[str, Any]) -> dict[str, Any]:
        if operation == "system.info":
            allowed = ("command_name", "command_version", "os", "python_version", "environment", "dry_run")
            return {key: output[key] for key in allowed if key in output}
        checks = output.get("checks", {})
        return {
            "environment": output.get("environment"),
            "dry_run": output.get("dry_run"),
            "checks": {
                "platform": {key: checks.get("platform", {}).get(key) for key in ("system", "is_wsl")},
                "systemd": {key: checks.get("systemd", {}).get(key) for key in ("active", "status")},
                "docker": {key: checks.get("docker", {}).get(key) for key in ("cli_available", "daemon_accessible")},
                "opentofu": {"available": checks.get("opentofu", {}).get("available")},
                "ports": checks.get("ports", {}),
            },
        }
