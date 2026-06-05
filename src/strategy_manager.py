from __future__ import annotations

import pandas as pd
from decimal import Decimal

class StrategyManager:
    """Generate strategy signals from historical market data."""

    def __init__(self, strategy_type: str, params: dict):
        self.strategy_type = strategy_type
        self.params = params

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Route signal generation to the selected strategy family."""

        if self.strategy_type == "auto_compound":
            return self._auto_compound_signals(df)
        if self.strategy_type == "multi_arbitrage":
            return self._multi_arbitrage_signals(df)
        raise ValueError(f"不支持的策略类型: {self.strategy_type}")

    def _auto_compound_signals(self, df: pd.DataFrame) -> pd.Series:
        """Emit hold-or-exit signals based on daily profit and loss thresholds."""

        max_sell = Decimal(str(self.params.get("max_sell_amount", 0.03)))
        min_sell = Decimal(str(self.params.get("min_sell_amount", -0.02)))
        returns = df['price'].pct_change().fillna(Decimal(0))
        signal = pd.Series(1, index=df.index, dtype='int64')
        signal[returns >= max_sell] = 0
        signal[returns <= min_sell] = 0
        return signal

    def _multi_arbitrage_signals(self, df: pd.DataFrame) -> pd.Series:
        """Emit arbitrage signals when the cross-exchange spread is large enough."""

        spread_threshold = float(self.params.get("spread_threshold", 0.008))
        spread = df["max_price"] - df["min_price"]
        spread_ratio = (spread / df["min_price"]).fillna(0.0)
        return (spread_ratio >= spread_threshold).astype("int64")
