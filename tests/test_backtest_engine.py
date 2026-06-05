"""Unit and integration-style tests for the simulation engine."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from simulator.backtest_engine import BacktestEngineCore
from src.models import BacktestConfig


def build_config(
    strategy_type: str,
    params: dict,
    selected_exchanges: list[str] | None = None,
) -> BacktestConfig:
    """Create a reusable backtest configuration for tests."""
    return BacktestConfig(
        start_time="2024-01-01",
        end_time="2024-01-03",
        initial_capital=Decimal("100.0"),           # 改为 Decimal
        strategy_id=1,
        strategy_name="test-strategy",
        strategy_type=strategy_type,
        params=params,
        selected_exchanges=selected_exchanges or ["Coinbase"],
    )


def test_auto_compound_preserves_growth_without_triggers() -> None:
    """Basic functionality: steady gains should increase equity when no trigger fires."""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exchange": ["Coinbase", "Coinbase", "Coinbase"],
            "price": [100.0, 110.0, 121.0],
            "gas_price": [0.0, 0.0, 0.0],
            "gas_used": [0, 0, 0],                  # 使用整数
        }
    )
    # 确保价格列为 Decimal（可选，引擎内部会转换）
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "auto_compound",
        {
            "compound_ratio": 1.0,
            "max_sell_amount": 0.5,
            "min_sell_amount": -0.5,
        },
    )

    result = engine.run_backtest(df, config)

    # Decimal 转为 float 后比较
    assert float(result.final_equity) == pytest.approx(121.0)
    assert float(result.cumulative_return) == pytest.approx(0.21)


def test_auto_compound_triggers_stop_loss_after_price_crash() -> None:
    """Extreme scenario: a sharp crash should eventually push the strategy out of position."""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exchange": ["Coinbase", "Coinbase", "Coinbase"],
            "price": [100.0, 50.0, 50.0],
            "gas_price": [0.0, 0.0, 0.0],
            "gas_used": [0, 0, 0],
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "auto_compound",
        {
            "compound_ratio": 1.0,
            "max_sell_amount": 0.5,
            "min_sell_amount": -0.1,
        },
    )

    result = engine.run_backtest(df, config)

    assert float(result.final_equity) == pytest.approx(50.0)
    assert "sell_or_stop" in result.trade_points["type"].tolist()

def test_auto_compound_triggers_take_profit_on_rise() -> None:
    """自动复投策略应在价格涨幅超过止盈阈值时清仓（信号为0）。"""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exchange": ["Coinbase", "Coinbase", "Coinbase"],
            "price": [100.0, 120.0, 120.0],   # 第二天涨20%，超过止盈阈值15%
            "gas_price": [0.0, 0.0, 0.0],
            "gas_used": [0, 0, 0],
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "auto_compound",
        {
            "compound_ratio": 1.0,
            "max_sell_amount": 0.15,   # 止盈阈值
            "min_sell_amount": -0.10,
        },
    )
    result = engine.run_backtest(df, config)

    # 第二天应触发止盈，第三天无持仓，最终权益 = 初始100 * (1+0.2) = 120
    assert float(result.final_equity) == pytest.approx(120.0)
    # 检查 trade_points 中包含止盈记录
    assert any(tp == "sell_or_stop" for tp in result.trade_points["type"])


def test_auto_compound_compound_ratio_reduces_exposure() -> None:
    """复投比例小于1时，应降低权益波动（涨跌幅度按比例缩放）。"""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exchange": ["Coinbase", "Coinbase", "Coinbase"],
            "price": [100.0, 110.0, 121.0],   # 日收益率10%, 10%
            "gas_price": [0.0, 0.0, 0.0],
            "gas_used": [0, 0, 0],
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)))

    config_full = build_config(
        "auto_compound",
        {"compound_ratio": 1.0, "max_sell_amount": 0.5, "min_sell_amount": -0.5},
    )
    config_half = build_config(
        "auto_compound",
        {"compound_ratio": 0.5, "max_sell_amount": 0.5, "min_sell_amount": -0.5},
    )

    result_full = engine.run_backtest(df, config_full)
    result_half = engine.run_backtest(df, config_half)

    # 满仓收益 = 100 * 1.1 * 1.1 = 121
    assert float(result_full.final_equity) == pytest.approx(121.0)
    # 半仓收益 = 100 * (1 + 0.5*0.1) * (1 + 0.5*0.1) = 100 * 1.05 * 1.05 = 110.25
    assert float(result_half.final_equity) == pytest.approx(110.25)


def test_auto_compound_gas_cost_reduces_net_profit() -> None:
    """Gas 费用应正确从权益中扣除，降低净收益。"""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exchange": ["Coinbase", "Coinbase", "Coinbase"],
            "price": [100.0, 110.0, 110.0],
            "gas_price": [50.0, 50.0, 50.0],
            "gas_used": [21000, 21000, 21000],
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "auto_compound",
        {
            "compound_ratio": 1.0,
            "max_sell_amount": 0.5,
            "min_sell_amount": -0.5,
        },
    )
    result = engine.run_backtest(df, config)

    # 第一天建仓交易消耗 Gas: 50 Gwei * 21000 * 1e9 Wei = 0.00105 ETH
    # 毛利润 = 10，净收益 = 10 - 0.00105 = 9.99895
    expected_net_profit = 10.0 - (50 * 21000 * 1e9) / 1e18
    assert float(result.net_profit) == pytest.approx(expected_net_profit, abs=1e-6)
    assert result.total_gas_cost == 50 * 21000 * 1_000_000_000

def test_auto_compound_extreme_gas_cost_erodes_all_profit() -> None:
    """极高的 Gas 费用可能导致净收益为负。"""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "exchange": ["Coinbase", "Coinbase", "Coinbase"],
            "price": [100.0, 101.0, 101.0],   # 微涨1%
            "gas_price": [500.0, 500.0, 500.0],   # 500 Gwei
            "gas_used": [200000, 200000, 200000], # 复杂合约 Gas
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "auto_compound",
        {
            "compound_ratio": 1.0,
            "max_sell_amount": 0.5,
            "min_sell_amount": -0.5,
        },
    )
    result = engine.run_backtest(df, config)

    config_low_tp = build_config(
        "auto_compound",
        {
            "compound_ratio": 1.0,
            "max_sell_amount": 0.005,  # 0.5% 止盈
            "min_sell_amount": -0.5,
        },
    )
    result = engine.run_backtest(df, config_low_tp)
    assert result.total_gas_cost > 0
    assert result.net_profit < result.gross_profit

def test_auto_compound_compound_ratio_comparison() -> None:
    """对比不同复投比例对最终权益的影响：复投比例越高，上涨行情中收益越高。"""
    engine = BacktestEngineCore()
    # 使用5天连续上涨10%的数据，避免年化收益率计算溢出
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "exchange": ["Coinbase"] * 5,
            "price": [100.0, 110.0, 121.0, 133.1, 146.41],
            "gas_price": [0.0] * 5,
            "gas_used": [0] * 5,
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))

    config_full = build_config(
        "auto_compound",
        {"compound_ratio": 1.0, "max_sell_amount": 0.5, "min_sell_amount": -0.5},
    )
    config_half = build_config(
        "auto_compound",
        {"compound_ratio": 0.5, "max_sell_amount": 0.5, "min_sell_amount": -0.5},
    )

    result_full = engine.run_backtest(df, config_full)
    result_half = engine.run_backtest(df, config_half)

    # 满仓最终权益 = 100 * 1.1^4 = 146.41
    assert float(result_full.final_equity) == pytest.approx(146.41, rel=1e-6)
    # 半仓最终权益 = 100 * (1 + 0.5*0.1)^4 = 100 * (1.05^4) = 121.550625
    expected_half = 100.0 * (1.05 ** 4)
    assert float(result_half.final_equity) == pytest.approx(expected_half, rel=1e-6)
    # 满仓净收益应大于半仓净收益
    assert result_full.net_profit > result_half.net_profit

def test_multi_arbitrage_requires_two_exchanges() -> None:
    """Input validation: arbitrage needs at least two exchanges."""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "exchange": ["Coinbase"],
            "price": [100.0],
            "gas_price": [0.0],
            "gas_used": [0],
        }
    )
    config = build_config(
        "multi_arbitrage",
        {"spread_threshold": 0.01, "trade_amount": 1000.0},
        selected_exchanges=["Coinbase"],
    )

    with pytest.raises(ValueError, match="至少2个交易所"):
        engine.run_backtest(df, config)


def test_multi_arbitrage_thresholds_support_comparative_analysis() -> None:
    """Comparative analysis: lower spread thresholds should admit more trades."""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": [
                "2024-01-01",
                "2024-01-01",
                "2024-01-02",
                "2024-01-02",
                "2024-01-03",
                "2024-01-03",
            ],
            "exchange": [
                "Coinbase",
                "Kraken",
                "Coinbase",
                "Kraken",
                "Coinbase",
                "Kraken",
            ],
            "price": [100.0, 110.0, 100.0, 102.0, 100.0, 112.0],
            "gas_price": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "gas_used": [0, 0, 0, 0, 0, 0],
        }
    )
    # 转换价格列为 Decimal
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))
    df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)))

    low_threshold = build_config(
        "multi_arbitrage",
        {"spread_threshold": 0.01, "trade_amount": 1000.0},
        selected_exchanges=["Coinbase", "Kraken"],
    )
    high_threshold = build_config(
        "multi_arbitrage",
        {"spread_threshold": 0.08, "trade_amount": 1000.0},
        selected_exchanges=["Coinbase", "Kraken"],
    )

    low_result = engine.run_backtest(df, low_threshold)
    high_result = engine.run_backtest(df, high_threshold)

    assert low_result.trade_count > high_result.trade_count
    # net_profit 是 Decimal，需转为 float 比较
    assert float(low_result.net_profit) > float(high_result.net_profit)



def test_multi_arbitrage_no_spread_no_trade() -> None:
    """无价差或价差低于阈值时，不应产生任何套利交易。"""
    engine = BacktestEngineCore()
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "exchange": ["Coinbase", "Kraken", "Coinbase", "Kraken"],
            "price": [100.0, 100.0, 101.0, 101.0],   # 价差为0
            "gas_price": [0.0, 0.0, 0.0, 0.0],
            "gas_used": [0, 0, 0, 0],
        }
    )
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "multi_arbitrage",
        {"spread_threshold": 0.01, "trade_amount": 1000.0},
        selected_exchanges=["Coinbase", "Kraken"],
    )
    result = engine.run_backtest(df, config)

    assert result.trade_count == 0
    assert float(result.net_profit) == 0.0

def test_multi_arbitrage_extreme_spread_high_profit() -> None:
    """极端价差（如100%）应产生极高套利利润。"""
    engine = BacktestEngineCore()
    # 生成 5 天数据，每天价差 100%
    dates = []
    exchanges = []
    prices = []
    for i in range(5):
        dates.extend([f"2024-01-0{i+1}", f"2024-01-0{i+1}"])
        exchanges.extend(["Coinbase", "Kraken"])
        prices.extend([100.0, 200.0])
    df = pd.DataFrame({
        "date": dates,
        "exchange": exchanges,
        "price": prices,
        "gas_price": [0.0] * 10,
        "gas_used": [0] * 10,
    })
    df["price"] = df["price"].apply(lambda x: Decimal(str(x)))

    config = build_config(
        "multi_arbitrage",
        {"spread_threshold": 0.01, "trade_amount": 1000.0},
        selected_exchanges=["Coinbase", "Kraken"],
    )
    result = engine.run_backtest(df, config)

    # 5 天每天一次套利，每次利润 1000，总利润 5000
    assert result.trade_count == 5
    assert float(result.net_profit) == pytest.approx(5000.0, rel=1e-6)