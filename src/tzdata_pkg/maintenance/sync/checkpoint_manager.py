"""
Checkpoint manager for resumable data synchronization.
Saves and restores sync progress to support resuming after failures.
"""
import logging
from datetime import date
from typing import Optional
import json

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manage checkpoints for resumable sync operations."""
    
    @staticmethod
    def save_checkpoint(
        catalog_id: int,
        task_id: int,
        last_success_date: date,
        batch_index: int = 0,
        total_batches: int = 0,
        extra_data: Optional[dict] = None
    ) -> bool:
        """
        Save a checkpoint for a sync task.
        
        Args:
            catalog_id: ID of the data catalog
            task_id: ID of the sync task
            last_success_date: Last successfully synced date
            batch_index: Current batch index (0-based)
            total_batches: Total number of batches
            extra_data: Additional checkpoint data
        
        Returns:
            True if saved successfully, False otherwise
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            checkpoint_data = {
                'last_date': last_success_date.isoformat(),
                'batch_index': batch_index,
                'total_batches': total_batches
            }
            
            if extra_data:
                checkpoint_data.update(extra_data)
            
            with pool.transaction() as conn:
                conn.execute("""
                    UPDATE sync_task
                    SET checkpoint_data = ?
                    WHERE id = ?
                """, (json.dumps(checkpoint_data), task_id))
            
            logger.debug(
                f"Saved checkpoint for task {task_id}: "
                f"date={last_success_date}, batch={batch_index}/{total_batches}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    @staticmethod
    def load_checkpoint(task_id: int) -> Optional[dict]:
        """
        Load checkpoint data for a task.
        
        Args:
            task_id: ID of the sync task
        
        Returns:
            Dictionary with checkpoint data, or None if not found
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT checkpoint_data
                    FROM sync_task
                    WHERE id = ?
                """, (task_id,))
                
                row = cursor.fetchone()
                
                if row and row[0]:
                    checkpoint = json.loads(row[0])
                    
                    # Convert string dates back to date objects
                    if 'last_date' in checkpoint:
                        checkpoint['last_date'] = date.fromisoformat(
                            checkpoint['last_date']
                        )
                    
                    return checkpoint
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    @staticmethod
    def clear_checkpoint(task_id: int) -> bool:
        """
        Clear checkpoint data for a task.
        
        Args:
            task_id: ID of the sync task
        
        Returns:
            True if cleared successfully, False otherwise
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                conn.execute("""
                    UPDATE sync_task
                    SET checkpoint_data = NULL
                    WHERE id = ?
                """, (task_id,))
            
            logger.debug(f"Cleared checkpoint for task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear checkpoint: {e}")
            return False
    
    @staticmethod
    def should_resume_from_checkpoint(task_id: int) -> bool:
        """
        Check if a task should resume from a checkpoint.
        
        Args:
            task_id: ID of the sync task
        
        Returns:
            True if checkpoint exists and should be used
        """
        checkpoint = CheckpointManager.load_checkpoint(task_id)
        return checkpoint is not None and 'last_date' in checkpoint
