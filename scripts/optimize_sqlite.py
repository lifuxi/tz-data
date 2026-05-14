#!/usr/bin/env python3
"""
SQLite 数据库优化工具
启用 WAL 模式、调整缓存、优化性能
"""
import sqlite3
import logging
from pathlib import Path
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class SQLiteOptimizer:
    """SQLite 数据库优化器"""
    
    def __init__(self, db_path: str):
        """
        初始化优化器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    
    def optimize(self) -> dict:
        """
        执行所有优化操作
        
        Returns:
            优化结果
        """
        logger.info(f"优化数据库: {self.db_path.name}")
        logger.info("=" * 60)
        
        results = {}
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            
            # 1. 启用 WAL 模式
            results['wal_mode'] = self._enable_wal(conn)
            
            # 2. 调整缓存大小
            results['cache_size'] = self._set_cache_size(conn, cache_mb=64)
            
            # 3. 启用同步优化
            results['synchronous'] = self._set_synchronous(conn, level='NORMAL')
            
            # 4. 设置临时存储
            results['temp_store'] = self._set_temp_store(conn, store='MEMORY')
            
            # 5. 分析数据库
            results['analyze'] = self._analyze_database(conn)
            
            # 6. 清理碎片
            results['vacuum'] = self._vacuum_database(conn)
            
            conn.close()
            
            logger.info("=" * 60)
            logger.info("✓ 优化完成!")
            
            return results
            
        except Exception as e:
            logger.error(f"优化失败: {e}")
            raise
    
    def _enable_wal(self, conn: sqlite3.Connection) -> bool:
        """
        启用 WAL (Write-Ahead Logging) 模式
        
        WAL 模式优势:
        - 读写不阻塞
        - 更好的并发性能
        - 崩溃恢复更快
        """
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            
            if mode == 'wal':
                logger.info("✓ WAL 模式已启用")
                return True
            else:
                logger.warning(f"⚠ WAL 模式启用失败，当前模式: {mode}")
                return False
                
        except Exception as e:
            logger.error(f"WAL 模式启用失败: {e}")
            return False
    
    def _set_cache_size(self, conn: sqlite3.Connection, cache_mb: int = 64) -> int:
        """
        设置缓存大小
        
        Args:
            conn: 数据库连接
            cache_mb: 缓存大小（MB）
        
        Returns:
            实际设置的缓存页数
        """
        try:
            # SQLite 缓存以页为单位，默认页大小 4096 字节
            page_size = conn.execute("PRAGMA page_size;").fetchone()[0]
            cache_pages = (cache_mb * 1024 * 1024) // page_size
            
            # 负值表示 KB，正值表示页数
            conn.execute(f"PRAGMA cache_size=-{cache_mb * 1024};")
            
            actual_cache = conn.execute("PRAGMA cache_size;").fetchone()[0]
            logger.info(f"✓ 缓存大小设置为: {cache_mb} MB ({actual_cache} 页)")
            
            return actual_cache
            
        except Exception as e:
            logger.error(f"缓存设置失败: {e}")
            return 0
    
    def _set_synchronous(self, conn: sqlite3.Connection, level: str = 'NORMAL') -> str:
        """
        设置同步级别
        
        级别说明:
        - OFF: 最快，但可能丢失数据
        - NORMAL: 平衡性能和安全性（推荐）
        - FULL: 最安全，但最慢
        
        Args:
            conn: 数据库连接
            level: 同步级别
        
        Returns:
            实际设置的级别
        """
        try:
            conn.execute(f"PRAGMA synchronous={level};")
            actual_level = conn.execute("PRAGMA synchronous;").fetchone()[0]
            
            logger.info(f"✓ 同步级别设置为: {level} ({actual_level})")
            return level
            
        except Exception as e:
            logger.error(f"同步级别设置失败: {e}")
            return 'UNKNOWN'
    
    def _set_temp_store(self, conn: sqlite3.Connection, store: str = 'MEMORY') -> str:
        """
        设置临时存储位置
        
        Args:
            conn: 数据库连接
            store: 存储位置 (MEMORY 或 FILE)
        
        Returns:
            实际设置的位置
        """
        try:
            conn.execute(f"PRAGMA temp_store={store};")
            actual_store = conn.execute("PRAGMA temp_store;").fetchone()[0]
            
            logger.info(f"✓ 临时存储设置为: {store} ({actual_store})")
            return store
            
        except Exception as e:
            logger.error(f"临时存储设置失败: {e}")
            return 'UNKNOWN'
    
    def _analyze_database(self, conn: sqlite3.Connection) -> bool:
        """
        分析数据库以优化查询计划
        
        Returns:
            是否成功
        """
        try:
            conn.execute("ANALYZE;")
            logger.info("✓ 数据库分析完成")
            return True
            
        except Exception as e:
            logger.error(f"数据库分析失败: {e}")
            return False
    
    def _vacuum_database(self, conn: sqlite3.Connection) -> bool:
        """
        清理数据库碎片，回收空间
        
        Returns:
            是否成功
        """
        try:
            # 获取优化前的大小
            size_before = self.db_path.stat().st_size
            
            conn.execute("VACUUM;")
            
            # 获取优化后的大小
            size_after = self.db_path.stat().st_size
            saved_mb = (size_before - size_after) / (1024 * 1024)
            
            if saved_mb > 0:
                logger.info(f"✓ 数据库清理完成，节省空间: {saved_mb:.2f} MB")
            else:
                logger.info("✓ 数据库清理完成")
            
            return True
            
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")
            return False
    
    def get_status(self) -> dict:
        """
        获取数据库当前状态
        
        Returns:
            状态信息字典
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            
            status = {
                'journal_mode': conn.execute("PRAGMA journal_mode;").fetchone()[0],
                'cache_size': conn.execute("PRAGMA cache_size;").fetchone()[0],
                'synchronous': conn.execute("PRAGMA synchronous;").fetchone()[0],
                'temp_store': conn.execute("PRAGMA temp_store;").fetchone()[0],
                'page_size': conn.execute("PRAGMA page_size;").fetchone()[0],
                'file_size_mb': self.db_path.stat().st_size / (1024 * 1024),
            }
            
            conn.close()
            return status
            
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {}


def optimize_all_databases(data_dir: str = "data"):
    """
    优化所有数据库
    
    Args:
        data_dir: 数据目录路径
    """
    db_files = [
        "tzdata_market.db",
        "tzdata_trading.db",
        "tzdata_analysis.db"
    ]
    
    data_path = Path(data_dir)
    
    for db_name in db_files:
        db_path = data_path / db_name
        
        if db_path.exists():
            try:
                optimizer = SQLiteOptimizer(str(db_path))
                optimizer.optimize()
                print()  # 空行分隔
            except Exception as e:
                logger.error(f"优化 {db_name} 失败: {e}")
        else:
            logger.warning(f"数据库文件不存在: {db_name}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 优化指定数据库
        db_path = sys.argv[1]
        optimizer = SQLiteOptimizer(db_path)
        optimizer.optimize()
        
        # 显示状态
        print("\n当前状态:")
        status = optimizer.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
    else:
        # 优化所有数据库
        optimize_all_databases()
