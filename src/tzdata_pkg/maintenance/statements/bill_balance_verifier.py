"""
Bill statement balance verifier.
Checks internal consistency of parsed bill statements using
double-entry bookkeeping principles (试算平衡).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BillBalanceVerifier:
    """
    Verifies that a bill statement is internally consistent.

    Balance equation:
        期末权益 = 期初权益 + 入金 - 出金 + 平仓盈亏 + 持仓盈亏 - 手续费 - 交割盈亏 +/- 其他
    """

    # Tolerance for floating-point comparison (元)
    TOLERANCE = 0.01

    @staticmethod
    def verify(
        balance_opening: float,
        balance_closing: float,
        deposits: float = 0.0,
        withdrawals: float = 0.0,
        realized_pnl: float = 0.0,
        floating_pnl: float = 0.0,
        commission: float = 0.0,
        delivery_pnl: float = 0.0,
        other_adjustments: float = 0.0
    ) -> dict:
        """
        Verify bill balance consistency.

        Args:
            balance_opening: 期初权益
            balance_closing: 期末权益 (should be the result)
            deposits: 入金总额
            withdrawals: 出金总额
            realized_pnl: 平仓盈亏
            floating_pnl: 持仓盈亏
            commission: 手续费总额
            delivery_pnl: 交割盈亏
            other_adjustments: 其他调整

        Returns:
            Dictionary with verification result:
                - balanced: bool
                - expected_closing: float
                - actual_closing: float
                - discrepancy: float
                - status: 'balanced' | 'suspicious' | 'unbalanced'
                - details: str
        """
        expected_closing = (
            balance_opening
            + deposits - withdrawals
            + realized_pnl + floating_pnl
            - commission
            + delivery_pnl
            + other_adjustments
        )

        discrepancy = abs(expected_closing - balance_closing)

        if discrepancy <= BillBalanceVerifier.TOLERANCE:
            return {
                'balanced': True,
                'expected_closing': round(expected_closing, 2),
                'actual_closing': round(balance_closing, 2),
                'discrepancy': round(discrepancy, 2),
                'status': 'balanced',
                'details': '账单平衡，数据可信'
            }
        elif discrepancy <= 100.0:
            return {
                'balanced': False,
                'expected_closing': round(expected_closing, 2),
                'actual_closing': round(balance_closing, 2),
                'discrepancy': round(discrepancy, 2),
                'status': 'suspicious',
                'details': f'差异 {discrepancy:.2f} 元，可能存在解析错误或遗漏数据'
            }
        else:
            return {
                'balanced': False,
                'expected_closing': round(expected_closing, 2),
                'actual_closing': round(balance_closing, 2),
                'discrepancy': round(discrepancy, 2),
                'status': 'unbalanced',
                'details': f'差异 {discrepancy:.2f} 元，账单数据严重不平，请检查'
            }

    @staticmethod
    def verify_from_parsed_bill(bill_data: dict) -> dict:
        """
        Verify balance from a parsed bill dictionary.

        Expected keys in bill_data:
            - balance_opening / 期初权益
            - balance_closing / 期末权益
            - deposits / 入金
            - withdrawals / 出金
            - realized_pnl / 平仓盈亏
            - floating_pnl / 持仓盈亏
            - commission / 手续费
        """
        def _get(keys: list[str], default: float = 0.0) -> float:
            """Try multiple key names (English/Chinese) for a value."""
            for key in keys:
                val = bill_data.get(key)
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
            return default

        return BillBalanceVerifier.verify(
            balance_opening=_get(['balance_opening', '期初权益', '期初客户权益']),
            balance_closing=_get(['balance_closing', '期末权益', '期末客户权益']),
            deposits=_get(['deposits', '入金', '本期入金']),
            withdrawals=_get(['withdrawals', '出金', '本期出金']),
            realized_pnl=_get(['realized_pnl', '平仓盈亏', '平盈']),
            floating_pnl=_get(['floating_pnl', '持仓盈亏', '浮动盈亏', '盯市盈亏']),
            commission=_get(['commission', '手续费', '成交手续费']),
            delivery_pnl=_get(['delivery_pnl', '交割盈亏', '交割盈亏']),
            other_adjustments=_get(['other_adjustments', '其他调整', '其他']),
        )
