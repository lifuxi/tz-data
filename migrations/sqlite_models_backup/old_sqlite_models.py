"""
BACKUP: Pre-migration sqlite_models.py (before Viewpoint 3 schema alignment).

This file preserves the OLD column definitions for reference during migration.
DO NOT import this file in production code.

Old definitions had columns that DID NOT match tz-data's canonical schema:
- Trade had bill_id ForeignKey (tz-data trades table has no bill_id FK)
- AccountSummary had client_id but no account_id, year, month indexes
- PositionSummary had client_id, avg_buy_price, avg_sell_price, speculation_hedge
  (tz-data has account_id, float_pl, created_at)
- Bill used status field differently (parse_status alias)

These mismatches caused:
1. Schema drift — tz-data writes columns tz2.0 doesn't expect
2. Silent data loss — columns with different names mean data in one isn't read by the other
3. Fragile coupling — any change in tz-data's schema breaks tz2.0 without warning

Migration: see migrations/sqlite_models_backup/README.md
"""

from datetime import date, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()
PositionsBase = declarative_base()


# ═══════════════════════════════════════════════════════════════════
# OLD Bill definition — KEPT as-is (tz2.0-specific columns preserved)
# ═══════════════════════════════════════════════════════════════════

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_date_start = Column(String(20), nullable=False, index=True)
    bill_date_end = Column(String(20), nullable=False)
    status = Column(String(20), default="parsed")
    file_path = Column(String(500))
    total_records = Column(Integer, default=0)
    parse_error = Column(Text)
    client_id = Column(String(50), index=True)
    client_name = Column(String(100))
    account_id = Column(String(50))
    currency = Column(String(10), default="CNY")
    balance_bf = Column(Float, default=0.0)
    balance_cf = Column(Float, default=0.0)
    deposit_withdrawal = Column(Float, default=0.0)
    realized_pl = Column(Float, default=0.0)
    mtm_pl = Column(Float, default=0.0)
    exercise_pl = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    premium_received = Column(Float, default=0.0)
    premium_paid = Column(Float, default=0.0)
    client_equity = Column(Float, default=0.0)
    margin_occupied = Column(Float, default=0.0)
    fund_available = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    @hybrid_property
    def bill_date(self):
        val = self.bill_date_start
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return datetime.combine(val, datetime.min.time())
        try:
            parsed = datetime.strptime(str(val), "%Y-%m-%d")
            return parsed
        except ValueError:
            return val

    @bill_date.setter
    def bill_date(self, value):
        if isinstance(value, datetime):
            self.bill_date_start = value.strftime("%Y-%m-%d")
            if self.bill_date_end is None:
                self.bill_date_end = value.strftime("%Y-%m-%d")
        elif isinstance(value, date):
            self.bill_date_start = value.isoformat()
            if self.bill_date_end is None:
                self.bill_date_end = value.isoformat()
        else:
            self.bill_date_start = str(value)
            if self.bill_date_end is None:
                self.bill_date_end = str(value)

    @hybrid_property
    def parse_status(self):
        return self.status

    @parse_status.setter
    def parse_status(self, value):
        self.status = value

    @property
    def upload_time(self):
        return self.created_at

    @property
    def updated_at(self):
        return self.created_at

    @updated_at.setter
    def updated_at(self, value):
        pass


# ═══════════════════════════════════════════════════════════════════
# OLD Trade definition — MISMATCH with tz-data schema
# ═══════════════════════════════════════════════════════════════════
# tz-data trades table: account_id, year, month, exchange, product,
#   premium, trade_id, position_type, created_at
# OLD tz2.0: bill_id (FK to bills)
#
# The bill_id column was tz2.0-specific and does NOT exist in tz-data's
# trades table. Data written by tz-data's bill import pipeline has no
# bill_id, so tz2.0 queries filtering by bill_id returned empty results.
# ═══════════════════════════════════════════════════════════════════

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True, index=True)  # REMOVED in new schema
    trade_date = Column(String(20), nullable=False, index=True)
    instrument = Column(String(30), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    offset_flag = Column(String(10), nullable=False)
    volume = Column(Integer, default=0)
    price = Column(Float, default=0.0)
    turnover = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)


# ═══════════════════════════════════════════════════════════════════
# OLD AccountSummary — MISMATCH with tz-data schema
# ═══════════════════════════════════════════════════════════════════
# tz-data account_summary: account_id, start_date, end_date, total_pnl,
#   accumulated_pnl, exercise_pnl, risk_degree, margin_call,
#   premium_received, premium_paid, market_value_long/short/equity
# OLD tz2.0: client_id (no account_id), end_date only (no start_date),
#   no accumulated_pnl/exercise_pnl/risk_degree/margin_call/...
# ═══════════════════════════════════════════════════════════════════

class AccountSummary(Base):
    __tablename__ = "account_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    client_id = Column(String(50), nullable=True, index=True)  # REPLACED by account_id
    balance_b_f = Column(Float, default=0.0)
    balance_c_f = Column(Float, default=0.0)
    client_equity = Column(Float, default=0.0)
    margin_occupied = Column(Float, default=0.0)
    deposit_withdrawal = Column(Float, default=0.0)
    realized_pl = Column(Float, default=0.0)
    mtm_pl = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    end_date = Column(String(20))


# ═══════════════════════════════════════════════════════════════════
# OLD PositionSummary — MISMATCH with tz-data schema
# ═══════════════════════════════════════════════════════════════════
# tz-data positions_summary: account_id, prev_settlement,
#   settlement_price, accumulated_pnl, margin_occupied, float_pl, created_at
# OLD tz2.0: bill_id (FK), client_id, avg_buy_price, avg_sell_price,
#   mtm_pl, speculation_hedge, market_value_long/short
# ═══════════════════════════════════════════════════════════════════

class PositionSummary(Base):
    __tablename__ = "positions_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True, index=True)  # REMOVED
    trade_date = Column(String(20), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    client_id = Column(String(50), nullable=True, index=True)  # REPLACED by account_id
    instrument = Column(String(30), nullable=False, index=True)
    long_position = Column(Integer, default=0)
    short_position = Column(Integer, default=0)
    avg_buy_price = Column(Float, default=0.0)  # REMOVED in new schema
    avg_sell_price = Column(Float, default=0.0)  # REMOVED in new schema
    prev_settlement = Column(Float, default=0.0)
    settlement_price = Column(Float, default=0.0)
    mtm_pl = Column(Float, default=0.0)  # REPLACED by float_pl
    margin_occupied = Column(Float, default=0.0)
    accumulated_pnl = Column(Float, default=0.0)
    speculation_hedge = Column(String(10), default="")  # REMOVED in new schema
    market_value_long = Column(Float, default=0.0)  # REMOVED in new schema
    market_value_short = Column(Float, default=0.0)  # REMOVED in new schema
