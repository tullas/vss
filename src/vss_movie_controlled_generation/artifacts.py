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
from .contracts import validate_attempt, validate_candidate, validate_empty_review, validate_generation_request


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

    def stage(self, result: ControlledFrameResult) -> Mapping[str, str]:
        if not self._reserved or self._attempt is None or self.approval is None or self._staged:
            raise CapabilityExecutionFailure("controlled generation staging is invalid")
        scope = self.request["scope"]
        candidate = {
            "schema_version": "1", "contract_identity": "generated_review_candidate", "contract_version": "1",
            "candidate_id": "generated-review-" + "0" * 32, "status": "development_review_quarantined",
            "request_sha256": self.request["request_sha256"], "approval_sha256": approval_digest(self.approval),
            "attempt_sha256": self._attempt["attempt_sha256"],
            "lineage": dict(self.request["lineage"]),
            "scope": {key: scope[key] for key in (
                "tenant_id", "universe_id", "production_id", "project_id", "scene_id", "frame_id",
            )},
            "provider": {"identity": self.request["provider"]["identity"], "version": self.request["provider"]["version"],
                         "model_snapshot": self.request["provider"]["model_snapshot"], "endpoint": self.request["provider"]["endpoint"],
                         "settings": dict(self.request["provider"]["settings"]),
                         "provider_request_sha256": self.request["provider"]["provider_request_sha256"],
                         "projection_sha256": self.request["projection"]["projection_sha256"],
                         "price_policy_identity": self.request["provider"]["price_policy_identity"],
                         "data_policy_identity": self.request["provider"]["data_policy_identity"]},
            "response": {"response_sha256": result.response_sha256, "provider_created": result.provider_created,
                         "request_id": result.request_id, "latency_ms": result.latency_ms,
                         "usage": dict(result.usage), "estimated_cost_usd": result.estimated_cost_usd},
            "media": {"content_sha256": result.media.content_sha256, "media_type": result.media.media_type,
                      "width": result.media.width, "height": result.media.height,
                      "byte_count": len(result.media.content), "content_credentials_present": False},
            "eligibility": {"input": "eligible_public_external_processing",
                            "output": "quarantined_development_review_only"},
            "preservation": {"policy": "disposable_local", "durable": False,
                             "reproducibility": "identity_and_provenance_only"},
            "authority": {"production": False, "asset": False, "publication": False, "export": False,
                          "workflow": False, "scheduling": False, "provider_execution": False,
                          "runtime_execution": False},
            "limitations": ["development_review_media_only", "not_a_final_selection", "not_a_production_asset",
                            "not_reproducible_pixels", "no_retention_guarantee"],
            "candidate_sha256": "0" * 64,
        }
        candidate["candidate_id"] = "generated-review-" + canonical_digest({
            key: item for key, item in candidate.items() if key not in {"candidate_id", "candidate_sha256"}
        })[:32]
        candidate["candidate_sha256"] = canonical_digest(candidate)
        validate_candidate(candidate)
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
        self._staged = [
            (self._temporary(result.media.content), self.root / "image.png"),
            (self._temporary(self._json(review)), self.root / "review.json"),
            (self._temporary(self._json(candidate)), self.root / "generated-review-candidate.json"),
        ]
        return {"artifact_root": str(self.root.relative_to(self.repository_root)),
                "image": str((self.root / "image.png").relative_to(self.repository_root)),
                "candidate": str((self.root / "generated-review-candidate.json").relative_to(self.repository_root)),
                "review": str((self.root / "review.json").relative_to(self.repository_root))}

    def publish(self) -> None:
        try:
            for source, destination in self._staged:
                os.link(source, destination, follow_symlinks=False)
                source.unlink()
        except OSError as exc:
            self.abort()
            raise RuntimeInternalFailure("controlled generation artifact publication failed") from exc
        self._staged = []

    def abort(self) -> None:
        for source, _ in self._staged:
            source.unlink(missing_ok=True)
        self._staged = []
