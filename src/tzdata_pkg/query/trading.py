"""Trading data query module.

Provides user-friendly access to bills, trades, and account data.
"""

from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.storage.trading_store import TradingStore


class TradingQuery:
    """High-level trading data queries."""

    def __init__(self, registry: DBRegistry):
        self._store = TradingStore(registry)

    def bills(self, account_id: Optional[str] = None) -> list[dict]:
        """List available bills.

        Args:
            account_id: Filter by account

        Returns:
            List of bill summary dicts.
        """
        return self._store.list_bills(account_id=account_id)

    def trades(self, account_id: Optional[str] = None,
               start_date: Optional[str] = None, end_date: Optional[str] = None,
               instrument: Optional[str] = None) -> list[dict]:
        """Query trade records.

        Args:
            account_id: Filter by account
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            instrument: Filter by instrument

        Returns:
            List of trade dicts.
        """
        return self._store.list_trades(
            account_id=account_id, start_date=start_date,
            end_date=end_date, instrument=instrument,
        )

    def matched_trades(self, instrument: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> list[dict]:
        """Query matched (open-close pair) trades.

        Returns:
            List of matched trade dicts.
        """
        return self._store.list_matched_trades(
            instrument=instrument, start_date=start_date, end_date=end_date,
        )

    def positions(self, instrument: Optional[str] = None,
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> list[dict]:
        """Query position summaries.

        Returns:
            List of position summary dicts.
        """
        return self._store.get_positions_summary(
            instrument=instrument, start_date=start_date, end_date=end_date,
        )

    def account_summary(self, account_id: Optional[str] = None) -> list[dict]:
        """Query account monthly summaries.

        Returns:
            List of account summary dicts.
        """
        return self._store.get_account_summary(account_id=account_id)

    def pnl_summary(self, account_id: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> dict:
        """Get P&L summary for an account.

        Returns:
            Dict with total_pnl, trade_count, avg_pnl, etc.
        """
        trades = self.trades(
            account_id=account_id, start_date=start_date, end_date=end_date,
        )
        if not trades:
            return {"trade_count": 0}

        pnl_values = [t.get("realized_pl", 0) or 0 for t in trades]
        fee_values = [t.get("fee", 0) or 0 for t in trades]

        return {
            "account_id": account_id or "all",
            "trade_count": len(trades),
            "total_pnl": sum(pnl_values),
            "total_fees": sum(fee_values),
            "avg_pnl_per_trade": sum(pnl_values) / len(pnl_values),
            "date_range": f"{start_date or 'all'} ~ {end_date or 'all'}",
        }
