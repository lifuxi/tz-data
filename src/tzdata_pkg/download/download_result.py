from dataclasses import dataclass
from typing import Optional


@dataclass
class DownloadResult:
    """Download result structure."""
    success: bool
    url: str
    file_path: Optional[str]
    error: Optional[str]
    data_type: str
    trade_date: str
    record_count: int = 0
