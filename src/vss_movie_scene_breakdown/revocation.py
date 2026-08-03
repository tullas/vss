from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True, slots=True)
class MovieRevocation:
    target_type: str
    target_id: str
    digest: str | None
    effective_at: str
    reason_category: str
    lifecycle: str = "active"

class MovieRevocationSnapshot:
    identity="vss.movie.revocation.snapshot"; version="1"
    def __init__(self, records=()):
        self._records=tuple(records)
        for r in self._records:
            datetime.strptime(r.effective_at, "%Y-%m-%dT%H:%M:%SZ")
    @classmethod
    def built_in(cls): return cls(())
    def evaluate(self, target_type, target_id, digest, now):
        for record in self._records:
            if record.target_type == target_type and record.target_id == target_id and (record.digest is None or record.digest == digest) and record.lifecycle == "active" and record.effective_at <= now:
                return "revoked"
        return "eligible"
