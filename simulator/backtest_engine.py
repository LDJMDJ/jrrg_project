# simulator/backtest_engine.py (完整修正版)

from __future__ import annotations

from decimal import Decimal, getcontext
import numpy as np
import pandas as pd

from src.gas_calculator import GasCalculator
from src.models import BacktestConfig, BacktestResult
from src.strategy_manager import StrategyManager

getcontext().prec = 28


class BacktestEngineCore:
    def __init__(self):
        self.gas_calculator = GasCalculator()

    def run_backtest(self, df: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
        """Dispatch the request to the concrete strategy-specific simulator."""
        if df.empty:
            raise ValueError("所选时间范围内无历史数据，请重新选择。")

        if config.strategy_type == "auto_compound":
            return self._run_auto_compound(df, config)
        if config.strategy_type == "multi_arbitrage":
            return self._run_multi_arbitrage(df, config)
        raise ValueError(f"不支持的策略类型: {config.strategy_type}")

    # ------------------------------------------------------------------
    # 自动复投策略
    # ------------------------------------------------------------------
    def _run_auto_compound(self, df: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
        # 确保价格和 Gas 为 Decimal
        df = df.copy()
        df['price'] = df['price'].apply(lambda x: Decimal(str(x)))
        df['gas_price'] = df['gas_price'].apply(lambda x: Decimal(str(x)))
        df['gas_used'] = df['gas_used'].apply(lambda x: int(x))

        daily = (
            df.groupby("date", as_index=False)
            .agg(
                price=("price", lambda x: sum(x) / Decimal(len(x))),
                gas_price=("gas_price", lambda x: sum(x) / Decimal(len(x))),
                gas_used=("gas_used", "mean"),
            )
            .sort_values("date")
            .reset_index(drop=True)
        )

        # 计算日收益率 (Decimal)
        prices = daily["price"].tolist()
        returns = [Decimal(0)]
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        daily["ret"] = returns

        # 生成信号 (返回 int Series)
        strategy = StrategyManager(config.strategy_type, config.params)
        signals = strategy.generate_signals(daily)   # 返回 0/1

        # 将信号转换为 Decimal
        signals_dec = signals.apply(lambda x: Decimal(x))
        compound_ratio = Decimal(str(config.params.get("compound_ratio", 0.7)))

        # 前一日信号决定仓位，缺失值用 1 填充
        target_position = signals_dec.shift(1).fillna(Decimal(1))
        # 限制在 [0,1] 范围内
        target_position = target_position.apply(lambda x: Decimal(0) if x < Decimal(0) else (Decimal(1) if x > Decimal(1) else x))
        target_position = target_position * compound_ratio

        # 计算 effective_ret（逐元素乘法）
        effective_ret = pd.Series(
            [ret * pos for ret, pos in zip(daily["ret"], target_position)],
            index=daily.index
        )
    
        # 权益曲线
        equity_values = [Decimal(str(config.initial_capital))]
        for ret in effective_ret[1:]:
            equity_values.append(equity_values[-1] * (Decimal(1) + ret))
        equity_series = pd.Series(equity_values, index=daily.index)
    
        # 交易点
        prev_position = target_position.shift(1).fillna(Decimal(0))
        trade_mask = (target_position - prev_position).abs() > Decimal("1e-12")
        trade_points = daily.loc[trade_mask, ["date"]].copy()
        trade_points["type"] = np.where(
            (target_position.loc[trade_mask] > prev_position.loc[trade_mask]).values,
            "buy",
            "sell_or_stop",
        )
        # 修改 profit 赋值
        trigger_ret = daily["ret"].shift(1).fillna(Decimal(0))
        profits = []
        for idx in trade_points.index:
            if trade_points.loc[idx, "type"] == "sell_or_stop":
                profits.append(trigger_ret.loc[idx])
            else:
                profits.append(Decimal(0))
        trade_points["profit"] = profits
        trade_points["trade_price"] = daily.loc[trade_mask, "price"].values
        prev_equity = equity_series.shift(1).fillna(Decimal(str(config.initial_capital)))
        turnover_ratio = (target_position - prev_position).abs()
        trade_points["trade_amount"] = (prev_equity.loc[trade_mask] * turnover_ratio.loc[trade_mask]).apply(
            lambda x: x.quantize(Decimal("0.000001"))
        )
        gas_used_dec = daily.loc[trade_mask, "gas_used"].apply(lambda x: Decimal(str(x)))
        gas_fee_series = (
            daily.loc[trade_mask, "gas_price"] * gas_used_dec * Decimal(1_000_000_000)
        ).apply(lambda x: int(x.quantize(Decimal("1"))))
        trade_points["gas_fee"] = gas_fee_series
        return self._build_result(
            date_series=daily["date"],
            equity_series=equity_series,
            trade_points=trade_points,
            initial_capital=Decimal(str(config.initial_capital)),
        )

    # ------------------------------------------------------------------
    # 多协议套利策略
    # ------------------------------------------------------------------
    def _run_multi_arbitrage(self, df: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
        if len(config.selected_exchanges) < 2:
            raise ValueError("多协议套利策略必须选择至少2个交易所。")

        df = df.copy()
        df['price'] = df['price'].apply(lambda x: Decimal(str(x)))
        df['gas_price'] = df['gas_price'].apply(lambda x: Decimal(str(x)))

        pivot_price = df.pivot_table(index="date", columns="exchange", values="price", aggfunc="mean")
        pivot_gas = df.pivot_table(index="date", columns="exchange", values="gas_price", aggfunc="mean")
        pivot_gas_used = df.pivot_table(index="date", columns="exchange", values="gas_used", aggfunc="mean")

        calc = pd.DataFrame(index=pivot_price.index)
        calc["max_price"] = pivot_price.max(axis=1).apply(lambda x: Decimal(str(x)) if pd.notna(x) else Decimal(0))
        calc["min_price"] = pivot_price.min(axis=1).apply(lambda x: Decimal(str(x)) if pd.notna(x) else Decimal(0))
        calc["gas_price"] = pivot_gas.mean(axis=1).apply(lambda x: Decimal(str(x)) if pd.notna(x) else Decimal(0))
        calc["gas_used"] = pivot_gas_used.mean(axis=1).apply(lambda x: Decimal(str(x)) if pd.notna(x) else Decimal(0))
        calc = calc.dropna().reset_index()
        strategy = StrategyManager(config.strategy_type, config.params)
        signals = strategy.generate_signals(calc)   # 传入 calc，包含 max_price/min_price

        trade_amount = Decimal(str(config.params.get("trade_amount", 1000.0)))
        spread = calc["max_price"] - calc["min_price"]
        # 修改 spread_ratio 计算
        min_price_clean = calc["min_price"].apply(lambda x: x if x != Decimal(0) else Decimal(1))
        spread_ratio = spread / min_price_clean
        profit_per_trade = trade_amount * spread_ratio
        daily_profit = pd.Series(
            [Decimal(sig) * profit if sig else Decimal(0) for sig, profit in zip(signals, profit_per_trade)],
            index=calc.index
        )

        equity_values = []
        cum = Decimal(str(config.initial_capital))
        for profit in daily_profit:   # daily_profit 包含所有日期的利润（包括第一天）
            cum += profit
            equity_values.append(cum)
        equity_series = pd.Series(equity_values, index=calc.index)

        trade_mask = signals > 0
        trade_points = calc.loc[trade_mask, ["date"]].copy()
        trade_points["type"] = "arbitrage"
        trade_points["profit"] = daily_profit.loc[trade_mask].apply(lambda x: x.quantize(Decimal("0.000001")))
        trade_points["trade_price"] = calc.loc[trade_mask, "min_price"]
        trade_points["trade_amount"] = trade_amount
        trade_points["gas_fee"] = (
            2 * calc.loc[trade_mask, "gas_price"] * calc.loc[trade_mask, "gas_used"] *1_000_000_000
        ).apply(lambda x: int(x.quantize(Decimal("1"))))

        return self._build_result(
            date_series=calc["date"],
            equity_series=equity_series,
            trade_points=trade_points,
            initial_capital=Decimal(str(config.initial_capital)),
        )

    # ------------------------------------------------------------------
    # 结果构建
    # ------------------------------------------------------------------
    def _build_result(self, date_series, equity_series, trade_points, initial_capital):
        raw_equity_curve = pd.DataFrame({"date": date_series, "equity": equity_series})

        if not trade_points.empty and "gas_fee" in trade_points.columns:
            gas_by_date_wei = trade_points.groupby("date")["gas_fee"].sum()
            cumulative_gas_eth = pd.Series(index=raw_equity_curve.index, dtype=object)
            cum_gas = Decimal(0)
            for i, date in enumerate(raw_equity_curve["date"]):
                if date in gas_by_date_wei.index:
                    cum_gas += Decimal(int(gas_by_date_wei[date])) / Decimal("1e18")
                cumulative_gas_eth.iloc[i] = cum_gas
            equity_curve = raw_equity_curve.copy()
            equity_curve["equity"] = raw_equity_curve["equity"] - cumulative_gas_eth
            total_gas_cost = int(sum(gas_by_date_wei))
            net_profit = equity_curve["equity"].iloc[-1] - initial_capital
        else:
            equity_curve = raw_equity_curve
            total_gas_cost = 0
            net_profit = equity_curve["equity"].iloc[-1] - initial_capital

        final_equity = equity_curve["equity"].iloc[-1]
        cumulative_return = net_profit / initial_capital if initial_capital != Decimal(0) else Decimal(0)
        annualized_return = self._annualized_return(equity_curve["date"], initial_capital, final_equity)
        max_drawdown = self._max_drawdown(equity_curve["equity"])
        trade_count = len(trade_points)
        win_rate = float((trade_points["profit"] > Decimal(0)).sum()) / trade_count if trade_count > 0 else 0.0
        gross_profit = final_equity - initial_capital + Decimal(total_gas_cost) / Decimal("1e18")

        return BacktestResult(
            equity_curve=equity_curve,
            trade_points=trade_points,
            cumulative_return=cumulative_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            trade_count=trade_count,
            win_rate=win_rate,
            gross_profit=gross_profit,
            total_gas_cost=total_gas_cost,
            net_profit=net_profit,
            final_equity=final_equity,
        )

    @staticmethod
    def _max_drawdown(equity: pd.Series) -> Decimal:
        if equity.empty:
            return Decimal(0)
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max.replace(0, Decimal(1))
        min_dd = drawdown.min()
        return min_dd if not pd.isna(min_dd) else Decimal(0)

    @staticmethod
    def _annualized_return(date_series, initial_capital, final_equity) -> Decimal:
        if initial_capital <= 0:
            return Decimal(0)
        dates = pd.to_datetime(date_series)
        if dates.empty:
            return Decimal(0)
        days = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
        total_return = final_equity / initial_capital
        if total_return <= 0:
            return Decimal(-1)
        # 将 Decimal 转为 float 计算幂（仅用于展示）
        annualized = float(total_return) ** (365.0 / days) - 1.0
        return Decimal(str(annualized))