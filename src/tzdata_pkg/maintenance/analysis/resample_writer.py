"""
重采样结果写入器。

将重采样后的多周期 K 线写入 SQLite minute_quotes 表和 QuestDB future_minute 表。
"""
import logging
from typing import Optional

import pandas as pd

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.analysis.resampler import OHLCVResampler

logger = logging.getLogger(__name__)


class ResampleWriter:
    """写入重采样结果到 SQLite + QuestDB。"""

    @staticmethod
    def write_sqlite(df_resampled: pd.DataFrame, frequency: str) -> int:
        """将重采样数据写入 SQLite minute_quotes 表。

        使用 INSERT OR IGNORE 避免重复写入。
        """
        if df_resampled.empty:
            return 0

        pool = DBRegistry().get_pool("market")
        count = 0

        with pool.transaction() as conn:
            for _, row in df_resampled.iterrows():
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO minute_quotes
                            (exchange, contract_code, trade_date, trade_time,
                             frequency, open, high, low, close, volume,
                             turnover, open_interest, vwap, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row["exchange"],
                        row["contract_code"],
                        row["trade_date"],
                        row["trade_time"],
                        frequency,
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                        int(row["volume"]) if row["volume"] else None,
                        row["turnover"],
                        int(row["open_interest"]) if "open_interest" in row and row["open_interest"] else None,
                        row.get("vwap"),
                        row["source"],
                    ))
                    count += 1
                except Exception:
                    pass  # Duplicate or invalid row

        return count

    @staticmethod
    def write_questdb(df_resampled: pd.DataFrame) -> int:
        """将重采样数据写入 QuestDB future_minute 表。"""
        if df_resampled.empty:
            return 0

        from tzdata_pkg.storage.questdb_store import QuestDBStore

        # 构建 dict list
        quotes = []
        for _, row in df_resampled.iterrows():
            quotes.append({
                "trade_date": str(row["trade_date"]),
                "trade_time": str(row["trade_time"]),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": int(row["volume"]) if row["volume"] else 0,
                "turnover": row["turnover"],
                "open_interest": int(row["open_interest"]) if "open_interest" in row and row["open_interest"] else 0,
                "source": "resampled",
            })

        exchange = df_resampled["exchange"].iloc[0]
        contract_code = df_resampled["contract_code"].iloc[0]
        product_code = contract_code[:2] if len(contract_code) >= 2 else contract_code

        return QuestDBStore.insert_minute_quotes(
            exchange=exchange,
            contract_code=contract_code,
            product_code=product_code,
            quotes=quotes,
        )

    @staticmethod
    def resample_and_write(
        df_1min: pd.DataFrame,
        target_freq: str,
        contract_code: str,
        exchange: str = "CFFEX",
        write_to_sqlite: bool = True,
        write_to_questdb: bool = True,
    ) -> dict:
        """重采样 + 写入的完整流程。

        Returns:
            {"sqlite_count": int, "questdb_count": int, "validation": dict}
        """
        df_resampled = OHLCVResampler.resample_from_1min(
            df_1min, target_freq, contract_code, exchange
        )

        if df_resampled.empty:
            logger.warning(f"No bars produced for {contract_code} @ {target_freq}")
            return {"sqlite_count": 0, "questdb_count": 0, "validation": {}}

        validation = OHLCVResampler.validate_resample(
            len(df_1min), len(df_resampled), target_freq
        )
        logger.info(f"Resample {contract_code} @ {target_freq}: "
                     f"{validation['original_bars']} → {validation['resampled_bars']} bars "
                     f"(valid: {validation['valid']})")

        sqlite_count = 0
        questdb_count = 0

        if write_to_sqlite:
            sqlite_count = ResampleWriter.write_sqlite(df_resampled, target_freq)

        if write_to_questdb:
            questdb_count = ResampleWriter.write_questdb(df_resampled)

        return {
            "sqlite_count": sqlite_count,
            "questdb_count": questdb_count,
            "validation": validation,
        }
