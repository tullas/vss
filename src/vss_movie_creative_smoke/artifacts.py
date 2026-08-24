from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from vss_runtime.artifacts import PictorialArtifactPublisher
from vss_runtime.errors import CapabilityExecutionFailure, RuntimeInternalFailure

from .provider import SmokeProviderResult
from .service import (
    AUTHORIZED_COST_CEILING_USD, ENDPOINT, EXPERIMENT_IDENTITY, MAXIMUM_ESTIMATED_COST_USD, MODEL_IDENTITY,
    OUTPUT_FORMAT, OUTPUT_HEIGHT, OUTPUT_QUALITY, OUTPUT_WIDTH, PROVIDER_IDENTITY,
    SMOKE_3_EXPERIMENT_IDENTITY, AdmittedCreativeSmoke,
)


class SmokeExperimentArtifactPublisher:
    """Create-once experiment state and audit-gated media/evidence publication."""

    def __init__(self, repository_root: Path, experiment_identity: str = EXPERIMENT_IDENTITY) -> None:
        self.repository_root = repository_root.resolve(strict=True)
        if experiment_identity not in {EXPERIMENT_IDENTITY, SMOKE_3_EXPERIMENT_IDENTITY}:
            raise CapabilityExecutionFailure("creative smoke experiment identity is unsupported")
        self.experiment_identity = experiment_identity
        self.root = self.repository_root / ".local/movie" / experiment_identity
        self.image_publisher = PictorialArtifactPublisher(repository_root)
        self._staged: list[tuple[Path, Path]] = []
        self._ready = False
        self._reserved = False
        self._cancelled = False
        self._attempt_id: str | None = None
        self._binding: dict[str, Any] | None = None
        self._artifact_path: str | None = None
        self._validate_root(create=False)

    def _validate_root(self, *, create: bool) -> None:
        current = self.repository_root
        for name in (".local", "movie", self.experiment_identity):
            current = current / name
            try:
                info = current.lstat()
            except FileNotFoundError:
                if not create:
                    continue
                current.mkdir(mode=0o700)
                info = current.lstat()
            except OSError as exc:
                raise CapabilityExecutionFailure("creative smoke evidence root is unsafe") from exc
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CapabilityExecutionFailure("creative smoke evidence root is unsafe")
        try:
            resolved = self.root.resolve(strict=create)
        except OSError as exc:
            raise CapabilityExecutionFailure("creative smoke evidence root is unsafe") from exc
        if resolved == self.repository_root or not resolved.is_relative_to(self.repository_root):
            raise CapabilityExecutionFailure("creative smoke evidence root escapes trusted repository")
        if create and resolved != self.root:
            raise CapabilityExecutionFailure("creative smoke evidence root is redirected")

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
        return (stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and os.access(current, os.W_OK | os.X_OK))

    def check_readiness(self, admitted: AdmittedCreativeSmoke) -> None:
        """Validate create-once state and output roots without mutating either."""
        if self._reserved or self._cancelled or type(admitted) is not AdmittedCreativeSmoke:
            raise CapabilityExecutionFailure("creative smoke preflight state is invalid")
        if admitted.experiment_identity != self.experiment_identity:
            raise CapabilityExecutionFailure("creative smoke experiment boundary mismatch")
        expected = self.repository_root / ".local/movie" / self.experiment_identity
        if self.root != expected:
            raise CapabilityExecutionFailure("creative smoke evidence root is not isolated")
        self._validate_root(create=False)
        destination = self.root / "attempt.json"
        if destination.exists() or destination.is_symlink():
            raise CapabilityExecutionFailure("creative smoke provider attempt has already been consumed")
        if self.root.exists():
            try:
                if any(self.root.iterdir()):
                    raise CapabilityExecutionFailure("creative smoke evidence root is not unused")
            except OSError as exc:
                raise CapabilityExecutionFailure("creative smoke evidence root is unsafe") from exc
        if (not self._writable_ancestor(self.root)
                or not self._writable_ancestor(self.image_publisher.root)):
            raise CapabilityExecutionFailure("creative smoke output root is not ready")
        self._ready = True

    @staticmethod
    def _json_bytes(value: dict[str, Any]) -> bytes:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"

    def _binding_value(self, admitted: AdmittedCreativeSmoke, attempt_id: str) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "experiment": self.experiment_identity,
            "attempt_identity": attempt_id,
            "maximum_provider_attempts": 1,
            "maximum_estimated_cost_usd": MAXIMUM_ESTIMATED_COST_USD,
            "authorized_cost_ceiling_usd": AUTHORIZED_COST_CEILING_USD,
            "provider_identity": PROVIDER_IDENTITY,
            "model_identity": MODEL_IDENTITY,
            "endpoint_identity": ENDPOINT,
            "settings": {
                "n": 1, "width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT,
                "quality": OUTPUT_QUALITY, "output_format": OUTPUT_FORMAT,
            },
            "authoritative_frame": {
                "project_id": admitted.project_id,
                "scene_id": admitted.scene_id,
                "storyboard_specification_digest": admitted.storyboard_specification_digest,
                "frame_id": admitted.frame_id,
                "frame_specification_digest": admitted.frame_specification_digest,
                "knowledge_lineage_digest": admitted.knowledge_lineage_digest,
            },
            "base_semantic_request_digest": admitted.base_semantic_request_digest,
            "depiction_projection_digest": admitted.depiction_projection_digest,
            "provider_request_digest": admitted.provider_request_digest,
            "experiment_admission_id": admitted.admission_id,
        }

    def reserve(self, admitted: AdmittedCreativeSmoke, attempt_id: str) -> None:
        if not self._ready or self._reserved or self._cancelled or type(admitted) is not AdmittedCreativeSmoke:
            raise CapabilityExecutionFailure("creative smoke attempt reservation is invalid")
        if not isinstance(attempt_id, str) or len(attempt_id) != 32 or any(c not in "0123456789abcdef" for c in attempt_id):
            raise CapabilityExecutionFailure("creative smoke attempt identity is invalid")
        self._validate_root(create=True)
        os.chmod(self.root, 0o700)
        destination = self.root / "attempt.json"
        if destination.exists() or destination.is_symlink():
            raise CapabilityExecutionFailure("creative smoke provider attempt has already been consumed")
        try:
            if any(self.root.iterdir()):
                raise CapabilityExecutionFailure("creative smoke evidence root is not unused")
        except OSError as exc:
            raise CapabilityExecutionFailure("creative smoke evidence root is unsafe") from exc
        binding = self._binding_value(admitted, attempt_id)
        content = self._json_bytes({**binding, "status": "attempted", "artifact_path": None})
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(destination, flags, 0o600)
            try:
                written = 0
                while written < len(content):
                    count = os.write(descriptor, content[written:])
                    if count <= 0:
                        raise OSError("short write")
                    written += count
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except FileExistsError as exc:
            raise CapabilityExecutionFailure("creative smoke provider attempt has already been consumed") from exc
        except OSError as exc:
            raise CapabilityExecutionFailure("creative smoke attempt state could not be reserved") from exc
        self._reserved = True
        self._ready = False
        self._attempt_id = attempt_id
        self._binding = binding

    def _stage_json(self, directory_name: str, filename: str, value: dict[str, Any]) -> str:
        directory = self.root / directory_name
        try:
            info = directory.lstat()
        except FileNotFoundError:
            directory.mkdir(mode=0o700)
            info = directory.lstat()
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                or directory.resolve(strict=True) != directory):
            raise CapabilityExecutionFailure("creative smoke evidence destination is unsafe")
        destination = directory / filename
        if destination.exists() or destination.is_symlink():
            raise CapabilityExecutionFailure("creative smoke evidence already exists")
        content = self._json_bytes(value)
        descriptor, name = tempfile.mkstemp(prefix=".evidence-", suffix=".tmp", dir=directory)
        temporary = Path(name)
        try:
            os.fchmod(descriptor, 0o600)
            written = 0
            while written < len(content):
                count = os.write(descriptor, content[written:])
                if count <= 0:
                    raise OSError("short write")
                written += count
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._staged.append((temporary, destination))
        return destination.relative_to(self.repository_root).as_posix()

    def stage(self, admitted: AdmittedCreativeSmoke, result: SmokeProviderResult, attempt_id: str) -> dict[str, str]:
        if (not self._reserved or self._cancelled or attempt_id != self._attempt_id
                or type(admitted) is not AdmittedCreativeSmoke or type(result) is not SmokeProviderResult):
            raise CapabilityExecutionFailure("creative smoke publication state is invalid")
        media = result.media
        image_path = self.image_publisher.stage(
            admitted.storyboard_specification_digest, admitted.frame_id,
            media.content_sha256, media.content,
        )
        self._artifact_path = image_path
        internal_path = self._stage_json("evidence", "result.json", {
            "schema_version": "1",
            "experiment": self.experiment_identity,
            "status": "generated_awaiting_human_review",
            "attempt_identity": attempt_id,
            "authoritative_frame": self._binding["authoritative_frame"],
            "base_semantic_request_digest": admitted.base_semantic_request_digest,
            "depiction_projection_digest": admitted.depiction_projection_digest,
            "provider_request_digest": admitted.provider_request_digest,
            "provider_identity": PROVIDER_IDENTITY,
            "model_identity": MODEL_IDENTITY,
            "provider_call_count": 1,
            "maximum_estimated_cost_usd": MAXIMUM_ESTIMATED_COST_USD,
            "estimated_cost_usd": result.estimated_cost_usd,
            "sanitized_usage": dict(result.usage),
            "latency_ms": result.latency_ms,
            "media": {
                "path": image_path, "media_type": media.media_type,
                "width": media.width, "height": media.height,
                "bytes": len(media.content), "sha256": media.content_sha256,
            },
            "png": result.png.as_dict(),
            "content_credentials": {
                "present": result.png.content_credentials_present,
                "chunk_type": "caBX" if result.png.content_credentials_present else None,
                "chunk_bytes": result.png.content_credentials_chunk_bytes,
                "cryptographically_verified": False,
                "grants_authority": False,
            },
            "authority_boundary": {key: False for key in (
                "production_approval", "production_asset_admission", "final_frame_selection",
                "publication_authority", "workflow_authority", "autonomous_authority",
                "reusable_execution_authority",
            )},
        })
        review_path = self._stage_json("review", "reviewer.json", {
            "schema_version": "1",
            "experiment": self.experiment_identity,
            "image_path": image_path,
            "media_sha256": media.content_sha256,
            "questions": {
                "mira_subject_treatment_appropriate": None,
                "lantern_locked_gate_discovery_legible": None,
                "courtyard_at_dawn_context_perceptible": None,
                "control_or_ui_text_visible": None,
                "lantern_significance_remains_unresolved": None,
                "bounded_artistic_interpretation_present": None,
                "known_canon_contradiction_present": None,
                "motivated_cinematic_shot": None,
            },
            "disposition": None,
            "allowed_dispositions": ["USE", "REGENERATE", "REJECT"],
            "regenerate_authorizes_another_call": False,
        })
        return {"artifact_path": image_path, "evidence_path": internal_path, "review_path": review_path}

    def _mark(self, status_value: str, artifact_path: str | None) -> None:
        if not self._reserved or self._binding is None:
            return
        state_path = self.root / "attempt.json"
        try:
            info = state_path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError("unsafe state")
            content = self._json_bytes({**self._binding, "status": status_value, "artifact_path": artifact_path})
            descriptor, name = tempfile.mkstemp(prefix=".attempt-", suffix=".tmp", dir=self.root)
            temporary = Path(name)
            try:
                os.fchmod(descriptor, 0o600)
                os.write(descriptor, content)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, state_path)
        except OSError as exc:
            raise RuntimeInternalFailure("creative smoke attempt state could not be finalized") from exc

    def publish(self) -> None:
        try:
            self.image_publisher.publish()
            for temporary, destination in self._staged:
                os.link(temporary, destination, follow_symlinks=False)
                os.chmod(destination, 0o600)
                temporary.unlink()
            self._staged.clear()
            self._mark("succeeded", self._artifact_path)
            self._reserved = False
        except RuntimeInternalFailure:
            self.abort()
            raise
        except OSError as exc:
            self.abort()
            raise RuntimeInternalFailure("creative smoke artifacts could not be published") from exc

    def abort(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        self.image_publisher.abort()
        for temporary, _ in self._staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        self._staged.clear()
        if self._reserved:
            self._mark("failed", None)
            self._reserved = False
