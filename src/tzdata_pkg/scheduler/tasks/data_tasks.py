"""
Celery tasks for tz-data data layer.

Scheduled tasks:
- 18:30  同步指数日线 (sync_index_daily) — 000852/000300
- 18:30  计算日频 VWAP (compute_daily_vwap) — 回填 trades.vwap
- 20:00  预计算期权希腊字母 (compute_option_greeks) — 全量 MO 合约
"""
import logging
import sqlite3
from datetime import date, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.scheduler.task_logger import log_beat_task

logger = logging.getLogger(__name__)

TZDATA_TRADING_DB = "C:/myspace/tz-data/data/tzdata_trading.db"

# ============================================================
# Index Daily Sync (000852 中证1000, 000300 沪深300)
# ============================================================


@celery_app.task
@log_beat_task
def sync_index_daily():
    """同步中证1000/沪深300指数日线数据，写入 daily_index_prices 表。
    每日 18:30 执行。
    """
    try:
        today = date.today()
        start = (today - timedelta(days=30)).isoformat()  # 拉取近 30 天数据
        end = today.isoformat()

        total = 0
        for index_code in ['000852', '000300']:
            count = _download_and_store_index(index_code, start, end)
            total += count

        logger.info(f"Index daily sync completed: {total} records stored")
        return {
            'status': 'completed',
            'date': today.isoformat(),
            'records_stored': total,
            'indices': ['000852', '000300'],
        }
    except Exception as e:
        logger.error(f"Index daily sync failed: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}


def _download_and_store_index(index_code: str, start_date: str, end_date: str) -> int:
    """下载并存储指数日线数据到 daily_index_prices 表。"""
    try:
        # Try akshare first (free, no API key needed)
        import akshare as ak

        # akshare index daily: index_zh_a_hist for Chinese A-share indices
        ak_symbol = f"{index_code}"
        df = ak.index_zh_a_hist(
            symbol=ak_symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )

        if df is None or df.empty:
            logger.warning(f"No index data for {index_code}")
            return 0

        conn = sqlite3.connect(TZDATA_TRADING_DB)
        count = 0
        for _, row in df.iterrows():
            trade_date = str(row.get('日期', ''))[:10]
            if not trade_date:
                continue

            conn.execute(
                """INSERT OR REPLACE INTO daily_index_prices
                   (index_code, trade_date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    index_code,
                    trade_date,
                    float(row.get('开盘', 0)),
                    float(row.get('最高', 0)),
                    float(row.get('最低', 0)),
                    float(row.get('收盘', 0)),
                    float(row.get('成交量', 0)),
                )
            )
            count += 1

        conn.commit()
        conn.close()
        logger.info(f"Stored {count} daily_index_prices records for {index_code}")
        return count

    except ImportError:
        logger.error("akshare not installed, cannot sync index data")
        return 0
    except Exception as e:
        logger.warning(f"Failed to sync {index_code}: {e}")
        return 0


# ============================================================
# Option Greeks Pre-compute (full contract coverage)
# ============================================================


@celery_app.task
@log_beat_task
def compute_option_greeks():
    """预计算期权希腊字母，写入 option_greeks_daily 表。
    从 mo_contract_master 获取全量活跃合约，而非仅 trades 中的合约。
    每日 20:00 执行。
    """
    try:
        today = date.today()
        trade_date = today.isoformat()
        date_str = today.strftime("%Y%m%d")

        # 1. 获取全量活跃合约
        conn = sqlite3.connect(TZDATA_TRADING_DB)
        contracts = conn.execute("""
            SELECT contract_code, strike_price, option_type, expiry_date
            FROM mo_contract_master
            WHERE status = 'active'
        """).fetchall()
        conn.close()

        if not contracts:
            logger.info("No active MO contracts, skipping Greeks precompute")
            return {
                'status': 'completed',
                'date': trade_date,
                'records_stored': 0,
                'note': 'no active contracts',
            }

        logger.info(f"Computing Greeks for {len(contracts)} active MO contracts")

        # 2. 通过 Tushare 获取 Greeks 数据
        total = 0
        try:
            from tzdata_pkg.config import get_tushare_config
            from tzdata_pkg.download.tushare.client import TushareClient

            tushare_cfg = get_tushare_config()
            client = TushareClient(token=tushare_cfg["token"])

            conn = sqlite3.connect(TZDATA_TRADING_DB)
            for contract_code, strike, opt_type, expiry in contracts:
                ts_code = _to_tushare_code(contract_code)
                if not ts_code:
                    continue

                df = client.opt_daily(ts_code, start_date=date_str, end_date=date_str)
                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    conn.execute(
                        """INSERT OR REPLACE INTO option_greeks_daily
                           (trade_date, symbol, option_type, strike_price,
                            expiry_date, underlying_price, iv,
                            delta, gamma, vega, theta)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            trade_date,
                            contract_code,
                            opt_type or _extract_option_type(contract_code),
                            strike or _extract_strike(contract_code),
                            expiry or _extract_expiry(contract_code),
                            float(row.get('settle', 0)),
                            float(row.get('iv', 0)),
                            float(row.get('delta', 0)),
                            float(row.get('gamma', 0)),
                            float(row.get('vega', 0)),
                            float(row.get('theta', 0)),
                        )
                    )
                    total += 1

            conn.commit()
            conn.close()

        except Exception as e:
            logger.warning(f"Greeks precompute failed: {e}")

        logger.info(f"Option Greeks precompute completed: {total} records stored")
        return {
            'status': 'completed',
            'date': trade_date,
            'contracts_checked': len(contracts),
            'records_stored': total,
        }
    except Exception as e:
        logger.error(f"Option Greeks precompute failed: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}


# ============================================================
# Daily VWAP Computation
# ============================================================


@celery_app.task
@log_beat_task
def compute_daily_vwap():
    """从 minute_quotes 计算日频 VWAP 并回填 trades.vwap 字段。
    每日 18:30 执行。
    """
    try:
        today = date.today()
        trade_date = today.strftime("%Y%m%d")

        conn = sqlite3.connect(TZDATA_TRADING_DB)

        # 1. 检查 trades 表是否有 vwap 列
        trade_cols = [c[1] for c in conn.execute("PRAGMA table_info(trades)").fetchall()]
        if 'vwap' not in trade_cols:
            logger.warning("trades.vwap column not found, skipping VWAP computation")
            conn.close()
            return {'status': 'skipped', 'reason': 'vwap column not found'}

        # 2. 获取当日有交易的合约列表
        instruments = conn.execute(
            "SELECT DISTINCT instrument FROM trades WHERE trade_date = ?",
            (trade_date,)
        ).fetchall()

        total = 0
        for (instrument,) in instruments:
            # 3. 从 minute_quotes 计算该合约的 VWAP
            # VWAP = SUM(price * volume) / SUM(volume)
            vwap_row = conn.execute(
                """SELECT SUM(price * volume) / SUM(volume) as vwap
                   FROM minute_quotes
                   WHERE symbol = ? AND trade_date = ?
                   AND volume > 0""",
                (instrument, trade_date)
            ).fetchone()

            if vwap_row and vwap_row[0] is not None:
                vwap = round(vwap_row[0], 4)
                conn.execute(
                    "UPDATE trades SET vwap = ? WHERE trade_date = ? AND instrument = ?",
                    (vwap, trade_date, instrument)
                )
                total += 1

        conn.commit()
        conn.close()

        logger.info(f"Daily VWAP computation completed: {total} instruments updated")
        return {
            'status': 'completed',
            'date': trade_date,
            'instruments_updated': total,
        }
    except Exception as e:
        logger.error(f"Daily VWAP computation failed: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}


# ============================================================
# Helper functions
# ============================================================


def _to_tushare_code(symbol: str) -> str:
    """将合约代码转换为 Tushare 格式。

    Example: MO2603-C-8500 → MO2603-C-8500.CFFEX
    """
    if 'CFFEX' in symbol or 'SHFE' in symbol or 'DCE' in symbol or 'CZCE' in symbol:
        return symbol

    # Determine exchange from symbol prefix
    prefix = symbol[:2].upper()
    exchange_map = {
        'MO': 'CFFEX', 'IO': 'CFFEX', 'HO': 'CFFEX',  # 中金所
        'CU': 'SHFE', 'AL': 'SHFE', 'ZN': 'SHFE',     # 上期所
        'M': 'DCE', 'Y': 'DCE', 'P': 'DCE',            # 大商所
        'CF': 'CZCE', 'SR': 'CZCE', 'TA': 'CZCE',      # 郑商所
    }
    exchange = exchange_map.get(prefix)
    if exchange:
        return f"{symbol}.{exchange}"
    return symbol


def _extract_option_type(symbol: str) -> str:
    """从合约代码提取期权类型。"""
    if '-C-' in symbol.upper():
        return 'CE'
    if '-P-' in symbol.upper():
        return 'PE'
    return ''


def _extract_strike(symbol: str) -> float:
    """从合约代码提取行权价。"""
    import re
    match = re.search(r'-(?:C|P)-(\d+)', symbol, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0


def _extract_expiry(symbol: str) -> str:
    """从合约代码提取到期日（粗略估计）。"""
    import re
    # Format: MO2603-C-8500 → 2026-03 (assuming MO = CFFEX option)
    match = re.search(r'([A-Z]+)(\d{4})', symbol)
    if match:
        year_part = match.group(2)[:2]
        month_part = match.group(2)[2:]
        year = 2000 + int(year_part) if int(year_part) < 80 else 1900 + int(year_part)
        return f"{year}-{month_part}-01"
    return ''
