from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from vss_providers import ControlledFrameResult
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import thaw_json
from vss_runtime.errors import CapabilityExecutionFailure, RuntimeInternalFailure

from .approval import approval_digest
from .contracts import (
    validate_attempt, validate_attempt_outcome, validate_candidate_media, validate_empty_review,
    validate_generation_request,
)
from .service import content_credentials_summary


class ControlledGenerationArtifactPublisher:
    """Create-once attempt state with audit-gated candidate admission."""

    def __init__(self, repository_root: Path, request: Mapping[str, Any], approval: Mapping[str, Any] | None) -> None:
        self.repository_root = repository_root.resolve(strict=True)
        self.request = validate_generation_request(thaw_json(request))
        self.approval = thaw_json(approval) if approval is not None else None
        self.root = self.repository_root / ".local/movie/m10-0-controlled-review-frame" / self.request["request_sha256"]
        self._ready = False
        self._reserved = False
        self._staged: list[tuple[Path, Path]] = []
        self._attempt: dict[str, Any] | None = None
        self._pending_evidence: dict[str, Any] | None = None
        self._pending_candidate_sha256: str | None = None
        self._outcome_written = False
        self._validate_root(create=False)

    def _validate_root(self, *, create: bool) -> None:
        current = self.repository_root
        for name in (".local", "movie", "m10-0-controlled-review-frame", self.request["request_sha256"]):
            current = current / name
            try:
                info = current.lstat()
            except FileNotFoundError:
                if not create:
                    continue
                current.mkdir(mode=0o700)
                info = current.lstat()
            except OSError as exc:
                raise CapabilityExecutionFailure("controlled generation output root is unsafe") from exc
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CapabilityExecutionFailure("controlled generation output root is unsafe")
        if create:
            resolved = self.root.resolve(strict=True)
            if resolved != self.root or not resolved.is_relative_to(self.repository_root):
                raise CapabilityExecutionFailure("controlled generation output root escapes repository")

    @staticmethod
    def _writable_ancestor(path: Path) -> bool:
        current = path
        while not current.exists():
            if current.parent == current:
                return False
            current = current.parent
        try:
            info = current.lstat()
        except OSError:
            return False
        return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and os.access(current, os.W_OK | os.X_OK)

    @staticmethod
    def _json(value: dict[str, Any]) -> bytes:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"

    def check_readiness(self) -> None:
        self._validate_root(create=False)
        if self.root.exists():
            try:
                if any(self.root.iterdir()):
                    raise CapabilityExecutionFailure("controlled generation request was already consumed")
            except OSError as exc:
                raise CapabilityExecutionFailure("controlled generation output root is unsafe") from exc
        if not self._writable_ancestor(self.root):
            raise CapabilityExecutionFailure("controlled generation output root is not ready")
        self._ready = True

    def reserve(self, attempt_id: str) -> None:
        if not self._ready or self._reserved or self.approval is None:
            raise CapabilityExecutionFailure("controlled generation reservation is invalid")
        if not isinstance(attempt_id, str) or len(attempt_id) != 32 or any(c not in "0123456789abcdef" for c in attempt_id):
            raise CapabilityExecutionFailure("controlled generation attempt identity is invalid")
        self._validate_root(create=True)
        os.chmod(self.root, 0o700)
        try:
            if any(self.root.iterdir()):
                raise CapabilityExecutionFailure("controlled generation request was already consumed")
        except OSError as exc:
            raise CapabilityExecutionFailure("controlled generation output root is unsafe") from exc
        attempt = {
            "schema_version": "1", "contract_identity": "controlled_media_generation_attempt",
            "contract_version": "1", "request_sha256": self.request["request_sha256"],
            "approval_sha256": approval_digest(self.approval), "attempt_id": attempt_id,
            "status": "attempted", "provider_identity": self.request["provider"]["identity"],
            "model_snapshot": self.request["provider"]["model_snapshot"], "maximum_provider_attempts": 1,
            "reserved_cost_usd": self.request["bounds"]["maximum_cost_usd"], "attempt_sha256": "0" * 64,
        }
        attempt["attempt_sha256"] = canonical_digest(attempt)
        validate_attempt(attempt)
        destination = self.root / "attempt.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(destination, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self._json(attempt)); stream.flush(); os.fsync(stream.fileno())
        except OSError as exc:
            raise CapabilityExecutionFailure("controlled generation attempt reservation failed") from exc
        self._attempt = attempt
        self._reserved = True

    def _temporary(self, content: bytes) -> Path:
        descriptor, name = tempfile.mkstemp(prefix=".stage-", dir=self.root)
        path = Path(name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
        except Exception:
            try: os.close(descriptor)
            except OSError: pass
            path.unlink(missing_ok=True)
            raise
        return path

    @staticmethod
    def _unavailable_evidence() -> dict[str, Any]:
        return {
            "response": {"availability": "unavailable", "response_sha256": None,
                         "provider_created": None, "request_id": None, "latency_ms": None},
            "usage_and_cost": {"availability": "unavailable", "input_tokens": None,
                               "output_tokens": None, "total_tokens": None,
                               "estimated_cost_usd": None},
            "media": {"availability": "unavailable", "content_sha256": None,
                      "byte_count": None, "content_credentials": None},
        }

    def _build_outcome(self, *, terminal_status: str, classification: str,
                       evidence: Mapping[str, Any] | None,
                       candidate_sha256: str | None) -> dict[str, Any]:
        if self._attempt is None or self.approval is None:
            raise CapabilityExecutionFailure("controlled generation outcome lacks its reservation")
        material = dict(evidence or self._unavailable_evidence())
        outcome = {
            "schema_version": "1", "contract_identity": "controlled_media_generation_attempt_outcome",
            "contract_version": "1", "request_sha256": self.request["request_sha256"],
            "approval_sha256": approval_digest(self.approval),
            "attempt_sha256": self._attempt["attempt_sha256"],
            "terminal_status": terminal_status, "classification": classification,
            "provider": {
                "identity": self.request["provider"]["identity"],
                "version": self.request["provider"]["version"],
                "implementation_identity": self.request["provider"]["implementation_identity"],
                "model_snapshot": self.request["provider"]["model_snapshot"],
            },
            "provider_call_count": 1,
            "response": dict(material["response"]),
            "usage_and_cost": dict(material["usage_and_cost"]),
            "media": dict(material["media"]),
            "candidate_sha256": candidate_sha256,
            "authority": {key: False for key in (
                "production", "asset", "publication", "export", "workflow", "scheduling",
                "provider_execution", "runtime_execution",
            )},
            "outcome_sha256": "0" * 64,
        }
        outcome["outcome_sha256"] = canonical_digest(outcome)
        return validate_attempt_outcome(outcome)

    def _record_outcome(self, outcome: dict[str, Any]) -> None:
        if self._outcome_written:
            return
        destination = self.root / "attempt-outcome.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(destination, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self._json(outcome)); stream.flush(); os.fsync(stream.fileno())
        except OSError as exc:
            raise RuntimeInternalFailure("controlled generation attempt outcome failed") from exc
        self._outcome_written = True

    def record_provider_failure(self, failure: Exception) -> None:
        classification = getattr(failure, "classification", "provider_failed")
        if classification not in {"response_invalid", "output_invalid", "cost_exceeded", "provider_failed"}:
            classification = "provider_failed"
        evidence = getattr(failure, "evidence", None)
        terminal = "output_rejected" if classification in {
            "response_invalid", "output_invalid", "cost_exceeded",
        } else "provider_failed"
        self._record_outcome(self._build_outcome(
            terminal_status=terminal, classification=classification,
            evidence=evidence if isinstance(evidence, Mapping) else None,
            candidate_sha256=None,
        ))

    def stage(self, result: ControlledFrameResult) -> Mapping[str, str]:
        if (not self._reserved or self._attempt is None or self.approval is None
                or self._staged or self._outcome_written):
            raise CapabilityExecutionFailure("controlled generation staging is invalid")
        scope = self.request["scope"]
        credentials = content_credentials_summary(result.media.content)
        if dict(result.content_credentials) != credentials:
            raise CapabilityExecutionFailure("controlled generation metadata reconstruction mismatch")
        candidate = {
            "schema_version": "1", "contract_identity": "generated_review_candidate", "contract_version": "2",
            "candidate_id": "generated-review-" + "0" * 32, "status": "development_review_quarantined",
            "request_sha256": self.request["request_sha256"], "approval_sha256": approval_digest(self.approval),
            "attempt_sha256": self._attempt["attempt_sha256"],
            "lineage": dict(self.request["lineage"]),
            "scope": {key: scope[key] for key in (
                "tenant_id", "universe_id", "production_id", "project_id", "scene_id", "frame_id",
            )},
            "capability": dict(self.request["capability"]),
            "provider": {"identity": self.request["provider"]["identity"], "version": self.request["provider"]["version"],
                         "implementation_identity": self.request["provider"]["implementation_identity"],
                         "model_snapshot": self.request["provider"]["model_snapshot"], "endpoint": self.request["provider"]["endpoint"],
                         "settings": dict(self.request["provider"]["settings"]),
                         "provider_request_sha256": self.request["provider"]["provider_request_sha256"],
                         "projection_sha256": self.request["projection"]["projection_sha256"],
                         "price_policy_identity": self.request["provider"]["price_policy_identity"],
                         "data_policy_identity": self.request["provider"]["data_policy_identity"],
                         "output_policy_identity": self.request["provider"]["output_policy_identity"],
                         "manifest_sha256": self.request["provider"]["manifest_sha256"],
                         "implementation_sha256": self.request["provider"]["implementation_sha256"]},
            "response": {"response_sha256": result.response_sha256, "provider_created": result.provider_created,
                         "request_id": result.request_id, "latency_ms": result.latency_ms,
                         "usage": dict(result.usage), "estimated_cost_usd": result.estimated_cost_usd},
            "media": {"content_sha256": result.media.content_sha256, "media_type": result.media.media_type,
                      "width": result.media.width, "height": result.media.height,
                      "byte_count": len(result.media.content), "content_credentials": credentials},
            "eligibility": {"input": "eligible_public_external_processing",
                            "output": "quarantined_development_review_only"},
            "preservation": {"policy": "disposable_local", "durable": False,
                             "reproducibility": "identity_and_provenance_only"},
            "authority": {"production": False, "asset": False, "publication": False, "export": False,
                          "workflow": False, "scheduling": False, "provider_execution": False,
                          "runtime_execution": False},
            "limitations": ["development_review_media_only", "not_a_final_selection", "not_a_production_asset",
                            "not_reproducible_pixels", "content_credentials_not_verified",
                            "no_retention_guarantee"],
            "candidate_sha256": "0" * 64,
        }
        candidate["candidate_id"] = "generated-review-" + canonical_digest({
            key: item for key, item in candidate.items() if key not in {"candidate_id", "candidate_sha256"}
        })[:32]
        candidate["candidate_sha256"] = canonical_digest(candidate)
        validate_candidate_media(candidate, result.media.content)
        review = {
            "schema_version": "1", "contract_identity": "generated_review_candidate_review", "contract_version": "1",
            "candidate_sha256": candidate["candidate_sha256"],
            "inspection_questions": ["narrative_relationship_and_action_legible", "no_control_plane_text",
                                     "deliberate_ambiguity_preserved", "artistic_interpretation_bounded",
                                     "no_canonical_contradiction"],
            "disposition": None, "reviewer_accountability_id": None, "review_sha256": "0" * 64,
        }
        review["review_sha256"] = canonical_digest(review)
        validate_empty_review(review)
        evidence = {
            "response": {"availability": "available", "response_sha256": result.response_sha256,
                         "provider_created": result.provider_created, "request_id": result.request_id,
                         "latency_ms": result.latency_ms},
            "usage_and_cost": {"availability": "available", **dict(result.usage),
                               "estimated_cost_usd": result.estimated_cost_usd},
            "media": {"availability": "available", "content_sha256": result.media.content_sha256,
                      "byte_count": len(result.media.content), "content_credentials": credentials},
        }
        self._pending_evidence = evidence
        self._pending_candidate_sha256 = candidate["candidate_sha256"]
        self._staged = [
            (self._temporary(result.media.content), self.root / "image.png"),
            (self._temporary(self._json(review)), self.root / "review.json"),
            (self._temporary(self._json(candidate)), self.root / "generated-review-candidate.json"),
        ]
        return {"artifact_root": str(self.root.relative_to(self.repository_root)),
                "image": str((self.root / "image.png").relative_to(self.repository_root)),
                "candidate": str((self.root / "generated-review-candidate.json").relative_to(self.repository_root)),
                "review": str((self.root / "review.json").relative_to(self.repository_root)),
                "attempt_outcome": str((self.root / "attempt-outcome.json").relative_to(self.repository_root))}

    def publish(self) -> None:
        linked: list[Path] = []
        try:
            for source, destination in self._staged:
                os.link(source, destination, follow_symlinks=False)
                source.unlink()
                linked.append(destination)
            outcome = self._build_outcome(
                terminal_status="admitted", classification="admitted",
                evidence=self._pending_evidence,
                candidate_sha256=self._pending_candidate_sha256,
            )
            self._record_outcome(outcome)
        except (OSError, RuntimeInternalFailure) as exc:
            for destination in reversed(linked):
                destination.unlink(missing_ok=True)
            self._staged = []
            if not self._outcome_written:
                try:
                    self._record_outcome(self._build_outcome(
                        terminal_status="output_rejected", classification="publication_failed",
                        evidence=self._pending_evidence, candidate_sha256=None,
                    ))
                except RuntimeInternalFailure:
                    pass
            raise RuntimeInternalFailure("controlled generation artifact publication failed") from exc
        self._staged = []

    def abort(self) -> None:
        for source, _ in self._staged:
            source.unlink(missing_ok=True)
        self._staged = []
        if self._reserved and not self._outcome_written:
            self._record_outcome(self._build_outcome(
                terminal_status="output_rejected" if self._pending_evidence is not None else "ambiguous",
                classification="runtime_or_audit_failed" if self._pending_evidence is not None else "ambiguous",
                evidence=self._pending_evidence, candidate_sha256=None,
            ))
