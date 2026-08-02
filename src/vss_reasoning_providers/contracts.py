from __future__ import annotations

from typing import Protocol

from vss_reasoning.models import CandidateOptions, DeterministicReasoningContext


class DeterministicOptionsProvider(Protocol):
    def generate_option_primitives(
        self, context: DeterministicReasoningContext
    ) -> CandidateOptions: ...
