class PerformanceError(RuntimeError):
    """Safe base failure for the local performance laboratory."""


class InvalidPerformanceProfile(PerformanceError):
    pass


class PerformanceCorrectnessFailure(PerformanceError):
    pass


class PerformanceTimeout(PerformanceError):
    pass


class PerformanceReportFailure(PerformanceError):
    pass
