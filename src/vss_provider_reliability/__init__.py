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

__all__ = (
    "DigitalTwinScenario",
    "EXTERNAL_PROVIDER_ADMISSION_RULE",
    "FailureClass",
    "FlightRecorder",
    "ProviderDigitalTwin",
    "ProviderReadiness",
    "ProviderReliabilityEngineer",
    "assess_readiness",
)
