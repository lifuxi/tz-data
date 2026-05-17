"""
Celery task for MO market environment analysis.

Classifies market conditions based on underlying price action and IV:
- Trend: up/down/neutral (20-day return)
- Volatility: high/low (20-day amplitude, IV change)
- Volume: expanding/contracting (20-day avg volume trend)

Writes to option_sim_market_env table.
"""
import logging
import sqlite3
from datetime import date, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.scheduler.task_logger import log_beat_task

logger = logging.getLogger(__name__)

TZDATA_TRADING_DB = "C:/myspace/tz-data/data/tzdata_trading.db"


@celery_app.task
@log_beat_task
def compute_mo_market_env():
    """
    Compute MO market environment classification.
    Scheduled at 17:30 on trading days.
    """
    try:
        today = date.today()
        trade_date = today.isoformat()
        lookback_start = (today - timedelta(days=40)).isoformat()  # 40 calendar days ~ 20 trading days

        conn = sqlite3.connect(TZDATA_TRADING_DB)

        # 1. Get 000852 underlying daily data
        idx_rows = conn.execute("""
            SELECT trade_date, open, high, low, close, volume
            FROM option_sim_underlying_daily
            WHERE underlying = '000852' AND trade_date >= ?
            ORDER BY trade_date DESC LIMIT 20
        """, (lookback_start,)).fetchall()

        if len(idx_rows) < 5:
            conn.close()
            logger.warning("Insufficient underlying data for market env analysis")
            return {'status': 'skipped', 'reason': 'insufficient data'}

        closes = [float(r[4]) for r in idx_rows]
        highs = [float(r[2]) for r in idx_rows]
        lows = [float(r[3]) for r in idx_rows]
        volumes = [float(r[5]) if r[5] else 0 for r in idx_rows]

        # 2. Get MO IV data (average IV per date)
        iv_rows = conn.execute("""
            SELECT trade_date, AVG(iv) as avg_iv
            FROM option_sim_iv_series
            WHERE underlying = 'MO' AND trade_date >= ? AND iv > 0
            GROUP BY trade_date
            ORDER BY trade_date DESC LIMIT 20
        """, (lookback_start,)).fetchall()

        iv_values = [float(r[1]) for r in iv_rows] if iv_rows else []

        conn.close()

        # 3. Calculate metrics
        latest_close = closes[0]
        prev_close = closes[-1] if len(closes) > 1 else latest_close
        ret_20d = (latest_close - prev_close) / prev_close * 100 if prev_close else 0

        max_high = max(highs)
        min_low = min(lows)
        amplitude_20d = (max_high - min_low) / min_low * 100 if min_low else 0

        # IV change
        iv_change_pct = 0
        if len(iv_values) >= 2:
            iv_latest = iv_values[0]
            iv_prev = iv_values[-1]
            iv_change_pct = (iv_latest - iv_prev) / iv_prev * 100 if iv_prev else 0

        # Volume average
        avg_volume_20d = sum(volumes[:10]) if volumes else 0  # Recent 10 days avg

        # 4. Classify
        env_type = _classify_market(ret_20d, amplitude_20d, iv_change_pct)

        # 5. Write to DB
        conn = sqlite3.connect(TZDATA_TRADING_DB)
        conn.execute("""
            INSERT OR REPLACE INTO option_sim_market_env
            (underlying, trade_date, env_type, ret_20d, amplitude_20d,
             vol_change_pct, avg_volume_20d)
            VALUES ('MO', ?, ?, ?, ?, ?, ?)
        """, (
            trade_date,
            env_type,
            round(ret_20d, 2),
            round(amplitude_20d, 2),
            round(iv_change_pct, 2),
            round(avg_volume_20d, 2),
        ))
        conn.commit()
        conn.close()

        logger.info(f"MO market env computed: {env_type} "
                    f"(ret={ret_20d:.1f}%, amp={amplitude_20d:.1f}%, iv_change={iv_change_pct:.1f}%)")
        return {
            'status': 'completed',
            'trade_date': trade_date,
            'env_type': env_type,
            'ret_20d': round(ret_20d, 2),
            'amplitude_20d': round(amplitude_20d, 2),
            'iv_change_pct': round(iv_change_pct, 2),
        }

    except Exception as e:
        logger.error(f"Market env analysis failed: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}


def _classify_market(ret_20d: float, amplitude_20d: float, iv_change_pct: float) -> str:
    """
    Classify market environment.

    Categories:
    - trend_up: 20d return > 3%
    - trend_down: 20d return < -3%
    - high_vol: 20d amplitude > 5% AND IV change > 10%
    - low_vol: 20d amplitude < 2% AND IV change < -5%
    - neutral: everything else
    """
    if ret_20d > 3:
        return 'trend_up'
    if ret_20d < -3:
        return 'trend_down'
    if amplitude_20d > 5 and iv_change_pct > 10:
        return 'high_vol'
    if amplitude_20d < 2 and iv_change_pct < -5:
        return 'low_vol'
    return 'neutral'
