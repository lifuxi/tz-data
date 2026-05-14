"""
Bill-to-market reconciliation engine.
Compares trade execution prices in bill statements with market quotes
to analyze slippage and execution quality.
"""
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


class BillMarketReconciler:
    """
    Reconciles bill trade records with market quote data.

    Analyzes:
    - Slippage: difference between bill execution price and market price
    - VWAP comparison: execution price vs volume-weighted average price
    - Time-based price verification: was the price valid at execution time?
    """

    @staticmethod
    def reconcile_trades(
        trades: list[dict],
        market_quotes: list[dict],
        price_tolerance_pct: float = 5.0
    ) -> list[dict]:
        """
        Reconcile bill trades against market quotes.

        Args:
            trades: List of trade records from bill statement
                Each trade has: {
                    'contract_code': str,
                    'trade_date': str (YYYY-MM-DD),
                    'direction': str ('buy' or 'sell'),
                    'price': float,
                    'volume': int,
                }
            market_quotes: List of market quote records
                Each quote has: {
                    'trade_date': str,
                    'contract_code': str,
                    'open': float, 'high': float, 'low': float, 'close': float,
                    'settle': float, 'vwap': float (optional),
                }
            price_tolerance_pct: Alert threshold for price deviation (%)

        Returns:
            List of reconciliation results for each trade
        """
        results = []

        # Build quote lookup: (date, contract) -> quote
        quote_lookup = {}
        for q in market_quotes:
            key = (q['trade_date'], q.get('contract_code', ''))
            quote_lookup[key] = q

        for trade in trades:
            trade_date = trade.get('trade_date', '')
            contract = trade.get('contract_code', '')
            exec_price = trade.get('price', 0)
            direction = trade.get('direction', '')
            volume = trade.get('volume', 0)

            quote = quote_lookup.get((trade_date, contract))

            if not quote:
                results.append({
                    'trade_date': trade_date,
                    'contract_code': contract,
                    'direction': direction,
                    'exec_price': exec_price,
                    'volume': volume,
                    'status': 'no_quote',
                    'slippage': None,
                    'slippage_pct': None,
                    'warning': 'No market quote found for this date/contract'
                })
                continue

            # Use VWAP if available, otherwise use settle price as reference
            ref_price = quote.get('vwap') or quote.get('settle') or quote.get('close')

            if not ref_price or ref_price == 0:
                results.append({
                    'trade_date': trade_date,
                    'contract_code': contract,
                    'direction': direction,
                    'exec_price': exec_price,
                    'volume': volume,
                    'status': 'no_ref_price',
                    'slippage': None,
                    'slippage_pct': None,
                    'warning': 'No valid reference price in market quote'
                })
                continue

            slippage = exec_price - ref_price
            slippage_pct = (slippage / ref_price) * 100

            # For buy trades, positive slippage = paid more than reference (bad)
            # For sell trades, negative slippage = received less than reference (bad)
            if direction == 'buy':
                is_alert = slippage_pct > price_tolerance_pct
            else:
                is_alert = abs(slippage_pct) > price_tolerance_pct

            results.append({
                'trade_date': trade_date,
                'contract_code': contract,
                'direction': direction,
                'exec_price': round(exec_price, 2),
                'ref_price': round(ref_price, 2),
                'volume': volume,
                'status': 'alert' if is_alert else 'ok',
                'slippage': round(slippage, 2),
                'slippage_pct': round(slippage_pct, 4),
                'warning': f'滑点 {slippage_pct:.2f}%' if is_alert else None,
                'high': quote.get('high'),
                'low': quote.get('low'),
                'in_range': quote.get('low', 0) <= exec_price <= quote.get('high', float('inf')),
            })

        return results

    @staticmethod
    def generate_slippage_report(reconciled: list[dict]) -> dict:
        """
        Generate aggregated slippage report from reconciled trades.

        Returns:
            Summary report with statistics
        """
        if not reconciled:
            return {'total_trades': 0, 'message': 'No trades to analyze'}

        total = len(reconciled)
        with_slippage = [r for r in reconciled if r.get('slippage') is not None]
        alerts = [r for r in reconciled if r.get('status') == 'alert']
        no_quotes = [r for r in reconciled if r.get('status') == 'no_quote']

        avg_slippage_pct = 0
        max_slippage = 0
        max_slippage_trade = None

        for r in with_slippage:
            pct = abs(r.get('slippage_pct', 0))
            if pct > max_slippage:
                max_slippage = pct
                max_slippage_trade = r
            avg_slippage_pct += pct

        if with_slippage:
            avg_slippage_pct /= len(with_slippage)

        return {
            'total_trades': total,
            'matched_quotes': len(with_slippage),
            'no_quotes': len(no_quotes),
            'alert_count': len(alerts),
            'avg_slippage_pct': round(avg_slippage_pct, 4),
            'max_slippage_pct': round(max_slippage, 4),
            'max_slippage_trade': max_slippage_trade,
            'alert_details': [r for r in alerts]
        }

    @staticmethod
    def reconcile_from_db(
        account_id: int,
        trade_date_start: date,
        trade_date_end: date,
        price_tolerance_pct: float = 5.0
    ) -> dict:
        """
        Reconcile bill trades against market data stored in database.

        Args:
            account_id: Account ID to reconcile
            trade_date_start: Start date
            trade_date_end: End date
            price_tolerance_pct: Alert threshold

        Returns:
            Reconciliation report
        """
        try:
            from tzdata_pkg.storage.db_registry import DBRegistry

            pool = DBRegistry().get_pool('trading')
            trades = []
            quotes = []

            # Fetch trades from trades table
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT trade_date, instrument, direction, price, volume
                    FROM trades
                    WHERE account_id = ?
                      AND trade_date BETWEEN ? AND ?
                      AND price IS NOT NULL
                    ORDER BY trade_date
                """, (str(account_id), trade_date_start.isoformat(), trade_date_end.isoformat()))

                for row in cursor.fetchall():
                    trades.append({
                        'trade_date': row[0],
                        'contract_code': row[1],
                        'direction': row[2],
                        'price': row[3],
                        'volume': row[4],
                    })

            # Fetch market quotes (daily) from market DB
            market_pool = DBRegistry().get_pool('market')
            with market_pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT contract_code, trade_date, open, high, low, close, settle
                    FROM daily_quotes
                    WHERE trade_date BETWEEN ? AND ?
                    ORDER BY trade_date
                """, (trade_date_start.isoformat(), trade_date_end.isoformat()))

                for row in cursor.fetchall():
                    quotes.append({
                        'contract_code': row[0],
                        'trade_date': row[1],
                        'open': row[2],
                        'high': row[3],
                        'low': row[4],
                        'close': row[5],
                        'settle': row[6],
                    })

            reconciled = BillMarketReconciler.reconcile_trades(
                trades, quotes, price_tolerance_pct
            )
            report = BillMarketReconciler.generate_slippage_report(reconciled)

            return {
                'success': True,
                'account_id': account_id,
                'date_range': f'{trade_date_start} to {trade_date_end}',
                'reconciled': reconciled,
                'report': report
            }

        except Exception as e:
            logger.error(f"Reconciliation from DB failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
