"""Market data query module.

Provides user-friendly access to quotes, positions, contracts, and Tushare data.
"""

from datetime import date
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.storage.market_store import MarketStore


class MarketQuery:
    """High-level market data queries."""

    def __init__(self, registry: DBRegistry):
        self._store = MarketStore(registry)

    def quotes(self, exchange: Optional[str] = None, contract: Optional[str] = None,
               start_date: Optional[str] = None, end_date: Optional[str] = None,
               frequency: str = "daily") -> list[dict]:
        """Query quote data.

        Args:
            exchange: Exchange code (CFFEX, SHFE, etc.)
            contract: Contract code (MO2505, AU2506, etc.)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            frequency: "daily" or "minute"

        Returns:
            List of quote dicts sorted by date.
        """
        return self._store.get_quotes(
            exchange=exchange, contract=contract,
            start_date=start_date, end_date=end_date,
            frequency=frequency,
        )

    def positions(self, exchange: Optional[str] = None, contract: Optional[str] = None,
                  trade_date: Optional[str] = None) -> list[dict]:
        """Query position ranking data.

        Args:
            exchange: Exchange code
            contract: Contract code
            trade_date: Specific date (YYYY-MM-DD)

        Returns:
            List of position detail dicts.
        """
        return self._store.get_positions(
            exchange=exchange, contract=contract, trade_date=trade_date,
        )

    def contracts(self, exchange: Optional[str] = None, variety: Optional[str] = None,
                  contract_type: Optional[str] = None) -> list[dict]:
        """Query contract metadata.

        Args:
            exchange: Exchange code
            variety: Underlying variety (MO, IM, AU, etc.)
            contract_type: "futures" or "option_call"/"option_put"

        Returns:
            List of contract dicts.
        """
        return self._store.list_contracts(
            exchange=exchange, variety=variety, contract_type=contract_type,
        )

    def top_holders(self, contract: str, trade_date: Optional[str] = None,
                    limit: int = 20) -> dict:
        """Get top holders by long/short volume for a contract.

        Args:
            contract: Contract code
            trade_date: Specific date (defaults to latest)
            limit: Number of top holders to return

        Returns:
            Dict with "long" and "short" lists of (member_name, volume).
        """
        positions = self.positions(contract=contract, trade_date=trade_date)

        long_ranking = sorted(positions, key=lambda x: x.get("long_volume", 0) or 0, reverse=True)[:limit]
        short_ranking = sorted(positions, key=lambda x: x.get("short_volume", 0) or 0, reverse=True)[:limit]

        return {
            "contract": contract,
            "trade_date": trade_date or "latest",
            "long": [{"member": p["member_name"], "volume": p["long_volume"]} for p in long_ranking],
            "short": [{"member": p["member_name"], "volume": p["short_volume"]} for p in short_ranking],
        }

    def quote_summary(self, contract: str, start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> Optional[dict]:
        """Get summary statistics for a contract's quotes.

        Returns:
            Dict with avg_close, max_volume, total_turnover, etc. or None.
        """
        quotes = self.quotes(contract=contract, start_date=start_date, end_date=end_date)
        if not quotes:
            return None

        closes = [q["close"] for q in quotes if q.get("close")]
        volumes = [q["volume"] for q in quotes if q.get("volume")]

        return {
            "contract": contract,
            "data_points": len(quotes),
            "date_range": f"{quotes[0].get('trade_date', '?')} ~ {quotes[-1].get('trade_date', '?')}",
            "avg_close": sum(closes) / len(closes) if closes else None,
            "max_close": max(closes) if closes else None,
            "min_close": min(closes) if closes else None,
            "max_volume": max(volumes) if volumes else None,
        }
