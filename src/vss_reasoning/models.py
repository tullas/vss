from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vss_reasoning_contracts import ValidatedSemanticRequest, ValidatedSemanticResult


@dataclass(frozen=True, slots=True)
class ImplementationIdentity:
    identity: str
    version: str
    api_version: str
    lifecycle_status: str
    trust: str


@dataclass(frozen=True, slots=True)
class ReasoningPolicy:
    identity: str
    version: str
    environments: frozenset[str]
    classifications: frozenset[str]
    purposes: frozenset[str]
    maximum_provider_calls: int = 1
    maximum_iterations: int = 8


@dataclass(frozen=True, slots=True)
class DeterministicReasoningContext:
    request_id: str
    correlation_id: str
    execution_id: str
    environment: str
    permitted_purpose: str
    data_classification: str
    strategy: ImplementationIdentity
    provider: ImplementationIdentity
    deadline: float
    maximum_result_bytes: int
    maximum_provider_calls: int
    maximum_iterations: int
    semantic_content_digest: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class OptionPrimitive:
    profile_id: str
    title: str
    description: str
    benefits: tuple[str, ...]
    drawbacks: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateOptions:
    options: tuple[OptionPrimitive, ...]
    provider_calls: int
    iterations: int


@dataclass(frozen=True, slots=True)
class ReasoningOutcome:
    output: Mapping[str, Any]
    validated_request: ValidatedSemanticRequest
    validated_result: ValidatedSemanticResult | None
    content_digest: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", MappingProxyType(dict(self.output)))
