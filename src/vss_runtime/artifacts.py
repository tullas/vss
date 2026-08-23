from __future__ import annotations

import os
import hashlib
import stat
import tempfile
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
