class KnowledgeContractError(Exception):
    """Safe base error for knowledge contract failures."""


class InvalidKnowledgeInput(KnowledgeContractError):
    pass


class UnknownKnowledgeContract(KnowledgeContractError):
    pass


class KnowledgeRegistryFailure(KnowledgeContractError):
    pass


class KnowledgeIntegrityFailure(KnowledgeContractError):
    pass
