"""
Core synchronization engine.
Orchestrates data sync operations with support for incremental/full sync and checkpoint resume.
"""
import logging
from datetime import date, timedelta
from typing import Optional
from dataclasses import dataclass, field

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
from tzdata_pkg.maintenance.sources.source_manager import SourceManager
from tzdata_pkg.maintenance.sync.checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)


@dataclass
class SyncBatch:
    """Represents a batch of dates to sync."""
    start_date: date
    end_date: date
    index: int
    total: int
    
    def __repr__(self):
        return f"SyncBatch({self.start_date} to {self.end_date}, {self.index+1}/{self.total})"


@dataclass 
class SyncResult:
    """Result of a sync operation."""
    success: bool
    catalog_id: int
    records_fetched: int = 0
    batches_completed: int = 0
    total_batches: int = 0
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    
    @property
    def progress_pct(self) -> float:
        if self.total_batches == 0:
            return 0.0
        return (self.batches_completed / self.total_batches) * 100


class SyncEngine:
    """
    Core synchronization engine.
    
    Supports:
    - Incremental sync (only missing data)
    - Full sync (specified date range)
    - Resumable sync (checkpoint-based)
    - Batch processing (to avoid rate limits)
    """
    
    # Default batch size (days per batch)
    DEFAULT_BATCH_DAYS = 30
    
    def __init__(
        self,
        catalog_id: int,
        mode: str = 'incremental',
        task_id: Optional[int] = None,
        batch_days: int = DEFAULT_BATCH_DAYS
    ):
        """
        Initialize sync engine.
        
        Args:
            catalog_id: ID of the data catalog to sync
            mode: Sync mode ('incremental' or 'full')
            task_id: ID of the sync task (for checkpoint management)
            batch_days: Number of days per batch
        """
        self.catalog_id = catalog_id
        self.mode = mode
        self.task_id = task_id
        self.batch_days = batch_days
        
        self.catalog = None
        self.source = None
        self.result = None
        
        logger.info(
            f"Initialized SyncEngine: catalog={catalog_id}, "
            f"mode={mode}, batch_days={batch_days}"
        )
    
    def execute(self) -> SyncResult:
        """
        Execute the sync operation.

        Returns:
            SyncResult with operation details
        """
        import time
        start_time = time.time()

        try:
            # Step 1: Load catalog configuration
            self._load_catalog()

            # Step 2: Get data source adapter
            self._get_data_source()

            # Step 2.5: Acquire concurrency slot and catalog lock
            from tzdata_pkg.maintenance.sync.concurrency_controller import ConcurrencyController

            catalog_lock = ConcurrencyController.get_catalog_lock(self.catalog_id)
            if not catalog_lock.acquire(blocking=False):
                return SyncResult(
                    success=False,
                    catalog_id=self.catalog_id,
                    error_message=f'Catalog {self.catalog_id} is already being synced'
                )

            try:
                # Step 3: Calculate date range
                if self.mode == 'incremental':
                    date_range = self._calculate_incremental_range()
                else:
                    date_range = self._calculate_full_range()

                if not date_range:
                    return SyncResult(
                        success=True,
                        catalog_id=self.catalog_id,
                        error_message='No data to sync'
                    )

                start_date, end_date = date_range

                # Step 4: Split into batches
                batches = self._split_into_batches(start_date, end_date)

                logger.info(
                    f"Starting sync: {len(batches)} batches, "
                    f"range={start_date} to {end_date}"
                )

                # Step 5: Process each batch
                total_records = 0
                completed_batches = 0

                for i, batch in enumerate(batches):
                    try:
                        records = self._process_batch(batch, i, len(batches))
                        total_records += records
                        completed_batches = i + 1

                        # Update result progress
                        self.result = SyncResult(
                            success=True,
                            catalog_id=self.catalog_id,
                            records_fetched=total_records,
                            batches_completed=completed_batches,
                            total_batches=len(batches),
                            duration_seconds=time.time() - start_time
                        )

                        # Save checkpoint after each successful batch
                        if self.task_id:
                            CheckpointManager.save_checkpoint(
                                self.catalog_id,
                                self.task_id,
                                batch.end_date,
                                i,
                                len(batches)
                            )

                        logger.info(
                            f"Batch {i+1}/{len(batches)} completed: "
                            f"{records} records"
                        )

                    except Exception as e:
                        logger.error(f"Batch {i+1} failed: {e}")

                        return SyncResult(
                            success=False,
                            catalog_id=self.catalog_id,
                            records_fetched=total_records,
                            batches_completed=completed_batches,
                            total_batches=len(batches),
                            error_message=f"Batch {i+1} failed: {str(e)}",
                            duration_seconds=time.time() - start_time
                        )

                # Step 6: Update catalog last_sync timestamp
                CatalogManager.update_last_sync(
                    self.catalog_id,
                    date.today()
                )

                # Step 7: Reconcile data_status_local with actual table COUNT(*)
                self._reconcile_total_records()

                # Final result
                result = SyncResult(
                    success=True,
                    catalog_id=self.catalog_id,
                    records_fetched=total_records,
                    batches_completed=len(batches),
                    total_batches=len(batches),
                    duration_seconds=time.time() - start_time
                )

                logger.info(
                    f"Sync completed successfully: "
                    f"{total_records} records in {result.duration_seconds:.2f}s"
                )

                return result

            finally:
                catalog_lock.release()

        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)

            return SyncResult(
                success=False,
                catalog_id=self.catalog_id,
                error_message=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _load_catalog(self):
        """Load catalog configuration from database."""
        self.catalog = CatalogManager.get_catalog(self.catalog_id)
        
        if not self.catalog:
            raise ValueError(f"Catalog {self.catalog_id} not found")
        
        logger.debug(f"Loaded catalog: {self.catalog['catalog_name']}")
    
    def _get_data_source(self):
        """Get data source adapter based on catalog configuration."""
        source_name = self.catalog.get('data_source', 'tushare')
        
        self.source = SourceManager.get_source(source_name)
        
        if not self.source:
            raise ValueError(f"Failed to get data source: {source_name}")
        
        logger.debug(f"Using data source: {source_name}")
    
    def _calculate_incremental_range(self) -> Optional[tuple[date, date]]:
        """
        Calculate date range for incremental sync.
        
        Returns:
            Tuple of (start_date, end_date), or None if no sync needed
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        # Get local latest date
        with pool.transaction() as conn:
            cursor = conn.execute("""
                SELECT latest_date
                FROM data_status_local
                WHERE catalog_id = ?
            """, (self.catalog_id,))
            
            row = cursor.fetchone()
            local_latest_raw = row[0] if row else None

        # Convert string to date if needed
        if local_latest_raw and isinstance(local_latest_raw, str):
            local_latest = date.fromisoformat(local_latest_raw)
        else:
            local_latest = local_latest_raw
        
        # Get remote latest date from source
        contract_code = self.catalog.get('contract_code', '')
        data_type = self.catalog.get('data_type', 'daily')
        
        remote_latest = self.source.get_latest_date(contract_code, data_type)
        
        if not remote_latest:
            logger.warning("Could not get remote latest date")
            return None
        
        if not local_latest:
            # No local data, do full sync from beginning
            logger.info("No local data found, will sync from scratch")
            return (remote_latest - timedelta(days=365), remote_latest)
        
        # Calculate incremental range using trade calendar
        trading_days = TradeCalendarManager.get_trading_days(
            local_latest, remote_latest
        )

        if not trading_days:
            logger.info("Local data is up to date")
            return None

        start_date = trading_days[0]
        end_date = trading_days[-1]

        # If local_latest itself is a trading day with data, skip it
        if start_date == local_latest:
            trading_days = trading_days[1:]
            if not trading_days:
                logger.info("Local data is up to date")
                return None
            start_date = trading_days[0]

        logger.info(
            f"Incremental sync range: {start_date} to {end_date} "
            f"({len(trading_days)} trading days)"
        )

        return (start_date, end_date)
    
    def _calculate_full_range(self) -> tuple[date, date]:
        """
        Calculate date range for full sync.
        
        For full sync, use a reasonable historical range.
        In production, this could be configurable.
        
        Returns:
            Tuple of (start_date, end_date)
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=365)  # Last 1 year
        
        logger.info(f"Full sync range: {start_date} to {end_date}")
        
        return (start_date, end_date)
    
    def _split_into_batches(
        self,
        start_date: date,
        end_date: date
    ) -> list[SyncBatch]:
        """
        Split date range into batches.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of SyncBatch objects
        """
        batches = []
        current = start_date
        batch_index = 0
        
        while current <= end_date:
            batch_end = min(current + timedelta(days=self.batch_days - 1), end_date)
            
            # Calculate total batches for progress reporting
            total_days = (end_date - start_date).days + 1
            total_batches = (total_days + self.batch_days - 1) // self.batch_days
            
            batch = SyncBatch(
                start_date=current,
                end_date=batch_end,
                index=batch_index,
                total=total_batches
            )
            
            batches.append(batch)
            
            current = batch_end + timedelta(days=1)
            batch_index += 1
        
        logger.debug(f"Split into {len(batches)} batches")
        
        return batches
    
    def _process_batch(
        self,
        batch: SyncBatch,
        batch_index: int,
        total_batches: int
    ) -> int:
        """
        Process a single batch of data.
        """
        from tzdata_pkg.maintenance.sync.concurrency_controller import ConcurrencyController

        # Wait for rate limiter token before fetching
        source_name = self.catalog.get('data_source', 'tushare')
        if not ConcurrencyController.wait_for_rate_limit(source_name, timeout=120):
            raise RuntimeError(f"Rate limit timeout for source: {source_name}")

        data_type = self.catalog['data_type']
        contract_code = self.catalog.get('contract_code', '')

        if data_type == 'daily':
            return self._fetch_daily_batch(batch, contract_code)
        elif data_type == 'minute':
            return self._fetch_minute_batch(batch, contract_code)
        elif data_type in ('top20_holdings', 'position'):
            return self._fetch_holdings_batch(batch, contract_code)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
    
    def _fetch_daily_batch(
        self,
        batch: SyncBatch,
        contract_code: str
    ) -> int:
        """Fetch daily quotes for a batch."""
        from tzdata_pkg.storage.questdb_store import QuestDBStore
        from tzdata_pkg.storage.market_store import MarketStore

        # Use product_code as fallback when contract_code is empty
        effective_code = contract_code or self.catalog.get('product_code', '')

        data = self.source.fetch_daily_quotes(
            effective_code,
            batch.start_date,
            batch.end_date
        )

        if not data:
            return 0

        # Store in SQLite (primary)
        exchange = self.catalog.get('exchange_code', '')
        product_code = self.catalog.get('product_code', '')

        inserted = 0
        try:
            store = MarketStore(DBRegistry())
            inserted = store.save_quotes(data)
        except Exception as e:
            logger.error(f"SQLite quote insert failed: {e}")

        # Also store in QuestDB (secondary, if available)
        try:
            QuestDBStore.insert_daily_quotes(
                exchange=exchange,
                contract_code=effective_code,
                product_code=product_code,
                quotes=data
            )
        except Exception:
            pass

        # Update date range metadata (total_records is reconcised post-sync)
        if inserted > 0:
            latest_date = max(
                date.fromisoformat(q['trade_date']) if '-' in q['trade_date']
                else date(int(q['trade_date'][:4]), int(q['trade_date'][4:6]), int(q['trade_date'][6:8]))
                for q in data if 'trade_date' in q
            )
            QuestDBStore.update_data_status_local(
                catalog_id=self.catalog_id,
                latest_date=latest_date,
                earliest_date=batch.start_date
            )

        # Per-batch update is skipped here to avoid overwriting cumulative total;
        # the execute() method updates data_status_local with COUNT(*) after all batches complete.

        return inserted
    
    def _fetch_minute_batch(
        self,
        batch: SyncBatch,
        contract_code: str
    ) -> int:
        """Fetch minute quotes for a batch."""
        from tzdata_pkg.storage.questdb_store import QuestDBStore
        
        frequency = self.catalog.get('frequency', '1min')
        total_records = 0
        exchange = self.catalog.get('exchange_code', '')
        product_code = self.catalog.get('product_code', '')

        # Use product_code as fallback when contract_code is empty
        effective_code = contract_code or product_code

        # Fetch minute data day by day
        current = batch.start_date
        while current <= batch.end_date:
            data = self.source.fetch_minute_quotes(
                effective_code,
                current,
                frequency
            )
            
            if data:
                inserted = QuestDBStore.insert_minute_quotes(
                    exchange=exchange,
                    contract_code=contract_code,
                    product_code=product_code,
                    quotes=data,
                    frequency=frequency
                )
                total_records += inserted
            
            current += timedelta(days=1)
        
        # Update metadata status
        if total_records > 0:
            QuestDBStore.update_data_status_local(
                catalog_id=self.catalog_id,
                latest_date=batch.end_date,
                earliest_date=batch.start_date,
                total_records=total_records
            )
        
        return total_records
    
    def _fetch_holdings_batch(
        self,
        batch: SyncBatch,
        contract_code: str
    ) -> int:
        """Fetch top 20 holdings for a batch."""
        from tzdata_pkg.storage.questdb_store import QuestDBStore
        from tzdata_pkg.storage.db_registry import DBRegistry
        from tzdata_pkg.storage.market_store import MarketStore

        total_records = 0
        exchange = self.catalog.get('exchange_code', '')
        product_code = self.catalog.get('product_code', '')

        # Use product_code as fallback when contract_code is empty
        effective_code = contract_code or product_code

        # Fetch holdings day by day
        current = batch.start_date
        while current <= batch.end_date:
            data = self.source.fetch_top20_holdings(
                effective_code,
                current
            )

            if data:
                # Source returns separate long/short rows; aggregate into one row per contract per rank
                from collections import defaultdict
                grouped = defaultdict(lambda: {
                    'long_volume': 0, 'short_volume': 0,
                    'long_change': 0, 'short_change': 0, 'member_name': ''
                })
                for d in data:
                    key = (d['contract_code'], d['rank'])
                    if d['side'] == 'long':
                        grouped[key]['long_volume'] = d['volume']
                        grouped[key]['long_change'] = d['volume_change']
                        grouped[key]['member_name'] = d['member_name']
                    else:
                        grouped[key]['short_volume'] = d['volume']
                        grouped[key]['short_change'] = d['volume_change']

                # Store in SQLite (primary)
                inserted = 0
                try:
                    store = MarketStore(DBRegistry())
                    rows = []
                    for (contract, rank), info in grouped.items():
                        rows.append({
                            'exchange': exchange,
                            'trade_date': current.strftime('%Y%m%d'),
                            'contract_code': contract,
                            'product': product_code,
                            'member_name': info['member_name'],
                            'rank': rank,
                            'long_volume': info['long_volume'],
                            'short_volume': info['short_volume'],
                            'long_change': info['long_change'],
                            'short_change': info['short_change'],
                            'source': 'exchange',
                        })
                    inserted = store.save_positions(rows)
                except Exception as e:
                    logger.error(f"SQLite position insert failed: {e}")

                # Also store in QuestDB (secondary, if available)
                try:
                    QuestDBStore.insert_top20_holdings(
                        exchange=exchange,
                        contract_code=contract_code,
                        product_code=product_code,
                        holdings=data
                    )
                except Exception:
                    pass

                total_records += inserted

            current += timedelta(days=1)

        # Update metadata status
        if total_records > 0:
            try:
                QuestDBStore.update_data_status_local(
                    catalog_id=self.catalog_id,
                    latest_date=batch.end_date,
                    earliest_date=batch.start_date,
                    total_records=total_records
                )
            except Exception:
                pass

        return total_records

    def _reconcile_total_records(self):
        """
        Reconcile data_status_local.total_records with actual table COUNT(*).

        This corrects the drift that can occur when per-batch updates overwrite
        the cumulative total, or when INSERT OR REPLACE deduplicates rows.
        """
        from tzdata_pkg.storage.questdb_store import QuestDBStore
        from tzdata_pkg.storage.db_registry import DBRegistry

        registry = DBRegistry()
        pool = registry.get_pool('market')
        if not pool:
            return

        catalog = CatalogManager.get_catalog(self.catalog_id)
        if not catalog:
            return

        data_type = catalog.get('data_type', '')
        product_code = catalog.get('product_code', '')
        contract_code = catalog.get('contract_code', '')
        exchange = catalog.get('exchange_code', '')

        # Query actual row count from the appropriate table
        try:
            with pool.transaction() as conn:
                if data_type == 'daily':
                    if contract_code:
                        row = conn.execute(
                            "SELECT COUNT(*) FROM daily_quotes WHERE exchange=? AND contract_code=?",
                            (exchange, contract_code)
                        ).fetchone()
                    elif product_code:
                        row = conn.execute(
                            "SELECT COUNT(*) FROM daily_quotes WHERE exchange=? AND contract_code LIKE ?",
                            (exchange, f'{product_code}%')
                        ).fetchone()
                    else:
                        return
                elif data_type in ('top20_holdings', 'position'):
                    if contract_code:
                        row = conn.execute(
                            "SELECT COUNT(*) FROM position_detail WHERE exchange=? AND contract_code=?",
                            (exchange, contract_code)
                        ).fetchone()
                    elif product_code:
                        row = conn.execute(
                            "SELECT COUNT(*) FROM position_detail WHERE exchange=? AND contract_code LIKE ?",
                            (exchange, f'{product_code}%')
                        ).fetchone()
                    else:
                        return
                else:
                    return

                actual_count = row[0] if row else 0

                QuestDBStore.reconcile_data_status_total(self.catalog_id, actual_count)

                logger.info(
                    f"Reconciled data_status_local for catalog {self.catalog_id}: "
                    f"total_records={actual_count}"
                )
        except Exception as e:
            logger.warning(f"Failed to reconcile total records for catalog {self.catalog_id}: {e}")
