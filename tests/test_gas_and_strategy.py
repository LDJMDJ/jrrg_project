"""Focused tests for gas accounting and signal generation."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from src.gas_calculator import GasCalculator
from src.strategy_manager import StrategyManager


def test_gas_cost_matches_eth_formula() -> None:
    """Gas cost should return Wei integer, which converts correctly to ETH."""
    calculator = GasCalculator()

    trade_count = 2
    avg_gas_price_gwei = 50.0
    avg_gas_used = 200000.0

    total_wei = calculator.calculate_total_gas_cost(
        trade_count=trade_count,
        avg_gas_price_gwei=avg_gas_price_gwei,
        avg_gas_used=avg_gas_used,
    )

    # 兼容返回 int 或 Decimal
    assert isinstance(total_wei, (int, Decimal))
    # 转换为 float 进行近似比较
    total_wei_float = float(total_wei) if isinstance(total_wei, Decimal) else total_wei
    assert total_wei_float / 1e18 == pytest.approx(0.02)

    # 验证公式（注意 avg_gas_used 可能是 float，需要转为 int）
    expected_wei = trade_count * int(avg_gas_used) * int(avg_gas_price_gwei) * 1_000_000_000
    assert total_wei_float == expected_wei


def test_auto_compound_signal_uses_profit_and_loss_thresholds() -> None:
    """Signal logic should stop both on large gains and on large losses."""
    strategy = StrategyManager(
        "auto_compound",
        {"max_sell_amount": 0.10, "min_sell_amount": -0.08},
    )
    df = pd.DataFrame({"price": [100.0, 115.0, 90.0]})

    signals = strategy.generate_signals(df)

    # 信号为整数列表
    assert signals.tolist() == [1, 0, 0]


def test_multi_arbitrage_signal_respects_spread_threshold() -> None:
    """Arbitrage should only trigger when the spread ratio exceeds the threshold."""
    strategy = StrategyManager("multi_arbitrage", {"spread_threshold": 0.05})
    df = pd.DataFrame(
        {
            "min_price": [100.0, 100.0, 100.0],
            "max_price": [102.0, 105.0, 110.0],
        }
    )

    signals = strategy.generate_signals(df)

    assert signals.tolist() == [0, 1, 1]

#基础功能测试
def test_gas_cost_zero_for_no_trades() -> None:
    """无交易时 Gas 总成本应为 0。"""
    calculator = GasCalculator()
    total_wei = calculator.calculate_total_gas_cost(0, 50.0, 200000)
    assert total_wei == 0


def test_auto_compound_signal_boundary_equal_to_threshold() -> None:
    """收益率正好等于阈值时，信号应为 0（止盈或止损）。"""
    strategy = StrategyManager(
        "auto_compound",
        {"max_sell_amount": 0.10, "min_sell_amount": -0.10},
    )
    df = pd.DataFrame({"price": [100.0, 110.0, 90.0]})   # +10% 和 -10%
    signals = strategy.generate_signals(df)
    # 均等于阈值，应触发止盈止损，信号为 0
    assert signals.tolist() == [1, 0, 0]


def test_multi_arbitrage_signal_boundary_equal_to_threshold() -> None:
    """价差率正好等于阈值时，信号应为 1（触发套利）。"""
    strategy = StrategyManager("multi_arbitrage", {"spread_threshold": 0.05})
    df = pd.DataFrame(
        {
            "min_price": [100.0, 100.0],
            "max_price": [105.0, 105.0],   # 价差率 5%
        }
    )
    signals = strategy.generate_signals(df)
    assert signals.tolist() == [1, 1]


def test_gas_calculator_handles_large_numbers() -> None:
    """Gas 计算应正确处理大数值（高 Gas 价格、多次交易）。"""
    calculator = GasCalculator()
    total_wei = calculator.calculate_total_gas_cost(
        trade_count=1000,
        avg_gas_price_gwei=1000.0,
        avg_gas_used=500000,
    )
    # 预期 Wei = 1000 * 500000 * 1000 * 1e9 = 5e20
    assert total_wei == 500_000_000_000_000_000_000  
    # 转换为 ETH 应为 500.0
    assert total_wei / 1e18 == 500.0


# ========== 新增极端场景测试 ==========

def test_auto_compound_signal_all_zeros_when_extreme_losses() -> None:
    """连续大幅亏损，信号应全为 0（清仓离场）。"""
    strategy = StrategyManager(
        "auto_compound",
        {"max_sell_amount": 0.05, "min_sell_amount": -0.05},
    )
    df = pd.DataFrame({"price": [100.0, 80.0, 64.0, 51.2]})   # 每次跌20%
    signals = strategy.generate_signals(df)
    # 第一日无信号变化（默认持仓），第二日开始每日跌幅超过5%，信号为0
    assert signals.tolist() == [1, 0, 0, 0]


def test_multi_arbitrage_signal_all_ones_when_extreme_spreads() -> None:
    """连续极端价差，信号应全为 1。"""
    strategy = StrategyManager("multi_arbitrage", {"spread_threshold": 0.01})
    df = pd.DataFrame(
        {
            "min_price": [100.0, 100.0, 100.0],
            "max_price": [200.0, 300.0, 400.0],   # 价差率 >> 阈值
        }
    )
    signals = strategy.generate_signals(df)
    assert signals.tolist() == [1, 1, 1]
