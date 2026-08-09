from __future__ import annotations

from dataclasses import dataclass
from vss_reasoning_contracts import canonical_digest

from vss_reasoning_providers import BuiltinDeterministicOptionsProvider, DeterministicOptionsProvider
from vss_reasoning_strategies import DeterministicGenerateOptionsStrategy

from .errors import ReasoningUnavailable
from .models import ImplementationIdentity
from vss_reasoning_providers import DeterministicSceneProductionOptionsProvider
from vss_reasoning_strategies import DeterministicSceneProductionOptionsStrategy
from vss_reasoning_providers import DeterministicCharacterContinuityProvider, DeterministicCharacterContinuityAnalysisProvider
from vss_reasoning_strategies import DeterministicCharacterContinuityStrategy, DeterministicCharacterContinuityAnalysisStrategy

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

@dataclass(frozen=True, slots=True)
class SceneProductionOptionsImplementationRegistry:
    strategy: DeterministicSceneProductionOptionsStrategy
    provider: DeterministicSceneProductionOptionsProvider
    @classmethod
    def built_in(cls):
        return cls(DeterministicSceneProductionOptionsStrategy(), DeterministicSceneProductionOptionsProvider())
    def resolve(self):
        if type(self.strategy) is not DeterministicSceneProductionOptionsStrategy or type(self.provider) is not DeterministicSceneProductionOptionsProvider:
            raise ReasoningUnavailable("production-options implementation substitution rejected")
        expected = ("vss.generate-scene-production-options.deterministic","1.0.0","vss.reasoning.deterministic-scene-production-options","1.0.0","1")
        actual = (self.strategy.identity,self.strategy.version,self.provider.identity,self.provider.version,self.provider.api_version)
        if actual != expected: raise ReasoningUnavailable("production-options implementation is incompatible")
        return self.strategy, self.provider
    @property
    def digest(self):
        return canonical_digest({"strategy":[self.strategy.identity,self.strategy.version],"provider":[self.provider.identity,self.provider.version,self.provider.api_version],"calls":1,"iterations":1,"retry":False,"fallback":False,"ranking":False})

@dataclass(frozen=True, slots=True)
class CharacterContinuityImplementationRegistry:
    strategy: DeterministicCharacterContinuityStrategy
    provider: DeterministicCharacterContinuityProvider
    analysis_strategy: DeterministicCharacterContinuityAnalysisStrategy
    analysis_provider: DeterministicCharacterContinuityAnalysisProvider

    @classmethod
    def built_in(cls):
        return cls(DeterministicCharacterContinuityStrategy(), DeterministicCharacterContinuityProvider(), DeterministicCharacterContinuityAnalysisStrategy(), DeterministicCharacterContinuityAnalysisProvider())

    def resolve(self, task_version="2"):
        if task_version == "3":
            actual = (self.analysis_strategy.identity, self.analysis_strategy.version, self.analysis_provider.identity, self.analysis_provider.version, self.analysis_provider.api_version)
            expected = ("vss.analyze-character-continuity.deterministic", "1.1.0", "vss.reasoning.character-continuity.deterministic", "1.1.0", "1")
            if type(self.analysis_strategy) is not DeterministicCharacterContinuityAnalysisStrategy or type(self.analysis_provider) is not DeterministicCharacterContinuityAnalysisProvider or actual != expected:
                raise ReasoningUnavailable("character continuity analysis implementation substitution rejected")
            return self.analysis_strategy, self.analysis_provider
        if task_version != "2" or type(self.strategy) is not DeterministicCharacterContinuityStrategy or type(self.provider) is not DeterministicCharacterContinuityProvider:
            raise ReasoningUnavailable("character continuity implementation substitution rejected")
        expected = ("vss.analyze-character-continuity.deterministic", "1.0.0", "vss.reasoning.character-continuity.deterministic", "1.0.0", "1")
        actual = (self.strategy.identity, self.strategy.version, self.provider.identity, self.provider.version, self.provider.api_version)
        if actual != expected:
            raise ReasoningUnavailable("character continuity implementation is incompatible")
        return self.strategy, self.provider

    @property
    def digest(self):
        return canonical_digest({"m5.2":{"strategy":[self.strategy.identity,self.strategy.version], "provider":[self.provider.identity,self.provider.version,self.provider.api_version]}, "m5.3":{"strategy":[self.analysis_strategy.identity,self.analysis_strategy.version], "provider":[self.analysis_provider.identity,self.analysis_provider.version,self.analysis_provider.api_version]}, "calls":1, "iterations":1, "retry":False, "fallback":False, "persistence":False})
