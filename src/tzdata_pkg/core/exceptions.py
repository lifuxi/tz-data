"""
Custom exception hierarchy for tz-data.
"""


class TZDataException(Exception):
    """Base exception for tz-data."""

    def __init__(self, message: str = "tz-data error", code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DataAccessException(TZDataException):
    """Error accessing database or data source."""

    def __init__(self, message: str, source: str = ""):
        full = f"Data access error from {source}: {message}" if source else message
        super().__init__(message=full, code="DATA_ACCESS_ERROR")
        self.source = source


class DataParseError(TZDataException):
    """Error parsing data files (bills, CSVs, etc.)."""

    def __init__(self, message: str, file_path: str = ""):
        location = f" in {file_path}" if file_path else ""
        super().__init__(
            message=f"Data parse error{location}: {message}",
            code="DATA_PARSE_ERROR",
        )
        self.file_path = file_path


class DataSourceUnavailableError(TZDataException):
    """External data source temporarily unavailable."""

    def __init__(self, source: str, message: str = ""):
        full = (
            f"Data source '{source}' is unavailable: {message}"
            if message
            else f"Data source '{source}' is unavailable"
        )
        super().__init__(message=full, code="DATA_SOURCE_UNAVAILABLE")


class DownloadError(TZDataException):
    """Error during data download."""

    def __init__(self, message: str, url: str = "", status_code: int = 0):
        self.url = url
        self.status_code = status_code
        full = f"Download failed from {url}: {message}" if url else message
        super().__init__(message=full, code="DOWNLOAD_ERROR")


class ValidationError(TZDataException):
    """Data validation failed."""

    def __init__(self, message: str, field: str = ""):
        full = f"Validation error in '{field}': {message}" if field else message
        super().__init__(message=full, code="VALIDATION_ERROR")
        self.field = field


class StorageError(TZDataException):
    """Error writing to storage."""

    def __init__(self, message: str, db_path: str = ""):
        full = f"Storage error: {message}"
        super().__init__(message=full, code="STORAGE_ERROR")
        self.db_path = db_path
