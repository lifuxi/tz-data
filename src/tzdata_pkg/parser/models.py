"""
Data models for bill parsing results.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List


@dataclass
class BillSummary:
    """Bill summary data."""
    client_id: str
    client_name: str
    account_id: str
    currency: str
    bill_date_start: date
    bill_date_end: date

    # Financial summary
    balance_bf: float = 0.0
    balance_cf: float = 0.0
    deposit_withdrawal: float = 0.0
    realized_pl: float = 0.0
    mtm_pl: float = 0.0
    exercise_pl: float = 0.0
    commission: float = 0.0
    exercise_fee: float = 0.0
    delivery_fee: float = 0.0
    premium_received: float = 0.0
    premium_paid: float = 0.0
    delivery_pl: float = 0.0

    # Margin and equity
    initial_margin: float = 0.0
    pledge_amount: float = 0.0
    client_equity: float = 0.0
    fx_pledge_occ: float = 0.0
    margin_occupied: float = 0.0
    delivery_margin: float = 0.0
    market_value_long: float = 0.0
    market_value_short: float = 0.0
    market_value_equity: float = 0.0
    fund_available: float = 0.0
    risk_degree: float = 0.0
    margin_call: float = 0.0


@dataclass
class DepositRecord:
    """Deposit/withdrawal record."""
    date: date
    type: str
    deposit: float
    withdrawal: float
    exchange_rate: Optional[float]
    account_id: str
    note: str


@dataclass
class TransactionRecord:
    """Transaction/trade record."""
    date: date
    invest_unit: str
    exchange: str
    trading_code: str
    product: str
    instrument: str
    direction: str
    hedge_type: str
    price: float
    lots: int
    turnover: float
    open_close: str
    fee: float
    realized_pl: float
    premium: float
    trans_no: str
    account_id: str

    # Derived fields
    instrument_type: str = "future"
    option_type: Optional[str] = None


@dataclass
class PositionRecord:
    """Position holding record."""
    date: date
    invest_unit: str
    exchange: str
    trading_code: str
    product: str
    instrument: str
    direction: str
    hedge_type: str
    positions: int
    prev_settle: float
    curr_settle: float
    mtm_pl: float
    float_pl: float
    margin: float
    account_id: str

    # Derived fields
    instrument_type: str = "future"


@dataclass
class ParseLog:
    """Parse operation log."""
    file_path: str
    success: bool
    timestamp: str
    records_parsed: int = 0
    error_message: Optional[str] = None
    sections_parsed: List[str] = field(default_factory=list)


@dataclass
class BillParseResult:
    """Complete bill parse result."""
    summary: Optional[BillSummary] = None
    deposits: List[DepositRecord] = field(default_factory=list)
    transactions: List[TransactionRecord] = field(default_factory=list)
    positions: List[PositionRecord] = field(default_factory=list)
    parse_log: Optional[ParseLog] = None
