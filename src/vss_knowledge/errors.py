class KnowledgeOperationError(Exception):
    pass


class UnknownKnowledgeSource(KnowledgeOperationError):
    pass


class KnowledgePolicyDenied(KnowledgeOperationError):
    pass


class KnowledgeFixtureFailure(KnowledgeOperationError):
    pass


class KnowledgeAuditFailure(KnowledgeOperationError):
    pass
