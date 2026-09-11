"""Bounded, offline provider reliability diagnostics.

This package records evidence and rehearses provider lifecycles.  It has no
provider handles, credentials, network transport, retry, or execution APIs.
"""

from .foundation import (
    EXTERNAL_PROVIDER_ADMISSION_RULE,
    FailureClass,
    FlightRecorder,
    ProviderReliabilityEngineer,
    ProviderReadiness,
    assess_readiness,
)
from .digital_twin import DigitalTwinScenario, ProviderDigitalTwin
from .lifecycle import (
    ApprovedShotPackage,
    LifecycleFailure,
    LifecycleResult,
    LifecycleState,
    OfflineProductionLifecycle,
    kpis,
)
from .semantics import provider_acceptance_evidenced, retry_permitted, same_operation_recovery_required

__all__ = (
    "DigitalTwinScenario",
    "EXTERNAL_PROVIDER_ADMISSION_RULE",
    "FailureClass",
    "FlightRecorder",
    "ProviderDigitalTwin",
    "ProviderReadiness",
    "ProviderReliabilityEngineer",
    "assess_readiness",
    "ApprovedShotPackage",
    "LifecycleFailure",
    "LifecycleResult",
    "LifecycleState",
    "OfflineProductionLifecycle",
    "kpis",
    "provider_acceptance_evidenced",
    "retry_permitted",
    "same_operation_recovery_required",
)
