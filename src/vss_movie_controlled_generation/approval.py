from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any

from vss_reasoning_contracts import canonical_bytes, canonical_digest
from vss_resource_contracts import ResourceContractError, ResourceContractRegistry

from .contracts import validate_generation_request


AUTHORITY_IDENTITY = "vss.controlled-media.local-human-approver/1"
APPROVER_SECRET_NAME = "VSS_CONTROLLED_MEDIA_APPROVER_HMAC_KEY"  # pragma: allowlist secret
KEY_EPOCH = 1


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ResourceContractError("controlled media approval time is invalid") from exc


def _material(value: dict[str, Any]) -> dict[str, Any]:
    return {**value, "signature": "0" * 64}


def _key(secret: str) -> bytes:
    if not isinstance(secret, str) or not 32 <= len(secret) <= 512:
        raise ResourceContractError("controlled media approval credential is unavailable")
    return secret.encode("utf-8")


def issue_approval(request: dict[str, Any], *, recorded_by: str, secret: str,
                   issued_at: str, expires_at: str) -> dict[str, Any]:
    request = validate_generation_request(request)
    issued = _parse_time(issued_at)
    expires = _parse_time(expires_at)
    if not issued < expires or (expires - issued).total_seconds() > 900:
        raise ResourceContractError("controlled media approval expiry is invalid")
    value = {
        "schema_version": "1", "contract_identity": "controlled_media_generation_approval",
        "contract_version": "1", "operation_identity": request["operation_identity"],
        "operation_version": request["operation_version"], "request_sha256": request["request_sha256"],
        "environment": request["environment"], "purpose": request["purpose"],
        "provider_identity": request["provider"]["identity"],
        "model_snapshot": request["provider"]["model_snapshot"],
        "maximum_provider_attempts": request["bounds"]["maximum_provider_attempts"],
        "maximum_cost_usd": request["bounds"]["maximum_cost_usd"], "reusable": False,
        "issued_at": issued_at, "expires_at": expires_at, "authority_identity": AUTHORITY_IDENTITY,
        "key_epoch": KEY_EPOCH, "recorded_by": recorded_by, "signature": "0" * 64,
    }
    value["signature"] = hmac.new(_key(secret), canonical_bytes(_material(value)), hashlib.sha256).hexdigest()
    errors = list(ResourceContractRegistry.built_in().iter_errors("controlled_media_generation_approval/1", value))
    if errors:
        raise ResourceContractError("controlled media approval does not match its contract")
    return value


def verify_approval(approval: Any, request: dict[str, Any], *, secret: str,
                    now: str, key_epoch: int = KEY_EPOCH) -> dict[str, Any]:
    request = validate_generation_request(request)
    if not isinstance(approval, dict):
        raise ResourceContractError("controlled media approval is required")
    errors = list(ResourceContractRegistry.built_in().iter_errors("controlled_media_generation_approval/1", approval))
    if errors:
        raise ResourceContractError("controlled media approval does not match its contract")
    expected = hmac.new(_key(secret), canonical_bytes(_material(approval)), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(approval["signature"], expected):
        raise ResourceContractError("controlled media approval signature mismatch")
    if approval["key_epoch"] != key_epoch:
        raise ResourceContractError("controlled media approval is revoked")
    current = _parse_time(now)
    issued = _parse_time(approval["issued_at"])
    expires = _parse_time(approval["expires_at"])
    if (expires - issued).total_seconds() > 900 or current < issued or current >= expires:
        raise ResourceContractError("controlled media approval is not currently valid")
    expected_binding = {
        "request_sha256": request["request_sha256"], "environment": request["environment"],
        "purpose": request["purpose"], "provider_identity": request["provider"]["identity"],
        "model_snapshot": request["provider"]["model_snapshot"],
        "maximum_provider_attempts": request["bounds"]["maximum_provider_attempts"],
        "maximum_cost_usd": request["bounds"]["maximum_cost_usd"],
    }
    if any(approval[key] != item for key, item in expected_binding.items()):
        raise ResourceContractError("controlled media approval binding mismatch")
    return approval


def approval_digest(approval: dict[str, Any]) -> str:
    return canonical_digest(approval)
