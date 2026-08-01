from __future__ import annotations

from typing import Any, Protocol

from .context import CapabilityExecutionContext
from .results import CapabilityResult


class CapabilityHandler(Protocol):
    sdk_api_version: str
    capability_identity: str
    command_identity: str

    def __call__(
        self,
        context: CapabilityExecutionContext,
        input_data: dict[str, Any],
        dry_run: bool,
    ) -> CapabilityResult: ...
