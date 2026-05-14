"""
Bill parser for China Futures Market Monitoring Center settlement statements.
Parses MTM (Mark-to-Market) settlement statement files.

Migrated from tz2.0/src/data/bill_parser/parser.py.
"""
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from tzdata_pkg.core.exceptions import DataParseError
from tzdata_pkg.parser.models import (
    BillSummary, DepositRecord, TransactionRecord, PositionRecord,
    ParseLog, BillParseResult
)

import logging
logger = logging.getLogger(__name__)


class BillParser:
    """Parser for futures settlement statement files."""

    def __init__(self):
        logger.info("BillParser initialized")

    def parse_file(self, file_path: Path) -> BillParseResult:
        """
        Parse a settlement statement file.

        Args:
            file_path: Path to the bill file

        Returns:
            BillParseResult with parsed data

        Raises:
            DataParseError: If file cannot be parsed
        """
        if not file_path.exists():
            raise DataParseError(
                message=f"File not found: {file_path}",
                file_path=str(file_path)
            )

        try:
            content = None
            encodings_to_try = ['utf-8', 'gbk', 'gb2312']

            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise DataParseError(
                    message="Unable to decode file with supported encodings (UTF-8, GBK, GB2312)",
                    file_path=str(file_path)
                )

            logger.info(f"Parsing bill file: {file_path}")

            result = BillParseResult()
            parse_log = ParseLog(
                file_path=str(file_path),
                success=False,
                timestamp=datetime.now().isoformat()
            )

            try:
                result.summary = self._parse_summary(content, str(file_path))
                parse_log.sections_parsed.append('summary')
            except Exception as e:
                logger.warning(f"Failed to parse summary: {e}")

            try:
                result.deposits = self._parse_deposits(content, str(file_path))
                parse_log.sections_parsed.append('deposits')
                parse_log.records_parsed += len(result.deposits)
            except Exception as e:
                logger.warning(f"Failed to parse deposits: {e}")

            try:
                result.transactions = self._parse_transactions(content, str(file_path))
                parse_log.sections_parsed.append('transactions')
                parse_log.records_parsed += len(result.transactions)
            except Exception as e:
                logger.warning(f"Failed to parse transactions: {e}")

            try:
                result.positions = self._parse_positions(content, str(file_path))
                parse_log.sections_parsed.append('positions')
                parse_log.records_parsed += len(result.positions)
            except Exception as e:
                logger.warning(f"Failed to parse positions: {e}")

            if result.summary is None:
                raise DataParseError(
                    message="Failed to parse bill summary - required section missing",
                    file_path=str(file_path)
                )

            parse_log.success = True
            result.parse_log = parse_log

            logger.info(
                f"Successfully parsed {file_path.name}: "
                f"{len(result.deposits)} deposits, "
                f"{len(result.transactions)} transactions, "
                f"{len(result.positions)} positions"
            )

            return result

        except DataParseError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse bill file {file_path}: {e}")
            raise DataParseError(
                message=f"Parse error: {str(e)}",
                file_path=str(file_path)
            )

    def _parse_summary(self, content: str, file_path: str) -> BillSummary:
        """Parse bill summary section."""
        client_match = re.search(
            r'客户号\s+Client\s+ID：\s*(\S+)\s+.*?客户名称\s+Client\s+Name：\s*(.+?)(?:\n|$)',
            content
        )
        if not client_match:
            raise DataParseError(
                message="Cannot find client ID and name",
                file_path=file_path
            )

        client_id = client_match.group(1).strip()
        client_name = client_match.group(2).strip()

        date_range_match = re.search(
            r'日期\s+Date：(\d{8})-(\d{8})',
            content
        )
        date_single_match = re.search(
            r'日期\s+Date：(\d{8})(?:\s|$)',
            content
        )

        if date_range_match:
            bill_date_start = datetime.strptime(date_range_match.group(1), '%Y%m%d').date()
            bill_date_end = datetime.strptime(date_range_match.group(2), '%Y%m%d').date()
        elif date_single_match:
            bill_date = datetime.strptime(date_single_match.group(1), '%Y%m%d').date()
            bill_date_start = bill_date
            bill_date_end = bill_date
        else:
            raise DataParseError(
                message="Cannot find bill date (expected format: YYYYMMDD or YYYYMMDD-YYYYMMDD)",
                file_path=file_path
            )

        account_match = re.search(
            r'资金账号：(\d+)\s+币种：(\S+)',
            content
        )
        account_id = account_match.group(1) if account_match else client_id
        currency = "CNY"

        def extract_float(pattern: str) -> float:
            match = re.search(pattern, content)
            if match:
                num_str = re.sub(r'[,\s]', '', match.group(1))
                try:
                    return float(num_str)
                except ValueError:
                    return 0.0
            return 0.0

        return BillSummary(
            client_id=client_id,
            client_name=client_name,
            account_id=account_id,
            currency=currency,
            bill_date_start=bill_date_start,
            bill_date_end=bill_date_end,
            balance_bf=extract_float(r'期初结存\s+Balance\s+B/F：\s*([-\d,.\s]+)'),
            balance_cf=extract_float(r'期末结存\s+Balance\s+C/F：\s*([-\d,.\s]+)'),
            deposit_withdrawal=extract_float(r'出\s+入\s+金\s+Deposit/Withdrawal：\s*([-\d,.\s]+)'),
            realized_pl=extract_float(r'平仓盈亏\s+Realized\s+P/L：\s*([-\d,.\s]+)'),
            mtm_pl=extract_float(r'持仓盯市盈亏\s+MTM\s+P/L：\s*([-\d,.\s]+)'),
            exercise_pl=extract_float(r'期权执行盈亏\s+Exercise\s+P/L：\s*([-\d,.\s]+)'),
            commission=extract_float(r'手\s+续\s+费\s+Commission：\s*([-\d,.\s]+)'),
            premium_received=extract_float(r'权利金收入\s+Premium\s+Received：\s*([-\d,.\s]+)'),
            premium_paid=extract_float(r'权利金支出\s+Premium\s+Paid：\s*([-\d,.\s]+)'),
            client_equity=extract_float(r'客户权益\s+Client\s+Equity：\s*([-\d,.\s]+)'),
            fund_available=extract_float(r'可用资金\s+Fund\s+Avail.：\s*([-\d,.\s]+)'),
            margin_occupied=extract_float(r'保证金占用\s+Margin\s+Occupied：\s*([-\d,.\s]+)'),
        )

    def _parse_deposits(self, content: str, file_path: str) -> List[DepositRecord]:
        """Parse deposit/withdrawal records."""
        deposits = []

        deposit_section = re.search(
            r'出入金明细\s+Deposit/Withdrawal\s*\n.*?\n(.*?)共\s+\d+条',
            content,
            re.DOTALL
        )

        if not deposit_section:
            logger.debug("No deposit/withdrawal section found in bill")
            return deposits

        section_text = deposit_section.group(1)
        lines = section_text.strip().split('\n')
        for line in lines:
            if not line.startswith('|') or '---' in line:
                continue

            fields = [f.strip() for f in line.split('|')]
            if len(fields) < 8:
                continue

            try:
                data_fields = fields[1:]
                date_str = data_fields[0].strip()
                # Skip header rows: first field should be 8-digit date
                if not re.match(r'\d{8}', date_str):
                    continue

                deposit_date = datetime.strptime(date_str, '%Y%m%d').date()

                def safe_float(val: str) -> float:
                    val_clean = re.sub(r'[,\s]', '', val)
                    try:
                        return float(val_clean)
                    except ValueError:
                        return 0.0

                exchange_rate_str = data_fields[4].strip() if len(data_fields) > 4 else ""
                exchange_rate = safe_float(exchange_rate_str) if exchange_rate_str else None

                deposits.append(DepositRecord(
                    date=deposit_date,
                    type=data_fields[1].strip(),
                    deposit=safe_float(data_fields[2]),
                    withdrawal=safe_float(data_fields[3]),
                    exchange_rate=exchange_rate,
                    account_id=data_fields[5].strip() if len(data_fields) > 5 else "",
                    note=data_fields[6].strip() if len(data_fields) > 6 else ""
                ))
            except (ValueError, IndexError):
                continue

        return deposits

    def _parse_transactions(self, content: str, file_path: str) -> List[TransactionRecord]:
        """Parse transaction records.

        Actual column order (18 columns, pipe-delimited):
        [0]=date  [1]=invest_unit  [2]=exchange  [3]=trading_code  [4]=product
        [5]=instrument  [6]=direction(买/卖)  [7]=hedge_type(投/保)  [8]=price
        [9]=lots  [10]=turnover  [11]=open_close(开平)  [12]=fee
        [13]=realized_pl  [14]=premium  [15]=trans_no  [16]=account_id
        """
        transactions = []

        txn_section = re.search(
            r'成交记录\s+Transaction\s+Record\s*\n.*?\n(.*?)共\s+\d+条',
            content,
            re.DOTALL
        )

        if not txn_section:
            return transactions

        section_text = txn_section.group(1)
        lines = section_text.strip().split('\n')
        for line in lines:
            if not line.startswith('|') or '---' in line:
                continue

            fields = [f.strip() for f in line.split('|')]
            if len(fields) < 17:
                continue

            try:
                data_fields = fields[1:]
                if len(data_fields) < 16:
                    continue

                # Skip header rows: first field should be 8-digit date
                txn_date_str = data_fields[0].strip()
                if not re.match(r'\d{8}', txn_date_str):
                    continue

                txn_date = datetime.strptime(txn_date_str, '%Y%m%d').date()
                instrument = data_fields[5].strip()
                instrument_type, option_type = self._classify_instrument(instrument)

                def safe_float(val: str, default: float = 0.0) -> float:
                    val_clean = re.sub(r'[,\s]', '', val)
                    try:
                        return float(val_clean)
                    except ValueError:
                        return default

                def safe_int(val: str, default: int = 0) -> int:
                    val_clean = re.sub(r'[,\s]', '', val)
                    try:
                        return int(val_clean)
                    except ValueError:
                        return default

                transactions.append(TransactionRecord(
                    date=txn_date,
                    invest_unit=data_fields[1],
                    exchange=data_fields[2],
                    trading_code=data_fields[3],
                    product=data_fields[4],
                    instrument=instrument,
                    direction=data_fields[6],
                    hedge_type=data_fields[7],
                    price=safe_float(data_fields[8]),
                    lots=safe_int(data_fields[9]),
                    turnover=safe_float(data_fields[10]),
                    open_close=data_fields[11],
                    fee=safe_float(data_fields[12]),
                    realized_pl=safe_float(data_fields[13]),
                    premium=safe_float(data_fields[14]),
                    trans_no=data_fields[15],
                    account_id=data_fields[16] if len(data_fields) > 16 else "",
                    instrument_type=instrument_type,
                    option_type=option_type
                ))
            except (ValueError, IndexError) as e:
                logger.debug(f"Skipping transaction line: {e}")
                continue

        return transactions

    def _parse_positions(self, content: str, file_path: str) -> List[PositionRecord]:
        """Parse position records.

        Actual column order (18 columns, pipe-delimited):
        [0]=invest_unit  [1]=exchange     [2]=trading_code  [3]=product
        [4]=instrument   [5]=open_date    [6]=hedge_type    [7]=direction
        [8]=positions    [9]=prev_settle  [10]=curr_settle  [11]=mtm_pl
        [12]=float_pl    [13]=margin      [14]=market_value [15]=account_id
        """
        positions = []

        pos_section = re.search(
            r'持仓明细\s+Positions\s+Detail\s*\n.*?\n(.*?)共\s+\d+条',
            content,
            re.DOTALL
        )

        if not pos_section:
            pos_section = re.search(
                r'持仓记录\s+Position\s+Record\s*\n.*?\n(.*?)共\s+\d+条',
                content,
                re.DOTALL
            )

        if not pos_section:
            logger.debug("No position section found in bill")
            return positions

        section_text = pos_section.group(1)
        lines = section_text.strip().split('\n')
        for line in lines:
            if not line.startswith('|') or '---' in line:
                continue

            fields = [f.strip() for f in line.split('|')]
            if len(fields) < 17:
                continue

            try:
                data_fields = fields[1:]
                # Skip header rows: first field should be numeric (account ID)
                # and NOT Chinese characters or English labels
                first = data_fields[0].strip()
                if not first or not first[0].isdigit():
                    continue

                # Skip summary row (starts with "共")
                if '共' in first:
                    continue

                invest_unit = first
                exchange = data_fields[1]
                trading_code = data_fields[2]
                product = data_fields[3]
                instrument = data_fields[4].strip()
                open_date_str = data_fields[5].strip() if len(data_fields) > 5 else ""
                hedge_type = data_fields[6]
                direction = data_fields[7]

                instrument_type, _ = self._classify_instrument(instrument)

                def safe_float(val: str) -> float:
                    val_clean = re.sub(r'[,\s]', '', val)
                    try:
                        return float(val_clean)
                    except ValueError:
                        return 0.0

                def safe_int(val: str) -> int:
                    val_clean = re.sub(r'[,\s]', '', val)
                    try:
                        return int(val_clean)
                    except ValueError:
                        return 0

                pos_date = None
                if open_date_str and re.match(r'\d{8}', open_date_str):
                    pos_date = datetime.strptime(open_date_str, '%Y%m%d').date()

                positions.append(PositionRecord(
                    date=pos_date,
                    invest_unit=invest_unit,
                    exchange=exchange,
                    trading_code=trading_code,
                    product=product,
                    instrument=instrument,
                    direction=direction,
                    hedge_type=hedge_type,
                    positions=safe_int(data_fields[8]) if len(data_fields) > 8 else 0,
                    prev_settle=safe_float(data_fields[9]) if len(data_fields) > 9 else 0.0,
                    curr_settle=safe_float(data_fields[10]) if len(data_fields) > 10 else 0.0,
                    mtm_pl=safe_float(data_fields[11]) if len(data_fields) > 11 else 0.0,
                    float_pl=safe_float(data_fields[12]) if len(data_fields) > 12 else 0.0,
                    margin=safe_float(data_fields[13]) if len(data_fields) > 13 else 0.0,
                    account_id=data_fields[15] if len(data_fields) > 15 else "",
                    instrument_type=instrument_type
                ))
            except (ValueError, IndexError):
                continue

        return positions

    def _classify_instrument(self, instrument: str) -> tuple:
        """
        Classify instrument as future or option, and determine option type.

        Args:
            instrument: Instrument code (e.g., MO2603-C-8500, AG2606)

        Returns:
            Tuple of (instrument_type, option_type)
            instrument_type: 'future' or 'option'
            option_type: 'C' (call), 'P' (put), or None
        """
        option_match = re.search(r'-([CP])-\d+', instrument)
        if option_match:
            return 'option', option_match.group(1)

        if re.match(r'^[A-Z]+\d+$', instrument):
            return 'future', None

        return 'future', None
