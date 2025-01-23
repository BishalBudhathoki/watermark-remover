class DownloadError(Exception):
    """Raised when there is an error during download."""
    pass

class ValidationError(Exception):
    """Raised when there is a validation error."""
    pass

class DatabaseError(Exception):
    """Raised when there is a database error."""
    pass

class APIError(Exception):
    """Raised when there is an API error."""
    pass

class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    pass
