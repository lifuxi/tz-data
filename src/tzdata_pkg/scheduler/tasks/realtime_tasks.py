"""Celery periodic tasks for realtime market data."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app


def _get_market_pool():
    from tzdata_pkg.storage.db_registry import DBRegistry
    return DBRegistry().get_pool("market")


@celery_app.task(
    name="tzdata_pkg.scheduler.tasks.realtime_tasks.pre_market_snapshot",
    bind=True,
)
def pre_market_snapshot(self):
    """盘前快照 — 每日 09:25:05 执行，刷新所有活跃 symbol。"""
    pool = _get_market_pool()
    try:
        with pool.connection() as conn:
            cur = conn.execute(
                "SELECT symbol FROM market_data_catalog WHERE is_active = 1",
            )
            symbols = [row["symbol"] for row in cur.fetchall()]

        # Force refresh from primary source
        from tzdata_pkg.market.drivers.qq_finance_driver import QQFinanceDriver
        import asyncio
        import time

        driver = QQFinanceDriver()
        asyncio.get_event_loop().run_until_complete(driver.connect({"poll_interval": 2}))

        refreshed = 0
        for symbol in symbols:
            try:
                async def _fetch():
                    await driver.subscribe([symbol])
                    await asyncio.sleep(1)  # wait for one poll cycle
                    await driver.unsubscribe([symbol])

                asyncio.get_event_loop().run_until_complete(_fetch())
                refreshed += 1
            except Exception:
                pass

        asyncio.get_event_loop().run_until_complete(driver.disconnect())

        # Log event
        with pool.transaction() as conn:
            conn.execute(
                """INSERT INTO market_data_event_log (event_type, source_name, severity, message, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("snapshot", "pre_market", "info",
                 f"Pre-market snapshot: refreshed {refreshed}/{len(symbols)} symbols",
                 datetime.utcnow().isoformat()),
            )

        return {"status": "ok", "refreshed": refreshed, "total": len(symbols)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task(
    name="tzdata_pkg.scheduler.tasks.realtime_tasks.gap_detection",
    bind=True,
)
def gap_detection(self):
    """检测数据缺口 — 交易时段每 30 秒执行。"""
    pool = _get_market_pool()
    try:
        now = datetime.utcnow()
        # Only run during trading hours (09:00-15:15 CST)
        cst_now = now + timedelta(hours=8)
        if not ((9 <= cst_now.hour < 15) or (cst_now.hour == 15 and cst_now.minute <= 15)):
            return {"status": "skipped", "reason": "outside trading hours"}

        with pool.connection() as conn:
            cur = conn.execute(
                """SELECT symbol, updated_at FROM realtime_snapshots_cache
                   WHERE updated_at < ?""",
                ((now - timedelta(seconds=5)).isoformat(),),
            )
            gaps = [dict(r) for r in cur.fetchall()]

        if gaps:
            from tzdata_pkg.market.event_logger import MarketEventLogger
            event_logger = MarketEventLogger(pool)
            for g in gaps:
                event_logger.log(
                    "gap", symbol=g["symbol"], severity="warning",
                    message=f"Data gap detected: last update {g['updated_at']}",
                )

        return {"status": "ok", "gaps": len(gaps), "symbols": [g["symbol"] for g in gaps[:10]]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task(
    name="tzdata_pkg.scheduler.tasks.realtime_tasks.quality_report_generator",
    bind=True,
)
def quality_report_generator(self):
    """质量日报 — 每日 15:30 执行。"""
    pool = _get_market_pool()
    try:
        with pool.connection() as conn:
            # Today's quality summary
            cur = conn.execute(
                """SELECT source_name,
                          AVG(quality_score) as avg_score,
                          SUM(gap_count) as total_gaps,
                          SUM(suspect_count) as total_suspects,
                          AVG(delay_ms) as avg_delay,
                          COUNT(DISTINCT symbol) as symbols_tracked
                   FROM data_quality_metrics
                   WHERE trade_date = date('now')
                   GROUP BY source_name""",
            )
            sources = [dict(r) for r in cur.fetchall()]

        return {
            "status": "ok",
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "sources": sources,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task(
    name="tzdata_pkg.scheduler.tasks.realtime_tasks.catalog_auto_expire",
    bind=True,
)
def catalog_auto_expire(self):
    """合约到期自动退禁 — 每日 00:00 执行。"""
    pool = _get_market_pool()
    try:
        now = datetime.utcnow().strftime("%Y-%m-%d")
        with pool.transaction() as conn:
            # Disable expired entries
            cur = conn.execute(
                """UPDATE market_data_catalog SET is_active = 0
                   WHERE subscribe_until < ? AND subscribe_until IS NOT NULL AND is_active = 1""",
                (now,),
            )
            expired = cur.rowcount

            # Clean up old event logs (> 90 days)
            cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
            conn.execute(
                "DELETE FROM market_data_event_log WHERE created_at < ?",
                (cutoff,),
            )

        return {"status": "ok", "expired_contracts": expired}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task(
    name="tzdata_pkg.scheduler.tasks.realtime_tasks.questdb_to_parquet_archive",
    bind=True,
)
def questdb_to_parquet_archive(self):
    """归档 30 天前 QuestDB 数据为 Parquet — 每日 02:00 执行。"""
    try:
        # Check if QuestDB is available
        import os
        from tzdata_pkg.storage.db_registry import DBRegistry

        registry = DBRegistry()
        try:
            qdb = registry.get_questdb_connection()
        except Exception:
            return {"status": "skipped", "reason": "QuestDB not available"}

        cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        # Archive logic would go here — export to Parquet then delete
        # For Phase 1, just log the intent
        from tzdata_pkg.market.event_logger import MarketEventLogger
        event_logger = MarketEventLogger(_get_market_pool())
        event_logger.log(
            "snapshot", severity="info",
            message=f"Parquet archive scheduled for data before {cutoff}",
        )

        return {"status": "ok", "cutoff": cutoff, "note": "Phase 1: archive logic pending QuestDB setup"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
