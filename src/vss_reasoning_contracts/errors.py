class SemanticContractError(ValueError):
    """Safe base error for inert semantic contract processing."""


class InvalidSemanticInput(SemanticContractError):
    pass


class UnsupportedContractVersion(SemanticContractError):
    pass


class UnknownContractIdentity(SemanticContractError):
    pass


class IncompatibleContract(SemanticContractError):
    pass


class InvalidContractSchema(SemanticContractError):
    pass


class RegistryIntegrityError(SemanticContractError):
    pass


class UnsafeSemanticContent(SemanticContractError):
    pass


class ContractDisabled(SemanticContractError):
    pass


class InternalContractError(SemanticContractError):
    pass
