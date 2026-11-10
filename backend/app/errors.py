class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProviderError(AppError):
    """An explicitly configured AWS call failed. Callers must not replace it."""

    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class ConfigurationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=503)
