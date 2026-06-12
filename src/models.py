from dataclasses import dataclass
from typing import Any
from decimal import Decimal
import pandas as pd


@dataclass
class BacktestConfig:
    """Input parameters required to run a backtest experiment."""

    start_time: str
    end_time: str
    initial_capital: Decimal
    strategy_id: int
    strategy_name: str
    strategy_type: str
    params: dict[str, Any]
    selected_exchanges: list[str]


@dataclass
class BacktestResult:
    """Aggregated outputs produced by the simulation engine."""

    equity_curve: pd.DataFrame
    trade_points: pd.DataFrame
    cumulative_return: float
    annualized_return: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    gross_profit: Decimal
    total_gas_cost: int
    net_profit: Decimal
    final_equity: Decimal
