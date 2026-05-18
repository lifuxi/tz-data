"""
CFMMC (China Futures Market Monitoring Center) statement parser.
Parses standard CFMMC CSV format statements.
"""
import csv
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CFMMCParser:
    """Parser for CFMMC standard format statements."""
    
    def parse_file(self, file_path: str) -> list:
        """Instance method wrapper for compatibility with maintenance routes.

        Returns a list of trade records (for backward compatibility).
        """
        result = self.parse(file_path)
        return result.get('trades', [])

    @staticmethod
    def parse(file_path: str) -> dict:
        """
        Parse a CFMMC statement file.
        
        Args:
            file_path: Path to the CSV file
        
        Returns:
            Dictionary with parsed data:
            - summary: Account summary information
            - trades: List of trade records
            - positions: List of position records
            - funds: List of fund flow records
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Detect encoding
            encoding = CFMMCParser._detect_encoding(file_path)
            
            # Parse different sections
            result = {
                'summary': {},
                'trades': [],
                'positions': [],
                'funds': [],
                'parse_date': datetime.now().isoformat()
            }
            
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                
                current_section = None
                
                for row in reader:
                    if not row or all(cell.strip() == '' for cell in row):
                        continue
                    
                    # Detect section headers
                    first_cell = row[0].strip() if row else ''
                    
                    if '成交记录' in first_cell or 'Trade' in first_cell:
                        current_section = 'trades'
                        continue
                    elif '持仓' in first_cell or 'Position' in first_cell:
                        current_section = 'positions'
                        continue
                    elif '资金' in first_cell or 'Fund' in first_cell:
                        current_section = 'funds'
                        continue
                    elif '汇总' in first_cell or 'Summary' in first_cell:
                        current_section = 'summary'
                        continue
                    
                    # Parse based on current section
                    if current_section == 'trades':
                        trade = CFMMCParser._parse_trade_row(row)
                        if trade:
                            result['trades'].append(trade)
                    elif current_section == 'positions':
                        position = CFMMCParser._parse_position_row(row)
                        if position:
                            result['positions'].append(position)
                    elif current_section == 'funds':
                        fund = CFMMCParser._parse_fund_row(row)
                        if fund:
                            result['funds'].append(fund)
                    elif current_section == 'summary':
                        result['summary'] = CFMMCParser._parse_summary_row(row)
            
            logger.info(
                f"Parsed CFMMC statement: "
                f"{len(result['trades'])} trades, "
                f"{len(result['positions'])} positions"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse CFMMC statement: {e}")
            raise
    
    @staticmethod
    def _detect_encoding(file_path: str) -> str:
        """Detect file encoding."""
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except ImportError:
            return 'utf-8'
    
    @staticmethod
    def _parse_trade_row(row: list) -> Optional[dict]:
        """Parse a trade record row."""
        # Simplified parsing - adjust based on actual CFMMC format
        if len(row) < 10:
            return None
        
        try:
            return {
                'trade_date': row[0].strip(),
                'contract': row[1].strip(),
                'direction': row[2].strip(),
                'volume': int(row[3]) if row[3].strip() else 0,
                'price': float(row[4]) if row[4].strip() else 0.0,
                'turnover': float(row[5]) if row[5].strip() else 0.0,
                'commission': float(row[6]) if row[6].strip() else 0.0,
            }
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def _parse_position_row(row: list) -> Optional[dict]:
        """Parse a position record row."""
        if len(row) < 8:
            return None
        
        try:
            return {
                'contract': row[0].strip(),
                'direction': row[1].strip(),
                'volume': int(row[2]) if row[2].strip() else 0,
                'avg_price': float(row[3]) if row[3].strip() else 0.0,
                'market_value': float(row[4]) if row[4].strip() else 0.0,
                'float_pnl': float(row[5]) if row[5].strip() else 0.0,
            }
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def _parse_fund_row(row: list) -> Optional[dict]:
        """Parse a fund flow record row."""
        if len(row) < 5:
            return None
        
        try:
            return {
                'date': row[0].strip(),
                'type': row[1].strip(),
                'amount': float(row[2]) if row[2].strip() else 0.0,
                'balance': float(row[3]) if row[3].strip() else 0.0,
                'note': row[4].strip() if len(row) > 4 else '',
            }
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def _parse_summary_row(row: list) -> dict:
        """Parse summary information."""
        # Simplified - extract key metrics
        return {
            'raw_data': row
        }
