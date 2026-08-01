from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .errors import (
    InvalidWorkflow,
    RecursiveWorkflowInvocation,
    UnknownWorkflowOperation,
    UnsupportedWorkflowVersion,
)
from .models import WorkflowManifest

SUPPORTED_SCHEMA_VERSION = "1"
SUPPORTED_RUNTIME_API_VERSION = "1"
MAX_STEPS = 32
WORKFLOW_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
UNSAFE_VALUE = re.compile(r"(?:\$\{|\{\{|\$\(|`|&&|\|\||[;|]\s*(?:sh|bash|python|exec)\b)")


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidWorkflow("workflow schema is unavailable") from exc
    if not isinstance(value, dict):
        raise InvalidWorkflow("workflow schema is invalid")
    return value


def _contains_unsafe_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(UNSAFE_VALUE.search(value))
    if isinstance(value, dict):
        return any(_contains_unsafe_value(key) or _contains_unsafe_value(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_unsafe_value(item) for item in value)
    return False


def load_workflow(path: Path, schema_path: Path, allowed_operations: frozenset[str]) -> tuple[WorkflowManifest, str]:
    try:
        content = path.read_bytes()
        value = yaml.safe_load(content)
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidWorkflow("workflow YAML is malformed") from exc
    if not isinstance(value, dict):
        raise InvalidWorkflow("workflow must be an object")
    errors = sorted(Draft202012Validator(_load_schema(schema_path)).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise InvalidWorkflow(f"workflow is invalid: {errors[0].message}")
    if value["schema_version"] != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedWorkflowVersion("unsupported workflow schema version")
    if value["runtime_api_version"] != SUPPORTED_RUNTIME_API_VERSION:
        raise UnsupportedWorkflowVersion("unsupported workflow runtime API version")
    if not WORKFLOW_NAME.fullmatch(value["name"]):
        raise InvalidWorkflow("workflow name is unsafe")
    step_ids = [step["id"] for step in value["steps"]]
    if len(step_ids) != len(set(step_ids)):
        raise InvalidWorkflow("workflow contains duplicate step IDs")
    for step in value["steps"]:
        operation = step["operation"]
        if operation.startswith("workflow."):
            raise RecursiveWorkflowInvocation("recursive workflow invocation is prohibited")
        if operation not in allowed_operations:
            raise UnknownWorkflowOperation(f"unknown workflow operation: {operation}")
        if _contains_unsafe_value(step["input"]):
            raise InvalidWorkflow("workflow input contains an expression or shell fragment")
    workflow = WorkflowManifest(
        schema_version=value["schema_version"],
        name=value["name"],
        version=value["version"],
        description=value["description"],
        runtime_api_version=value["runtime_api_version"],
        execution_policy=value["execution_policy"],
        steps=tuple(value["steps"]),
    )
    return workflow, hashlib.sha256(content).hexdigest()
