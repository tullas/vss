from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SUPPORTED_ENVIRONMENTS = ("development", "staging", "production")
_SECRET_KEY = re.compile(r"(?:secret|password|token|api.?key|private.?key)", re.IGNORECASE)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    """A user-correctable configuration error."""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not read YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"configuration must be a YAML object: {path}")
    return value


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key in sorted(override):
        value = override[key]
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _validate(configuration: dict[str, Any], schema_path: Path) -> None:
    try:
        with schema_path.open(encoding="utf-8") as stream:
            schema = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not read schema {schema_path}: {exc}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(configuration), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise ConfigError(f"invalid configuration at {location}: {error.message}")


def load_configuration(environment: str, config_root: Path | str | None = None) -> dict[str, Any]:
    """Load defaults plus an environment override and validate the result."""
    if environment not in SUPPORTED_ENVIRONMENTS:
        allowed = ", ".join(SUPPORTED_ENVIRONMENTS)
        raise ConfigError(f"unknown environment '{environment}'; expected one of: {allowed}")
    root = Path(config_root) if config_root is not None else _PROJECT_ROOT / "config"
    defaults_path = root / "defaults.yml"
    environment_path = root / "environments" / f"{environment}.yml"
    schema_path = root / "schema" / "v1.json"
    if not defaults_path.is_file():
        raise ConfigError(f"missing defaults file: {defaults_path}")
    if not environment_path.is_file():
        raise ConfigError(f"missing environment file: {environment_path}")
    configuration = _merge(_read_yaml(defaults_path), _read_yaml(environment_path))
    _validate(configuration, schema_path)
    return configuration


def _redact(value: Any, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {name: _redact(child, name) for name, child in value.items()}
    if isinstance(value, list):
        return [_redact(child, key) for child in value]
    return value


def render_configuration(environment: str, config_root: Path | str | None = None) -> str:
    """Return deterministic, secret-redacted YAML for an environment."""
    return yaml.safe_dump(_redact(load_configuration(environment, config_root)), sort_keys=True)
