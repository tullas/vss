from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


AUTHORITY = {"runtime_execution": False, "provider_execution": False, "production": False,
             "publication": False, "workflow_activation": False, "security_exception": False,
             "product_authority": False, "merge": False, "push": False}
BACKLOG = Path("docs/engineering/improvement-backlog-v1.json")
SCHEMA = Path("schemas/dev-improvement-candidate-v1.schema.json")


class ImprovementBacklogFailure(Exception):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ImprovementBacklogFailure("improvement backlog is malformed") from exc
    if type(value) is not dict:
        raise ImprovementBacklogFailure("improvement backlog is malformed")
    return value


class ImprovementBacklog:
    """Git-durable, advisory development backlog; it never grants execution authority."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = self.root / BACKLOG
        self.schema = _read(self.root / SCHEMA)

    def _validate(self, value: dict[str, Any]) -> None:
        errors = list(Draft202012Validator(self.schema).iter_errors(value))
        if errors or value.get("authority") != AUTHORITY:
            raise ImprovementBacklogFailure("improvement backlog is malformed")
        ids = [item["candidate_id"] for item in value["candidates"]]
        if len(ids) != len(set(ids)):
            raise ImprovementBacklogFailure("improvement backlog ordering is invalid")
        for candidate in value["candidates"]:
            if candidate["candidate_id"] != self.candidate_id(candidate):
                raise ImprovementBacklogFailure("improvement candidate ID is not deterministic")
            if candidate["disposition"] == "rejected" and candidate["status"] != "closed":
                raise ImprovementBacklogFailure("rejected candidate must be closed")

    def load(self) -> dict[str, Any]:
        value = _read(self.path)
        self._validate(value)
        return value

    def candidate_id(self, candidate: dict[str, Any]) -> str:
        material = {key: value for key, value in candidate.items() if key != "candidate_id"}
        return "improvement-" + _digest(material)[:24]

    def admit(self, candidate: dict[str, Any]) -> dict[str, Any]:
        candidate = json.loads(json.dumps(candidate))
        candidate["schema_version"] = "1"
        candidate["protocol"] = "vss.dev-improvement-candidate"
        candidate["advisory"] = True
        candidate["implementation_authorized"] = False
        candidate["candidate_id"] = self.candidate_id(candidate)
        current = self.load()
        existing = {item["candidate_id"]: item for item in current["candidates"]}
        if candidate["candidate_id"] in existing:
            if existing[candidate["candidate_id"]] != candidate:
                raise ImprovementBacklogFailure("candidate ID collision")
            return existing[candidate["candidate_id"]]
        validator = Draft202012Validator(self.schema)
        errors = list(validator.iter_errors({"schema_version": "1", "protocol": "vss.dev-improvement-backlog", "candidates": [candidate], "authority": AUTHORITY}))
        if errors:
            raise ImprovementBacklogFailure("improvement candidate is malformed")
        current["candidates"].append(candidate)
        current["candidates"].sort(key=lambda item: item["candidate_id"])
        self._validate(current)
        raw = _canonical(current) + b"\n"
        if len(raw) > 128 * 1024:
            raise ImprovementBacklogFailure("improvement backlog exceeded its bound")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".improvement-", delete=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno()); temporary = Path(stream.name)
        os.replace(temporary, self.path)
        return candidate

    def due(self, milestone_id: str) -> dict[str, Any]:
        if not milestone_id:
            raise ImprovementBacklogFailure("milestone boundary is required")
        candidates = sorted([item for item in self.load()["candidates"]
                      if item["status"] == "queued" and item["trigger"]["kind"] == "milestone-boundary"]
                           , key=lambda item: (-item["priority"], item["candidate_id"]))
        return {"schema_version": "1", "protocol": "vss.dev-improvement-report",
                "milestone_boundary": milestone_id, "candidates": candidates,
                "selected_for_review": [item["candidate_id"] for item in candidates],
                "advisory": True, "implementation_authorized": False, "authority": dict(AUTHORITY)}
