from __future__ import annotations

import json
import os
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Callable

from vss_movie_contracts.errors import MovieContractError

CapabilityExecutionFailure = MovieContractError

EXPERIMENT_IDENTITY = "creative-reality-check-1"
LABEL_PREFIX = "candidate-"
SCORE_KEYS = (
    "story_intent_fidelity", "emotional_fidelity", "character_action_correctness",
    "environment_fidelity", "composition_cinematic_usefulness", "unwanted_invention",
    "overall_storyboard_usefulness",
)


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _is_label(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 26 and value.startswith(LABEL_PREFIX)
            and all(c in "0123456789abcdef" for c in value[len(LABEL_PREFIX):]))


class CreativeExperimentPlanStore:
    """Persist one immutable blinded plan and irreversible per-slot attempts."""

    def __init__(self, repository_root: Path, token_hex: Callable[[int], str] = secrets.token_hex,
                 shuffle: Callable[[list[str]], None] | None = None) -> None:
        self.repository_root = repository_root.resolve(strict=True)
        self.root = self.repository_root / ".local/movie/creative-reality-check-1"
        self._token_hex = token_hex
        self._shuffle = shuffle or secrets.SystemRandom().shuffle

    def _validate_root(self, create: bool) -> None:
        current = self.repository_root
        for name in (".local", "movie", "creative-reality-check-1"):
            current = current / name
            try:
                info = current.lstat()
            except FileNotFoundError:
                if not create:
                    continue
                current.mkdir(mode=0o700)
                info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CapabilityExecutionFailure("creative experiment plan root is unsafe")
        if create and self.root.resolve(strict=True) != self.root:
            raise CapabilityExecutionFailure("creative experiment plan root is redirected")

    @staticmethod
    def _encode(value: dict) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"

    def _create_exclusive(self, path: Path, value: dict) -> None:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
            try:
                content = self._encode(value)
                os.write(descriptor, content)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except FileExistsError as exc:
            raise CapabilityExecutionFailure("creative experiment plan conflicts with existing evidence") from exc
        except OSError as exc:
            raise CapabilityExecutionFailure("creative experiment plan could not be persisted") from exc

    def _read(self, path: Path) -> dict:
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise CapabilityExecutionFailure("creative experiment plan evidence is unsafe")
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CapabilityExecutionFailure("creative experiment plan evidence is malformed") from exc
        if not isinstance(value, dict):
            raise CapabilityExecutionFailure("creative experiment plan evidence is malformed")
        return value

    def _validate(self, internal: dict, reviewer: dict, expected: dict[str, str]) -> None:
        if set(internal) != {"schema_version", "experiment", "slots"} or internal.get("schema_version") != "1" or internal.get("experiment") != EXPERIMENT_IDENTITY:
            raise CapabilityExecutionFailure("creative experiment internal plan is malformed")
        if set(reviewer) != {"schema_version", "experiment", "candidates"} or reviewer.get("schema_version") != "1" or reviewer.get("experiment") != EXPERIMENT_IDENTITY:
            raise CapabilityExecutionFailure("creative experiment reviewer plan is malformed")
        slots, candidates = internal.get("slots"), reviewer.get("candidates")
        if not isinstance(slots, list) or not isinstance(candidates, list) or len(slots) != 6 or len(candidates) != 6:
            raise CapabilityExecutionFailure("creative experiment plan must contain six slots")
        labels: list[str] = []
        conditions: list[str] = []
        for ordinal, (slot, candidate) in enumerate(zip(slots, candidates), 1):
            if not isinstance(slot, dict) or set(slot) != {"ordinal", "candidate_label", "condition", "expected_prompt_digest"}:
                raise CapabilityExecutionFailure("creative experiment internal plan is malformed")
            if slot.get("ordinal") != ordinal or not _is_label(slot.get("candidate_label")) or slot.get("condition") not in {"A", "B"}:
                raise CapabilityExecutionFailure("creative experiment internal plan is malformed")
            if slot.get("expected_prompt_digest") != expected[slot["condition"]] or not _is_digest(slot.get("expected_prompt_digest")):
                raise CapabilityExecutionFailure("creative experiment plan conflicts with authoritative prompts")
            if not isinstance(candidate, dict) or set(candidate) != {"ordinal", "candidate_label", "image_path", "scores_1_to_5", "disposition", "qualitative"}:
                raise CapabilityExecutionFailure("creative experiment reviewer plan is malformed")
            image_path = candidate.get("image_path")
            if candidate.get("ordinal") != ordinal or candidate.get("candidate_label") != slot["candidate_label"] or not (image_path is None or (isinstance(image_path, str) and image_path.startswith(".local/movie/storyboard-images/") and len(image_path) <= 512)) or candidate.get("disposition") is not None:
                raise CapabilityExecutionFailure("creative experiment reviewer plan is malformed")
            scores = candidate.get("scores_1_to_5")
            qualitative = candidate.get("qualitative")
            if not isinstance(scores, dict) or set(scores) != set(SCORE_KEYS) or any(value is not None for value in scores.values()):
                raise CapabilityExecutionFailure("creative experiment reviewer plan is malformed")
            if not isinstance(qualitative, dict) or set(qualitative) != {"communicated", "invented_or_missed", "requested_correction", "preference_or_rejection_reason"} or any(value is not None for value in qualitative.values()):
                raise CapabilityExecutionFailure("creative experiment reviewer plan is malformed")
            labels.append(slot["candidate_label"]); conditions.append(slot["condition"])
        if len(set(labels)) != 6 or conditions.count("A") != 3 or conditions.count("B") != 3:
            raise CapabilityExecutionFailure("creative experiment plan balance or labels are invalid")

    def initialize(self, expected_prompt_digests: dict[str, str]) -> tuple[dict, dict]:
        if set(expected_prompt_digests) != {"A", "B"} or not all(_is_digest(value) for value in expected_prompt_digests.values()):
            raise CapabilityExecutionFailure("creative experiment prompt identities are invalid")
        self._validate_root(True)
        internal_path, reviewer_path = self.root / "internal-condition-plan.json", self.root / "reviewer-plan.json"
        if internal_path.exists() or reviewer_path.exists():
            if not internal_path.exists() or not reviewer_path.exists():
                raise CapabilityExecutionFailure("creative experiment plan evidence is incomplete")
            internal, reviewer = self._read(internal_path), self._read(reviewer_path)
            self._validate(internal, reviewer, expected_prompt_digests)
            return internal, reviewer
        conditions = ["A"] * 3 + ["B"] * 3
        self._shuffle(conditions)
        labels: list[str] = []
        while len(labels) < 6:
            label = LABEL_PREFIX + self._token_hex(8)
            if _is_label(label) and label not in labels:
                labels.append(label)
        internal = {"schema_version": "1", "experiment": EXPERIMENT_IDENTITY, "slots": [
            {"ordinal": ordinal, "candidate_label": label, "condition": condition,
             "expected_prompt_digest": expected_prompt_digests[condition]}
            for ordinal, (label, condition) in enumerate(zip(labels, conditions), 1)
        ]}
        reviewer = {"schema_version": "1", "experiment": EXPERIMENT_IDENTITY, "candidates": [
            {"ordinal": ordinal, "candidate_label": label, "image_path": None,
             "scores_1_to_5": {key: None for key in SCORE_KEYS}, "disposition": None,
             "qualitative": {key: None for key in ("communicated", "invented_or_missed", "requested_correction", "preference_or_rejection_reason")}}
            for ordinal, label in enumerate(labels, 1)
        ]}
        self._validate(internal, reviewer, expected_prompt_digests)
        self._create_exclusive(internal_path, internal)
        try:
            self._create_exclusive(reviewer_path, reviewer)
        except Exception:
            internal_path.unlink(missing_ok=True)
            raise
        return internal, reviewer

    def next_slot(self, expected_prompt_digests: dict[str, str], execution_id: str, *, reserve: bool) -> dict:
        internal, _ = self.initialize(expected_prompt_digests)
        attempts = self.root / "attempts"
        attempts.mkdir(mode=0o700, exist_ok=True)
        if attempts.is_symlink() or attempts.resolve() != attempts:
            raise CapabilityExecutionFailure("creative experiment attempt evidence is unsafe")
        for slot in internal["slots"]:
            path = attempts / f"{slot['candidate_label']}.json"
            if path.exists():
                attempt = self._read(path)
                if set(attempt) != {"schema_version", "experiment", "ordinal", "candidate_label", "execution_attempt_id", "status"} or attempt.get("schema_version") != "1" or attempt.get("experiment") != EXPERIMENT_IDENTITY or attempt.get("ordinal") != slot["ordinal"] or attempt.get("candidate_label") != slot["candidate_label"] or attempt.get("status") not in {"attempted", "failed", "succeeded"}:
                    raise CapabilityExecutionFailure("creative experiment attempt evidence is malformed")
                continue
            if reserve:
                self._create_exclusive(path, {"schema_version": "1", "experiment": EXPERIMENT_IDENTITY,
                    "ordinal": slot["ordinal"], "candidate_label": slot["candidate_label"],
                    "execution_attempt_id": execution_id, "status": "attempted"})
            return slot
        raise CapabilityExecutionFailure("creative experiment plan has no unattempted candidates")

    def mark(self, label: str, status_value: str, image_path: str | None = None) -> None:
        if status_value not in {"failed", "succeeded"} or not _is_label(label):
            raise CapabilityExecutionFailure("creative experiment attempt status is invalid")
        if (status_value == "succeeded") != isinstance(image_path, str):
            raise CapabilityExecutionFailure("creative experiment attempt publication is invalid")
        path = self.root / "attempts" / f"{label}.json"
        attempt = self._read(path)
        if attempt.get("candidate_label") != label or attempt.get("status") != "attempted":
            raise CapabilityExecutionFailure("creative experiment candidate was already attempted")
        attempt["status"] = status_value
        descriptor, name = tempfile.mkstemp(prefix=".attempt-", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        try:
            os.fchmod(descriptor, 0o600); os.write(descriptor, self._encode(attempt)); os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        if status_value == "succeeded":
            reviewer_path = self.root / "reviewer-plan.json"
            reviewer = self._read(reviewer_path)
            matches = [candidate for candidate in reviewer.get("candidates", []) if candidate.get("candidate_label") == label]
            if len(matches) != 1 or matches[0].get("image_path") is not None:
                raise CapabilityExecutionFailure("creative experiment reviewer candidate conflicts with publication")
            matches[0]["image_path"] = image_path
            descriptor, name = tempfile.mkstemp(prefix=".reviewer-", suffix=".tmp", dir=self.root)
            temporary = Path(name)
            try:
                os.fchmod(descriptor, 0o600); os.write(descriptor, self._encode(reviewer)); os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, reviewer_path)
