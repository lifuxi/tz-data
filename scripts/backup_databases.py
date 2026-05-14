#!/usr/bin/env python3
"""
tz-data 数据库备份工具
支持自动备份、压缩和清理旧备份
"""
import os
import sys
import shutil
import gzip
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/backup.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class DatabaseBackup:
    """SQLite 数据库备份管理器"""
    
    def __init__(self, project_root: str = None):
        """
        初始化备份管理器
        
        Args:
            project_root: 项目根目录，默认为当前目录
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.data_dir = self.project_root / "data"
        self.backup_dir = self.project_root / "backups"
        
        # 数据库文件列表
        self.db_files = [
            "tzdata_market.db",
            "tzdata_trading.db",
            "tzdata_analysis.db"
        ]
        
        # 备份保留天数
        self.retention_days = 7
        
        # 创建备份目录
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def backup_all(self, compress: bool = True) -> dict:
        """
        备份所有数据库
        
        Args:
            compress: 是否压缩备份文件
        
        Returns:
            备份结果字典
        """
        logger.info("=" * 60)
        logger.info("开始数据库备份")
        logger.info("=" * 60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {
            "timestamp": timestamp,
            "total": len(self.db_files),
            "success": 0,
            "failed": 0,
            "files": []
        }
        
        for db_name in self.db_files:
            db_path = self.data_dir / db_name
            
            if not db_path.exists():
                logger.warning(f"⚠️  数据库文件不存在: {db_name}")
                results["failed"] += 1
                continue
            
            try:
                if compress:
                    backup_file = self._compress_backup(db_path, timestamp)
                else:
                    backup_file = self._copy_backup(db_path, timestamp)
                
                results["success"] += 1
                results["files"].append({
                    "name": db_name,
                    "backup_file": str(backup_file),
                    "size_mb": backup_file.stat().st_size / (1024 * 1024)
                })
                
                logger.info(f"✓ 成功备份: {db_name} -> {backup_file.name}")
                
            except Exception as e:
                results["failed"] += 1
                logger.error(f"✗ 备份失败: {db_name} - {e}")
        
        # 清理旧备份
        self.cleanup_old_backups()
        
        # 打印总结
        logger.info("=" * 60)
        logger.info(f"备份完成! 成功: {results['success']}, 失败: {results['failed']}")
        logger.info("=" * 60)
        
        return results
    
    def _copy_backup(self, db_path: Path, timestamp: str) -> Path:
        """
        复制备份（不压缩）
        
        Args:
            db_path: 数据库文件路径
            timestamp: 时间戳
        
        Returns:
            备份文件路径
        """
        backup_name = f"{db_path.stem}.bak.{timestamp}{db_path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(db_path, backup_path)
        return backup_path
    
    def _compress_backup(self, db_path: Path, timestamp: str) -> Path:
        """
        压缩备份（gzip）
        
        Args:
            db_path: 数据库文件路径
            timestamp: 时间戳
        
        Returns:
            备份文件路径
        """
        backup_name = f"{db_path.stem}.bak.{timestamp}{db_path.suffix}.gz"
        backup_path = self.backup_dir / backup_name
        
        with open(db_path, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return backup_path
    
    def cleanup_old_backups(self) -> int:
        """
        清理超过保留天数的旧备份
        
        Returns:
            删除的文件数量
        """
        logger.info(f"清理 {self.retention_days} 天前的旧备份...")
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        
        for backup_file in self.backup_dir.glob("*.bak.*"):
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                try:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.debug(f"删除旧备份: {backup_file.name}")
                except Exception as e:
                    logger.error(f"删除失败: {backup_file.name} - {e}")
        
        if deleted_count > 0:
            logger.info(f"✓ 已删除 {deleted_count} 个旧备份文件")
        else:
            logger.info("没有需要清理的旧备份")
        
        return deleted_count
    
    def list_backups(self) -> List[dict]:
        """
        列出所有备份文件
        
        Returns:
            备份文件信息列表
        """
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob("*.bak.*")):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size_mb": stat.st_size / (1024 * 1024),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        
        return backups
    
    def restore(self, db_name: str, backup_file: str = None) -> bool:
        """
        恢复数据库
        
        Args:
            db_name: 数据库名称（如 tzdata_market.db）
            backup_file: 备份文件路径，如果为 None 则使用最新的备份
        
        Returns:
            是否成功
        """
        db_path = self.data_dir / db_name
        
        if not backup_file:
            # 查找最新的备份
            pattern = f"{Path(db_name).stem}.bak.*"
            backups = sorted(self.backup_dir.glob(pattern), 
                           key=lambda x: x.stat().st_mtime, 
                           reverse=True)
            
            if not backups:
                logger.error(f"未找到 {db_name} 的备份文件")
                return False
            
            backup_file = backups[0]
            logger.info(f"使用最新备份: {backup_file.name}")
        
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_file}")
            return False
        
        try:
            # 如果是压缩文件，先解压
            if backup_file.endswith('.gz'):
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                    with gzip.open(backup_path, 'rb') as f_in:
                        shutil.copyfileobj(f_in, tmp)
                    tmp_path = Path(tmp.name)
            else:
                tmp_path = backup_path
            
            # 备份当前数据库（以防万一）
            if db_path.exists():
                backup_current = db_path.with_suffix('.db.before_restore')
                shutil.copy2(db_path, backup_current)
                logger.info(f"已备份当前数据库: {backup_current.name}")
            
            # 恢复数据库
            shutil.copy2(tmp_path, db_path)
            
            # 清理临时文件
            if backup_file.endswith('.gz'):
                tmp_path.unlink()
            
            logger.info(f"✓ 成功恢复: {db_name}")
            return True
            
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="tz-data 数据库备份工具")
    parser.add_argument("--action", choices=["backup", "restore", "list", "cleanup"],
                       default="backup", help="操作类型")
    parser.add_argument("--db", help="数据库名称（用于恢复）")
    parser.add_argument("--file", help="备份文件路径（用于恢复）")
    parser.add_argument("--no-compress", action="store_true",
                       help="不压缩备份文件")
    parser.add_argument("--retention-days", type=int, default=7,
                       help="备份保留天数（默认 7 天）")
    
    args = parser.parse_args()
    
    backup_manager = DatabaseBackup()
    backup_manager.retention_days = args.retention_days
    
    if args.action == "backup":
        backup_manager.backup_all(compress=not args.no_compress)
    
    elif args.action == "restore":
        if not args.db:
            logger.error("恢复操作需要指定 --db 参数")
            sys.exit(1)
        
        success = backup_manager.restore(args.db, args.file)
        sys.exit(0 if success else 1)
    
    elif args.action == "list":
        backups = backup_manager.list_backups()
        
        if not backups:
            print("没有找到备份文件")
        else:
            print(f"\n{'文件名':<50} {'大小(MB)':<12} {'创建时间'}")
            print("-" * 90)
            for backup in backups:
                print(f"{backup['name']:<50} {backup['size_mb']:<12.2f} {backup['created']}")
            print(f"\n总计: {len(backups)} 个备份文件\n")
    
    elif args.action == "cleanup":
        deleted = backup_manager.cleanup_old_backups()
        print(f"已删除 {deleted} 个旧备份文件")


if __name__ == "__main__":
    main()
