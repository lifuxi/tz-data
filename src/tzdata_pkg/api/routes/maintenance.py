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

@router.get("/catalogs", summary="数据目录列表")
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


@router.post("/catalogs", summary="创建数据目录")
def create_catalog(request: dict):
    """Create a new data catalog."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

    try:
        catalog_id = CatalogManager.create_catalog(**request)
        return {"success": True, "catalog_id": catalog_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalogs/{catalog_id}", summary="目录详情")
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


@router.put("/catalogs/{catalog_id}", summary="更新数据目录")
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

@router.get("/health/snapshot", summary="最新健康快照")
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


@router.get("/health/diff", summary="健康快照差异对比")
def get_diff_status():
    """Get diff status for all catalogs."""
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator
    
    try:
        diffs = HealthSnapshotGenerator.get_all_diffs()
        return {"success": True, "data": diffs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Quality Check Endpoints ===

@router.get("/quality/overview", summary="数据质量总览")
def quality_overview():
    """
    Combined data quality overview: reconciliation status + gap detection + health snapshots.
    Single endpoint for the frontend quality dashboard tab.
    """
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    from tzdata_pkg.storage.db_registry import DBRegistry

    catalogs = CatalogManager.get_enabled_catalogs()
    pool = DBRegistry().get_pool('market')
    result = []

    for cat in catalogs:
        catalog_id = cat['id']
        exchange = cat.get('exchange_code', '')
        product_code = cat.get('product_code', '')
        contract_code = cat.get('contract_code', '')
        data_type = cat.get('data_type', '')

        item = {
            'catalog_id': catalog_id,
            'name': cat.get('catalog_name', ''),
            'exchange': exchange,
            'product': product_code,
            'data_type': data_type,
        }

        # 1. Get recorded total from data_status_local
        with pool.transaction() as conn:
            row = conn.execute("""
                SELECT total_records, earliest_date, latest_date
                FROM data_status_local WHERE catalog_id = ?
            """, (catalog_id,)).fetchone()
            item['recorded_total'] = row[0] if row and row[0] else 0
            item['earliest_date'] = row[1] if row and row[1] else '-'
            item['latest_date'] = row[2] if row and row[2] else '-'

        # 2. Get actual total from table COUNT(*)
        try:
            with pool.connection() as conn:
                if data_type == 'daily':
                    if contract_code:
                        query = "SELECT COUNT(*) FROM daily_quotes WHERE exchange=? AND contract_code=?"
                        params = (exchange, contract_code)
                    elif product_code:
                        query = "SELECT COUNT(*) FROM daily_quotes WHERE exchange=? AND contract_code LIKE ?"
                        params = (exchange, f'{product_code}%')
                    else:
                        query = "SELECT COUNT(*) FROM daily_quotes WHERE exchange=?"
                        params = (exchange,)
                elif data_type in ('top20_holdings', 'position'):
                    if contract_code:
                        query = "SELECT COUNT(*) FROM position_detail WHERE exchange=? AND contract_code=?"
                        params = (exchange, contract_code)
                    elif product_code:
                        query = "SELECT COUNT(*) FROM position_detail WHERE exchange=? AND contract_code LIKE ?"
                        params = (exchange, f'{product_code}%')
                    else:
                        query = "SELECT COUNT(*) FROM position_detail WHERE exchange=?"
                        params = (exchange,)
                else:
                    query = None

                if query:
                    item['actual_total'] = conn.execute(query, params).fetchone()[0]
                else:
                    item['actual_total'] = 0
        except Exception:
            item['actual_total'] = 0

        # 3. Drift
        item['drift'] = abs((item.get('recorded_total', 0) or 0) - (item.get('actual_total', 0) or 0))
        item['drift_status'] = 'ok' if item['drift'] == 0 else ('warn' if item['drift'] < max(item['actual_total'] * 0.01, 100) else 'error')

        # 4. Expected trading days vs actual
        if item['earliest_date'] and item['latest_date'] and item['earliest_date'] != '-':
            try:
                from datetime import date as _date
                def _parse_d(s):
                    if isinstance(s, _date): return s
                    if '-' in s: return _date.fromisoformat(s)
                    return _date(int(s[:4]), int(s[4:6]), int(s[6:8]))

                earliest = _parse_d(item['earliest_date'])
                latest = _parse_d(item['latest_date'])

                if product_code and data_type == 'daily':
                    trading_days = TradeCalendarManager.get_product_trading_days(product_code, earliest, latest)
                    if not trading_days:
                        trading_days = TradeCalendarManager.get_trading_days(earliest, latest, exchange)
                else:
                    trading_days = TradeCalendarManager.get_trading_days(earliest, latest, exchange)

                item['expected_days'] = len(trading_days)

                # Actual unique dates
                def _norm_d(dt):
                    if '-' in dt: return dt
                    return f'{dt[:4]}-{dt[4:6]}-{dt[6:8]}'

                with pool.connection() as conn:
                    if data_type == 'daily':
                        if contract_code:
                            rows = conn.execute("SELECT DISTINCT trade_date FROM daily_quotes WHERE exchange=? AND contract_code=?", (exchange, contract_code)).fetchall()
                        elif product_code:
                            rows = conn.execute("SELECT DISTINCT trade_date FROM daily_quotes WHERE exchange=? AND contract_code LIKE ?", (exchange, f'{product_code}%')).fetchall()
                        else:
                            rows = []
                    elif data_type in ('top20_holdings', 'position'):
                        if contract_code:
                            rows = conn.execute("SELECT DISTINCT trade_date FROM position_detail WHERE exchange=? AND contract_code=?", (exchange, contract_code)).fetchall()
                        elif product_code:
                            rows = conn.execute("SELECT DISTINCT trade_date FROM position_detail WHERE exchange=? AND contract_code LIKE ?", (exchange, f'{product_code}%')).fetchall()
                        else:
                            rows = []
                    else:
                        rows = []

                actual_dates = {_norm_d(r[0]) for r in rows}
                trading_set = {d.isoformat() for d in trading_days}
                missing = sorted(trading_set - actual_dates)

                item['actual_days'] = len(actual_dates & trading_set)
                item['missing_days'] = len(missing)
                item['missing_dates'] = missing[:5]  # First 5 for display
                item['completeness_pct'] = round((len(trading_set) - len(missing)) / len(trading_set) * 100, 1) if trading_set else 100.0
            except Exception:
                item['expected_days'] = 0
                item['actual_days'] = 0
                item['missing_days'] = 0
                item['missing_dates'] = []
                item['completeness_pct'] = 0.0
        else:
            item['expected_days'] = 0
            item['actual_days'] = 0
            item['missing_days'] = 0
            item['missing_dates'] = []
            item['completeness_pct'] = 0.0

        # 5. Health snapshot
        snapshot = HealthSnapshotGenerator.get_latest_snapshot(catalog_id)
        item['quality_score'] = snapshot.get('data_quality_score', 0) if snapshot else 0
        item['consistency_status'] = snapshot.get('consistency_status', 'unknown') if snapshot else 'unknown'

        result.append(item)

    # Summary
    total_catalogs = len(result)
    missing_count = sum(1 for r in result if r.get('missing_days', 0) > 0)
    drift_count = sum(1 for r in result if r.get('drift_status') == 'error')

    return {
        'success': True,
        'data': result,
        'summary': {
            'total_catalogs': total_catalogs,
            'catalogs_missing': missing_count,
            'catalogs_with_drift': drift_count,
            'avg_completeness': round(sum(r.get('completeness_pct', 0) for r in result) / total_catalogs, 1) if total_catalogs else 0,
        }
    }


@router.get("/quality/{catalog_id}", summary="目录质量评估")
def check_quality(catalog_id: int):
    """Check data quality for a catalog."""
    from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator

    try:
        quality = QualityEvaluator.evaluate_catalog_quality(catalog_id)
        return {"success": True, "data": quality}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Health Snapshot Endpoints (RESTful) ===

@router.post("/health-snapshots/generate", summary="生成健康快照")
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


@router.get("/health-snapshots", summary="历史健康快照列表")
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


@router.get("/health-snapshots/latest", summary="最新健康快照")
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

@router.get("/accounts", summary="账户列表")
def list_accounts(active_only: bool = True):
    """List futures accounts."""
    from tzdata_pkg.maintenance.statements.account_manager import AccountManager
    
    try:
        accounts = AccountManager.list_accounts(is_active=active_only)
        return {"success": True, "data": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts", summary="创建账户")
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

@router.get("/exchanges", summary="交易所列表")
def list_exchanges(active_only: bool = True):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        data = ExchangeManager.list_all(is_active=active_only)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exchanges", summary="创建交易所")
def create_exchange(request: dict):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        cid = ExchangeManager.create(**request)
        return {"success": True, "id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/exchanges/{exchange_id}", summary="更新交易所")
def update_exchange(exchange_id: int, request: dict):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        ok = ExchangeManager.update(exchange_id, **request)
        return {"success": True, "updated": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/exchanges/{exchange_id}", summary="删除交易所")
def delete_exchange(exchange_id: int):
    from tzdata_pkg.maintenance.metadata.exchange_manager import ExchangeManager
    try:
        ok = ExchangeManager.delete(exchange_id)
        return {"success": True, "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Product Management Endpoints ===

@router.get("/products", summary="品种列表")
def list_products(exchange_code: Optional[str] = None):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        data = ProductManager.list_all(exchange_code=exchange_code)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products", summary="创建品种")
def create_product(request: dict):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        cid = ProductManager.create(**request)
        return {"success": True, "id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}", summary="更新品种")
def update_product(product_id: int, request: dict):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        ok = ProductManager.update(product_id, **request)
        return {"success": True, "updated": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}", summary="删除品种")
def delete_product(product_id: int):
    from tzdata_pkg.maintenance.metadata.product_manager import ProductManager
    try:
        ok = ProductManager.delete(product_id)
        return {"success": True, "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# === Contract Sync (must be before /contracts/{contract_id} to avoid route conflict) ===

@router.post("/contracts/import-from-tushare", summary="从Tushare导入合约")
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


@router.post("/contracts/check-expired", summary="检查到期合约")
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


@router.get("/contracts/expiring", summary="即将到期合约列表")
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

@router.get("/contracts", summary="合约列表")
def list_contracts(exchange_code: Optional[str] = None, product_code: Optional[str] = None,
                   status: Optional[str] = None):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        data = ContractManager.list_all(exchange_code=exchange_code, product_code=product_code, status=status)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts", summary="创建合约")
def create_contract(request: dict):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        cid = ContractManager.create(**request)
        return {"success": True, "id": cid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contracts/{contract_id}", summary="更新合约")
def update_contract(contract_id: int, request: dict):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        ok = ContractManager.update(contract_id, **request)
        return {"success": True, "updated": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contracts/{contract_id}", summary="删除合约")
def delete_contract(contract_id: int):
    from tzdata_pkg.maintenance.metadata.contract_manager import ContractManager
    try:
        ok = ContractManager.delete(contract_id)
        return {"success": True, "deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Alert Management Endpoints ===

@router.get("/alerts", summary="告警列表")
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


@router.get("/alerts/recent", summary="最近告警")
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

@router.post("/trade-calendar/init", summary="初始化交易日历")
def init_trade_calendar(year_start: int = 2025, year_end: int = 2026):
    """Initialize trade calendar with Chinese futures exchange holidays."""
    from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager
    try:
        count = TradeCalendarManager.init_calendar(year_start, year_end)
        return {"success": True, "initialized": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/trading-days", summary="交易日列表")
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


@router.get("/trade-calendar/is-trading-day", summary="是否交易日")
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


@router.get("/trade-calendar/calendar", summary="日历数据")
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


@router.get("/trade-calendar/status", summary="日历状态")
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


@router.get("/trade-calendar/count", summary="交易日计数")
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


@router.get("/trade-calendar/product/stats", summary="产品日历统计")
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


@router.post("/trade-calendar/product/init", summary="产品日历初始化")
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


@router.post("/trade-calendar/system-init", summary="系统初始化日历")
def system_init_calendar(year_end: int = 2026, init_products: bool = True):
    """Run full system initialization: 1990-year_end exchange calendar + CFFEX product calendars."""
    from tzdata_pkg.cli.calendar_system_init import run_system_init
    try:
        result = run_system_init(year_start=1990, year_end=year_end, init_products=init_products)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/product/listing-dates", summary="产品上市日期")
def get_listing_dates():
    """Get all product listing dates."""
    from tzdata_pkg.maintenance.metadata import trade_calendar
    try:
        dates = trade_calendar.PRODUCT_LISTING_DATES
        return {"success": True, "data": {k: v.isoformat() for k, v in dates.items()}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-calendar/product/trading-days", summary="产品交易日列表")
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


@router.post("/trade-calendar/add-holiday", summary="添加节假日")
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


@router.get("/trade-calendar/next-trading-day", summary="下一个交易日")
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


@router.get("/trade-calendar/prev-trading-day", summary="上一个交易日")
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


@router.get("/trade-calendar/trading-days-count", summary="区间交易日数")
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

@router.post("/trade-calendar/import-from-tushare", summary="从Tushare导入日历")
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

@router.get("/trade-calendar/cache/status", summary="缓存状态")
def get_cache_status():
    """Get calendar cache status."""
    from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
    cache = CalendarCache.get_instance()
    return {"success": True, "cache": cache.status()}


@router.post("/trade-calendar/cache/preload", summary="缓存预热")
def preload_cache(years: Optional[str] = None):
    """Preload calendar cache. Years as comma-separated list (e.g. '2025,2026,2027')."""
    from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
    cache = CalendarCache.get_instance()
    year_list = [int(y.strip()) for y in years.split(',')] if years else None
    cache.preload(years=year_list)
    return {"success": True, "cache": cache.status()}


# === Special Date Override ===

@router.post("/trade-calendar/special-dates", summary="添加特殊日期")
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


@router.get("/trade-calendar/special-dates", summary="特殊日期列表")
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


@router.delete("/trade-calendar/special-dates", summary="删除特殊日期")
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

@router.get("/main-contract/{product_code}", summary="获取主力合约")
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


@router.post("/main-contract/{product_code}", summary="设置主力合约")
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


@router.get("/main-contract/{product_code}/series", summary="主力合约序列")
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


@router.get("/main-contract/{product_code}/rollovers", summary="换月记录")
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


@router.post("/main-contract/{product_code}/auto-populate", summary="自动填充主力合约")
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

@router.get("/trading-hours/is-trading-time", summary="是否交易时间")
def check_trading_time(template_id: str, time_str: str):
    """Check if a time is within trading hours."""
    from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
    try:
        mgr = TradingHoursManager()
        result = mgr.is_trading_time(template_id, time_str)
        return {"success": True, "template_id": template_id, "time": time_str, "is_trading": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading-hours/{template_id}", summary="交易时间模板详情")
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


@router.post("/trading-hours/templates", summary="创建交易时间模板")
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


@router.get("/trading-hours/{template_id}/sessions", summary="时段列表")
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


@router.get("/statements", summary="账单列表")
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


@router.post("/statements/upload", summary="上传账单文件")
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


@router.post("/statements/{statement_id}/parse", summary="解析账单")
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


@router.delete("/statements/{statement_id}", summary="删除账单")
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


@router.post("/statements/preview", summary="上传并预览解析")
async def preview_statement(file: UploadFile = File(...), account_id: Optional[str] = None):
    """Step 1+2: 上传文件并解析预览，不提交到数据库。"""
    import tempfile
    from tzdata_pkg.maintenance.statements.parsers.cfmmc_parser import CFMMCParser
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename)[1] if file.filename else '.txt'
        unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename or 'upload'}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        # Parse for preview
        parser = CFMMCParser()
        parsed = parser.parse(file_path)

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file.filename,
            "file_size": len(content),
            "preview": {
                "summary": parsed.get('summary', {}),
                "trades": parsed.get('trades', []),
                "positions": parsed.get('positions', []),
                "funds": parsed.get('funds', []),
                "trade_count": len(parsed.get('trades', [])),
                "position_count": len(parsed.get('positions', [])),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConfirmStatementRequest(BaseModel):
    file_path: str
    file_name: str
    account_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/statements/confirm", summary="确认提交账单")
def confirm_statement(req: ConfirmStatementRequest):
    """Step 3: 将已解析的账单数据提交到数据库。"""
    from tzdata_pkg.maintenance.statements.parsers.cfmmc_parser import CFMMCParser
    from tzdata_pkg.storage.db_registry import DBRegistry
    import re
    try:
        if not os.path.exists(req.file_path):
            raise HTTPException(status_code=404, detail="上传文件不存在")

        parser = CFMMCParser()
        parsed = parser.parse(req.file_path)

        # Extract bill date from filename (e.g. "20260513.txt" -> "2026-05-13")
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', req.file_name or '')
        bill_date = f"{date_match[1]}-{date_match[2]}-{date_match[3]}" if date_match else None

        # Extract summary fields
        summary = parsed.get('summary', {})
        raw_summary = summary.get('raw_data', [])

        pool = DBRegistry().get_pool('trading')
        with pool.transaction() as conn:
            # Insert into bills table — match actual schema column names
            cursor = conn.execute("""
                INSERT INTO bills (
                    account_id, bill_date_start, bill_date_end, file_path,
                    status, client_name, currency,
                    balance_bf, balance_cf, client_equity,
                    deposit_withdrawal, realized_pl, mtm_pl, commission,
                    premium_received, premium_paid, fund_available, margin_occupied,
                    total_records, parse_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.account_id or parsed.get('client_id', ''),
                bill_date,
                bill_date,
                req.file_path,
                'parsed',
                parsed.get('client_name', ''),
                'CNY',
                summary.get('balance_bf'),
                summary.get('balance_cf'),
                summary.get('client_equity'),
                summary.get('deposit_withdrawal'),
                summary.get('realized_pnl'),
                summary.get('mtm_pnl'),
                summary.get('commission'),
                summary.get('premium_received'),
                summary.get('premium_paid'),
                summary.get('fund_available'),
                summary.get('margin_occupied'),
                len(parsed.get('trades', [])),
                None,
            ))
            bill_id = cursor.lastrowid

        return {
            "success": True,
            "bill_id": bill_id,
            "bill_date": bill_date,
            "trade_count": len(parsed.get('trades', [])),
            "position_count": len(parsed.get('positions', [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Bill Balance Verification ===

@router.post("/statements/verify-balance", summary="余额校验")
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

@router.post("/statements/reconcile", summary="滑点对账")
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


@router.get("/statements/reconcile/{account_id}", summary="对账结果")
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

@router.post("/credentials", summary="创建CFMMC凭证")
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

@router.get("/sync/status", summary="同步状态")
def get_sync_status():
    """Get current sync concurrency and rate limit status."""
    from tzdata_pkg.maintenance.sync.concurrency_controller import ConcurrencyController
    try:
        status = ConcurrencyController.get_status()
        return {"success": True, "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === System Config (API tokens, shared settings) ===

@router.get("/system-config", summary="系统配置列表")
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


@router.get("/system-config/{config_key}", summary="配置项详情")
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


@router.get("/schedule", summary="Celery调度任务列表")
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


@router.put("/system-config", summary="更新系统配置")
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
        from tzdata_pkg.config import invalidate_config_cache
        invalidate_config_cache(request.key)
        return {"success": True, "message": f"Config '{request.key}' saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/system-config/{config_key}", summary="删除系统配置")
def delete_system_config(config_key: str):
    """Delete a system config entry."""
    from tzdata_pkg.storage.db_registry import DBRegistry
    try:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("DELETE FROM system_config WHERE config_key = ?", (config_key,))
        from tzdata_pkg.config import invalidate_config_cache
        invalidate_config_cache(config_key)
        return {"success": True, "message": f"Config '{config_key}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notification/test", summary="测试通知")
def test_notification():
    """Send a test DingTalk notification to verify webhook configuration."""
    from tzdata_pkg.config import _get_system_config_value
    import os

    webhook_url = _get_system_config_value("dingtalk.webhook") or os.getenv("DINGTALK_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="钉钉 Webhook 未配置，请先在系统配置中设置 dingtalk.webhook")

    try:
        import requests
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "测试通知",
                "text": "## 测试通知\n\n**级别**: info\n\n**时间**: 现在\n\n**详情**: 这是一条来自 tz-data 系统的测试通知消息。",
            },
        }
        resp = requests.post(webhook_url, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            return {"success": True, "message": "测试通知发送成功"}
        else:
            raise HTTPException(status_code=502, detail=f"钉钉返回: {result}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {e}")


@router.post("/notification/test-wechat", summary="测试企业微信通知")
def test_wechat_notification():
    """Send a test WeChat Work notification to verify webhook configuration."""
    from tzdata_pkg.config import _get_system_config_value
    import os

    webhook_url = _get_system_config_value("wechat.webhook") or os.getenv("WECHAT_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="企业微信 Webhook 未配置，请先在系统配置中设置 wechat.webhook")

    try:
        import requests
        payload = {
            "msgtype": "text",
            "text": {
                "content": "[tz-data 测试通知]\n\n这是一条来自 tz-data 系统的测试通知消息。\n时间：现在\n级别：info"
            },
        }
        resp = requests.post(webhook_url, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            return {"success": True, "message": "企业微信测试通知发送成功"}
        else:
            raise HTTPException(status_code=502, detail=f"企业微信返回: {result}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {e}")


# === Data Dashboard ===

# Table descriptions for business context
_TABLE_DESCRIPTIONS: dict[str, str] = {
    # market DB
    "contracts": "合约主表",
    "daily_quotes": "日线行情数据",
    "minute_quotes": "分钟线行情数据",
    "settlement_prices": "结算价数据",
    "position_detail": "持仓明细（Top20）",
    "download_log": "下载日志",
    "download_progress": "下载进度",
    "download_failures": "下载失败记录",
    "file_checksums": "文件校验和",
    "data_quality_checks": "数据质量检查",
    "exchange_config": "交易所配置",
    "product_config": "品种配置",
    "contract_info": "合约信息（维护系统）",
    "trade_calendar": "交易日历",
    "special_date_override": "特殊日期覆盖",
    "product_listing_dates": "品种上市日期",
    "data_catalog": "数据目录",
    "data_status_local": "本地数据状态",
    "data_status_remote": "远程数据状态",
    "sync_task": "同步任务记录",
    "data_health_snapshot": "数据健康快照",
    "data_diff_log": "数据差异对比",
    "main_contract_map": "主力合约映射",
    "trading_hours_template": "交易时间模板",
    "product_trading_hours": "品种交易时间",
    "system_config": "系统配置",
    "sync_audit_log": "同步审计日志",
    # trading DB
    "bills": "账单记录",
    "bill_raw_sections": "账单原始段落",
    "trades": "交易记录",
    "matched_trades": "匹配后的开平仓交易",
    "trade_performance": "交易绩效分析",
    "positions_summary": "持仓汇总",
    "account_summary": "账户概览",
    "account_cashflow": "账户现金流",
    "trade_comparison_analysis": "交易对比分析",
    "cffex_daily_settlement": "中金所日结算",
    "strategies": "策略配置",
    "strategy_performance_summary": "策略绩效汇总",
    "strategy_summary": "策略日报",
    "backtest_results": "回测结果",
    "option_sim_strategies": "期权模拟策略",
    "option_sim_trades": "期权模拟交易",
    "option_sim_iv_series": "期权模拟 IV 序列",
    "paper_accounts": "模拟账户",
    "paper_position": "模拟持仓",
    "paper_trade": "模拟交易",
    "paper_order": "模拟订单",
    "reports": "报告",
    "report_templates": "报告模板",
    "risk_config": "风控配置",
    "risk_history": "风控历史",
    "futures_accounts": "期货账户配置",
    "statement_status": "账单状态",
    "bill_fund_flows": "账单资金流水",
    "option_greeks_daily": "期权希腊字母（日频）",
    "daily_index_prices": "指数日线数据",
    "contract_expiry": "合约到期信息",
    "mo_contract_master": "MO 合约主表",
    # analysis DB
    "institution_master": "机构会员主表",
    "institution_name_mapping": "机构名称映射",
    "institution_profiles": "机构画像",
    "institution_daily_features": "机构日频特征",
    "feature_daily": "市场日频特征汇总",
    "cffex_holdings_continuous": "中金所持仓连续序列",
    "option_features": "期权特征（Greeks）",
    "trading_signals": "交易信号",
    "signal_triggers": "信号触发记录",
    "market_regime": "市场状态分类",
    "institution_lead_lag": "机构领先滞后分析",
    "model_validation_records": "模型验证记录",
    "tushare_daily": "Tushare 日线",
    "tushare_minute": "Tushare 分钟线",
    "tushare_option": "Tushare 期权",
    "task_execution_log": "任务执行日志",
    "analysis_cache": "分析缓存",
}

# Date column names to try for each table (for time range detection)
_DATE_COLUMNS: dict[str, list[str]] = {
    "daily_quotes": ["trade_date"],
    "minute_quotes": ["trade_date"],
    "settlement_prices": ["trade_date"],
    "position_detail": ["trade_date"],
    "trade_calendar": ["trade_date"],
    "data_health_snapshot": ["snapshot_date"],
    "data_diff_log": ["trade_date"],
    "main_contract_map": ["trade_date"],
    "bills": ["bill_date_start", "bill_date_end"],
    "bill_fund_flows": ["trade_date"],
    "trades": ["trade_date"],
    "matched_trades": ["open_date", "close_date"],
    "trade_performance": ["open_date", "close_date"],
    "positions_summary": ["trade_date"],
    "account_summary": ["start_date", "end_date"],
    "trade_comparison_analysis": ["analysis_date", "open_date"],
    "cffex_daily_settlement": ["trade_date"],
    "strategy_summary": ["date"],
    "backtest_results": ["start_date", "end_date"],
    "option_sim_trades": ["entry_date", "exit_date"],
    "option_sim_iv_series": ["trade_date"],
    "paper_trade": ["trade_date"],
    "option_greeks_daily": ["trade_date"],
    "daily_index_prices": ["trade_date"],
    "statement_status": ["statement_date"],
    "institution_daily_features": ["trade_date"],
    "feature_daily": ["trade_date"],
    "cffex_holdings_continuous": ["trade_date"],
    "option_features": ["trade_date"],
    "trading_signals": ["signal_date"],
    "signal_triggers": ["trigger_date"],
    "market_regime": ["trade_date"],
    "institution_lead_lag": ["trade_date"],
    "model_validation_records": ["validation_date"],
    "tushare_daily": ["trade_date"],
    "tushare_minute": ["trade_date"],
    "tushare_option": ["trade_date"],
    "sync_audit_log": ["trade_date", "start_time"],
    "task_execution_log": ["start_time"],
}


def _normalize_date(raw: str) -> str | None:
    """Normalize a date string to YYYY-MM-DD. Returns None for non-date values."""
    if not raw:
        return None
    s = str(raw).strip()
    # YYYYMMDD -> YYYY-MM-DD
    if len(s) == 8 and s.isdigit() and s.startswith(("19", "20")):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    # YYYY-MM-DD (already correct)
    if len(s) >= 10 and s[0:4].isdigit() and s[4] == "-" and s[5:7].isdigit() and s[7] == "-" and s[8:10].isdigit():
        return s[:10]
    # Not a valid date (e.g. 'MOOSE', 'IF', 'IH')
    return None


def _get_table_stats(conn, table_name: str) -> dict:
    """Get row count and date range for a table."""
    result: dict = {"name": table_name, "rows": 0, "cols": 0, "earliest_date": None, "latest_date": None}

    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        result["rows"] = row[0] if row else 0

        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        result["cols"] = len(cols)

        date_cols = _DATE_COLUMNS.get(table_name, [])
        if not date_cols:
            col_names = [c[1] for c in cols]
            for candidate in ["trade_date", "date", "created_at", "snapshot_date", "start_date", "end_time"]:
                if candidate in col_names:
                    date_cols = [candidate]
                    break

        for dc in date_cols:
            if dc in [c[1] for c in cols]:
                # Filter out non-date values (e.g. 'MOOSE', 'IF', 'IH') by requiring 4-digit year prefix
                dr = conn.execute(
                    f"SELECT MIN({dc}), MAX({dc}) FROM {table_name} WHERE {dc} LIKE '19%' OR {dc} LIKE '20%'"
                ).fetchone()
                if dr and dr[0]:
                    min_d = _normalize_date(dr[0])
                    max_d = _normalize_date(dr[1])
                    if min_d:
                        result["earliest_date"] = min_d
                    if max_d:
                        result["latest_date"] = max_d
                    break
    except Exception:
        pass

    return result


def _get_db_tables(db_path: str) -> list[dict]:
    """Get all tables with stats from a SQLite database."""
    import sqlite3

    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

        results = []
        for (table_name,) in tables:
            stats = _get_table_stats(conn, table_name)
            stats["description"] = _TABLE_DESCRIPTIONS.get(table_name, "")
            stats["source"] = _infer_source(table_name)
            results.append(stats)
        return results
    finally:
        conn.close()


def _infer_source(table_name: str) -> str:
    """Infer data source from table name."""
    if table_name.startswith("tushare"):
        return "tushare"
    if "cffex" in table_name:
        return "cffex"
    if "shfe" in table_name:
        return "shfe"
    if "bill" in table_name or "statement" in table_name:
        return "cfmmc"
    if "akshare" in table_name:
        return "akshare"
    return "exchange"


@router.get("/dashboard", summary="数据大盘")
def get_dashboard():
    """获取本地数据大盘：库表结构、数据量、业务指标、消费情况。"""
    from tzdata_pkg.cache.cache_service import analysis_cache

    cache_key = "dashboard:get_dashboard"
    cached = analysis_cache.get(cache_key)
    if cached is not None:
        return cached

    from pathlib import Path
    from tzdata_pkg.config import DATA_DIR, TZDATA_MARKET_DB, TZDATA_TRADING_DB, TZDATA_ANALYSIS_DB
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
    from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator
    from tzdata_pkg.storage.db_registry import DBRegistry

    result: dict = {"databases": [], "catalogs": [], "tasks": [], "consumption": [], "summary": {}}

    # 1. Database table stats
    db_configs = [
        {"name": "tzdata_market.db", "path": str(TZDATA_MARKET_DB)},
        {"name": "tzdata_trading.db", "path": str(TZDATA_TRADING_DB)},
        {"name": "tzdata_analysis.db", "path": str(TZDATA_ANALYSIS_DB)},
    ]

    total_tables = 0
    total_records = 0

    for db_cfg in db_configs:
        db_path = db_cfg["path"]
        tables = _get_db_tables(db_path)
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        db_records = sum(t["rows"] for t in tables)

        result["databases"].append({
            "name": db_cfg["name"],
            "path": db_path,
            "size_mb": round(db_size, 2),
            "tables": tables,
        })
        total_tables += len(tables)
        total_records += db_records

    # 2. Catalogs with status
    try:
        catalogs = CatalogManager.get_enabled_catalogs()
        for cat in catalogs:
            cat_info = {
                "id": cat.get("id"),
                "name": cat.get("catalog_name", ""),
                "exchange": cat.get("exchange_code", ""),
                "product": cat.get("product_code", ""),
                "data_type": cat.get("data_type", ""),
                "source": cat.get("data_source", ""),
                "enabled": bool(cat.get("is_enabled", 1)),
                "last_sync_at": _normalize_date(cat.get("last_sync_at", "")) or "",
            }
            snapshot = HealthSnapshotGenerator.get_latest_snapshot(cat["id"])
            if snapshot:
                cat_info["quality_score"] = snapshot.get("data_quality_score", 0)
                cat_info["completeness_pct"] = snapshot.get("completeness_pct", 0)
                cat_info["sync_status"] = snapshot.get("last_sync_status", "unknown")
                cat_info["missing_days"] = snapshot.get("missing_days", 0)

            # Enrich with data_status_local info
            try:
                pool = DBRegistry().get_pool("market")
                with pool.connection() as conn:
                    row = conn.execute(
                        "SELECT earliest_date, latest_date, total_records FROM data_status_local WHERE catalog_id = ?",
                        (cat["id"],),
                    ).fetchone()
                    if row:
                        cat_info["earliest_date"] = _normalize_date(row[0]) or ""
                        cat_info["latest_date"] = _normalize_date(row[1]) or ""
                        cat_info["total_records"] = row[2] or 0
                        has_data = row[2] and row[2] > 0
                        # Override unknown/missing sync status when actual data exists
                        if cat_info.get("sync_status") in ("unknown", "never_synced") and has_data:
                            cat_info["sync_status"] = "completed"
                        # Initialize missing metrics with sensible defaults when no snapshot
                        if "quality_score" not in cat_info:
                            cat_info["quality_score"] = 50.0 if has_data else 0.0
                        if "completeness_pct" not in cat_info:
                            cat_info["completeness_pct"] = 0.0
                        if "missing_days" not in cat_info:
                            cat_info["missing_days"] = 0
                        if "sync_status" not in cat_info:
                            cat_info["sync_status"] = "completed" if has_data else "unknown"
            except Exception:
                pass

            # Ensure all fields have defaults
            cat_info.setdefault("quality_score", 0.0)
            cat_info.setdefault("completeness_pct", 0.0)
            cat_info.setdefault("missing_days", 0)
            cat_info.setdefault("sync_status", "unknown")
            cat_info.setdefault("earliest_date", "")
            cat_info.setdefault("latest_date", "")
            cat_info.setdefault("total_records", 0)

            result["catalogs"].append(cat_info)
    except Exception as e:
        logger.warning(f"Dashboard catalog enrichment failed: {e}")

    # 3. Scheduled tasks from Celery Beat
    try:
        from tzdata_pkg.scheduler.celery_app import celery_app

        beat_schedule = celery_app.conf.get("beat_schedule", {})
        task_names = {
            "mo-minute-sync": "MO 分钟数据同步",
            "mo-iv-sync": "MO IV 数据同步",
            "mo-underlying-sync": "标的日线同步",
            "mo-position-sync": "MO 持仓同步",
            "ho-position-sync": "HO 持仓同步",
            "io-position-sync": "IO 持仓同步",
            "mo-market-env": "MO 市场环境分析",
            "mo-quality-check": "MO 数据质量检查",
            "mo-contract-sync": "MO 合约同步",
            "daily-incremental-sync": "全量目录增量同步",
            "daily-status-refresh": "数据状态刷新",
            "daily-completeness-check": "数据完整性检查",
            "daily-bill-missing-check": "账单缺失检测",
            "daily-trade-matching": "交易开平匹配",
            "daily-bill-calendar-check": "账单日历检查",
            "sync-index-daily": "指数日线同步",
            "compute-daily-vwap": "日频 VWAP 计算",
            "compute-option-greeks": "期权希腊字母预计算",
        }

        schedule_display = {
            "mo-minute-sync": "交易日 15:30",
            "mo-iv-sync": "交易日 16:00",
            "mo-underlying-sync": "交易日 16:30",
            "mo-position-sync": "交易日 17:00",
            "ho-position-sync": "交易日 17:05",
            "io-position-sync": "交易日 17:10",
            "mo-market-env": "交易日 17:30",
            "mo-quality-check": "每日 18:00",
            "mo-contract-sync": "周六 10:00",
            "daily-incremental-sync": "每日 18:00",
            "daily-status-refresh": "每日 18:30",
            "daily-completeness-check": "每日 19:00",
            "daily-bill-missing-check": "每日 20:00",
            "daily-trade-matching": "每日 20:30",
            "daily-bill-calendar-check": "交易日 21:00",
            "sync-index-daily": "交易日 18:30",
            "compute-daily-vwap": "交易日 18:35",
            "compute-option-greeks": "每日 20:00",
        }

        # Get recent task execution from sync_audit_log
        audit_data: dict = {}
        try:
            pool = DBRegistry().get_pool("market")
            with pool.connection() as conn:
                rows = conn.execute("""
                    SELECT task_name, success, records_fetched, end_time
                    FROM sync_audit_log
                    WHERE end_time IS NOT NULL
                    ORDER BY end_time DESC
                """).fetchall()
                for task_name, success, records, end_time in rows:
                    if task_name not in audit_data:
                        audit_data[task_name] = {
                            "last_run": str(end_time)[:19],
                            "last_status": "success" if success else "failed",
                            "last_records": records,
                        }
        except Exception:
            pass

        for task_key, task_cfg in beat_schedule.items():
            display_name = task_names.get(task_key, task_key)
            schedule_str = schedule_display.get(task_key, "")
            audit = audit_data.get(task_key, {})

            result["tasks"].append({
                "key": task_key,
                "name": display_name,
                "schedule": schedule_str,
                "last_run": audit.get("last_run", ""),
                "last_status": audit.get("last_status", ""),
                "last_records": audit.get("last_records", 0),
            })
    except Exception as e:
        logger.warning(f"Dashboard task enrichment failed: {e}")

    # 4. Data consumption mapping
    result["consumption"] = [
        {"data_type": "日线行情", "tables": "daily_quotes", "api_endpoint": "/api/v1/market/quotes", "consumers": "tz2.0 工作台、前端 K 线"},
        {"data_type": "分钟行情", "tables": "minute_quotes", "api_endpoint": "/api/v1/market/quotes", "consumers": "tz2.0 分钟 K 线、VWAP 计算"},
        {"data_type": "持仓排名", "tables": "position_detail", "api_endpoint": "/api/v1/positions/{product}", "consumers": "tz2.0 持仓分析、机构特征"},
        {"data_type": "账单数据", "tables": "bills, trades", "api_endpoint": "/api/v1/trades, /api/v1/bills", "consumers": "tz2.0 账单分析、交易绩效"},
        {"data_type": "交易信号", "tables": "trading_signals", "api_endpoint": "/api/v1/signals", "consumers": "tz2.0 信号监控"},
        {"data_type": "市场状态", "tables": "market_regime", "api_endpoint": "/api/v1/regime", "consumers": "tz2.0 策略过滤"},
        {"data_type": "机构特征", "tables": "institution_daily_features", "api_endpoint": "/api/v1/institution-features", "consumers": "tz2.0 因子分析"},
        {"data_type": "期权特征", "tables": "option_features", "api_endpoint": "/api/v1/option-features", "consumers": "tz2.0 期权策略"},
        {"data_type": "IV 快照", "tables": "option_sim_iv_series", "api_endpoint": "/api/v1/iv-snapshot", "consumers": "tz2.0 波动率分析"},
        {"data_type": "指数日线", "tables": "daily_index_prices", "api_endpoint": "/api/v1/market/index/{code}/daily", "consumers": "tz2.0 标的分析"},
        {"data_type": "希腊字母", "tables": "option_greeks_daily", "api_endpoint": "/api/v1/options/greeks/{date}", "consumers": "tz2.0 期权风控"},
    ]

    # 5. Summary
    catalogs_synced_today = 0
    quality_scores = []
    for cat in result["catalogs"]:
        if cat.get("last_sync_at", "").startswith(str(datetime.now().date())):
            catalogs_synced_today += 1
        if cat.get("quality_score"):
            quality_scores.append(cat["quality_score"])

    tasks_today = 0
    tasks_failed_today = 0
    today_prefix = str(datetime.now().date())
    for task in result["tasks"]:
        if task.get("last_run", "").startswith(today_prefix):
            tasks_today += 1
            if task.get("last_status") == "failed":
                tasks_failed_today += 1

    result["summary"] = {
        "total_tables": total_tables,
        "total_records": total_records,
        "total_catalogs": len(result["catalogs"]),
        "catalogs_synced_today": catalogs_synced_today,
        "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0,
        "tasks_today": tasks_today,
        "tasks_failed_today": tasks_failed_today,
    }

    analysis_cache.set(cache_key, result, ttl=300, tags=["dashboard"])
    return result


@router.get("/sync-failures", summary="同步失败记录")
def get_sync_failures(hours: int = 24, limit: int = 50):
    """Query recent sync task failures from task_failure_log."""
    from tzdata_pkg.storage.db_registry import DBRegistry

    pool = DBRegistry().get_pool('market')
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, task_name, task_id, error_type, error_message,
                   failed_at, notified, retries
            FROM task_failure_log
            WHERE failed_at >= datetime('now', ?)
            ORDER BY failed_at DESC
            LIMIT ?
            """,
            (f'-{hours} hours', limit),
        ).fetchall()

    return {
        'success': True,
        'data': [
            {
                'id': r[0],
                'task_name': r[1],
                'task_id': r[2],
                'error_type': r[3],
                'error_message': r[4],
                'failed_at': r[5],
                'notified': bool(r[6]),
                'retries': r[7],
            }
            for r in rows
        ],
        'summary': {
            'total_failures': len(rows),
            'window_hours': hours,
        }
    }


@router.get("/sync-failures/stats", summary="同步失败统计")
def get_sync_failure_stats(hours: int = 24):
    """Sync failure statistics: count by task, error type."""
    from tzdata_pkg.storage.db_registry import DBRegistry

    pool = DBRegistry().get_pool('market')
    with pool.connection() as conn:
        by_task = conn.execute(
            """
            SELECT task_name, COUNT(*) as cnt, MAX(failed_at) as last_failure
            FROM task_failure_log
            WHERE failed_at >= datetime('now', ?)
            GROUP BY task_name
            ORDER BY cnt DESC
            """,
            (f'-{hours} hours',),
        ).fetchall()

        by_error = conn.execute(
            """
            SELECT error_type, COUNT(*) as cnt
            FROM task_failure_log
            WHERE failed_at >= datetime('now', ?)
            GROUP BY error_type
            ORDER BY cnt DESC
            """,
            (f'-{hours} hours',),
        ).fetchall()

    return {
        'success': True,
        'data': {
            'by_task': [{'task_name': r[0], 'count': r[1], 'last_failure': r[2]} for r in by_task],
            'by_error': [{'error_type': r[0], 'count': r[1]} for r in by_error],
            'total': sum(r[1] for r in by_task),
            'window_hours': hours,
        }
    }


@router.get("/beat-tasks")
def get_beat_task_log(days: int = 7):
    """P2-11: Get Celery Beat task execution history.

    Returns recent execution records for all Beat tasks, with status,
    duration, and error info. Flags tasks with delay > 30min as 'warn'.
    """
    from tzdata_pkg.storage.db_registry import DBRegistry

    pool = DBRegistry().get_pool('market')
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT task_name, scheduled_at, executed_at, status,
                   duration_ms, error
            FROM beat_task_log
            WHERE executed_at >= datetime('now', ?)
            ORDER BY executed_at DESC
            LIMIT 500
        """, (f'-{days} days',)).fetchall()

    from datetime import datetime, timedelta
    tasks = {}
    for r in rows:
        name = r[0]
        if name not in tasks:
            tasks[name] = []
        tasks[name].append({
            'scheduled_at': r[1],
            'executed_at': r[2],
            'status': r[3],
            'duration_ms': r[4],
            'error': r[5],
        })

    result = []
    for name, executions in tasks.items():
        last_exec = executions[0]
        # Check delay: if last execution was > 30min from now, mark warn
        delay_warn = False
        if last_exec['executed_at']:
            try:
                exec_time = datetime.strptime(last_exec['executed_at'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - exec_time > timedelta(minutes=30):
                    delay_warn = True
            except ValueError:
                pass

        result.append({
            'task_name': name,
            'last_status': last_exec['status'],
            'last_duration_ms': last_exec['duration_ms'],
            'last_error': last_exec.get('error'),
            'delay_warn': delay_warn,
            'recent_executions': executions[:5],
        })

    return {'success': True, 'data': {'tasks': result, 'window_days': days}}


# === Data Quality Audit ===

_last_audit_cache: dict = {}


@router.get("/quality/summary", summary="质量审计摘要")
def get_quality_summary():
    """Return the latest quality audit summary."""
    if _last_audit_cache:
        return {
            "success": True,
            "timestamp": _last_audit_cache.get("timestamp"),
            "overall_status": _last_audit_cache.get("overall_status"),
            "total_checks": _last_audit_cache.get("total_checks"),
            "passed": _last_audit_cache.get("passed"),
            "failed": _last_audit_cache.get("failed"),
            "warnings": _last_audit_cache.get("warnings"),
            "skipped": _last_audit_cache.get("skipped"),
            "cached": True,
        }

    from tzdata_pkg.verify.data_quality_auditor import DataQualityAuditor

    auditor = DataQualityAuditor()
    report = auditor.run_full_audit(scope="all")

    _last_audit_cache.update({
        "timestamp": report.timestamp,
        "overall_status": report.overall_status,
        "total_checks": report.total_checks,
        "passed": report.passed,
        "failed": report.failed,
        "warnings": report.warnings,
        "skipped": report.skipped,
    })

    return {
        "success": True,
        **_last_audit_cache,
        "cached": False,
    }


@router.get("/quality/detail", summary="质量审计详情")
def get_quality_detail():
    """Return full quality audit detail."""
    from tzdata_pkg.verify.data_quality_auditor import DataQualityAuditor

    auditor = DataQualityAuditor()
    report = auditor.run_full_audit(scope="all")

    return {
        "success": True,
        "timestamp": report.timestamp,
        "overall_status": report.overall_status,
        "total_checks": report.total_checks,
        "passed": report.passed,
        "failed": report.failed,
        "warnings": report.warnings,
        "skipped": report.skipped,
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "source": c.source,
                "expected": c.expected,
                "actual": c.actual,
                "deviation": c.deviation,
                "message": c.message,
            }
            for c in report.checks
        ],
    }


@router.post("/quality/trigger", summary="手动触发审计")
def trigger_quality_audit(scope: str = "all", background_tasks: BackgroundTasks = None):
    """Trigger a quality audit (can be async via background tasks)."""
    from tzdata_pkg.verify.data_quality_auditor import DataQualityAuditor

    auditor = DataQualityAuditor()
    report = auditor.run_full_audit(scope=scope)

    _last_audit_cache.clear()
    _last_audit_cache.update({
        "timestamp": report.timestamp,
        "overall_status": report.overall_status,
        "total_checks": report.total_checks,
        "passed": report.passed,
        "failed": report.failed,
        "warnings": report.warnings,
        "skipped": report.skipped,
    })

    return {
        "success": True,
        "scope": scope,
        "timestamp": report.timestamp,
        "overall_status": report.overall_status,
        "total_checks": report.total_checks,
        "passed": report.passed,
        "failed": report.failed,
        "warnings": report.warnings,
        "skipped": report.skipped,
    }

