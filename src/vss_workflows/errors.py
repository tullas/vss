from __future__ import annotations

from vss_commands.exit_codes import ExitCode


class WorkflowFailure(RuntimeError):
    exit_code = ExitCode.WORKFLOW_INTERNAL_ERROR
    category = "internal_workflow_failure"


class WorkflowNotFound(WorkflowFailure):
    exit_code = ExitCode.WORKFLOW_NOT_FOUND
    category = "workflow_not_found"


class InvalidWorkflow(WorkflowFailure):
    exit_code = ExitCode.INVALID_WORKFLOW
    category = "invalid_workflow"


class UnsupportedWorkflowVersion(InvalidWorkflow):
    exit_code = ExitCode.UNSUPPORTED_WORKFLOW_VERSION
    category = "unsupported_workflow_version"


class UnknownWorkflowOperation(InvalidWorkflow):
    exit_code = ExitCode.UNKNOWN_WORKFLOW_OPERATION
    category = "unknown_workflow_operation"


class RecursiveWorkflowInvocation(UnknownWorkflowOperation):
    pass


class WorkflowExecutionFailure(WorkflowFailure):
    exit_code = ExitCode.WORKFLOW_EXECUTION_FAILURE
    category = "workflow_execution_failure"


class WorkflowTimeout(WorkflowFailure):
    exit_code = ExitCode.WORKFLOW_TIMEOUT
    category = "workflow_timeout"


class InternalWorkflowFailure(WorkflowFailure):
    pass
