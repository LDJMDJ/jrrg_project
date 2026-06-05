from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from decimal import Decimal, getcontext
getcontext().prec = 28
import pandas as pd

from src.models import BacktestConfig, BacktestResult


class DataIOAdapter:
    """Persist and query project data from the SQLite database."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived database connection."""

        return sqlite3.connect(self.db_path)

    def list_exchanges(self) -> list[str]:
        """Return exchanges that currently have historical data."""

        conn = self._connect()
        try:
            df = pd.read_sql_query(
                "SELECT exchange_name FROM exchanges WHERE has_data=1 ORDER BY exchange_name", conn
            )
            return df["exchange_name"].tolist()
        finally:
            conn.close()

    def get_historical_date_bounds(self) -> tuple[str, str] | None:
        """Return the min and max dates available in the history table."""

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM historical_trades"
            ).fetchone()
            if not row or not row[0] or not row[1]:
                return None
            return str(row[0]), str(row[1])
        finally:
            conn.close()

    def list_strategies(self) -> pd.DataFrame:
        """Load strategy metadata for the management page."""

        conn = self._connect()
        try:
            return pd.read_sql_query(
                """
                SELECT strategy_id, strategy_name, strategy_type, description, params, built_in, created_at, updated_at
                FROM strategies
                ORDER BY built_in DESC, strategy_id ASC
                """,
                conn,
            )
        finally:
            conn.close()

    def create_strategy(
        self,
        strategy_name: str,
        strategy_type: str,
        description: str,
        params: dict,
    ) -> None:
        """Insert a new user-defined strategy into the database."""

        now_ts = int(datetime.now().timestamp())
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO strategies(strategy_name, strategy_type, description, params, built_in, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    strategy_name,
                    strategy_type,
                    description,
                    json.dumps(params, ensure_ascii=False),
                    now_ts,
                    now_ts,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def update_strategy(
        self,
        strategy_id: int,
        strategy_name: str,
        strategy_type: str,
        description: str,
        params: dict,
    ) -> None:
        """Update the editable fields of an existing strategy."""

        now_ts = int(datetime.now().timestamp())
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE strategies
                SET strategy_name=?, strategy_type=?, description=?, params=?, updated_at=?
                WHERE strategy_id=?
                """,
                (
                    strategy_name,
                    strategy_type,
                    description,
                    json.dumps(params, ensure_ascii=False),
                    now_ts,
                    strategy_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_strategy(self, strategy_id: int) -> None:
        """Delete a user-defined strategy and its related backtest records."""

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT built_in FROM strategies WHERE strategy_id=?", (strategy_id,)
            ).fetchone()
            if not row:
                raise ValueError("策略不存在")
            if int(row[0]) == 1:
                raise ValueError("内置策略不可删除")
            conn.execute("DELETE FROM backtest_records WHERE strategy_id=?", (strategy_id,))
            conn.execute("DELETE FROM strategies WHERE strategy_id=?", (strategy_id,))
            conn.commit()
        finally:
            conn.close()

    def load_historical_data(
        self,
        start_time: str,
        end_time: str,
        exchanges: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load historical prices and gas data.
        
        The returned DataFrame has 'price' and 'gas_price' columns as Decimal objects.
        """
        conn = self._connect()
        try:
            if exchanges:
                placeholders = ",".join(["?"] * len(exchanges))
                sql = f"""
                    SELECT timestamp, date, exchange, price, gas_used, gas_price
                    FROM historical_trades
                    WHERE date BETWEEN ? AND ?
                    AND exchange IN ({placeholders})
                    ORDER BY timestamp ASC, exchange ASC
                """
                params = [start_time, end_time, *exchanges]
                df = pd.read_sql_query(sql, conn, params=params)
            else:
                df = pd.read_sql_query(
                    """
                    SELECT timestamp, date, exchange, price, gas_used, gas_price
                    FROM historical_trades
                    WHERE date BETWEEN ? AND ?
                    ORDER BY timestamp ASC, exchange ASC
                    """,
                    conn,
                    params=[start_time, end_time],
                )
            if df.empty:
                return df

            # Convert TEXT columns to Decimal
            df["price"] = df["price"].apply(lambda x: Decimal(str(x)) if x is not None else Decimal(0))
            df["gas_price"] = df["gas_price"].apply(lambda x: Decimal(str(x)) if x is not None else Decimal(0))
            return df
        finally:
            conn.close()

    def save_backtest_result(self, result: BacktestResult, config: BacktestConfig) -> None:
        """Persist a backtest run.
        
        All Decimal fields are converted to strings before storage.
        """
        conn = self._connect()
        try:
            # Prepare equity_curve JSON with Decimal -> string conversion
            # 处理 equity_curve
            equity_df = result.equity_curve.copy()
            if "equity" in equity_df.columns:
                equity_df["equity"] = equity_df["equity"].apply(str)
            equity_json = equity_df.to_json(orient="records", force_ascii=False)

            # 处理 trade_points
            trade_df = result.trade_points.copy() if not result.trade_points.empty else pd.DataFrame()
            if not trade_df.empty:
                for col in ["profit", "trade_amount", "gas_fee"]:
                    if col in trade_df.columns:
                        trade_df[col] = trade_df[col].apply(str)
            trade_json = trade_df.to_json(orient="records", force_ascii=False)

            # All monetary values as strings (Decimal)
            initial_capital_str = str(config.initial_capital)
            final_equity_str = str(result.final_equity)
            cumulative_return_str = str(result.cumulative_return)
            annualized_return_str = str(result.annualized_return)
            max_drawdown_str = str(result.max_drawdown)
            total_gas_cost_str = str(result.total_gas_cost)   # integer Wei stored as string
            net_profit_str = str(result.net_profit)
            conn.execute(
    """
    INSERT INTO backtest_records(
        strategy_id, start_date, end_date, selected_exchanges, execution_time,
        initial_capital, final_equity, cumulative_return, annualized_return,
        max_drawdown, total_gas_cost, net_profit, trade_count, win_rate,
        equity_curve, trade_points, status, error_message
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', NULL)
    """,
    (
        config.strategy_id,
        config.start_time,
        config.end_time,
        json.dumps(config.selected_exchanges, ensure_ascii=False),
        int(datetime.now().timestamp()),
        initial_capital_str,
        final_equity_str,
        cumulative_return_str,
        annualized_return_str,
        max_drawdown_str,
        total_gas_cost_str,
        net_profit_str,
        result.trade_count,
        result.win_rate,
        equity_json,
        trade_json,
    )
)
            conn.commit()
        finally:
            conn.close()

    def list_backtest_records(self) -> pd.DataFrame:
        """List backtest records with summary fields.
        
        The returned DataFrame contains monetary columns as strings
        (original TEXT from DB). Caller can convert to Decimal if needed.
        """
        conn = self._connect()
        try:
            df = pd.read_sql_query(
                """
                SELECT r.record_id, r.strategy_id, s.strategy_name, r.start_date, r.end_date,
                       r.execution_time, r.initial_capital, r.final_equity, r.cumulative_return,
                       r.max_drawdown, r.total_gas_cost, r.net_profit, r.trade_count, r.win_rate,
                       r.status
                FROM backtest_records r
                LEFT JOIN strategies s ON s.strategy_id = r.strategy_id
                ORDER BY r.record_id DESC
                """,
                conn,
            )
            # Keep as strings – the UI can format or convert as needed.
            return df
        finally:
            conn.close()

    def get_backtest_record_detail(self, record_id: int) -> pd.DataFrame:
        """Retrieve a single backtest record and deserialize Decimal values.
        
        The returned DataFrame has the following columns converted to Decimal
        where applicable: initial_capital, final_equity, cumulative_return,
        annualized_return, max_drawdown, net_profit.
        The equity_curve and trade_points columns are parsed as JSON and
        their numeric fields are turned into Decimal objects.
        """
        conn = self._connect()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM backtest_records WHERE record_id=?",
                conn,
                params=[record_id],
            )
            if df.empty:
                return df

            # Convert scalar monetary fields from TEXT to Decimal
            scalar_cols = ["initial_capital", "final_equity", "cumulative_return",
                           "annualized_return", "max_drawdown", "net_profit"]
            for col in scalar_cols:
                if col in df.columns and df[col].iloc[0] is not None:
                    df[col] = df[col].apply(lambda x: Decimal(str(x)) if x else Decimal(0))

            # total_gas_cost is an integer stored as TEXT -> convert to int
            if "total_gas_cost" in df.columns and df["total_gas_cost"].iloc[0] is not None:
                df["total_gas_cost"] = df["total_gas_cost"].apply(lambda x: int(x) if x else 0)

            # Deserialize equity_curve JSON and convert equity to Decimal
            if "equity_curve" in df.columns and df["equity_curve"].iloc[0]:
                equity_json = df["equity_curve"].iloc[0]
                equity_curve = pd.read_json(equity_json)
                if "equity" in equity_curve.columns:
                    equity_curve["equity"] = equity_curve["equity"].apply(
                        lambda x: Decimal(str(x)) if x is not None else Decimal(0)
                    )
                df.at[0, "equity_curve"] = equity_curve

            # Deserialize trade_points JSON and convert profit/trade_amount/gas_fee to Decimal
            if "trade_points" in df.columns and df["trade_points"].iloc[0]:
                trade_json = df["trade_points"].iloc[0]
                trade_points = pd.read_json(trade_json)
                if not trade_points.empty:
                    for col in ["profit", "trade_amount", "gas_fee"]:
                        if col in trade_points.columns:
                            trade_points[col] = trade_points[col].apply(
                                lambda x: Decimal(str(x)) if x is not None else Decimal(0)
                            )
                df.at[0, "trade_points"] = trade_points

            return df
        finally:
            conn.close()

    def delete_backtest_record(self, record_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM backtest_records WHERE record_id=?", (record_id,))
            conn.commit()
        finally:
            conn.close()
