"""
Futures account manager.
Manages futures trading accounts and their credentials.
"""
import logging
from typing import Optional
import json
from datetime import date

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.statements.credential_vault import get_vault

logger = logging.getLogger(__name__)


class AccountManager:
    """Manage futures trading accounts."""
    
    @staticmethod
    def create_account(
        account_name: str,
        account_number: str,
        futures_company: str,
        cfmmc_username: Optional[str] = None,
        cfmmc_password: Optional[str] = None,
        exchanges_supported: Optional[list[str]] = None,
        tracking_start_date: Optional[date] = None
    ) -> int:
        """
        Create a new futures account.
        
        Args:
            account_name: Account name/nickname
            account_number: Account number
            futures_company: Futures company name
            cfmmc_username: CFMMC username (optional)
            cfmmc_password: CFMMC password (will be encrypted)
            exchanges_supported: List of supported exchanges
            tracking_start_date: Date to start tracking statements
        
        Returns:
            Account ID
        """
        registry = DBRegistry()
        conn = registry.get_pool('trading').get_connection()
        
        try:
            # Encrypt password if provided
            password_encrypted = None
            if cfmmc_password:
                vault = get_vault()
                password_encrypted = vault.encrypt(cfmmc_password)
            
            # Convert exchanges list to JSON string
            exchanges_json = json.dumps(exchanges_supported) if exchanges_supported else None
            
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO futures_accounts (
                    account_name, account_number, futures_company,
                    exchanges_supported, tracking_start_date,
                    cfmmc_username, cfmmc_password_encrypted,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                account_name,
                account_number,
                futures_company,
                exchanges_json,
                tracking_start_date.isoformat() if tracking_start_date else None,
                cfmmc_username,
                password_encrypted
            ))
            
            account_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Created account: {account_name} (ID: {account_id})")
            return account_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create account: {e}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def get_account(account_id: int) -> Optional[dict]:
        """
        Get account details by ID.
        
        Args:
            account_id: Account ID
        
        Returns:
            Account dictionary with decrypted password, or None
        """
        registry = DBRegistry()
        conn = registry.get_pool('trading').get_connection()
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, account_name, account_number, futures_company,
                       exchanges_supported, tracking_start_date,
                       cfmmc_username, cfmmc_password_encrypted,
                       is_active, last_statement_date, last_sync_at
                FROM futures_accounts
                WHERE id = ?
            """, (account_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Decrypt password
            password_decrypted = None
            if row[7]:  # cfmmc_password_encrypted
                try:
                    vault = get_vault()
                    password_decrypted = vault.decrypt(row[7])
                except Exception as e:
                    logger.error(f"Failed to decrypt password: {e}")
            
            return {
                'id': row[0],
                'account_name': row[1],
                'account_number': row[2],
                'futures_company': row[3],
                'exchanges_supported': json.loads(row[4]) if row[4] else [],
                'tracking_start_date': row[5],
                'cfmmc_username': row[6],
                'cfmmc_password': password_decrypted,
                'is_active': bool(row[8]),
                'last_statement_date': row[9],
                'last_sync_at': row[10]
            }
            
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def list_accounts(is_active: Optional[bool] = None) -> list[dict]:
        """
        List all accounts.
        
        Args:
            is_active: Filter by active status (None for all)
        
        Returns:
            List of account dictionaries (without passwords)
        """
        registry = DBRegistry()
        conn = registry.get_pool('trading').get_connection()
        
        try:
            query = """
                SELECT id, account_name, account_number, futures_company,
                       exchanges_supported, tracking_start_date,
                       cfmmc_username, is_active, last_statement_date
                FROM futures_accounts
            """
            params = []
            
            if is_active is not None:
                query += " WHERE is_active = ?"
                params.append(1 if is_active else 0)
            
            query += " ORDER BY id"
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'account_name': row[1],
                    'account_number': row[2],
                    'futures_company': row[3],
                    'exchanges_supported': json.loads(row[4]) if row[4] else [],
                    'tracking_start_date': row[5],
                    'cfmmc_username': row[6],
                    'is_active': bool(row[7]),
                    'last_statement_date': row[8]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to list accounts: {e}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    def update_credentials(
        account_id: int,
        cfmmc_username: Optional[str] = None,
        cfmmc_password: Optional[str] = None
    ) -> bool:
        """
        Update account credentials.
        
        Args:
            account_id: Account ID
            cfmmc_username: New username (optional)
            cfmmc_password: New password (will be encrypted, optional)
        
        Returns:
            True if updated successfully
        """
        registry = DBRegistry()
        conn = registry.get_pool('trading').get_connection()
        
        try:
            updates = []
            params = []
            
            if cfmmc_username is not None:
                updates.append("cfmmc_username = ?")
                params.append(cfmmc_username)
            
            if cfmmc_password is not None:
                vault = get_vault()
                password_encrypted = vault.encrypt(cfmmc_password)
                updates.append("cfmmc_password_encrypted = ?")
                params.append(password_encrypted)
            
            if not updates:
                return False
            
            params.append(account_id)
            query = f"UPDATE futures_accounts SET {', '.join(updates)} WHERE id = ?"
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            
            logger.info(f"Updated credentials for account {account_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update credentials: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def deactivate_account(account_id: int) -> bool:
        """
        Deactivate an account.
        
        Args:
            account_id: Account ID
        
        Returns:
            True if deactivated successfully
        """
        registry = DBRegistry()
        conn = registry.get_pool('trading').get_connection()
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE futures_accounts
                SET is_active = 0
                WHERE id = ?
            """, (account_id,))
            conn.commit()
            
            logger.info(f"Deactivated account {account_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to deactivate account: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def update_last_sync(account_id: int, statement_date: date) -> bool:
        """
        Update last statement date and sync timestamp.
        
        Args:
            account_id: Account ID
            statement_date: Date of the last statement
        
        Returns:
            True if updated successfully
        """
        registry = DBRegistry()
        conn = registry.get_pool('trading').get_connection()
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE futures_accounts
                SET last_statement_date = ?,
                    last_sync_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (statement_date.isoformat(), account_id))
            conn.commit()
            
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update last sync: {e}")
            return False
        finally:
            conn.close()
