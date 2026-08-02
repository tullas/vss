from __future__ import annotations


class ReasoningError(Exception):
    """Safe, typed failure raised by the bounded reasoning path."""


class InvalidReasoningRequest(ReasoningError):
    pass


class ReasoningUnauthorized(ReasoningError):
    pass


class ReasoningUnavailable(ReasoningError):
    pass


class ReasoningDeadlineExceeded(ReasoningError):
    pass


class ReasoningBudgetExceeded(ReasoningError):
    pass


class CandidateGenerationFailure(ReasoningError):
    pass


class InvalidReasoningResult(ReasoningError):
    pass


class ReasoningAuditFailure(ReasoningError):
    pass
