class RateLimitError(Exception):
    def __init__(self, message: str = "Too many requests"):
        self.message = message
        self.code = "rate_limit_exceeded"
        super().__init__(message)


class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    def __init__(self, message: str = "Not enough permissions"):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    def __init__(self, message: str = "Conflict"):
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str = "Invalid request"):
        self.message = message
        super().__init__(message)
