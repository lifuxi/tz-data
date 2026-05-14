"""Data verification models for bill reconciliation and cross-db checks."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VerifyCheck:
    """Single verification check result."""
    name: str
    status: str  # PASS / FAIL / WARN / SKIP
    source: str
    expected: Any
    actual: Any
    deviation: float = 0.0
    message: str = ""


@dataclass
class VerifyReport:
    """Complete verification report."""
    timestamp: str
    checks: list[VerifyCheck] = field(default_factory=list)

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.status == "SKIP")

    @property
    def overall_status(self) -> str:
        if self.failed > 0:
            return "UNRELIABLE"
        elif self.warnings > 0:
            return "QUESTIONABLE"
        elif self.passed > 0:
            return "TRUSTWORTHY"
        return "NO_DATA"
