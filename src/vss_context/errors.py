from vss_context_contracts.errors import ContextContractError
from .audit import ContextAuditFailure

class ContextAssemblyError(ContextContractError):
    pass

class ContextPolicyDenied(ContextAssemblyError):
    pass

class ContextBudgetExceeded(ContextAssemblyError):
    pass

class ContextPackageFailure(ContextAssemblyError):
    pass
