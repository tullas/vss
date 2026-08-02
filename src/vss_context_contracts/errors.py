class ContextContractError(Exception):
    """Safe base error for Context contract failures."""


class ContextRegistryError(ContextContractError):
    pass


class InvalidContextInput(ContextContractError):
    pass


class ContextIntegrityFailure(ContextContractError):
    pass
