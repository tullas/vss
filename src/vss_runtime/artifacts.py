from __future__ import annotations

import os
import hashlib
import stat
import tempfile
import json
from pathlib import Path

from .errors import CapabilityExecutionFailure, RuntimeInternalFailure


class StoryboardArtifactPublisher:
    __slots__ = ("repository_root", "root", "_temporary", "_destination", "_cancelled")

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve(strict=True)
        self.root = self.repository_root / ".local/movie/storyboards"
        self._temporary: Path | None = None
        self._destination: Path | None = None
        self._cancelled = False
        self._validate_fixed_root(create_missing=False)

    def _validate_fixed_root(self, *, create_missing: bool) -> None:
        current = self.repository_root
        for name in (".local", "movie", "storyboards"):
            current = current / name
            try:
                information = current.lstat()
            except FileNotFoundError:
                if not create_missing:
                    continue
                try:
                    current.mkdir(mode=0o700)
                    information = current.lstat()
                except OSError as exc:
                    raise CapabilityExecutionFailure("storyboard artifact root is unsafe") from exc
            except OSError as exc:
                raise CapabilityExecutionFailure("storyboard artifact root is unsafe") from exc
            if stat.S_ISLNK(information.st_mode) or not stat.S_ISDIR(information.st_mode):
                raise CapabilityExecutionFailure("storyboard artifact root is unsafe")
        try:
            resolved = self.root.resolve(strict=create_missing)
        except OSError as exc:
            raise CapabilityExecutionFailure("storyboard artifact root is unsafe") from exc
        if resolved == self.repository_root or not resolved.is_relative_to(self.repository_root):
            raise CapabilityExecutionFailure("storyboard artifact root escapes trusted repository")
        if create_missing and resolved != self.root:
            raise CapabilityExecutionFailure("storyboard artifact root is redirected")

    def stage(self, digest: str, content: bytes) -> str:
        if self._cancelled:
            raise CapabilityExecutionFailure("storyboard artifact publication was cancelled")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise CapabilityExecutionFailure("invalid storyboard artifact identity")
        try:
            self._validate_fixed_root(create_missing=True)
            os.chmod(self.root, 0o700)
            directory = self.root / digest
            if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
                raise CapabilityExecutionFailure("storyboard artifact destination is unsafe")
            directory.mkdir(mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
            resolved = directory.resolve()
            if not resolved.is_relative_to(self.root) or resolved != directory:
                raise CapabilityExecutionFailure("storyboard artifact destination escapes trusted root")
            destination = directory / "storyboard.svg"
            if destination.exists() or destination.is_symlink():
                info = destination.lstat()
                if not stat.S_ISREG(info.st_mode) or destination.is_symlink():
                    raise CapabilityExecutionFailure("storyboard artifact destination is unsafe")
                if destination.read_bytes() != content:
                    raise CapabilityExecutionFailure("storyboard artifact conflicts with existing content")
                self._destination = destination
                return destination.relative_to(self.repository_root).as_posix()
            descriptor, name = tempfile.mkstemp(prefix=".storyboard-", suffix=".tmp", dir=directory)
            temporary = Path(name)
            self._temporary, self._destination = temporary, destination
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
            return destination.relative_to(self.repository_root).as_posix()
        except CapabilityExecutionFailure:
            self.abort(); raise
        except OSError as exc:
            self.abort()
            raise CapabilityExecutionFailure("storyboard artifact could not be staged") from exc

    def publish(self) -> None:
        if self._temporary is None:
            return
        try:
            os.link(self._temporary, self._destination, follow_symlinks=False)
            os.chmod(self._destination, 0o600)
            self._temporary.unlink()
            self._temporary = None
        except OSError as exc:
            self.abort()
            raise RuntimeInternalFailure("storyboard artifact could not be published") from exc

    def abort(self) -> None:
        self._cancelled = True
        if self._temporary is not None:
            try:
                self._temporary.unlink(missing_ok=True)
            except OSError:
                pass
            self._temporary = None


class PictorialArtifactPublisher:
    """Create-only publisher for one content-addressed development PNG."""

    __slots__ = ("repository_root", "root", "_temporary", "_destination", "_cancelled")

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve(strict=True)
        self.root = self.repository_root / ".local/movie/storyboard-images"
        self._temporary: Path | None = None
        self._destination: Path | None = None
        self._cancelled = False
        self._validate_root(create_missing=False)

    def _validate_root(self, *, create_missing: bool) -> None:
        current = self.repository_root
        for name in (".local", "movie", "storyboard-images"):
            current = current / name
            try:
                info = current.lstat()
            except FileNotFoundError:
                if not create_missing:
                    continue
                try:
                    current.mkdir(mode=0o700)
                    info = current.lstat()
                except OSError as exc:
                    raise CapabilityExecutionFailure("pictorial artifact root is unsafe") from exc
            except OSError as exc:
                raise CapabilityExecutionFailure("pictorial artifact root is unsafe") from exc
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CapabilityExecutionFailure("pictorial artifact root is unsafe")
        try:
            resolved = self.root.resolve(strict=create_missing)
        except OSError as exc:
            raise CapabilityExecutionFailure("pictorial artifact root is unsafe") from exc
        if resolved == self.repository_root or not resolved.is_relative_to(self.repository_root):
            raise CapabilityExecutionFailure("pictorial artifact root escapes trusted repository")
        if create_missing and resolved != self.root:
            raise CapabilityExecutionFailure("pictorial artifact root is redirected")

    @staticmethod
    def _digest(value: str) -> bool:
        return len(value) == 64 and all(character in "0123456789abcdef" for character in value)

    def _directory(self, parent: Path, name: str) -> Path:
        directory = parent / name
        try:
            info = directory.lstat()
        except FileNotFoundError:
            directory.mkdir(mode=0o700)
            info = directory.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise CapabilityExecutionFailure("pictorial artifact destination is unsafe")
        os.chmod(directory, 0o700)
        if directory.resolve(strict=True) != directory or not directory.is_relative_to(self.root):
            raise CapabilityExecutionFailure("pictorial artifact destination escapes trusted root")
        return directory

    def stage(self, storyboard_digest: str, frame_id: str, content_digest: str, content: bytes) -> str:
        if self._cancelled:
            raise CapabilityExecutionFailure("pictorial artifact publication was cancelled")
        if (not self._digest(storyboard_digest) or not self._digest(content_digest)
                or len(frame_id) != 30 or not frame_id.startswith("frame-")
                or any(character not in "0123456789abcdef" for character in frame_id[6:])
                or not isinstance(content, bytes)
                or hashlib.sha256(content).hexdigest() != content_digest):
            raise CapabilityExecutionFailure("invalid pictorial artifact identity")
        try:
            self._validate_root(create_missing=True)
            os.chmod(self.root, 0o700)
            storyboard = self._directory(self.root, storyboard_digest)
            frame = self._directory(storyboard, frame_id)
            destination = frame / f"{content_digest}.png"
            if destination.exists() or destination.is_symlink():
                info = destination.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise CapabilityExecutionFailure("pictorial artifact destination is unsafe")
                if destination.read_bytes() != content:
                    raise CapabilityExecutionFailure("pictorial artifact conflicts with existing content")
                self._destination = destination
                return destination.relative_to(self.repository_root).as_posix()
            descriptor, name = tempfile.mkstemp(prefix=".pictorial-", suffix=".tmp", dir=frame)
            temporary = Path(name)
            self._temporary, self._destination = temporary, destination
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
            return destination.relative_to(self.repository_root).as_posix()
        except CapabilityExecutionFailure:
            self.abort(); raise
        except OSError as exc:
            self.abort()
            raise CapabilityExecutionFailure("pictorial artifact could not be staged") from exc

    def publish(self) -> None:
        if self._temporary is None:
            return
        try:
            os.link(self._temporary, self._destination, follow_symlinks=False)
            os.chmod(self._destination, 0o600)
            self._temporary.unlink()
            self._temporary = None
        except OSError as exc:
            self.abort()
            raise RuntimeInternalFailure("pictorial artifact could not be published") from exc

    def abort(self) -> None:
        self._cancelled = True
        if self._temporary is not None:
            try:
                self._temporary.unlink(missing_ok=True)
            except OSError:
                pass
            self._temporary = None


class CreativeExperimentArtifactPublisher:
    """Stages one blind candidate plus separate bounded review and condition evidence."""

    __slots__ = ("repository_root", "image_publisher", "root", "_staged", "_cancelled", "_plan_store", "_reserved_label", "_staged_image_path")

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve(strict=True)
        self.image_publisher = PictorialArtifactPublisher(repository_root)
        self.root = self.repository_root / ".local/movie/creative-reality-check-1"
        self._staged: list[tuple[Path, Path]] = []
        self._cancelled = False
        from vss_movie_creative_experiment.plan import CreativeExperimentPlanStore
        self._plan_store = CreativeExperimentPlanStore(self.repository_root)
        self._reserved_label: str | None = None
        self._staged_image_path: str | None = None
        self._validate_root(False)

    def next_candidate(self, admissions, execution_id: str, *, reserve: bool) -> tuple[object, dict]:
        expected = {condition: admitted.prompt_digest for condition, admitted in admissions.by_condition.items()}
        slot = self._plan_store.next_slot(expected, execution_id, reserve=reserve)
        if reserve:
            self._reserved_label = slot["candidate_label"]
        return admissions.by_condition[slot["condition"]], slot

    def _validate_root(self, create: bool) -> None:
        current = self.repository_root
        for name in (".local", "movie", "creative-reality-check-1"):
            current = current / name
            try:
                info = current.lstat()
            except FileNotFoundError:
                if not create:
                    continue
                current.mkdir(mode=0o700); info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CapabilityExecutionFailure("creative experiment artifact root is unsafe")
        resolved = self.root.resolve(strict=create)
        if resolved == self.repository_root or not resolved.is_relative_to(self.repository_root) or (create and resolved != self.root):
            raise CapabilityExecutionFailure("creative experiment artifact root escapes trusted repository")

    def _stage_json(self, group: str, label: str, value: dict) -> str:
        directory = self.root / group
        try:
            info = directory.lstat()
        except FileNotFoundError:
            directory.mkdir(mode=0o700); info = directory.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or directory.resolve() != directory:
            raise CapabilityExecutionFailure("creative experiment evidence destination is unsafe")
        content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        destination = directory / f"{label}.json"
        if destination.exists() or destination.is_symlink():
            info = destination.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or destination.read_bytes() != content:
                raise CapabilityExecutionFailure("creative experiment evidence conflicts with existing content")
            return destination.relative_to(self.repository_root).as_posix()
        descriptor, name = tempfile.mkstemp(prefix=".evidence-", suffix=".tmp", dir=directory)
        temporary = Path(name)
        try:
            os.fchmod(descriptor, 0o600); os.write(descriptor, content); os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._staged.append((temporary, destination))
        return destination.relative_to(self.repository_root).as_posix()

    def stage(self, admitted, label: str, media: bytes, content_digest: str, latency_ms: int,
              provider_identity: str, provider_model: str, attempt_id: str, usage: dict[str, int],
              content_credentials_present: bool = False,
              content_credentials_chunk_bytes: int | None = None) -> dict[str, str]:
        if self._cancelled or not label.startswith("candidate-") or len(label) != 26:
            raise CapabilityExecutionFailure("creative experiment candidate identity is invalid")
        self._validate_root(True); os.chmod(self.root, 0o700)
        image_path = self.image_publisher.stage(admitted.storyboard_specification_digest, admitted.frame_id, content_digest, media)
        self._staged_image_path = image_path
        mapping = self._stage_json("condition-mapping", label, {
            "schema_version": "1", "experiment": "creative-reality-check-1", "candidate_label": label,
            "condition": admitted.condition, "prompt_digest": admitted.prompt_digest,
            "semantic_request_digest": admitted.semantic_request_digest, "attempt_identity": attempt_id,
            "provider_identity": provider_identity, "model_identity": provider_model,
            "media_sha256": content_digest, "latency_ms": latency_ms, "provider_call_count": 1,
            "maximum_estimated_cost_usd": "0.07", "provider_usage": usage, "authoritative_frame": {
                "storyboard_specification_digest": admitted.storyboard_specification_digest,
                "frame_id": admitted.frame_id, "frame_specification_digest": admitted.frame_specification_digest,
                "knowledge_lineage_digest": admitted.knowledge_lineage_digest,
            }, "status": "generated_development_review_candidate",
            "content_credentials": {"present": content_credentials_present, "chunk_type": "caBX" if content_credentials_present else None,
                                    "chunk_bytes": content_credentials_chunk_bytes,
                                    "cryptographically_verified": False, "grants_authority": False},
        })
        review = self._stage_json("review", label, {
            "schema_version": "1", "experiment": "creative-reality-check-1", "candidate_label": label,
            "image_path": image_path, "scores_1_to_5": {key: None for key in (
                "story_intent_fidelity", "emotional_fidelity", "character_action_correctness",
                "environment_fidelity", "composition_cinematic_usefulness", "unwanted_invention",
                "overall_storyboard_usefulness")}, "disposition": None,
            "qualitative": {"communicated": None, "invented_or_missed": None,
                            "requested_correction": None, "preference_or_rejection_reason": None},
        })
        return {"artifact_path": image_path, "condition_mapping_path": mapping, "review_path": review}

    def publish(self) -> None:
        try:
            self.image_publisher.publish()
            for temporary, destination in self._staged:
                os.link(temporary, destination, follow_symlinks=False); os.chmod(destination, 0o600); temporary.unlink()
            self._staged.clear()
            if self._reserved_label is not None:
                self._plan_store.mark(self._reserved_label, "succeeded", self._staged_image_path)
                self._reserved_label = None
                self._staged_image_path = None
        except OSError as exc:
            self.abort(); raise RuntimeInternalFailure("creative experiment artifacts could not be published") from exc

    def abort(self) -> None:
        self._cancelled = True; self.image_publisher.abort()
        for temporary, _ in self._staged:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        self._staged.clear()
        if self._reserved_label is not None:
            self._plan_store.mark(self._reserved_label, "failed")
            self._reserved_label = None
            self._staged_image_path = None
