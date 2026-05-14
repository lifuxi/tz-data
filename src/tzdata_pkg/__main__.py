"""
CLI entry point for tz-data.
Usage: tzdata <command> [options]
"""
import click
from pathlib import Path
from datetime import date

from tzdata_pkg.config import get_data_dir
from tzdata_pkg.storage.db_registry import DBRegistry


@click.group()
@click.version_option(version="0.3.0", prog_name="tzdata")
def cli():
    """tz-data: Unified market data management for Chinese futures/options."""
    pass


# ── Download commands ───────────────────────────────────────

@cli.group()
def download():
    """Download market data from exchanges."""
    pass


@download.command()
@click.option("--product", default="MO", help="Product code (e.g., MO, IM, IC)")
@click.option("--data-type", default="daily", help="Data type: daily, position")
@click.option("--from", "start_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "end_date", help="End date (YYYY-MM-DD)")
@click.option("--incremental", is_flag=True, help="Download from last known date")
def cffex(product, data_type, start_date, end_date, incremental):
    """Download CFFEX market data (unified downloader)."""
    from tzdata_pkg.config import get_cffex_config
    from tzdata_pkg.download.cffex.unified_downloader import CFFEXUnifiedDownloader

    config = get_cffex_config()
    click.echo(f"Starting CFFEX download: product={product}, type={data_type}")

    try:
        with CFFEXUnifiedDownloader(config, product=product, data_type=data_type) as dl:
            if incremental:
                result = dl.download_incremental()
            elif start_date and end_date:
                sd = date.fromisoformat(start_date)
                ed = date.fromisoformat(end_date)
                result = dl.download_range(sd, ed)
            else:
                result = dl.download_full()
            click.echo(f"Download complete: {result}")
    except Exception as e:
        click.echo(f"Download failed: {e}", err=True)


@download.command()
@click.option("--product", default="AU", help="Product code (e.g., AU, AG, CU)")
@click.option("--incremental", is_flag=True, help="Download only new data")
def shfe(product, incremental):
    """Download SHFE market data (via AkShare)."""
    from tzdata_pkg.config import get_shfe_config
    from tzdata_pkg.download.shfe.daily_downloader import SHFEDailyDownloader

    config = get_shfe_config()
    click.echo(f"Starting SHFE download: product={product}")

    try:
        dl = SHFEDailyDownloader()
        if incremental:
            dl.incremental_download([product])
        else:
            dl.download_daily([product], date(2024, 1, 1), date.today())
        dl.close()
        click.echo("SHFE download complete")
    except Exception as e:
        click.echo(f"SHFE download failed: {e}", err=True)


@download.command()
@click.option("--type", "data_type", default="daily", help="Data type: daily, minute, option")
@click.option("--ts-code", help="Tushare contract code (e.g., MO2505.CFFEX)")
@click.option("--underlying", default="MO", help="Underlying for option downloads")
@click.option("--from", "start_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "end_date", help="End date (YYYY-MM-DD)")
def tushare(data_type, ts_code, underlying, start_date, end_date):
    """Download data from Tushare API."""
    from tzdata_pkg.config import get_tushare_config

    config = get_tushare_config()
    if not config["token"]:
        click.echo("Error: TUSHARE_TOKEN environment variable not set", err=True)
        return

    sd = date.fromisoformat(start_date) if start_date else date.today()
    ed = date.fromisoformat(end_date) if end_date else date.today()

    try:
        if data_type == "daily":
            from tzdata_pkg.download.tushare import TushareDailyDownloader
            code = ts_code or f"{underlying}2505.CFFEX"
            with TushareDailyDownloader(config, ts_code=code) as dl:
                result = dl.download_and_store(sd, ed)
        elif data_type == "minute":
            from tzdata_pkg.download.tushare import TushareMinuteDownloader
            freq = config.get("frequencies", ["1min"])[0]
            code = ts_code or f"{underlying}2505.CFFEX"
            with TushareMinuteDownloader(config, ts_code=code, freq=freq) as dl:
                result = dl.download_and_store(sd, ed)
        elif data_type == "option":
            from tzdata_pkg.download.tushare import TushareOptionDownloader
            with TushareOptionDownloader(config, ts_code=ts_code, underlying=underlying) as dl:
                result = dl.download_and_store(sd, ed)
        else:
            click.echo(f"Error: unknown data type '{data_type}'", err=True)
            return
        click.echo(f"Tushare download complete: {result}")
    except Exception as e:
        click.echo(f"Tushare download failed: {e}", err=True)


@download.command()
@click.option("--auto", is_flag=True, help="Auto-download using stored cookies")
@click.option("--from", "start_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "end_date", help="End date (YYYY-MM-DD)")
def cfmmc(auto, start_date, end_date):
    """Download bills from CFMMC."""
    from tzdata_pkg.config import get_cfmmc_config
    from tzdata_pkg.download.cfmmc import CFMMCDownloader

    config = get_cfmmc_config()
    sd = date.fromisoformat(start_date) if start_date else date.today()
    ed = date.fromisoformat(end_date) if end_date else date.today()

    try:
        with CFMMCDownloader(config) as dl:
            result = dl.download_and_store(sd, ed, auto=auto)
            click.echo(f"CFMMC download complete: {result}")
    except Exception as e:
        click.echo(f"CFMMC download failed: {e}", err=True)


# ── MO Data download commands ───────────────────────────────

@download.command()
@click.option("--type", "data_type", default="all", type=click.Choice(["all", "index", "etf", "futures", "component", "a50"]),
              help="Data type to sync")
@click.option("--from", "start_date", default="2022-01-01", help="Start date (YYYY-MM-DD)")
@click.option("--to", "end_date", help="End date (YYYY-MM-DD), defaults to today")
def mo_data(data_type, start_date, end_date):
    """Sync MO signal data (index, ETF, futures, components, A50) via akshare."""
    from datetime import date as _date
    from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader
    from tzdata_pkg.download.akshare.etf_daily import EtfDailyDownloader
    from tzdata_pkg.download.akshare.futures_daily import FuturesDailyDownloader
    from tzdata_pkg.download.akshare.component import ComponentDownloader
    from tzdata_pkg.download.akshare.a50_daily import A50DailyDownloader

    sd = _date.fromisoformat(start_date) if start_date else _date.today()
    ed = _date.fromisoformat(end_date) if end_date else _date.today()

    click.echo(f"Starting MO data sync: type={data_type}, {sd} -> {ed}")

    try:
        if data_type in ("all", "index"):
            for idx_code in ['000852', '000905']:
                click.echo(f"  Syncing index {idx_code}...")
                dl = IndexDailyDownloader(index_code=idx_code)
                results = dl.download_and_store(sd, ed)
                click.echo(f"    {results['records_stored']} records stored")
                dl.close()

        if data_type in ("all", "etf"):
            click.echo(f"  Syncing ETF 512100...")
            dl = EtfDailyDownloader(etf_code='512100')
            results = dl.download_and_store(sd, ed)
            click.echo(f"    {results['records_stored']} records stored")
            dl.close()

        if data_type in ("all", "futures"):
            click.echo(f"  Syncing IM futures...")
            dl = FuturesDailyDownloader(product='IM')
            results = dl.download_and_store(sd, ed)
            click.echo(f"    {results['records_stored']} records stored")
            dl.close()

        if data_type in ("all", "component"):
            click.echo(f"  Syncing CSI 1000 components...")
            dl = ComponentDownloader(index_code='000852')
            results = dl.download_and_store(sd, ed)
            click.echo(f"    {results['records_stored']} records stored")
            dl.close()

        if data_type in ("all", "a50"):
            click.echo(f"  Syncing A50 futures...")
            dl = A50DailyDownloader()
            results = dl.download_and_store(sd, ed)
            click.echo(f"    {results['records_stored']} records stored")
            dl.close()

        click.echo("MO data sync complete")
    except Exception as e:
        click.echo(f"MO data sync failed: {e}", err=True)


# ── Query commands ──────────────────────────────────────────

@cli.group()
def query():
    """Query data from tz-data."""
    pass


@query.command()
@click.option("--exchange", help="Exchange code (CFFEX, SHFE)")
@click.option("--contract", help="Contract code")
@click.option("--from", "start_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "end_date", help="End date (YYYY-MM-DD)")
def quotes(exchange, contract, start_date, end_date):
    """Query quote data."""
    from tzdata_pkg.query import TzDataClient

    client = TzDataClient()
    results = client.quotes(
        exchange=exchange, contract=contract,
        start_date=start_date, end_date=end_date,
    )
    click.echo(f"Found {len(results)} quote records")
    if results and len(results) <= 10:
        for r in results:
            click.echo(f"  {r.get('trade_date')} | {r.get('contract_code')} | O={r.get('open')} C={r.get('close')} V={r.get('volume')}")
    elif results:
        for r in results[:5]:
            click.echo(f"  {r.get('trade_date')} | {r.get('contract_code')} | O={r.get('open')} C={r.get('close')} V={r.get('volume')}")
        click.echo(f"  ... ({len(results) - 5} more)")


@query.command()
@click.option("--contract", help="Contract code")
@click.option("--date", "trade_date", help="Trade date (YYYY-MM-DD)")
def positions(contract, trade_date):
    """Query position ranking data."""
    from tzdata_pkg.query import TzDataClient

    client = TzDataClient()
    results = client.positions(contract=contract, trade_date=trade_date)
    click.echo(f"Found {len(results)} position records")
    if results and len(results) <= 10:
        for r in results:
            click.echo(f"  {r.get('member_name')} | L={r.get('long_volume')} S={r.get('short_volume')}")


@query.command()
@click.option("--account-id", help="Account ID")
def bills(account_id):
    """List available bills."""
    from tzdata_pkg.query import TzDataClient

    client = TzDataClient()
    results = client.bills(account_id=account_id)
    click.echo(f"Found {len(results)} bills")
    for r in results:
        click.echo(f"  {r.get('bill_date')} | {r.get('account_id')} | equity={r.get('client_equity')}")


@query.command()
@click.option("--account-id", help="Account ID")
@click.option("--from", "start_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "end_date", help="End date (YYYY-MM-DD)")
def pnl(account_id, start_date, end_date):
    """Show P&L summary."""
    from tzdata_pkg.query import TzDataClient

    client = TzDataClient()
    summary = client.pnl_summary(
        account_id=account_id, start_date=start_date, end_date=end_date,
    )
    click.echo(f"P&L Summary:")
    for k, v in summary.items():
        click.echo(f"  {k}: {v}")


# ── Status command ──────────────────────────────────────────

@cli.command()
def status():
    """Show data freshness and table statistics."""
    registry = DBRegistry()
    data_dir = get_data_dir()

    click.echo(f"Data directory: {data_dir}")
    click.echo("")

    for db_name, label in [("market", "Market Data"), ("trading", "Trading Data"), ("analysis", "Analysis Data")]:
        db_path = getattr(registry, f"{db_name}_db_path")
        click.echo(f"=== {label} ({db_path.name}) ===")
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            for (table,) in tables:
                if table.startswith("sqlite_"):
                    continue
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    click.echo(f"  {table}: {count:,} rows")
                except Exception:
                    click.echo(f"  {table}: (error)")
            conn.close()
        else:
            click.echo(f"  Database not yet created")
        click.echo("")


# ── Validate command ────────────────────────────────────────

@cli.command()
def validate():
    """Run data quality checks."""
    registry = DBRegistry()

    click.echo("Running data quality checks...")

    for db_name in ["market", "trading", "analysis"]:
        db_path = getattr(registry, f"{db_name}_db_path")
        if not db_path.exists():
            click.echo(f"  {db_name}: DB not found (skipped)")
            continue

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        for (table,) in tables:
            if table.startswith("sqlite_"):
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count == 0:
                click.echo(f"  {db_name}/{table}: EMPTY")
            else:
                click.echo(f"  {db_name}/{table}: OK ({count:,} rows)")
        conn.close()


# ── Scheduler command ───────────────────────────────────────

@cli.group()
def schedule():
    """Manage download scheduler."""
    pass


@schedule.command()
@click.option("--background", is_flag=True, help="Run in background mode")
@click.option("--jobs", "job_list", help="Comma-separated list of jobs to run (default: all)")
def start(background, job_list):
    """Start the download scheduler."""
    from tzdata_pkg.scheduler import TzDataScheduler
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    mode = "background" if background else "blocking"

    if job_list:
        job_names = [j.strip() for j in job_list.split(",")]
        scheduler = TzDataScheduler(mode=mode, jobs=[j for j in TzDataScheduler.DEFAULT_JOBS if j["name"] in job_names])
    else:
        scheduler = TzDataScheduler(mode=mode)

    try:
        click.echo(f"Starting scheduler in {mode} mode")
        click.echo(f"Jobs: {[j['name'] for j in scheduler.get_jobs()]}")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        click.echo("Scheduler stopped")


@schedule.command()
@click.argument("job_name")
def run(job_name):
    """Run a specific job immediately."""
    from tzdata_pkg.scheduler import TzDataScheduler
    import logging

    logging.basicConfig(level=logging.INFO)
    scheduler = TzDataScheduler(mode="blocking")
    try:
        click.echo(f"Running job: {job_name}")
        scheduler.run_now(job_name)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
    finally:
        scheduler.shutdown()


@schedule.command()
def list():
    """List scheduled jobs."""
    from tzdata_pkg.scheduler import TzDataScheduler

    scheduler = TzDataScheduler(mode="blocking")
    jobs = scheduler.get_jobs()
    if not jobs:
        click.echo("No jobs scheduled")
        return
    for job in jobs:
        click.echo(f"  {job['name']:20s} | next: {job['next_run_time']} | {job['trigger']}")
    scheduler.shutdown()


# ── Migrate command ─────────────────────────────────────────

@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without executing")
@click.option("--verify", is_flag=True, help="Only verify, don't migrate")
def migrate(dry_run, verify):
    """Migrate data from old 12-DB layout to new 3-DB layout."""
    from tzdata_pkg.config import get_data_dir
    from tzdata_pkg.migration import MigrationRunner

    data_dir = get_data_dir()
    runner = MigrationRunner(data_dir)

    if verify:
        click.echo("Verifying migration status...")
        results = runner.verify()
        for key, info in results.items():
            status = "OK" if info["matched"] else f"MISMATCH ({info['source']:,} → {info['target']:,})"
            click.echo(f"  {key}: {status}")
        return

    if dry_run:
        click.echo("DRY RUN: checking what would be migrated...")
    else:
        click.echo("Starting 12→3 DB migration...")

    report = runner.run(dry_run=dry_run)

    if dry_run:
        click.echo(f"Would migrate:")
    else:
        click.echo(f"Migration complete:")
    click.echo(f"  Tables: {report.tables_migrated}")
    click.echo(f"  Rows: {report.rows_migrated:,}")
    click.echo(f"  Duration: {report.started_at} → {report.completed_at}")
    if report.errors:
        click.echo(f"  Errors: {len(report.errors)}")
        for err in report.errors:
            click.echo(f"    - {err}")


# ── Import bills command ────────────────────────────────────

@cli.command()
@click.option("--dir", "bill_dir", default=None, help="Bill files directory path")
@click.option("--dry-run", is_flag=True, help="Parse but don't store")
def import_bills(bill_dir, dry_run):
    """Batch import bill files into trading databases."""
    from tzdata_pkg.config import BILLS_DB, TZDATA_TRADING_DB, DATA_DIR
    from tzdata_pkg.cli.bill_import import BillImportService

    if not bill_dir:
        bill_dir = str(DATA_DIR / "bills" / "raw")

    mode = "DRY RUN" if dry_run else "IMPORT"
    click.echo(f"Starting bill {mode} from: {bill_dir}")

    service = BillImportService(
        trading_db_path=str(TZDATA_TRADING_DB),
        bills_db_path=str(BILLS_DB),
    )
    stats = service.import_all(bill_dir, dry_run=dry_run)

    click.echo(f"\nBill Import Report ({mode})")
    click.echo(f"{'='*50}")
    click.echo(f"Files scanned:    {stats['total_files']}")
    click.echo(f"Successfully:     {stats['success']}")
    click.echo(f"Failed:           {stats['failed']}")
    if not dry_run:
        click.echo(f"Bills imported:   {stats['bills_imported']}")
        click.echo(f"Transactions:     {stats['transactions_imported']}")
        click.echo(f"Positions:        {stats['positions_imported']}")
    else:
        for f in stats["files"]:
            click.echo(f"  {f['file']}: {f['transactions']} txns, {f['positions']} positions")

    if stats["errors"]:
        click.echo(f"\nErrors ({len(stats['errors'])}):")
        for err in stats["errors"][:10]:
            click.echo(f"  - {err}")
        if len(stats["errors"]) > 10:
            click.echo(f"  ... and {len(stats['errors']) - 10} more")


# ── Verify commands ────────────────────────────────────────

@cli.group()
def verify():
    """Run data verification checks."""
    pass


def _print_report(report, title: str) -> None:
    """Print a verification report to console."""
    click.echo(f"\n{title}")
    click.echo(f"{'='*60}")
    click.echo(f"Timestamp:  {report.timestamp}")
    click.echo(f"Total: {report.total_checks}  |  PASS: {report.passed}  |  FAIL: {report.failed}  |  WARN: {report.warnings}  |  SKIP: {report.skipped}")
    click.echo(f"Status: {report.overall_status}")
    click.echo(f"{'='*60}")

    for check in report.checks:
        icon = {"PASS": "[OK]", "FAIL": "[!!]", "WARN": "[??]", "SKIP": "[--]"}.get(check.status, "[  ]")
        click.echo(f"  {icon} {check.name}: {check.status}")
        if check.message:
            click.echo(f"       {check.message}")
        if check.deviation != 0 and isinstance(check.deviation, (int, float)):
            click.echo(f"       expected={check.expected}, actual={check.actual}, deviation={check.deviation}")
        elif check.expected != check.actual:
            click.echo(f"       expected={check.expected}, actual={check.actual}")
    click.echo()


@verify.command()
@click.option("--dir", "bill_dir", default=None, help="Bill source files directory")
def bills(bill_dir):
    """Bill data reconciliation: parse files and validate summaries."""
    from tzdata_pkg.config import BILLS_DB, DATA_DIR
    from tzdata_pkg.verify import BillReconciler

    if not bill_dir:
        bill_dir = str(DATA_DIR / "bills" / "raw")

    click.echo(f"Reconciling bills from: {bill_dir}")
    reconciler = BillReconciler(bills_db_path=str(BILLS_DB), bill_dir=bill_dir)
    report = reconciler.reconcile_all()
    _print_report(report, "Bill Reconciliation Report")


@verify.command(name="cross-db")
def cross_db():
    """Cross-database consistency check."""
    from tzdata_pkg.config import BILLS_DB, TZDATA_TRADING_DB
    from tzdata_pkg.verify import CrossDBChecker

    click.echo("Checking cross-database consistency...")
    checker = CrossDBChecker(
        bills_db_path=str(BILLS_DB),
        trading_db_path=str(TZDATA_TRADING_DB),
    )
    report = checker.check_all()
    _print_report(report, "Cross-Database Consistency Report")


@verify.command()
def analysis():
    """Analysis result verification."""
    from tzdata_pkg.config import BILLS_DB
    from tzdata_pkg.verify import AnalysisVerifier

    click.echo("Verifying analysis results...")
    verifier = AnalysisVerifier(bills_db_path=str(BILLS_DB))
    report = verifier.verify_all()
    _print_report(report, "Analysis Verification Report")


@verify.command()
@click.option("--dir", "bill_dir", default=None, help="Bill source files directory")
def all(bill_dir):
    """Run all verification checks."""
    from tzdata_pkg.config import BILLS_DB, TZDATA_TRADING_DB, DATA_DIR
    from tzdata_pkg.verify import BillReconciler, CrossDBChecker, AnalysisVerifier

    if not bill_dir:
        bill_dir = str(DATA_DIR / "bills" / "raw")

    click.echo("Running ALL verification checks...")

    # Bill reconciliation
    reconciler = BillReconciler(bills_db_path=str(BILLS_DB), bill_dir=bill_dir)
    bill_report = reconciler.reconcile_all()
    _print_report(bill_report, "1. Bill Reconciliation")

    # Cross-database
    checker = CrossDBChecker(
        bills_db_path=str(BILLS_DB),
        trading_db_path=str(TZDATA_TRADING_DB),
    )
    cross_report = checker.check_all()
    _print_report(cross_report, "2. Cross-Database Consistency")

    # Analysis verification
    verifier = AnalysisVerifier(bills_db_path=str(BILLS_DB))
    analysis_report = verifier.verify_all()
    _print_report(analysis_report, "3. Analysis Verification")

    # Combined summary
    total_pass = bill_report.passed + cross_report.passed + analysis_report.passed
    total_fail = bill_report.failed + cross_report.failed + analysis_report.failed
    total_warn = bill_report.warnings + cross_report.warnings + analysis_report.warnings
    total_all = bill_report.total_checks + cross_report.total_checks + analysis_report.total_checks

    click.echo(f"\n{'='*60}")
    click.echo(f"COMBINED SUMMARY")
    click.echo(f"{'='*60}")
    click.echo(f"Total checks: {total_all}")
    click.echo(f"PASS: {total_pass}  |  FAIL: {total_fail}  |  WARN: {total_warn}")
    overall = "UNRELIABLE" if total_fail > 0 else ("QUESTIONABLE" if total_warn > 0 else "TRUSTWORTHY")
    click.echo(f"Overall status: {overall}")
    click.echo(f"{'='*60}")


# ── Serve command ───────────────────────────────────────────

@cli.command()
@click.option("--host", default="0.0.0.0", help="Listen address")
@click.option("--port", default=8000, help="Listen port")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host, port, reload):
    """Start the FastAPI API service."""
    import uvicorn
    click.echo(f"Starting API service on {host}:{port}")
    uvicorn.run(
        "tzdata_pkg.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
