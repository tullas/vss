"""Shared meanings for the irreversible provider boundary."""

from __future__ import annotations

from typing import Any, Mapping


def provider_acceptance_evidenced(diagnostic: Any = None, evidence: Mapping[str, Any] | None = None) -> bool:
    operation = getattr(diagnostic, "operation_name", None) if diagnostic is not None else None
    if (getattr(diagnostic, "submission_accepted", False) is True
            and isinstance(operation, str) and bool(operation)):
        return True
    return (isinstance(evidence, Mapping) and evidence.get("submission_accepted") is True
            and isinstance(evidence.get("operation_name"), str) and bool(evidence["operation_name"]))


def retry_permitted(*, accepted: bool) -> bool:
    return not accepted


def same_operation_recovery_required(*, accepted: bool) -> bool:
    return accepted
