"""
Celery tasks for statement/bill management.
"""
import logging
from datetime import datetime, timedelta
from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.scheduler.task_logger import log_beat_task

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def parse_statement_task(self, file_path: str, account_id: int):
    """
    Parse a statement file and store results.

    Args:
        file_path: Path to the statement file
        account_id: ID of the futures account
    """
    try:
        from tzdata_pkg.maintenance.statements.parsers.cfmmc_parser import CFMMCParser

        parser = CFMMCParser()
        result = parser.parse_file(file_path)

        return {
            'status': 'completed',
            'file_path': file_path,
            'account_id': account_id,
            'records_parsed': len(result) if result else 0
        }
    except Exception as e:
        logger.error(f"Statement parsing failed: {e}")
        return {
            'status': 'failed',
            'file_path': file_path,
            'account_id': account_id,
            'error': str(e)
        }


@celery_app.task(bind=True, max_retries=3)
def auto_fetch_statements(self, account_id: int):
    """
    Automatically fetch statements from CFMMC for an account.

    Args:
        account_id: ID of the futures account
    """
    try:
        from tzdata_pkg.maintenance.statements.credential_vault import CredentialVault
        from tzdata_pkg.maintenance.statements.cfmmc_scraper import scrape_bills_task
        from datetime import datetime, timedelta

        vault = CredentialVault()
        credentials = vault.get_credentials(account_id)

        if not credentials:
            return {
                'status': 'failed',
                'error': f'No credentials found for account {account_id}'
            }

        # Default: fetch bills from last 7 days
        end_date = datetime.now().date() - timedelta(days=1)
        start_date = end_date - timedelta(days=7)

        result = scrape_bills_task(
            username=credentials['username'],
            password=credentials['password'],
            start_date=start_date,
            end_date=end_date,
            account_id=account_id
        )

        return {
            'status': 'completed' if result.get('success') else 'failed',
            'account_id': account_id,
            'files_downloaded': result.get('files_downloaded', 0),
            'files': result.get('files', []),
            'error': result.get('error')
        }
    except Exception as e:
        logger.error(f"Auto-fetch failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'account_id': account_id
        }


@celery_app.task
def batch_upload_statements(self, file_paths: list[str], account_id: int):
    """
    Batch upload and parse multiple statement files.

    Args:
        file_paths: List of file paths
        account_id: ID of the futures account
    """
    results = []
    for file_path in file_paths:
        result = parse_statement_task.delay(file_path, account_id)
        results.append(result.id)

    return {
        'status': 'queued',
        'task_ids': results,
        'count': len(file_paths)
    }


@celery_app.task
@log_beat_task
def check_missing_bills_task():
    """
    Daily check for missing bills across all accounts.
    Executes at 20:00 daily via Celery Beat.
    """
    try:
        from tzdata_pkg.maintenance.statements.account_manager import AccountManager
        from tzdata_pkg.storage.db_registry import DBRegistry

        accounts = AccountManager.list_accounts(is_active=True)
        # Bills are stored in trading DB
        pool = DBRegistry().get_pool('trading')
        missing_report = []

        for account in accounts:
            try:
                # Get tracking start date for this account
                tracking_start = account.get('tracking_start_date')
                if not tracking_start:
                    continue

                start_date = datetime.strptime(tracking_start, '%Y-%m-%d').date()
                end_date = datetime.now().date() - timedelta(days=1)  # Yesterday

                # Get all trading dates (excluding weekends)
                trading_dates = _get_trading_dates(start_date, end_date)

                # Get dates with parsed bills
                with pool.transaction() as conn:
                    cursor = conn.execute("""
                        SELECT DISTINCT bill_date_start
                        FROM bills
                        WHERE account_id = ?
                          AND status = 'parsed'
                        ORDER BY bill_date_start
                    """, (str(account['id']),))
                    bill_dates = set(row[0] for row in cursor.fetchall())

                missing = [d for d in trading_dates if d.isoformat() not in bill_dates]

                if missing:
                    missing_report.append({
                        'account_id': account['id'],
                        'account_name': account['account_name'],
                        'missing_days': len(missing),
                        'latest_missing': missing[-1].isoformat() if missing else None
                    })
            except Exception as e:
                logger.warning(f"Failed to check bills for account {account['id']}: {e}")

        return {
            'status': 'completed',
            'accounts_checked': len(accounts),
            'accounts_with_missing': len(missing_report),
            'missing_report': missing_report
        }
    except Exception as e:
        logger.error(f"Missing bills check failed: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


def _get_trading_dates(start_date, end_date):
    """Get trading dates between start and end (excluding weekends)."""
    trading_dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Mon-Fri
            trading_dates.append(current)
        current += timedelta(days=1)
    return trading_dates


@celery_app.task
@log_beat_task
def trade_matching_task():
    """
    Run FIFO trade matching on raw trades.

    Reads from trades table, pairs open/close by instrument,
    writes to matched_trades and trade_performance.
    Scheduled daily at 20:30.
    """
    try:
        from tzdata_pkg.maintenance.statements.trade_matcher import TradeMatcher

        matcher = TradeMatcher()
        result = matcher.run()
        logger.info(f"Trade matching: {result}")
        return {
            'status': 'completed',
            **result,
        }
    except Exception as e:
        logger.error(f"Trade matching failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }
