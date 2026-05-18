"""Signal engine: generates trading signals from institution flow data.

Reads from tzdata_analysis.db (institution_daily_features, market_regime)
and writes trading_signals + signal_triggers tables.

Usage:
    from tzdata_pkg.maintenance.analysis.signal_engine import SignalEngine
    engine = SignalEngine(registry)
    engine.generate_daily_signals("2025-03-10")
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Signal type constants
ENTRY_LONG = "entry_long"
ENTRY_SHORT = "entry_short"
EXIT = "exit"
REDUCE = "reduce"

# Signal source constants
SOURCE_INSTITUTION = "institution_flow"
SOURCE_REGIME = "market_regime"
SOURCE_COMPOSITE = "composite"


class SignalEngine:
    """Generate and manage trading signals from analysis data."""

    def __init__(self, registry):
        self.registry = registry

    def _analysis_pool(self):
        return self.registry.get_pool("analysis")

    # ── Signal Generation ─────────────────────────────────────

    def generate_daily_signals(self, trade_date: str,
                               inst_threshold: float = 0.6,
                               regime_filter: bool = True) -> list[dict]:
        """Generate signals for a given trade date.

        Combines:
        1. Institution flow signals (large net volume from top members)
        2. Regime confirmation (only generate entry signals in trending regimes)

        Args:
            trade_date: YYYY-MM-DD
            inst_threshold: Minimum concentration score for institution signal
            regime_filter: Whether to filter by market regime

        Returns:
            List of generated signal dicts
        """
        pool = self._analysis_pool()
        with pool.connection() as conn:
            # Get institution features for the date
            features = conn.execute("""
                SELECT member_name, contract_code, exchange,
                       long_volume, short_volume, net_volume,
                       long_change, short_change, net_change,
                       member_rank_long, member_rank_short,
                       member_long_pct, member_short_pct,
                       concentration_score
                FROM institution_daily_features
                WHERE trade_date = ?
                ORDER BY concentration_score DESC
            """, (trade_date,)).fetchall()

            # Get current regime
            regime = None
            if regime_filter:
                row = conn.execute("""
                    SELECT regime_type, trend_strength, volatility_level, iv_regime
                    FROM market_regime
                    WHERE trade_date = ?
                    ORDER BY id DESC LIMIT 1
                """, (trade_date,)).fetchone()
                if row:
                    regime = dict(zip(
                        ["regime_type", "trend_strength", "volatility_level", "iv_regime"], row
                    ))

            signals = []
            for f in features:
                feat = dict(zip([
                    "member_name", "contract_code", "exchange",
                    "long_volume", "short_volume", "net_volume",
                    "long_change", "short_change", "net_change",
                    "member_rank_long", "member_rank_short",
                    "member_long_pct", "member_short_pct",
                    "concentration_score",
                ], f))

                sig = self._evaluate_signal(trade_date, feat, regime, inst_threshold)
                if sig:
                    signals.append(sig)

            # Save signals
            saved = self._save_signals(signals)
            logger.info(f"SignalEngine: {len(signals)} signals generated for {trade_date}, {saved} saved")
            return signals

    def _evaluate_signal(self, trade_date: str, feat: dict,
                         regime: dict | None, threshold: float) -> dict | None:
        """Evaluate whether a feature set generates a signal."""

        conc = feat.get("concentration_score") or 0
        net_vol = feat.get("net_volume") or 0
        net_change = feat.get("net_change") or 0

        # High concentration + strong net position → signal
        if conc < threshold:
            return None

        # Determine signal direction
        if net_vol > 0 and net_change > 0:
            signal_type = ENTRY_LONG
        elif net_vol < 0 and net_change < 0:
            signal_type = ENTRY_SHORT
        else:
            return None  # No clear directional signal

        # Regime filtering: only generate entry signals if regime supports
        if regime:
            regime_type = regime.get("regime_type", "")
            if signal_type == ENTRY_LONG and regime_type == "trending_down":
                return None  # Don't go long in downtrend
            if signal_type == ENTRY_SHORT and regime_type == "trending_up":
                return None  # Don't go short in uptrend

        strength = min(1.0, conc * 0.5 + abs(net_change) / max(abs(net_vol), 1) * 0.5)

        return {
            "signal_date": trade_date,
            "product": feat.get("contract_code"),
            "exchange": feat.get("exchange"),
            "signal_type": signal_type,
            "strength": round(strength, 3),
            "source": SOURCE_COMPOSITE if regime else SOURCE_INSTITUTION,
            "detail": json.dumps({
                "member_name": feat.get("member_name"),
                "concentration_score": conc,
                "net_volume": net_vol,
                "net_change": net_change,
                "regime": regime.get("regime_type") if regime else None,
            }),
            "triggered": 0,
        }

    def _save_signals(self, signals: list[dict]) -> int:
        """Save signals to trading_signals table."""
        if not signals:
            return 0

        pool = self._analysis_pool()
        count = 0
        with pool.connection() as conn:
            for sig in signals:
                try:
                    conn.execute("""
                        INSERT INTO trading_signals
                            (signal_date, product, exchange, signal_type,
                             strength, source, detail, triggered)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sig["signal_date"], sig["product"], sig["exchange"],
                        sig["signal_type"], sig["strength"], sig["source"],
                        sig["detail"], sig["triggered"],
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to save signal: {e}")

        return count

    # ── Signal Triggers ───────────────────────────────────────

    def trigger_signal(self, signal_id: int, entry_price: float,
                       trigger_date: str) -> int:
        """Mark a signal as triggered with entry price."""
        pool = self._analysis_pool()
        with pool.connection() as conn:
            conn.execute("""
                INSERT INTO signal_triggers
                    (signal_id, trigger_date, entry_price, status)
                VALUES (?, ?, ?, 'open')
            """, (signal_id, trigger_date, entry_price))

            conn.execute("""
                UPDATE trading_signals
                SET triggered = 1, triggered_date = ?
                WHERE id = ?
            """, (trigger_date, signal_id))

        logger.info(f"Signal {signal_id} triggered at {entry_price} on {trigger_date}")
        return signal_id

    def close_signal_trigger(self, trigger_id: int, exit_price: float,
                             holding_days: int) -> float:
        """Close a signal trigger and calculate PnL."""
        pool = self._analysis_pool()
        with pool.connection() as conn:
            # Get trigger info
            row = conn.execute("""
                SELECT st.entry_price, ts.signal_type
                FROM signal_triggers st
                JOIN trading_signals ts ON st.signal_id = ts.id
                WHERE st.id = ?
            """, (trigger_id,)).fetchone()

            if not row:
                logger.warning(f"Trigger {trigger_id} not found")
                return 0.0

            entry_price, signal_type = row

            # Calculate PnL based on signal direction
            if signal_type == ENTRY_LONG:
                pnl = exit_price - entry_price
            elif signal_type == ENTRY_SHORT:
                pnl = entry_price - exit_price
            else:
                pnl = 0.0

            conn.execute("""
                UPDATE signal_triggers
                SET exit_price = ?, holding_days = ?, pnl = ?, status = 'closed'
                WHERE id = ?
            """, (exit_price, holding_days, pnl, trigger_id))

            conn.execute("""
                UPDATE trading_signals
                SET triggered_pnl = ?
                WHERE id = (SELECT signal_id FROM signal_triggers WHERE id = ?)
            """, (pnl, trigger_id))

        logger.info(f"Trigger {trigger_id} closed: PnL={pnl:.2f}")
        return pnl

    # ── Signal Queries ────────────────────────────────────────

    def get_active_signals(self, trade_date: str) -> list[dict]:
        """Get untriggered signals for a date."""
        pool = self._analysis_pool()
        with pool.connection() as conn:
            cursor = conn.execute("""
                SELECT id, signal_date, product, exchange, signal_type,
                       strength, source, detail
                FROM trading_signals
                WHERE signal_date <= ? AND triggered = 0
                ORDER BY strength DESC
            """, (trade_date,))
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_signal_performance(self, start_date: str = None,
                               end_date: str = None) -> dict:
        """Aggregate performance of closed signal triggers."""
        pool = self._analysis_pool()
        where = "WHERE st.status = 'closed'"
        params: list = []
        if start_date:
            where += " AND st.trigger_date >= ?"
            params.append(start_date)
        if end_date:
            where += " AND st.trigger_date <= ?"
            params.append(end_date)

        with pool.connection() as conn:
            row = conn.execute(f"""
                SELECT COUNT(*) as total,
                       AVG(st.pnl) as avg_pnl,
                       SUM(CASE WHEN st.pnl > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate,
                       SUM(st.pnl) as total_pnl,
                       AVG(st.holding_days) as avg_holding_days
                FROM signal_triggers st
                {where}
            """, params).fetchone()

            if not row or row[0] == 0:
                return {"total": 0}

            return {
                "total": row[0],
                "avg_pnl": row[1] or 0,
                "win_rate": row[2] or 0,
                "total_pnl": row[3] or 0,
                "avg_holding_days": row[4] or 0,
            }
