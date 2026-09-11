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
from .certification import (
    CertificationStatus,
    ExpertiseDisposition,
    assess_certification_readiness,
    assert_request_matches_certification,
    assert_production_eligible,
    classify_expertise,
    durable_moving_shot_package,
    reconstruct_durable_moving_shot_request,
    validate_provider_certification,
)

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
    "CertificationStatus",
    "ExpertiseDisposition",
    "classify_expertise",
    "durable_moving_shot_package",
    "reconstruct_durable_moving_shot_request",
    "validate_provider_certification",
    "assess_certification_readiness",
    "assert_request_matches_certification",
    "assert_production_eligible",
)
