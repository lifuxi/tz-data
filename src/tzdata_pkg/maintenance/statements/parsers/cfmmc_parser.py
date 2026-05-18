"""
CFMMC / 期货公司结算单解析器。
支持徽商期货（及同类期货公司）导出的标准结算单格式。

文件格式特征：
- UTF-8 / GBK 编码的纯文本（非 CSV）
- 资金摘要：Key-Value 行式布局
- 成交记录、平仓明细、持仓明细、持仓汇总：管道符 | 分隔的表格
"""
import re
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CFMMCParser:
    """Parser for futures settlement statements (CFMMC standard)."""

    # Known keys in the summary section, mapped to output key
    SUMMARY_KEYS = [
        (r'期初结存\s*Balance\s*B/F', 'balance_bf'),
        (r'出\s*入\s*金\s*Deposit/Withdrawal', 'deposit_withdrawal'),
        (r'平仓盈亏\s*Realized\s*P/L', 'realized_pnl'),
        (r'持仓盯市盈亏\s*MTM\s*P/L', 'mtm_pnl'),
        (r'期权执行盈亏\s*Exercise\s*P/L', 'exercise_pnl'),
        (r'手\s*续\s*费\s*Commission', 'commission'),
        (r'行权手续费\s*Exercise\s*Fee', 'exercise_fee'),
        (r'交割手续费\s*Delivery\s*Fee', 'delivery_fee'),
        (r'货币质入\s*New\s*FX\s*Pledge', 'fx_pledge_in'),
        (r'货币质出\s*FX\s*Redemption', 'fx_pledge_out'),
        (r'质押变化金额\s*Chg\s*in\s*Pledge\s*Amt', 'pledge_change'),
        (r'权利金收入\s*Premium\s*Received', 'premium_received'),
        (r'权利金支出\s*Premium\s*Paid', 'premium_paid'),
        (r'交割盈亏\s*Delivery\s*P/L', 'delivery_pnl'),
        (r'期末结存\s*Balance\s*C/F', 'balance_cf'),
        (r'客户权益\s*Client\s*Equity', 'client_equity'),
        (r'保证金占用\s*Margin\s*Occupied', 'margin_occupied'),
        (r'可用资金\s*Fund\s*Avail', 'fund_available'),
        (r'风\s*险\s*度\s*Risk\s*Degree', 'risk_degree'),
    ]

    def parse_file(self, file_path: str) -> list:
        """Instance wrapper for backward compatibility. Returns trades list."""
        result = self.parse(file_path)
        return result.get('trades', [])

    @staticmethod
    def parse(file_path: str) -> dict:
        """Parse a settlement statement file.

        Returns:
            {
                'summary': dict with balance_bf, balance_cf, client_equity, ...
                'trades': list of trade records,
                'positions': list of position records,
                'positions_closed': list of closed position detail records,
                'client_id': str,
                'client_name': str,
                'statement_date': str,
                'parse_date': str,
            }
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        encoding = CFMMCParser._detect_encoding(file_path)

        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()

        lines = content.splitlines()

        result = {
            'summary': {},
            'trades': [],
            'positions': [],
            'positions_closed': [],
            'client_id': '',
            'client_name': '',
            'statement_date': '',
            'parse_date': datetime.now().isoformat(),
        }

        # 1. Parse header info
        CFMMCParser._parse_header(lines, result)

        # 2. Parse summary section (key-value rows before first table)
        CFMMCParser._parse_summary(lines, result)

        # 3. Parse pipe-delimited tables
        CFMMCParser._parse_tables(lines, result)

        logger.info(
            f"Parsed settlement statement for {result['client_id']}: "
            f"{len(result['trades'])} trades, "
            f"{len(result['positions'])} positions, "
            f"{len(result['positions_closed'])} closed"
        )

        return result

    # ------------------------------------------------------------------ #
    #  Header
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_header(lines, result):
        """Extract client ID, client name, statement date from header."""
        for line in lines[:10]:
            # Client ID
            m = re.search(r'客户号\s*Client\s*ID[：:]\s*(\S+)', line)
            if m:
                result['client_id'] = m.group(1).strip()

            # Client name
            m = re.search(r'客户名称\s*Client\s*Name[：:]\s*([一-鿿\w\s]+?)(?:\s+日期|\s*日期|\s*$)', line)
            if m:
                result['client_name'] = m.group(1).strip()

            # Statement date
            m = re.search(r'制表时间\s*Creation\s*Date[：:]\s*(\d{8})', line)
            if m:
                raw = m.group(1)
                result['statement_date'] = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

            m = re.search(r'日期\s*Date[：:]\s*(\d{8})', line)
            if m:
                raw = m.group(1)
                result['statement_date'] = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

    # ------------------------------------------------------------------ #
    #  Summary (key-value lines)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_summary(lines, result):
        """Parse summary key-value lines (before first table section)."""
        summary = {}
        for line in lines:
            for pattern, key in CFMMCParser.SUMMARY_KEYS:
                m = re.search(pattern + r'[：:]\s*(-?[\d,]+\.?\d*)', line)
                if m:
                    raw_val = m.group(1).replace(',', '')
                    summary[key] = float(raw_val)
                    # No break — each line has two key-value pairs

        result['summary'] = summary

    # ------------------------------------------------------------------ #
    #  Pipe-delimited tables
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_tables(lines, result):
        """Detect and parse all pipe-delimited table sections."""
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Detect table start by header keywords
            if '成交日期' in line and '投资单元' in line:
                # Transaction Record table
                i = CFMMCParser._parse_trade_table(lines, i, result)
            elif '平仓日期' in line and '投资单元' in line:
                # Position Closed table
                i = CFMMCParser._parse_position_closed_table(lines, i, result)
            elif line.startswith('| 投资单元') and '交易所' in line and '开仓日期' in line:
                # Positions Detail table
                i = CFMMCParser._parse_position_detail_table(lines, i, result)
            elif line.startswith('| 投资单元') and '品种' in line and '合约' in line and '昨结算' in line:
                # Positions Summary table
                i = CFMMCParser._parse_position_summary_table(lines, i, result)
            else:
                i += 1

    @staticmethod
    def _split_pipe_row(line):
        """Split a pipe-delimited row into cells.

        Format: |cell1|cell2|cell3|
        """
        if not line.startswith('|'):
            return []
        # Remove leading/trailing | and split
        inner = line.strip().strip('|')
        return [cell.strip() for cell in inner.split('|')]

    @staticmethod
    def _parse_trade_table(lines, start, result):
        """Parse transaction record table (成交记录).

        Columns (line 30-31 of sample):
        成交日期 | 投资单元 | 交易所 | 交易编码 | 品种 | 合约 | 买/卖 | 投/保 | 成交价 | 手数 | 成交额 | 开平 | 手续费 | 平仓盈亏 | 权利金收支 | 成交序号 | 资金账号
        """
        i = start
        # Skip header rows until we find the separator line
        while i < len(lines) and '-' not in lines[i]:
            i += 1
        # Skip separator
        while i < len(lines) and '---' in lines[i]:
            i += 1

        while i < len(lines):
            cells = CFMMCParser._split_pipe_row(lines[i])
            if not cells or len(cells) < 10:
                # Check for end of table (separator line or summary row starting with 共)
                if cells and cells[0].startswith('共'):
                    break
                if not cells or (lines[i].strip().startswith('|') and '-' in lines[i]):
                    break
                if not lines[i].strip().startswith('|'):
                    break
                i += 1
                continue

            # Skip summary row
            if cells[0].startswith('共'):
                break

            try:
                record = {
                    'trade_date': cells[0],
                    'invest_unit': cells[1],
                    'exchange': cells[2],
                    'trading_code': cells[3],
                    'product': cells[4],
                    'contract': cells[5],
                    'direction': cells[6].strip(),
                    'speculation': cells[7],
                    'price': CFMMCParser._parse_float(cells[8]),
                    'volume': CFMMCParser._parse_int(cells[9]),
                    'turnover': CFMMCParser._parse_float(cells[10]),
                    'open_close': cells[11],
                    'commission': CFMMCParser._parse_float(cells[12]),
                    'realized_pnl': CFMMCParser._parse_float(cells[13]),
                    'premium': CFMMCParser._parse_float(cells[14]) if len(cells) > 14 else 0.0,
                    'trans_no': cells[15] if len(cells) > 15 else '',
                    'account_id': cells[16] if len(cells) > 16 else '',
                }
                result['trades'].append(record)
            except (ValueError, IndexError):
                pass
            i += 1

        return i

    @staticmethod
    def _parse_position_closed_table(lines, start, result):
        """Parse position closed detail table (平仓明细).

        Columns:
        平仓日期 | 投资单元 | 交易所 | 交易编码 | 品种 | 合约 | 开仓日期 | 投/保 | 买/卖 | 手数 | 开仓价 | 昨结算 | 成交价 | 平仓盈亏 | 权利金收支 | 资金账号
        """
        i = start
        while i < len(lines) and '-' not in lines[i]:
            i += 1
        while i < len(lines) and '---' in lines[i]:
            i += 1

        while i < len(lines):
            cells = CFMMCParser._split_pipe_row(lines[i])
            if not cells or len(cells) < 10:
                if cells and cells[0].startswith('共'):
                    break
                if not cells or (lines[i].strip().startswith('|') and '-' in lines[i]):
                    break
                if not lines[i].strip().startswith('|'):
                    break
                i += 1
                continue

            if cells[0].startswith('共'):
                break

            try:
                record = {
                    'close_date': cells[0],
                    'invest_unit': cells[1],
                    'exchange': cells[2],
                    'trading_code': cells[3],
                    'product': cells[4],
                    'contract': cells[5],
                    'open_date': cells[6],
                    'speculation': cells[7],
                    'direction': cells[8].strip(),
                    'volume': CFMMCParser._parse_int(cells[9]),
                    'open_price': CFMMCParser._parse_float(cells[10]),
                    'prev_settlement': CFMMCParser._parse_float(cells[11]),
                    'close_price': CFMMCParser._parse_float(cells[12]),
                    'realized_pnl': CFMMCParser._parse_float(cells[13]),
                    'premium': CFMMCParser._parse_float(cells[14]) if len(cells) > 14 else 0.0,
                    'account_id': cells[15] if len(cells) > 15 else '',
                }
                result['positions_closed'].append(record)
            except (ValueError, IndexError):
                pass
            i += 1

        return i

    @staticmethod
    def _parse_position_detail_table(lines, start, result):
        """Parse position detail table (持仓明细).

        Columns:
        投资单元 | 交易所 | 交易编码 | 品种 | 合约 | 开仓日期 | 投/保 | 买/卖 | 持仓量 | 开仓价 | 昨结算 | 结算价 | 浮动盈亏 | 盯市盈亏 | 保证金 | 期权市值 | 资金账号
        """
        i = start
        # Skip header until separator (the header itself may be multiple lines)
        # Find the line with "---" after header
        while i < len(lines) and '-' not in lines[i]:
            i += 1
        while i < len(lines) and '---' in lines[i]:
            i += 1

        while i < len(lines):
            cells = CFMMCParser._split_pipe_row(lines[i])
            if not cells or len(cells) < 10:
                if cells and cells[0].startswith('共'):
                    break
                if not cells or (lines[i].strip().startswith('|') and '-' in lines[i]):
                    break
                if not lines[i].strip().startswith('|'):
                    break
                i += 1
                continue

            if cells[0].startswith('共'):
                break

            try:
                record = {
                    'invest_unit': cells[0],
                    'exchange': cells[1],
                    'trading_code': cells[2],
                    'product': cells[3],
                    'contract': cells[4],
                    'open_date': cells[5],
                    'speculation': cells[6],
                    'direction': cells[7].strip(),
                    'position': CFMMCParser._parse_int(cells[8]),
                    'open_price': CFMMCParser._parse_float(cells[9]),
                    'prev_settlement': CFMMCParser._parse_float(cells[10]),
                    'settlement_price': CFMMCParser._parse_float(cells[11]),
                    'float_pnl': CFMMCParser._parse_float(cells[12]),
                    'mtm_pnl': CFMMCParser._parse_float(cells[13]),
                    'margin': CFMMCParser._parse_float(cells[14]),
                    'option_market_value': CFMMCParser._parse_float(cells[15]) if len(cells) > 15 else 0.0,
                    'account_id': cells[16] if len(cells) > 16 else '',
                }
                result['positions'].append(record)
            except (ValueError, IndexError):
                pass
            i += 1

        return i

    @staticmethod
    def _parse_position_summary_table(lines, start, result):
        """Parse position summary table (持仓汇总).

        This section is similar to positions but aggregated.
        We skip it for now as positions detail already captures all data.
        """
        i = start
        # Skip to end of this table
        while i < len(lines):
            cells = CFMMCParser._split_pipe_row(lines[i])
            if cells and cells[0].startswith('共'):
                i += 1
                break
            if not lines[i].strip().startswith('|'):
                break
            i += 1
        return i

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
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
            # Try utf-8 first, then gbk
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read()
                return 'utf-8'
            except UnicodeDecodeError:
                return 'gbk'

    @staticmethod
    def _parse_float(val):
        """Parse a float value from string."""
        if val is None:
            return 0.0
        val = val.strip().replace(',', '')
        if not val or val == '-':
            return 0.0
        return float(val)

    @staticmethod
    def _parse_int(val):
        """Parse an int value from string."""
        if val is None:
            return 0
        val = val.strip().replace(',', '')
        if not val or val == '-':
            return 0
        return int(float(val))
