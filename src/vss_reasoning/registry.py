from __future__ import annotations

from dataclasses import dataclass

from vss_reasoning_providers import BuiltinDeterministicOptionsProvider, DeterministicOptionsProvider
from vss_reasoning_strategies import DeterministicGenerateOptionsStrategy

from .errors import ReasoningUnavailable
from .models import ImplementationIdentity

STRATEGY_IDENTITY = ImplementationIdentity(
    "vss.generate-options.deterministic", "1.0.0", "1", "active", "trusted_builtin"
)
PROVIDER_IDENTITY = ImplementationIdentity(
    "vss.reasoning.deterministic-options", "1.0.0", "1", "active", "trusted_builtin"
)


@dataclass(frozen=True, slots=True)
class ReasoningImplementationRegistry:
    strategy_identity: ImplementationIdentity
    provider_identity: ImplementationIdentity
    strategy: DeterministicGenerateOptionsStrategy
    provider: DeterministicOptionsProvider

    @classmethod
    def built_in(cls) -> "ReasoningImplementationRegistry":
        return cls(
            STRATEGY_IDENTITY,
            PROVIDER_IDENTITY,
            DeterministicGenerateOptionsStrategy(),
            BuiltinDeterministicOptionsProvider(),
        )

    def resolve(self) -> tuple[DeterministicGenerateOptionsStrategy, DeterministicOptionsProvider]:
        if self.strategy_identity != STRATEGY_IDENTITY or self.provider_identity != PROVIDER_IDENTITY:
            raise ReasoningUnavailable("reasoning implementation substitution rejected")
        if self.strategy_identity.lifecycle_status != "active":
            raise ReasoningUnavailable("reasoning strategy is unavailable")
        if self.provider_identity.lifecycle_status != "active":
            raise ReasoningUnavailable("reasoning provider is unavailable")
        if self.strategy_identity.trust != "trusted_builtin" or self.provider_identity.trust != "trusted_builtin":
            raise ReasoningUnavailable("reasoning implementation is not trusted")
        if self.strategy_identity.api_version != "1" or self.provider_identity.api_version != "1":
            raise ReasoningUnavailable("reasoning implementation API is incompatible")
        return self.strategy, self.provider

    def snapshot(self) -> dict[str, object]:
        return {
            "strategy": {
                "identity": self.strategy_identity.identity,
                "version": self.strategy_identity.version,
                "api_version": self.strategy_identity.api_version,
                "lifecycle_status": self.strategy_identity.lifecycle_status,
                "trust": self.strategy_identity.trust,
            },
            "provider": {
                "identity": self.provider_identity.identity,
                "version": self.provider_identity.version,
                "api_version": self.provider_identity.api_version,
                "lifecycle_status": self.provider_identity.lifecycle_status,
                "trust": self.provider_identity.trust,
            },
        }
