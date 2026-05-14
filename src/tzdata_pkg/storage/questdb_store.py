"""
QuestDB storage module for time-series market data.
Handles insertion and querying of market data in QuestDB.
"""
import logging
from datetime import date, datetime
from typing import Optional
import pandas as pd

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class QuestDBStore:
    """Storage operations for QuestDB time-series database."""
    
    @staticmethod
    def insert_daily_quotes(
        exchange: str,
        contract_code: str,
        product_code: str,
        quotes: list[dict]
    ) -> int:
        """
        Insert daily quotes into QuestDB.
        
        Args:
            exchange: Exchange code (e.g., 'CFFEX')
            contract_code: Contract code (e.g., 'IM2506')
            product_code: Product code (e.g., 'IM')
            quotes: List of quote dictionaries
        
        Returns:
            Number of records inserted
        """
        conn = get_registry().get_questdb_connection()
        
        if not conn:
            logger.error("QuestDB connection not available")
            return 0
        
        try:
            inserted = 0
            
            with conn.cursor() as cur:
                for quote in quotes:
                    # Convert trade_date string to timestamp
                    trade_date_str = quote.get('trade_date', '')
                    if isinstance(trade_date_str, str):
                        # Format: YYYYMMDD or YYYY-MM-DD
                        if '-' in trade_date_str:
                            ts = f"{trade_date_str}T00:00:00.000000Z"
                        else:
                            year = trade_date_str[:4]
                            month = trade_date_str[4:6]
                            day = trade_date_str[6:8]
                            ts = f"{year}-{month}-{day}T00:00:00.000000Z"
                    else:
                        continue
                    
                    cur.execute("""
                        INSERT INTO future_minute (
                            ts, exchange, contract_code, product_code,
                            open, high, low, close,
                            volume, turnover, open_interest,
                            source
                        ) VALUES (
                            CAST(%s AS TIMESTAMP),
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s
                        )
                    """, (
                        ts,
                        exchange,
                        contract_code,
                        product_code,
                        quote.get('open'),
                        quote.get('high'),
                        quote.get('low'),
                        quote.get('close'),
                        quote.get('volume', 0),
                        quote.get('turnover', 0.0),
                        quote.get('open_interest', 0),
                        'tushare'
                    ))
                    
                    inserted += 1
            
            logger.info(f"Inserted {inserted} daily quotes into QuestDB")
            return inserted
            
        except Exception as e:
            logger.error(f"Failed to insert daily quotes: {e}")
            return 0
    
    @staticmethod
    def insert_minute_quotes(
        exchange: str,
        contract_code: str,
        product_code: str,
        quotes: list[dict],
        frequency: str = '1min'
    ) -> int:
        """
        Insert minute quotes into QuestDB.
        
        Args:
            exchange: Exchange code
            contract_code: Contract code
            product_code: Product code
            quotes: List of minute quote dictionaries
            frequency: Data frequency
        
        Returns:
            Number of records inserted
        """
        conn = get_registry().get_questdb_connection()
        
        if not conn:
            logger.error("QuestDB connection not available")
            return 0
        
        try:
            inserted = 0
            
            with conn.cursor() as cur:
                for quote in quotes:
                    # Build timestamp from date and time
                    trade_time = quote.get('trade_time', '')
                    if not trade_time:
                        continue
                    
                    # Format: HH:MM or HH:MM:SS
                    if len(trade_time) == 5:  # HH:MM
                        trade_time += ':00'
                    
                    # Assuming today's date (should be passed as parameter in production)
                    # For now, use a placeholder - this needs to be fixed
                    ts = f"2026-01-01T{trade_time}.000000Z"
                    
                    cur.execute("""
                        INSERT INTO future_minute (
                            ts, exchange, contract_code, product_code,
                            open, high, low, close,
                            volume, turnover, open_interest,
                            source
                        ) VALUES (
                            CAST(%s AS TIMESTAMP),
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s
                        )
                    """, (
                        ts,
                        exchange,
                        contract_code,
                        product_code,
                        quote.get('open'),
                        quote.get('high'),
                        quote.get('low'),
                        quote.get('close'),
                        quote.get('volume', 0),
                        quote.get('turnover', 0.0),
                        quote.get('open_interest', 0),
                        'tushare'
                    ))
                    
                    inserted += 1
            
            logger.info(f"Inserted {inserted} minute quotes into QuestDB")
            return inserted
            
        except Exception as e:
            logger.error(f"Failed to insert minute quotes: {e}")
            return 0
    
    @staticmethod
    def insert_top20_holdings(
        exchange: str,
        contract_code: str,
        product_code: str,
        holdings: list[dict]
    ) -> int:
        """
        Insert top 20 holdings into QuestDB.
        
        Args:
            exchange: Exchange code
            contract_code: Contract code
            product_code: Product code
            holdings: List of holding dictionaries
        
        Returns:
            Number of records inserted
        """
        conn = get_registry().get_questdb_connection()
        
        if not conn:
            logger.error("QuestDB connection not available")
            return 0
        
        try:
            inserted = 0
            
            with conn.cursor() as cur:
                for holding in holdings:
                    # Use current date as timestamp (should be passed as parameter)
                    ts = "2026-01-01T00:00:00.000000Z"
                    
                    cur.execute("""
                        INSERT INTO top20_holdings (
                            ts, exchange, contract_code, product_code,
                            member_name, rank,
                            long_volume, short_volume,
                            long_change, short_change
                        ) VALUES (
                            CAST(%s AS TIMESTAMP),
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s
                        )
                    """, (
                        ts,
                        exchange,
                        contract_code,
                        product_code,
                        holding.get('member_name', ''),
                        holding.get('rank', 0),
                        holding.get('long_volume', 0),
                        holding.get('short_volume', 0),
                        holding.get('long_change', 0),
                        holding.get('short_change', 0)
                    ))
                    
                    inserted += 1
            
            logger.info(f"Inserted {inserted} holdings records into QuestDB")
            return inserted
            
        except Exception as e:
            logger.error(f"Failed to insert holdings: {e}")
            return 0
    
    @staticmethod
    def update_data_status_local(
        catalog_id: int,
        latest_date: date,
        earliest_date: Optional[date] = None,
        total_records: int = 0
    ) -> bool:
        """
        Update local data status in SQLite metadata table.
        
        Args:
            catalog_id: ID of the data catalog
            latest_date: Latest trade date
            earliest_date: Earliest trade date (optional)
            total_records: Total number of records
        
        Returns:
            True if updated successfully
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                # Check if record exists
                cursor = conn.execute("""
                    SELECT latest_date, earliest_date, total_records
                    FROM data_status_local
                    WHERE catalog_id = ?
                """, (catalog_id,))
                
                row = cursor.fetchone()
                
                if row:
                    # Update existing record
                    new_earliest = earliest_date or row[1]
                    new_total = row[2] + total_records
                    conn.execute("""
                        UPDATE data_status_local
                        SET latest_date = ?,
                            earliest_date = ?,
                            total_records = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE catalog_id = ?
                    """, (
                        latest_date.isoformat() if isinstance(latest_date, date) else latest_date,
                        new_earliest.isoformat() if new_earliest and isinstance(new_earliest, date) else new_earliest,
                        new_total,
                        catalog_id
                    ))
                else:
                    # Insert new record
                    conn.execute("""
                        INSERT INTO data_status_local (
                            catalog_id, latest_date, earliest_date, total_records,
                            last_updated
                        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        catalog_id,
                        latest_date.isoformat() if isinstance(latest_date, date) else latest_date,
                        earliest_date.isoformat() if earliest_date and isinstance(earliest_date, date) else earliest_date,
                        total_records
                    ))
            
            logger.debug(f"Updated data status for catalog {catalog_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update data status: {e}")
            return False
