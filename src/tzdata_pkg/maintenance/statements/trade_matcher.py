"""Trade matching service.

Pairs individual trades from the `trades` table into matched open/close records
using FIFO matching, stores results to `matched_trades` and `trade_performance`.
"""

import logging
import re
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

import sqlite3

from tzdata_pkg.config import TZDATA_TRADING_DB

logger = logging.getLogger(__name__)

# Contract multipliers.
CONTRACT_MULTIPLIERS = {
    # 化工
    'jm': 60, 'j': 100, 'i': 100,
    # 金属
    'ag': 15, 'au': 1000, 'cu': 5, 'al': 5, 'zn': 5, 'pb': 5, 'ni': 1, 'sn': 1, 'ss': 5,
    # 黑色
    'rb': 10, 'hc': 10,
    # 能化
    'p': 10, 'l': 5, 'v': 5, 'pp': 5, 'ma': 10, 'ta': 5, 'fu': 50, 'bu': 10, 'sp': 10, 'pg': 20,
    # 农产品
    'm': 10, 'y': 10, 'a': 10, 'b': 10, 'c': 10, 'cs': 10, 'jd': 10, 'ap': 10, 'cf': 5, 'sr': 10,
    'oi': 10, 'rm': 10,
    # 股指期货
    'if': 300, 'ic': 200, 'ih': 300, 'im': 200,
    # 股指期权
    'ho': 10000, 'io': 100, 'mo': 100,
    # 其他
    'lc': 1, 'si': 5, 'ao': 20,
}


@dataclass
class Position:
    trade_id: int
    instrument: str
    trade_date: str
    price: float
    volume: int
    remaining_volume: int
    direction: str  # 'long' or 'short'
    premium: float = 0.0
    commission: float = 0.0


@dataclass
class MatchedTrade:
    instrument: str
    exchange: str
    product: str
    is_option: int
    open_trade_id: int
    open_date: str
    open_price: float
    open_volume: int
    open_premium: float
    open_direction: str
    close_trade_id: int
    close_date: str
    close_price: float
    close_volume: int
    close_premium: float
    holding_days: int
    price_pnl: float
    premium_pnl: float
    multiplier: int
    money_pnl: float
    commission: float
    net_pnl: float
    status: str = 'closed'


class TradeMatcher:
    """FIFO trade matcher.

    Reads raw trades from tzdata_trading.db.trades, pairs open/close by instrument,
    writes to matched_trades and trade_performance.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(TZDATA_TRADING_DB)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.text_factory = lambda x: x.decode('utf-8')

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def ensure_tables(self):
        self.connect()
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS matched_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                exchange TEXT,
                product TEXT,
                is_option INTEGER DEFAULT 0,
                open_trade_id INTEGER,
                open_date TEXT NOT NULL,
                open_price REAL NOT NULL,
                open_volume INTEGER NOT NULL,
                open_premium REAL DEFAULT 0,
                open_direction TEXT,
                close_trade_id INTEGER,
                close_date TEXT,
                close_price REAL,
                close_volume INTEGER,
                close_premium REAL,
                holding_days INTEGER,
                price_pnl REAL,
                premium_pnl REAL DEFAULT 0,
                multiplier INTEGER DEFAULT 1,
                money_pnl REAL,
                commission REAL DEFAULT 0,
                net_pnl REAL,
                status TEXT DEFAULT 'closed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_matched_instrument ON matched_trades(instrument);
            CREATE INDEX IF NOT EXISTS idx_matched_open_date ON matched_trades(open_date);
            CREATE INDEX IF NOT EXISTS idx_matched_close_date ON matched_trades(close_date);
        """)

    @staticmethod
    def _get_product(instrument: str) -> str:
        match = re.match(r'^([a-zA-Z]+)', instrument)
        return match.group(1).lower() if match else ''

    @staticmethod
    def _is_option(instrument: str) -> bool:
        return bool(re.search(r'[CP][0-9]', instrument) or re.search(r'-[CP]-', instrument))

    @classmethod
    def _get_multiplier(cls, instrument: str) -> int:
        product = cls._get_product(instrument)
        return CONTRACT_MULTIPLIERS.get(product, 1)

    @staticmethod
    def _holding_days(open_date: str, close_date: str) -> int:
        try:
            o = datetime.strptime(open_date, '%Y%m%d')
            c = datetime.strptime(close_date, '%Y%m%d')
            return (c - o).days
        except Exception:
            return 0

    def get_all_trades(self) -> List[Dict]:
        self.connect()
        cursor = self.conn.execute("""
            SELECT id, trade_date, instrument, exchange, product,
                   direction, offset_flag, volume, price, commission, premium
            FROM trades
            ORDER BY trade_date, id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def match_trades(self) -> List[MatchedTrade]:
        trades = self.get_all_trades()
        logger.info(f"Loaded {len(trades)} trades")

        grouped = defaultdict(list)
        for t in trades:
            grouped[t['instrument']].append(t)

        results = []
        for instrument, inst_trades in grouped.items():
            is_opt = 1 if self._is_option(instrument) else 0
            multiplier = self._get_multiplier(instrument)

            # Two-pass: collect all opens and closes separately, then match.
            long_opens: List[Position] = []   # buy + open
            short_opens: List[Position] = []   # sell + open
            long_closes = []   # sell + close (closes long positions)
            short_closes = []  # buy + close (closes short positions)

            for t in inst_trades:
                direction = t['direction']
                offset = t['offset_flag']
                volume = t['volume'] or 0
                price = t['price'] or 0
                premium = t.get('premium') or 0
                commission = t.get('commission') or 0

                if direction == 'buy':
                    if offset == 'open':
                        long_opens.append(Position(
                            trade_id=t['id'], instrument=instrument,
                            trade_date=t['trade_date'], price=price,
                            volume=volume, remaining_volume=volume,
                            direction='long', premium=premium, commission=commission,
                        ))
                    else:
                        t['orig_volume'] = volume
                        short_closes.append(t)
                else:  # sell
                    if offset == 'open':
                        short_opens.append(Position(
                            trade_id=t['id'], instrument=instrument,
                            trade_date=t['trade_date'], price=price,
                            volume=volume, remaining_volume=volume,
                            direction='short', premium=premium, commission=commission,
                        ))
                    else:
                        t['orig_volume'] = volume
                        long_closes.append(t)

            # Match FIFO: long opens vs long closes, short opens vs short closes
            self._match_pairs(long_opens, long_closes, instrument, is_opt, multiplier, results)
            self._match_pairs(short_opens, short_closes, instrument, is_opt, multiplier, results)

        logger.info(f"Matched {len(results)} trades")
        return results

    def _match_pairs(self, opens, closes, instrument, is_opt, multiplier, results):
        """Match open positions against close trades in FIFO order."""
        ci = 0  # close index
        for pos in opens:
            if ci >= len(closes):
                break
            while ci < len(closes):
                close_t = closes[ci]
                remaining = close_t['volume'] or 0
                if remaining == 0:
                    ci += 1
                    continue
                if pos.remaining_volume <= 0:
                    break

                mv = min(pos.remaining_volume, remaining)
                self._create_match(pos, close_t, instrument, is_opt, multiplier, mv, results)
                pos.remaining_volume -= mv
                close_t['volume'] = remaining - mv

                if close_t['volume'] <= 0:
                    ci += 1

    def _create_match(self, pos, close_t, instrument, is_opt, multiplier, mv, results):
        """Create a single matched trade record."""
        close_premium = abs(close_t.get('premium') or 0)
        close_commission = close_t.get('commission') or 0

        hd = self._holding_days(pos.trade_date, close_t['trade_date'])

        if is_opt:
            open_prem_abs = abs(pos.premium)
            if pos.direction == 'long':
                prem_pnl = close_premium - open_prem_abs
            else:
                prem_pnl = open_prem_abs - close_premium
            price_pnl = 0
            money_pnl = prem_pnl * mv
        else:
            if pos.direction == 'long':
                price_pnl = close_t['price'] - pos.price
            else:
                price_pnl = pos.price - close_t['price']
            prem_pnl = 0
            money_pnl = price_pnl * mv * multiplier

        alloc_comm = (pos.commission / pos.volume * mv +
                      close_commission / (close_t.get('orig_volume') or close_t['volume']) * mv)
        net_pnl = money_pnl - alloc_comm

        open_prem_unit = abs(pos.premium) * mv / pos.volume
        close_prem_unit = close_premium * mv / (close_t.get('orig_volume') or close_t['volume'])

        results.append(MatchedTrade(
            instrument=instrument,
            exchange=close_t.get('exchange', ''),
            product=close_t.get('product', ''),
            is_option=is_opt,
            open_trade_id=pos.trade_id,
            open_date=pos.trade_date,
            open_price=pos.price,
            open_volume=mv,
            open_premium=open_prem_unit,
            open_direction=pos.direction,
            close_trade_id=close_t['id'],
            close_date=close_t['trade_date'],
            close_price=close_t['price'],
            close_volume=mv,
            close_premium=close_prem_unit,
            holding_days=hd,
            price_pnl=price_pnl,
            premium_pnl=prem_pnl * mv,
            multiplier=multiplier,
            money_pnl=money_pnl,
            commission=alloc_comm,
            net_pnl=net_pnl,
            status='closed',
        ))

    def save_results(self, results: List[MatchedTrade]) -> int:
        if not results:
            logger.warning("No matched trades to save")
            return 0

        self.connect()
        # Delete existing and re-insert
        self.conn.execute('DELETE FROM matched_trades')
        self.conn.execute('DELETE FROM trade_performance')

        for r in results:
            self.conn.execute("""
                INSERT INTO matched_trades (
                    instrument, exchange, product, is_option,
                    open_trade_id, open_date, open_price, open_volume, open_premium, open_direction,
                    close_trade_id, close_date, close_price, close_volume, close_premium,
                    holding_days, price_pnl, premium_pnl, multiplier, money_pnl, commission, net_pnl, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                r.instrument, r.exchange, r.product, r.is_option,
                r.open_trade_id, r.open_date, r.open_price, r.open_volume, r.open_premium, r.open_direction,
                r.close_trade_id, r.close_date, r.close_price, r.close_volume, r.close_premium,
                r.holding_days, r.price_pnl, r.premium_pnl, r.multiplier, r.money_pnl, r.commission, r.net_pnl,
                r.status,
            ))

        self.conn.commit()
        logger.info(f"Saved {len(results)} matched trades")
        return len(results)

    def populate_performance(self, results: List[MatchedTrade]) -> int:
        """Populate trade_performance from matched results."""
        if not results:
            return 0

        self.connect()
        count = 0
        for r in results:
            # Get the matched_trades id we just inserted
            mt_id = self.conn.execute(
                "SELECT id FROM matched_trades WHERE open_trade_id = ? AND close_trade_id = ? LIMIT 1",
                (r.open_trade_id, r.close_trade_id),
            ).fetchone()
            mt_id = mt_id[0] if mt_id else None

            underlying = expiry = option_type = None
            strike = delta = gamma = vega = theta = None
            strategy_type = strategy_id = None

            if r.is_option:
                m = re.match(r'^([A-Z]+)(\d{4,6})-([CP])-(\d+)', r.instrument)
                if m:
                    underlying = m.group(1)
                    yy = int(m.group(2)[:2])
                    mm = int(m.group(2)[2:])
                    option_type = 'call' if m.group(3) == 'C' else 'put'
                    strike = float(m.group(4))
                    from calendar import monthrange
                    year = 2000 + yy if yy < 50 else 1900 + yy
                    _, last = monthrange(year, mm)
                    expiry = f"{year}-{mm:02d}-{last:02d}"

            try:
                close_dt = datetime.strptime(r.close_date, '%Y%m%d')
                close_year = close_dt.year
                close_month = close_dt.month
                close_quarter = (close_month - 1) // 3 + 1
            except Exception:
                close_year = close_month = close_quarter = None

            pnl_ratio = None
            if r.open_price and r.open_price > 0:
                pnl_ratio = r.net_pnl / (r.open_price * r.open_volume * max(r.multiplier, 1))

            self.conn.execute("""
                INSERT INTO trade_performance (
                    matched_trade_id, instrument, is_option,
                    open_date, close_date, open_volume, open_direction,
                    money_pnl, premium_pnl, commission, net_pnl, pnl_ratio, holding_days,
                    underlying, expiry, option_type, strike,
                    delta, gamma, vega, theta,
                    strategy_type, strategy_id,
                    close_year, close_month, close_quarter
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                mt_id, r.instrument, r.is_option,
                r.open_date, r.close_date, r.open_volume, r.open_direction,
                r.money_pnl, r.premium_pnl, r.commission, r.net_pnl, pnl_ratio, r.holding_days,
                underlying, expiry, option_type, strike,
                delta, gamma, vega, theta,
                strategy_type, strategy_id,
                close_year, close_month, close_quarter,
            ))
            count += 1

        self.conn.commit()
        logger.info(f"Populated {count} trade_performance records")
        return count

    def run(self) -> Dict:
        """Execute full matching pipeline."""
        logger.info("Starting trade matching...")
        self.ensure_tables()

        results = self.match_trades()
        saved = self.save_results(results)
        perf = self.populate_performance(results)

        total_pnl = sum(r.net_pnl for r in results)
        by_instrument = defaultdict(int)
        for r in results:
            by_instrument[r.instrument] += 1

        logger.info(f"Trade matching complete: {saved} matched, {perf} performance records")
        return {
            'matched_count': saved,
            'performance_count': perf,
            'total_net_pnl': round(total_pnl, 2),
            'by_instrument': dict(by_instrument),
        }
