"""Institution builder: builds institution profiles from position detail data.

Reads raw position_detail data from tzdata_market.db (CFFEX holdings) and
writes aggregated institution data to tzdata_analysis.db:
- institution_master: unique institution registry
- institution_profiles: aggregated stats per institution
- institution_daily_features: daily per-institution position features
- institution_lead_lag: leading/lagging relationships between institutions

Usage:
    from tzdata_pkg.maintenance.analysis.institution_builder import InstitutionBuilder
    builder = InstitutionBuilder(registry)
    builder.build_daily("2025-03-10")
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class InstitutionBuilder:
    """Build and update institution analysis tables."""

    def __init__(self, registry):
        self.registry = registry

    def _analysis_pool(self):
        return self.registry.get_pool("analysis")

    def _market_pool(self):
        return self.registry.get_pool("market")

    # ── Daily Build ──────────────────────────────────────────

    def build_daily(self, trade_date: str) -> dict:
        """Build all institution tables for a given date.

        Pipeline:
        1. Sync institution master (new institutions)
        2. Compute daily features from position_detail
        3. Update institution profiles
        4. Compute lead-lag relationships

        Args:
            trade_date: YYYY-MM-DD

        Returns:
            {"features": N, "profiles_updated": M, "lead_lag": K}
        """
        features = self._build_daily_features(trade_date)
        profiles = self._update_profiles(trade_date)
        lead_lag = self._compute_lead_lag(trade_date)

        logger.info(
            f"InstitutionBuilder: {trade_date} — {features} features, "
            f"{profiles} profiles, {lead_lag} lead-lag"
        )
        return {
            "features": features,
            "profiles_updated": profiles,
            "lead_lag": lead_lag,
        }

    # ── Daily Features ───────────────────────────────────────

    def _build_daily_features(self, trade_date: str) -> int:
        """Compute institution_daily_features from position_detail."""
        pool = self._market_pool()

        # Get position data for the date
        with pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date, member_name, contract_code, exchange,
                       long_position, short_position,
                       total_long, total_short, total_volume
                FROM position_detail
                WHERE trade_date = ?
                AND member_name IS NOT NULL AND member_name != ''
            """, (trade_date,)).fetchall()

        if not rows:
            logger.warning(f"InstitutionBuilder: no position data for {trade_date}")
            return 0

        # Compute market totals
        market_long = sum(r[5] or 0 for r in rows)
        market_short = sum(r[6] or 0 for r in rows)

        # Build features
        pool = self._analysis_pool()
        count = 0
        with pool.connection() as conn:
            for r in rows:
                member_name = r[1]
                contract_code = r[2]
                exchange = r[3]
                long_vol = r[4] or 0
                short_vol = r[5] or 0
                net_vol = long_vol - short_vol

                # Changes from previous day (simplified — use same-day snapshot)
                long_pct = long_vol / market_long if market_long else 0
                short_pct = short_vol / market_short if market_short else 0

                # Concentration: how much of market this institution holds
                concentration = (long_pct + short_pct) / 2

                # Rank (simplified — would need full day sort for accurate rank)
                rank_long = None
                rank_short = None

                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO institution_daily_features
                            (trade_date, member_name, contract_code, exchange,
                             long_volume, short_volume, net_volume,
                             long_change, short_change, net_change,
                             member_rank_long, member_rank_short,
                             total_market_long, total_market_short,
                             member_long_pct, member_short_pct,
                             concentration_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_date, member_name, contract_code, exchange,
                        long_vol, short_vol, net_vol,
                        rank_long, rank_short,
                        market_long, market_short,
                        long_pct, short_pct,
                        concentration,
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to insert feature for {member_name}: {e}")

        return count

    # ── Institution Profiles ─────────────────────────────────

    def _update_profiles(self, trade_date: str) -> int:
        """Update institution_profiles with aggregated stats."""
        pool = self._analysis_pool()
        count = 0

        with pool.connection() as conn:
            # Get all unique members
            members = conn.execute("""
                SELECT member_name, SUM(long_volume) as total_long,
                       SUM(short_volume) as total_short
                FROM institution_daily_features
                WHERE trade_date <= ?
                GROUP BY member_name
            """, (trade_date,)).fetchall()

            for m in members:
                member_name, total_long, total_short = m
                net = total_long - total_short

                # Bias direction
                if net > 0:
                    bias = "long_bias"
                elif net < 0:
                    bias = "short_bias"
                else:
                    bias = "neutral"

                try:
                    conn.execute("""
                        INSERT INTO institution_profiles
                            (member_name, total_long, total_short,
                             first_appearance, last_appearance, bias_direction)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT DO UPDATE SET
                            total_long = excluded.total_long,
                            total_short = excluded.total_short,
                            last_appearance = excluded.last_appearance,
                            bias_direction = excluded.bias_direction,
                            last_updated = CURRENT_TIMESTAMP
                    """, (
                        member_name, total_long, total_short,
                        trade_date, trade_date, bias,
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to update profile for {member_name}: {e}")

        return count

    # ── Lead-Lag Analysis ────────────────────────────────────

    def _compute_lead_lag(self, trade_date: str, lookback: int = 5) -> int:
        """Compute lead-lag relationships between institutions.

        Identifies institutions whose position changes precede
        other institutions' changes.
        """
        pool = self._analysis_pool()
        count = 0

        with pool.connection() as conn:
            # Get recent features
            rows = conn.execute("""
                SELECT trade_date, member_name, contract_code,
                       net_volume, net_change, concentration_score
                FROM institution_daily_features
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
            """, (trade_date, lookback * 50)).fetchall()

            if len(rows) < lookback * 2:
                return 0

            # Simple lead-lag: members with highest concentration changes
            # that precede other members' changes
            members = {}
            for r in rows:
                name = r[1]
                if name not in members:
                    members[name] = []
                members[name].append({
                    "trade_date": r[0],
                    "net_volume": r[3],
                    "net_change": r[4],
                    "concentration": r[5],
                })

            # Find leading members (high concentration, early movers)
            leading = sorted(
                members.items(),
                key=lambda x: max((abs(m["net_change"]) or 0 for m in x[1]), default=0),
                reverse=True,
            )[:5]

            for leader_name, leader_data in leading:
                if not leader_data:
                    continue

                # Find lagging members (correlated but delayed)
                for follower_name, follower_data in members.items():
                    if follower_name == leader_name:
                        continue

                    # Simplified: check if follower's changes follow leader's
                    # direction within lookback window
                    if len(follower_data) < 2:
                        continue

                    leader_net = leader_data[0].get("net_change") or 0
                    follower_net = follower_data[0].get("net_change") or 0

                    if leader_net == 0 or follower_net == 0:
                        continue

                    # Same direction → potential lag
                    same_direction = (leader_net > 0) == (follower_net > 0)
                    correlation = abs(min(1.0, abs(follower_net) / max(abs(leader_net), 1)))

                    if same_direction and correlation > 0.3:
                        try:
                            conn.execute("""
                                INSERT INTO institution_lead_lag
                                    (trade_date, leading_member, lagging_members,
                                     correlation, lag_days, signal_direction, accuracy)
                                VALUES (?, ?, ?, ?, 1, ?, 0.5)
                            """, (
                                trade_date,
                                leader_name,
                                json.dumps([follower_name]),
                                round(correlation, 3),
                                "bullish" if leader_net > 0 else "bearish",
                            ))
                            count += 1
                        except Exception as e:
                            logger.warning(f"Failed to save lead-lag: {e}")

        return count

    # ── Institution Master ───────────────────────────────────

    def sync_institution_master(self) -> int:
        """Sync institution master list from daily features."""
        pool = self._analysis_pool()
        count = 0

        with pool.connection() as conn:
            # Get unique members from daily features
            members = conn.execute("""
                SELECT DISTINCT member_name, exchange
                FROM institution_daily_features
            """).fetchall()

            for member_name, exchange in members:
                # Determine category
                category = self._categorize_institution(member_name)

                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO institution_master
                            (exchange, member_name, category, status)
                        VALUES (?, ?, ?, 'active')
                    """, (exchange, member_name, category))
                    if conn.execute("SELECT changes()").fetchone()[0] > 0:
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to sync institution {member_name}: {e}")

        return count

    def _categorize_institution(self, name: str) -> str:
        """Categorize institution based on name patterns."""
        name_lower = name.lower()

        if any(kw in name_lower for kw in ["期货", "futures"]):
            return "futures_company"
        elif any(kw in name_lower for kw in ["银行", "bank"]):
            return "bank"
        elif any(kw in name_lower for kw in ["证券", "securities"]):
            return "securities"
        else:
            return "other"

    # ── Name Resolution ──────────────────────────────────────

    def resolve_name(self, raw_name: str, exchange: str = None) -> str:
        """Resolve raw institution name to canonical name."""
        pool = self._analysis_pool()

        with pool.connection() as conn:
            row = conn.execute("""
                SELECT canonical_name FROM institution_name_mapping
                WHERE raw_name = ? AND exchange = ?
            """, (raw_name, exchange)).fetchone()

            if row:
                return row[0]

            # No mapping found — use raw name as canonical
            conn.execute("""
                INSERT INTO institution_name_mapping
                    (raw_name, canonical_name, exchange, confidence)
                VALUES (?, ?, ?, 0.5)
            """, (raw_name, raw_name, exchange))

            return raw_name
