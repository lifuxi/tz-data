"""Analysis Celery tasks: institution building, signal generation, regime classification.

Scheduled daily after market close to pre-compute analysis data.
"""
import logging

from tzdata_pkg.scheduler.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="analysis_tasks.daily_institution_analysis")
def daily_institution_analysis(trade_date: str = None) -> dict:
    """Build institution analysis tables for a given date.

    Pipeline:
    1. Sync institution master list
    2. Build daily features from position_detail
    3. Update institution profiles
    4. Compute lead-lag relationships

    Scheduled: Daily 19:30 (after position data sync at 17:00)
    """
    from tzdata_pkg.storage.db_registry import DBRegistry
    from tzdata_pkg.maintenance.analysis.institution_builder import InstitutionBuilder

    registry = DBRegistry()
    builder = InstitutionBuilder(registry)

    if trade_date is None:
        from datetime import date
        trade_date = date.today().isoformat()

    # Sync master
    master_count = builder.sync_institution_master()

    # Build daily
    result = builder.build_daily(trade_date)
    result["master_synced"] = master_count

    logger.info(f"daily_institution_analysis({trade_date}): {result}")
    return result


@celery_app.task(name="analysis_tasks.daily_regime_classification")
def daily_regime_classification(trade_date: str = None, lookback: int = 20) -> dict:
    """Classify market regime for the given date.

    Scheduled: Daily 19:35 (after institution analysis)
    """
    from tzdata_pkg.storage.db_registry import DBRegistry
    from tzdata_pkg.maintenance.analysis.regime_classifier import RegimeClassifier

    if trade_date is None:
        from datetime import date
        trade_date = date.today().isoformat()

    registry = DBRegistry()
    classifier = RegimeClassifier(registry)
    result = classifier.classify_daily(trade_date, lookback=lookback)

    logger.info(f"daily_regime_classification({trade_date}): {result}")
    return result or {"status": "no_data"}


@celery_app.task(name="analysis_tasks.daily_signal_generation")
def daily_signal_generation(trade_date: str = None) -> dict:
    """Generate trading signals from institution + regime data.

    Scheduled: Daily 19:40 (after regime classification)
    """
    from tzdata_pkg.storage.db_registry import DBRegistry
    from tzdata_pkg.maintenance.analysis.signal_engine import SignalEngine

    if trade_date is None:
        from datetime import date
        trade_date = date.today().isoformat()

    registry = DBRegistry()
    engine = SignalEngine(registry)
    signals = engine.generate_daily_signals(trade_date)

    result = {
        "trade_date": trade_date,
        "signals_generated": len(signals),
        "signal_types": {},
    }
    for s in signals:
        st = s.get("signal_type", "unknown")
        result["signal_types"][st] = result["signal_types"].get(st, 0) + 1

    logger.info(f"daily_signal_generation({trade_date}): {result}")
    return result


@celery_app.task(name="analysis_tasks.analysis_pipeline")
def analysis_pipeline(trade_date: str = None) -> dict:
    """Run full analysis pipeline: institution → regime → signals.

    Scheduled: Daily 19:30
    """
    from datetime import date

    if trade_date is None:
        trade_date = date.today().isoformat()

    logger.info(f"analysis_pipeline starting for {trade_date}")

    inst = daily_institution_analysis(trade_date)
    regime = daily_regime_classification(trade_date)
    signals = daily_signal_generation(trade_date)

    return {
        "trade_date": trade_date,
        "institution": inst,
        "regime": regime,
        "signals": signals,
    }
