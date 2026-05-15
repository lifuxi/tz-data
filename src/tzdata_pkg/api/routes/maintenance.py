"""
Maintenance API routes.
Provides RESTful endpoints for data maintenance operations.
"""
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# === Request/Response Models ===

class AccountCreateRequest(BaseModel):
    account_name: str
    account_number: str
    futures_company: str
    cfmmc_username: Optional[str] = None
    cfmmc_password: Optional[str] = None
    exchanges_supported: Optional[list[str]] = None
    tracking_start_date: Optional[str] = None


class SystemConfigRequest(BaseModel):
    key: str
    value: str
    config_type: Optional[str] = 'text'
    description: Optional[str] = None


# === Catalog Endpoints ===

@router.get("/catalogs")
def list_catalogs(
    exchange: Optional[str] = None,
    product: Optional[str] = None
):
    """List data catalogs with optional filters."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
    
    try:
        catalogs = CatalogManager.list_catalogs(
            exchange_code=exchange,
            product_code=product
        )
        return {"success": True, "data": catalogs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalogs")
def create_catalog(request: dict):
    """Create a new data catalog."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

    try:
        catalog_id = CatalogManager.create_catalog(**request)
        return {"success": True, "catalog_id": catalog_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalogs/{catalog_id}")
def get_catalog(catalog_id: int):
    """Get a catalog by ID."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

    try:
        catalog = CatalogManager.get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail=f"Catalog {catalog_id} not found")
        return {"success": True, "data": catalog}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/catalogs/{catalog_id}")
def update_catalog(catalog_id: int, request: dict):
    """Update a catalog."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

    try:
        # Update individual fields
        fields = ['catalog_name', 'exchange_code', 'product_code', 'contract_code',
                  'data_type', 'frequency', 'data_source', 'sync_mode', 'is_enabled']
        registry = type('DBRegistry', (), {})()  # placeholder
        from tzdata_pkg.storage.db_registry import DBRegistry as _DBR
        pool = _DBR().get_pool('market')

        updates = []
        params = []
        for f in fields:
            if f in request:
                val = 1 if f == 'is_enabled' and request[f] else request[f]
                updates.append(f"{f} = ?")
                params.append(val)
        if not updates:
            return {"success": False, "message": "No fields to update"}

        updates.append("updated_at = datetime('now')")
        params.append(catalog_id)

        with pool.transaction() as conn:
            conn.execute(
                f"UPDATE data_catalog SET {', '.join(updates)} WHERE id = ?",
                params
            )

        return {"success": True, "catalog_id": catalog_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Health Check Endpoints ===

@router.get("/health/snapshot")
def get_health_snapshot(catalog_id: int):
    """Get latest health snapshot for a catalog."""
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator
    
    try:
        snapshot = HealthSnapshotGenerator.get_latest_snapshot(catalog_id)
        
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        
        return {"success": True, "data": snapshot}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/diff")
def get_diff_status():
    """Get diff status for all catalogs."""
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator
    
    try:
        diffs = HealthSnapshotGenerator.get_all_diffs()
        return {"success": True, "data": diffs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Quality Check Endpoints ===

@router.get("/quality/{catalog_id}")
def check_quality(catalog_id: int):
    """Check data quality for a catalog."""
    from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator
    
    try:
        quality = QualityEvaluator.evaluate_catalog_quality(catalog_id)
        return {"success": True, "data": quality}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Health Snapshot Endpoints (RESTful) ===

@router.post("/health-snapshots/generate")
def generate_all_snapshots():
    """Generate health snapshots for all enabled catalogs."""
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator

    try:
        results = HealthSnapshotGenerator.generate_all_snapshots()
        errors = [r for r in results if 'error' in r]
        return {
            "success": True,
            "generated": len(results) - len(errors),
            "errors": len(errors),
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-snapshots")
def list_health_snapshots(
    page: int = 1,
    page_size: int = 20
):
    """List all health snapshots with pagination."""
    from tzdata_pkg.storage.db_registry import DBRegistry

    try:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            # Get total count
            count_cursor = conn.execute("SELECT COUNT(*) FROM data_health_snapshot")
            total = count_cursor.fetchone()[0]

            # Get paginated results with catalog name
            offset = (page - 1) * page_size
            cursor = conn.execute("""
                SELECT s.id, s.catalog_id, c.catalog_name, s.snapshot_date,
                       s.missing_days, s.data_quality_score, s.completeness_pct,
                       s.consistency_status, s.last_sync_status, s.created_at
                FROM data_health_snapshot s
                LEFT JOIN data_catalog c ON s.catalog_id = c.id
                ORDER BY s.snapshot_date DESC, s.id DESC
                LIMIT ? OFFSET ?
            """, (page_size, offset))

            rows = cursor.fetchall()
            data = []
            for row in rows:
                data.append({
                    "id": row[0],
                    "catalog_id": row[1],
                    "catalog_name": row[2] or f"#{row[1]}",
                    "snapshot_date": row[3],
                    "missing_days": row[4] or 0,
                    "quality_score": round(row[5], 1) if row[5] else 0.0,
                    "completeness_pct": round(row[6], 1) if row[6] else 0.0,
                    "consistency_status": row[7],
                    "last_sync_status": row[8],
                    "created_at": row[9]
                })

        return {
            "success": True,
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-snapshots/latest")
def get_latest_health_snapshot():
    """Get aggregated latest health snapshots across all catalogs."""
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
    from tzdata_pkg.storage.db_registry import DBRegistry

    try:
        # Get latest snapshot for each catalog
        catalogs = CatalogManager.get_enabled_catalogs()
        pool = DBRegistry().get_pool('market')

        total_catalogs = len(catalogs)
        total_synced = 0
        total_quality = 0.0
        total_with_issues = 0
        catalog_issues = []
        exchange_stats = {}  # exchange_code -> {catalog_count, avg_quality, synced_count}

        with pool.transaction() as conn:
            for catalog in catalogs:
                cursor = conn.execute("""
                    SELECT missing_days, data_quality_score, completeness_pct,
                           last_sync_status, last_sync_error
                    FROM data_health_snapshot
                    WHERE catalog_id = ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, (catalog['id'],))
                row = cursor.fetchone()

                exchange = catalog.get('exchange_code', 'UNKNOWN')
                if exchange not in exchange_stats:
                    exchange_stats[exchange] = {'exchange_code': exchange, 'catalog_count': 0, 'quality_sum': 0.0, 'synced_count': 0}

                exchange_stats[exchange]['catalog_count'] += 1

                if row:
                    quality = row[1] or 0.0
                    missing = row[0] or 0
                    total_quality += quality
                    exchange_stats[exchange]['quality_sum'] += quality
                    if row[3] == 'completed':
                        total_synced += 1
                        exchange_stats[exchange]['synced_count'] += 1
                    if missing > 0:
                        total_with_issues += 1
                        catalog_issues.append({
                            "catalog_id": catalog['id'],
                            "catalog_name": catalog.get('catalog_name', f"#{catalog['id']}"),
                            "quality_score": round(quality, 1),
                            "completeness_pct": round(row[2], 1) if row[2] else 0.0,
                            "issues": f"缺失 {missing} 天"
                        })
                else:
                    exchange_stats[exchange]['quality_sum'] += 0

        avg_quality = round(total_quality / total_catalogs, 1) if total_catalogs > 0 else 0.0

        # Compute by_exchange averages
        by_exchange = {}
        for code, stats in exchange_stats.items():
            count = stats['catalog_count']
            by_exchange[code] = {
                'exchange_code': code,
                'catalog_count': count,
                'avg_quality': round(stats['quality_sum'] / count, 1) if count > 0 else 0.0,
                'synced_count': stats['synced_count']
            }

        enabled_count = sum(1 for c in catalogs if c.get('is_enabled', True))

        snapshot = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_catalogs": total_catalogs,
                "enabled_catalogs": enabled_count,
                "synced_today": total_synced,
                "avg_quality_score": avg_quality,
                "catalogs_with_issues": total_with_issues
            },
            "by_exchange": by_exchange,
            "catalogs_with_issues": catalog_issues
        }

        return {"success": True, "data": snapshot}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Account Management Endpoints ===

@router.get("/accounts")
def list_accounts(active_only: bool = True):
    """List futures accounts."""
    from tzdata_pkg.maintenance.statements.account_manager import AccountManager
    
    try:
        accounts = AccountManager.list_accounts(is_active=active_only)
        return {"success": True, "data": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts")
def create_account(request: AccountCreateRequest):
    """Create a new futures account."""
    from tzdata_pkg.maintenance.statements.account_manager import AccountManager
    
    try:
        account_id = AccountManager.create_account(
            account_name=request.account_name,
            account_number=request.account_number,
            futures_company=request.futures_company,
            cfmmc_username=request.cfmmc_username,
            cfmmc_password=request.cfmmc_password,
            exchanges_supported=request.exchanges_supported,
            tracking_start_date=request.tracking_start_date
        )
        
        return {"success": True, "account_id": account_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Exchange Management Endpoints ===

@router.get("/exchanges")
def list_exchanges(active_only: bool = True):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        data = ExchangeManager.list_all(is_active=active_only)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exchanges")
def create_exchange(request: dict):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        cid = ExchangeManager.create(**request)
        return {"success": True, "id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/exchanges/{exchange_id}")
def update_exchange(exchange_id: int, request: dict):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        ok = ExchangeManager.update(exchange_id, **request)
        return {"success": True, "updated": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/exchanges/{exchange_id}")
def delete_exchange(exchange_id: int):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        ok = ExchangeManager.delete(exchange_id)
        return {"success": True, "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Product Management Endpoints ===

@router.get("/products")
def list_products(exchange_code: Optional[str] = None):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        data = ProductManager.list_all(exchange_code=exchange_code)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products")
def create_product(request: dict):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        cid = ProductManager.create(**request)
        return {"success": True, "id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}")
def update_product(product_id: int, request: dict):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        ok = ProductManager.update(product_id, **request)
        return {"success": True, "updated": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}")
def delete_product(product_id: int):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        ok = ProductManager.delete(product_id)
        return {"success": True, "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# === Contract Sync (must be before /contracts/{contract_id} to avoid route conflict) ===

@router.post("/contracts/import-from-tushare")
def import_contracts_from_tushare(exchange: str = 'CFFEX', contract_type: str = 'futures'):
    """Import contracts from Tushare API. Auto-populates main contracts after import."""
    import logging
    from datetime import date, timedelta
    from tzdata_pkg.cli.import_contracts import ContractSyncService
    from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
    try:
        svc = ContractSyncService()
        if contract_type == 'options':
            result = svc.sync_options(exchange=exchange)
        else:
            result = svc.sync_futures(exchange=exchange)

        # Auto-populate main contracts for CFFEX futures
        if contract_type == 'futures' and result.get('inserted', 0) > 0:
            try:
                from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
                products = ProductManager.list_all(exchange_code=exchange)
                main_svc = MainContractService()
                today = date.today()
                year_end = date(today.year + 1, 12, 31)
                for p in products:
                    try:
                        main_svc.auto_populate(p['product_code'], today, year_end)
                    except Exception:
                        pass  # Skip products without quote data
                logging.getLogger(__name__).info("Auto-populated main contracts after import")
            except Exception as e:
                logging.getLogger(__name__).warning(f"Auto-populate main contracts failed: {e}")

        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts/check-expired")
def check_expired_contracts(reference_date: Optional[str] = None):
    """Mark expired contracts."""
    from datetime import datetime
    from tzdata_pkg.cli.import_contracts import ContractSyncService
    try:
        ref = datetime.strptime(reference_date, '%Y-%m-%d').date() if reference_date else None
        svc = ContractSyncService()
        result = svc.mark_expired(reference_date=ref)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/expiring")
def get_expiring_contracts(date: Optional[str] = None, days_ahead: int = 30):
    """Get contracts expiring within N days."""
    from datetime import datetime
    from tzdata_pkg.cli.import_contracts import ContractSyncService
    try:
        ref = datetime.strptime(date, '%Y-%m-%d').date() if date else None
        svc = ContractSyncService()
        results = svc.get_expiring(reference_date=ref, days_ahead=days_ahead)
        return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Contract Management Endpoints ===

@router.get("/contracts")
def list_contracts(exchange_code: Optional[str] = None, product_code: Optional[str] = None,
                   status: Optional[str] = None):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        data = ContractManager.list_all(exchange_code=exchange_code, product_code=product_code, status=status)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts")
def create_contract(request: dict):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        cid = ContractManager.create(**request)
        return {"success": True, "id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contracts/{contract_id}")
def update_contract(contract_id: int, request: dict):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        ok = ContractManager.update(contract_id, **request)
        return {"success": True, "updated": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contracts/{contract_id}")
def delete_contract(contract_id: int):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        ok = ContractManager.delete(contract_id)
        return {"success": True, "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Alert Management Endpoints ===

@router.get("/alerts")
def list_alerts(
    level: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """List alerts with optional filters and pagination."""
    from tzdata_pkg.core.monitoring import get_alert_manager
    
    try:
        alert_manager = get_alert_manager()
        all_alerts = alert_manager.alert_history
        
        # Apply filters
        filtered = all_alerts
        if level:
            filtered = [a for a in filtered if a.get('level') == level]
        if category:
            filtered = [a for a in filtered if a.get('category') == category]
        
        # Sort by timestamp (newest first)
        filtered = sorted(filtered, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Pagination
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = filtered[start:end]
        
        return {
            "success": True,
            "data": paginated,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/recent")
def get_recent_alerts(limit: int = 50):
    """Get recent alerts."""
    from tzdata_pkg.core.monitoring import get_alert_manager

    try:
        alert_manager = get_alert_manager()
        recent = alert_manager.get_recent_alerts(limit=limit)

        return {
            "success": True,
            "data": recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Trade Calendar Endpoints ===

@router.post("/trade-calendar/init")
def init_trade_calendar(year_start: int = 2025, year_end: int = 2026):
    """Initialize trade calendar with Chinese futures exchange holidays."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    try:
        count = TradeCalendarManager.init_calendar(year_start, year_end)
        return {"success": True, "initialized": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/trading-days")
def get_trading_days(start_date: str, end_date: str, exchange_code: str = 'ALL'):
    """Get trading days between two dates."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from datetime import datetime
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        days = TradeCalendarManager.get_trading_days(start, end, exchange_code)
        return {"success": True, "data": [d.isoformat() for d in days], "count": len(days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/is-trading-day")
def is_trading_day(trade_date: str, exchange_code: str = 'ALL'):
    """Check if a date is a trading day."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from datetime import datetime
    try:
        d = datetime.strptime(trade_date, '%Y-%m-%d').date()
        result = TradeCalendarManager.is_trading_day(d, exchange_code)
        return {"success": True, "trade_date": trade_date, "is_trading_day": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/calendar")
def get_calendar_view(year: int, exchange_code: str = 'ALL'):
    """Get full calendar data for a year, suitable for month/week calendar rendering."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from tzdata_pkg.storage.db_registry import DBRegistry
    from datetime import date
    try:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date, is_holiday, holiday_name
                FROM trade_calendar
                WHERE trade_date BETWEEN ? AND ?
                  AND exchange_code = ?
                ORDER BY trade_date
            """, (f"{year}-01-01", f"{year}-12-31", exchange_code))
            calendar_map = {}
            for row in rows.fetchall():
                calendar_map[row[0]] = {
                    'is_holiday': bool(row[1]),
                    'holiday_name': row[2] or ''
                }

        # Build full year calendar with each day's status
        months = []
        for month in range(1, 13):
            days = []
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year, 12, 31)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            current = start_date
            while current <= end_date:
                date_str = current.isoformat()
                info = calendar_map.get(date_str, {})
                is_weekend = current.weekday() >= 5
                is_trading = not is_weekend and not info.get('is_holiday', False)
                days.append({
                    'date': date_str,
                    'day': current.day,
                    'weekday': current.weekday(),
                    'is_weekend': is_weekend,
                    'is_trading': is_trading,
                    'is_holiday': info.get('is_holiday', False),
                    'holiday_name': info.get('holiday_name', ''),
                })
                current += timedelta(days=1)
            months.append({
                'month': month,
                'first_weekday': start_date.weekday(),
                'days': days,
            })

        return {"success": True, "data": {"year": year, "exchange_code": exchange_code, "months": months}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/status")
def get_calendar_status():
    """Get overall calendar status."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            # Year range
            row = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM trade_calendar WHERE exchange_code = 'ALL'").fetchone()
            year_start = row[0][:4] if row[0] else '-'
            year_end = row[1][:4] if row[1] else '-'
            # Exchange records
            exchange_count = conn.execute("SELECT COUNT(*) FROM trade_calendar WHERE exchange_code = 'ALL'").fetchone()[0]
            # Product count
            product_count = conn.execute("SELECT COUNT(DISTINCT product_code) FROM trade_calendar WHERE product_code != ''").fetchone()[0]
            # Total
            total_count = conn.execute("SELECT COUNT(*) FROM trade_calendar").fetchone()[0]
        return {"success": True, "data": {
            "year_start": year_start, "year_end": year_end,
            "exchange_records": exchange_count, "product_count": product_count,
            "total_records": total_count,
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/count")
def get_calendar_count():
    """Legacy endpoint for calendar counts."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM trade_calendar WHERE exchange_code = 'ALL'").fetchone()
            exchange_count = conn.execute("SELECT COUNT(*) FROM trade_calendar WHERE exchange_code = 'ALL'").fetchone()[0]
            product_count = conn.execute("SELECT COUNT(DISTINCT product_code) FROM trade_calendar WHERE product_code != ''").fetchone()[0]
            total_count = conn.execute("SELECT COUNT(*) FROM trade_calendar").fetchone()[0]
        return {
            "year_start": (row[0] or '')[:4], "year_end": (row[1] or '')[:4],
            "exchange_count": exchange_count, "product_count": product_count,
            "total_count": total_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/product/stats")
def get_product_stats(product_code: str):
    """Get statistics for a product calendar."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("""
                SELECT MIN(trade_date), MAX(trade_date), COUNT(*)
                FROM trade_calendar WHERE product_code = ?
            """, (product_code,)).fetchone()
            trading_2026 = conn.execute("""
                SELECT COUNT(*) FROM trade_calendar
                WHERE product_code = ? AND trade_date BETWEEN '2026-01-01' AND '2026-12-31' AND is_holiday = 0
            """, (product_code,)).fetchone()[0]
            trading_total = conn.execute("""
                SELECT COUNT(*) FROM trade_calendar
                WHERE product_code = ? AND is_holiday = 0
            """, (product_code,)).fetchone()[0]
        return {
            "min_date": row[0] or '',
            "max_date": row[1] or '',
            "total_count": row[2] or 0,
            "trading_days_total": trading_total,
            "trading_days_2026": trading_2026,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade-calendar/product/init")
def init_product_calendar(
    product_code: str,
    year_start: int = 2025,
    year_end: int = 2026,
):
    """Initialize product-level trade calendar from listing date."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from datetime import date
    try:
        count = TradeCalendarManager.init_product_calendar(
            product_code=product_code,
            year_start=year_start,
            year_end=year_end,
        )
        return {"success": True, "initialized": count, "product_code": product_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade-calendar/system-init")
def system_init_calendar(year_end: int = 2026, init_products: bool = True):
    """Run full system initialization: 1990-year_end exchange calendar + CFFEX product calendars."""
    from tzdata_pkg.cli.calendar_system_init import run_system_init
    try:
        result = run_system_init(year_start=1990, year_end=year_end, init_products=init_products)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/product/listing-dates")
def get_listing_dates():
    """Get all product listing dates."""
    from tzdata_pkg.maintenance.metadata import trade_calendar
    try:
        dates = trade_calendar.PRODUCT_LISTING_DATES
        return {"success": True, "data": {k: v.isoformat() for k, v in dates.items()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/product/trading-days")
def get_product_trading_days(
    product_code: str,
    start_date: str,
    end_date: str,
):
    """Get trading days for a specific product."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from datetime import date as dt_date
    try:
        start = dt_date.fromisoformat(start_date)
        end = dt_date.fromisoformat(end_date)
        days = TradeCalendarManager.get_product_trading_days(product_code, start, end)
        return {"success": True, "data": [d.isoformat() for d in days], "count": len(days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade-calendar/add-holiday")
def add_holiday(trade_date: str, holiday_name: str, exchange_code: str = 'ALL'):
    """Add a holiday to the trade calendar."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from datetime import datetime
    try:
        d = datetime.strptime(trade_date, '%Y-%m-%d').date()
        ok = TradeCalendarManager.add_holiday(d, holiday_name, exchange_code)
        return {"success": True, "added": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/next-trading-day")
def get_next_trading_day(date: str, n: int = 1, exchange_code: str = 'ALL'):
    """Get the nth trading day after the given date."""
    from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator
    from datetime import datetime
    try:
        d = datetime.strptime(date, '%Y-%m-%d').date()
        calc = DateCalculator()
        result = calc.get_next_trading_day(d, n=n, exchange_code=exchange_code)
        return {"success": True, "date": date, "n": n, "next_trading_day": result.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/prev-trading-day")
def get_prev_trading_day(date: str, n: int = 1, exchange_code: str = 'ALL'):
    """Get the nth trading day before the given date."""
    from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator
    from datetime import datetime
    try:
        d = datetime.strptime(date, '%Y-%m-%d').date()
        calc = DateCalculator()
        result = calc.get_prev_trading_day(d, n=n, exchange_code=exchange_code)
        return {"success": True, "date": date, "n": n, "prev_trading_day": result.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/trading-days-count")
def get_trading_days_count(start_date: str, end_date: str, exchange_code: str = 'ALL'):
    """Count trading days in a date range (inclusive)."""
    from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator
    from datetime import datetime
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        calc = DateCalculator()
        count = calc.get_trading_days_count(start, end, exchange_code=exchange_code)
        return {"success": True, "start_date": start_date, "end_date": end_date, "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Tushare Calendar Import ===

@router.post("/trade-calendar/import-from-tushare")
def import_calendar_from_tushare(exchange: str = 'CFFEX', start_date: str = None, end_date: str = None):
    """Import trade calendar from Tushare API."""
    from tzdata_pkg.cli.import_trade_calendar import CalendarImporter
    try:
        importer = CalendarImporter()
        result = importer.import_calendar(exchange=exchange, start_date=start_date, end_date=end_date)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Calendar Cache ===

@router.get("/trade-calendar/cache/status")
def get_cache_status():
    """Get calendar cache status."""
    from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
    cache = CalendarCache.get_instance()
    return {"success": True, "cache": cache.status()}


@router.post("/trade-calendar/cache/preload")
def preload_cache(years: Optional[str] = None):
    """Preload calendar cache. Years as comma-separated list (e.g. '2025,2026,2027')."""
    from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
    cache = CalendarCache.get_instance()
    year_list = [int(y.strip()) for y in years.split(',')] if years else None
    cache.preload(years=year_list)
    return {"success": True, "cache": cache.status()}


# === Special Date Override ===

@router.post("/trade-calendar/special-dates")
def create_special_date(
    exchange_code: str,
    trade_date: str,
    override_type: str,
    reason: str = '',
    operator: str = 'system',
):
    """Create a special date override."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
    try:
        d = datetime.strptime(trade_date, '%Y-%m-%d').date()
        mgr = SpecialDateManager()
        mgr.create(exchange_code=exchange_code, trade_date=d, override_type=override_type, reason=reason, operator=operator)
        return {"success": True, "exchange_code": exchange_code, "trade_date": trade_date}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/special-dates")
def list_special_dates(
    exchange_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """List special date overrides."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
    try:
        mgr = SpecialDateManager()
        sd = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
        ed = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        results = mgr.list(exchange_code=exchange_code, start_date=sd, end_date=ed)
        return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/trade-calendar/special-dates")
def delete_special_date(exchange_code: str, trade_date: str):
    """Delete a special date override."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
    try:
        d = datetime.strptime(trade_date, '%Y-%m-%d').date()
        mgr = SpecialDateManager()
        mgr.delete(exchange_code=exchange_code, trade_date=d)
        return {"success": True, "exchange_code": exchange_code, "trade_date": trade_date}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Main Contract Identification ===

@router.get("/main-contract/{product_code}")
def get_main_contract(product_code: str, date: str):
    """Get main contract for a product on a given date."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
    try:
        d = datetime.strptime(date, '%Y-%m-%d').date()
        svc = MainContractService()
        contract = svc.get_main_contract(product_code, d)
        return {"success": True, "product_code": product_code, "date": date, "contract_code": contract}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/main-contract/{product_code}")
def set_main_contract(product_code: str, date: str, contract_code: str):
    """Manually set main contract for a date."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
    try:
        d = datetime.strptime(date, '%Y-%m-%d').date()
        svc = MainContractService()
        svc.set_main_contract(product_code, d, contract_code)
        return {"success": True, "product_code": product_code, "date": date, "contract_code": contract_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/main-contract/{product_code}/series")
def get_main_contract_series(product_code: str, start_date: str, end_date: str):
    """Get main contract series for a date range."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
    try:
        s = datetime.strptime(start_date, '%Y-%m-%d').date()
        e = datetime.strptime(end_date, '%Y-%m-%d').date()
        svc = MainContractService()
        results = svc.get_main_series(product_code, s, e)
        return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/main-contract/{product_code}/rollovers")
def get_rollover_dates(product_code: str, start_date: str, end_date: str):
    """Get rollover dates (when main contract changes)."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
    try:
        s = datetime.strptime(start_date, '%Y-%m-%d').date()
        e = datetime.strptime(end_date, '%Y-%m-%d').date()
        svc = MainContractService()
        results = svc.get_rollover_dates(product_code, s, e)
        return {"success": True, "count": len(results), "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/main-contract/{product_code}/auto-populate")
def auto_populate_main_contract(product_code: str, start_date: str, end_date: str):
    """Auto-populate main contract mappings from open interest data."""
    from datetime import datetime
    from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
    try:
        s = datetime.strptime(start_date, '%Y-%m-%d').date()
        e = datetime.strptime(end_date, '%Y-%m-%d').date()
        svc = MainContractService()
        count = svc.auto_populate(product_code, s, e)
        return {"success": True, "inserted": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Trading Hours Management ===

@router.get("/trading-hours/is-trading-time")
def check_trading_time(template_id: str, time_str: str):
    """Check if a time is within trading hours."""
    from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
    try:
        mgr = TradingHoursManager()
        result = mgr.is_trading_time(template_id, time_str)
        return {"success": True, "template_id": template_id, "time": time_str, "is_trading": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading-hours/{template_id}")
def get_trading_hours_template(template_id: str):
    """Get trading hours template by ID."""
    from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
    try:
        mgr = TradingHoursManager()
        tmpl = mgr.get_template(template_id)
        if tmpl is None:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        return {"success": True, "data": tmpl}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading-hours/templates")
def create_trading_hours_template(
    template_id: str,
    template_name: str,
    exchange_code: str,
    product_type: str,
    normal_schedule: str,
    night_schedule: Optional[str] = None,
    is_default: int = 0,
):
    """Create a trading hours template. Schedules as JSON strings."""
    import json
    from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
    try:
        mgr = TradingHoursManager()
        mgr.create_template(
            template_id=template_id,
            template_name=template_name,
            exchange_code=exchange_code,
            product_type=product_type,
            normal_schedule=json.loads(normal_schedule),
            night_schedule=json.loads(night_schedule) if night_schedule else None,
            is_default=is_default
        )
        return {"success": True, "template_id": template_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading-hours/{template_id}/sessions")
def get_trading_sessions(template_id: str):
    """Get all trading sessions for a template."""
    from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
    try:
        mgr = TradingHoursManager()
        sessions = mgr.get_sessions(template_id)
        return {"success": True, "template_id": template_id, "sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Statement Upload & Management ===

import uuid

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads")


@router.get("/statements")
def list_statements(page: int = 1, page_size: int = 20, account_id: Optional[int] = None, status: Optional[str] = None):
    """List parsed statements/bills with pagination."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('trading')
        with pool.transaction() as conn:
            where = []
            params = []

            if account_id:
                where.append("bills.account_id = ?")
                params.append(str(account_id))
            if status:
                where.append("bills.status = ?")
                params.append(status)

            where_sql = " AND ".join(where) if where else "1=1"

            # Count
            cursor = conn.execute(f"SELECT COUNT(*) FROM bills WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # Data
            offset = (page - 1) * page_size
            cursor = conn.execute(f"""
                SELECT bills.id, bills.account_id, bills.bill_date_start, bills.bill_date_end,
                       bills.status, bills.client_name, bills.currency,
                       bills.balance_bf, bills.balance_cf, bills.client_equity,
                       bills.file_path, bills.created_at,
                       futures_accounts.account_name as account_name
                FROM bills
                LEFT JOIN futures_accounts ON bills.account_id = CAST(futures_accounts.id AS TEXT)
                WHERE {where_sql}
                ORDER BY bills.bill_date_start DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])

            rows = []
            for r in cursor.fetchall():
                rows.append({
                    'id': r[0],
                    'account_id': r[1],
                    'account_name': r[12] or r[1],
                    'file_name': os.path.basename(r[10] or ''),
                    'statement_date': r[2],
                    'status': r[4],
                    'client_name': r[5],
                    'currency': r[6],
                    'balance_bf': r[7],
                    'balance_cf': r[8],
                    'client_equity': r[9],
                    'parsed_at': r[11],
                })

            return {"data": rows, "total": total, "page": page, "page_size": page_size}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/statements/upload")
async def upload_statement(file: UploadFile = File(...), account_id: Optional[str] = None):
    """Upload a statement file."""
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename)[1] if file.filename else '.txt'
        unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename or 'upload'}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file.filename,
            "file_size": len(content)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/statements/{statement_id}/parse")
def parse_statement(statement_id: int):
    """Parse an uploaded statement file."""
    from tzdata_pkg.maintenance.statements.parsers.cfmmc_parser import CFMMCParser
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('trading')

        # Get the bill record
        with pool.transaction() as conn:
            cursor = conn.execute("SELECT file_path, status FROM bills WHERE id = ?", (statement_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Statement not found")
            file_path, status = row
            if not file_path or not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Statement file not found on disk")

        # Parse the file
        parser = CFMMCParser()
        result = parser.parse_file(file_path)

        return {
            "success": True,
            "statement_id": statement_id,
            "records_parsed": len(result) if result else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/statements/{statement_id}")
def delete_statement(statement_id: int):
    """Delete a statement record and its file."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('trading')

        with pool.transaction() as conn:
            cursor = conn.execute("SELECT file_path FROM bills WHERE id = ?", (statement_id,))
            row = cursor.fetchone()
            if row and row[0] and os.path.exists(row[0]):
                os.remove(row[0])
            conn.execute("DELETE FROM bills WHERE id = ?", (statement_id,))

        return {"success": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Bill Balance Verification ===

@router.post("/statements/verify-balance")
def verify_bill_balance(request: dict):
    """Verify bill statement balance consistency (试算平衡)."""
    from tzdata_pkg.maintenance.statements.bill_balance_verifier import BillBalanceVerifier
    try:
        result = BillBalanceVerifier.verify(
            balance_opening=request.get('balance_opening', 0),
            balance_closing=request.get('balance_closing', 0),
            deposits=request.get('deposits', 0),
            withdrawals=request.get('withdrawals', 0),
            realized_pnl=request.get('realized_pnl', 0),
            floating_pnl=request.get('floating_pnl', 0),
            commission=request.get('commission', 0),
            delivery_pnl=request.get('delivery_pnl', 0),
            other_adjustments=request.get('other_adjustments', 0),
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Bill-Market Reconciliation ===

@router.post("/statements/reconcile")
def reconcile_bill_trades(request: dict):
    """Reconcile bill trades against market quotes (滑点分析)."""
    from tzdata_pkg.maintenance.statements.bill_reconciler import BillMarketReconciler
    try:
        reconciled = BillMarketReconciler.reconcile_trades(
            trades=request.get('trades', []),
            market_quotes=request.get('market_quotes', []),
            price_tolerance_pct=request.get('price_tolerance_pct', 5.0)
        )
        report = BillMarketReconciler.generate_slippage_report(reconciled)
        return {"success": True, "reconciled": reconciled, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statements/reconcile/{account_id}")
def reconcile_from_db(
    account_id: int,
    start_date: str,
    end_date: str,
    price_tolerance_pct: float = 5.0
):
    """Reconcile bill trades against market data from database."""
    from tzdata_pkg.maintenance.statements.bill_reconciler import BillMarketReconciler
    from datetime import datetime
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        result = BillMarketReconciler.reconcile_from_db(
            account_id, start, end, price_tolerance_pct
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Credential Management ===

@router.post("/credentials")
def save_credential(request: dict):
    """Save encrypted CFMMC credentials for an account."""
    from tzdata_pkg.maintenance.statements.credential_vault import CredentialVault
    try:
        vault = CredentialVault()
        vault.save_credentials(
            account_id=request['account_id'],
            username=request['username'],
            password=request['password']
        )
        return {"success": True, "message": "Credential saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Sync Status Endpoint ===

@router.get("/sync/status")
def get_sync_status():
    """Get current sync concurrency and rate limit status."""
    from tzdata_pkg.maintenance.sync.concurrency_controller import ConcurrencyController
    try:
        status = ConcurrencyController.get_status()
        return {"success": True, "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === System Config (API tokens, shared settings) ===

@router.get("/system-config")
def list_system_config():
    """List all system configuration entries."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            rows = conn.execute(
                "SELECT config_key, config_value, config_type, description, updated_at FROM system_config ORDER BY config_key"
            ).fetchall()
        return {
            "success": True,
            "data": [
                {
                    "key": r[0],
                    "value": r[1],
                    "config_type": r[2],
                    "description": r[3],
                    "updated_at": r[4],
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-config/{config_key}")
def get_system_config(config_key: str):
    """Get a specific config value."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT config_key, config_value, config_type, description, updated_at FROM system_config WHERE config_key = ?",
                (config_key,)
            ).fetchone()
        if row is None:
            return {"success": False, "data": None}
        return {
            "success": True,
            "data": {
                "key": row[0],
                "value": row[1],
                "config_type": row[2],
                "description": row[3],
                "updated_at": row[4],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule")
def list_schedule():
    """List all Celery Beat scheduled tasks."""
    from tzdata_pkg.scheduler.celery_app import celery_app

    schedule = celery_app.conf.get('beat_schedule', {})
    tasks = []
    for name, entry in sorted(schedule.items()):
        schedule_obj = entry.get('schedule')
        # Extract human-readable schedule string
        schedule_str = str(schedule_obj) if schedule_obj else ''
        tasks.append({
            'name': name,
            'task': entry.get('task', ''),
            'schedule': schedule_str,
        })

    return {
        'success': True,
        'total': len(tasks),
        'tasks': tasks,
    }


@router.put("/system-config")
def upsert_system_config(request: SystemConfigRequest):
    """Create or update a system config entry."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("""
                INSERT INTO system_config (config_key, config_value, config_type, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    config_type = excluded.config_type,
                    description = excluded.description,
                    updated_at = CURRENT_TIMESTAMP
            """, (request.key, request.value, request.config_type, request.description))
        return {"success": True, "message": f"Config '{request.key}' saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/system-config/{config_key}")
def delete_system_config(config_key: str):
    """Delete a system config entry."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("DELETE FROM system_config WHERE config_key = ?", (config_key,))
        return {"success": True, "message": f"Config '{config_key}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
