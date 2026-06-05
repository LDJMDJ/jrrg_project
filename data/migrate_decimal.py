import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "defi_backtest.db"

def migrate():
    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 检查是否已经迁移过（例如已有列 price_text）
    cursor.execute("PRAGMA table_info(historical_trades)")
    columns = [col[1] for col in cursor.fetchall()]
    if "price_text" in columns:
        print("似乎已经迁移过（price_text 列存在），跳过。")
        conn.close()
        return

    # 2. 开始事务
    conn.execute("BEGIN IMMEDIATE")

    # ----- historical_trades -----
    # 创建新表，price / gas_price 改为 TEXT
    cursor.execute("""
        CREATE TABLE historical_trades_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            date TEXT NOT NULL,
            exchange TEXT NOT NULL,
            price TEXT NOT NULL,            -- 高精度存储 USD
            gas_price TEXT NOT NULL,        -- 高精度存储 Gwei
            gas_used INTEGER NOT NULL
        )
    """)
    # 复制数据并转换为 Decimal 字符串
    cursor.execute("SELECT id, timestamp, date, exchange, price, gas_price, gas_used FROM historical_trades")
    rows = cursor.fetchall()
    for row in rows:
        price_dec = str(Decimal(str(row[4])))   # 原 float -> string -> Decimal -> string
        gas_price_dec = str(Decimal(str(row[5])))
        cursor.execute(
            "INSERT INTO historical_trades_new (id, timestamp, date, exchange, price, gas_price, gas_used) VALUES (?,?,?,?,?,?,?)",
            (row[0], row[1], row[2], row[3], price_dec, gas_price_dec, row[6])
        )
    cursor.execute("DROP TABLE historical_trades")
    cursor.execute("ALTER TABLE historical_trades_new RENAME TO historical_trades")
    # 重建索引
    cursor.execute("CREATE INDEX idx_historical_time_date_exchange ON historical_trades(timestamp, date, exchange)")

    # ----- backtest_records -----
    cursor.execute("PRAGMA table_info(backtest_records)")
    old_cols = [col[1] for col in cursor.fetchall()]
    # 决定要转换的金额列
    numeric_cols = ["initial_capital", "final_equity", "cumulative_return", "annualized_return",
                    "max_drawdown", "net_profit"]
    # 注意 total_gas_cost 已经是 TEXT (Wei 字符串)，不需要再迁移，但需保留

    cursor.execute("""
        CREATE TABLE backtest_records_new (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            selected_exchanges TEXT NOT NULL,
            execution_time INTEGER NOT NULL,
            initial_capital TEXT NOT NULL,
            final_equity TEXT,
            cumulative_return TEXT,
            annualized_return TEXT,
            max_drawdown TEXT,
            total_gas_cost TEXT,
            net_profit TEXT,
            trade_count INTEGER,
            win_rate REAL,
            equity_curve TEXT,
            trade_points TEXT,
            status TEXT,
            error_message TEXT,
            FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
        )
    """)
    # 复制数据，将浮点列转为 Decimal 字符串
    cursor.execute("SELECT * FROM backtest_records")
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    for row in rows:
        row_dict = dict(zip(col_names, row))
        new_row = []
        for col in col_names:
            if col in numeric_cols and row_dict[col] is not None:
                val = str(Decimal(str(row_dict[col])))
            elif col == "win_rate":
                val = row_dict[col]   # win_rate 仍是比例浮点，保持 REAL
            else:
                val = row_dict[col]
            new_row.append(val)
        placeholders = ",".join(["?"] * len(col_names))
        cursor.execute(f"INSERT INTO backtest_records_new ({','.join(col_names)}) VALUES ({placeholders})", new_row)
    cursor.execute("DROP TABLE backtest_records")
    cursor.execute("ALTER TABLE backtest_records_new RENAME TO backtest_records")

    # ----- gas_evaluations 如果有金额列也一并处理（可选）-----
    cursor.execute("PRAGMA table_info(gas_evaluations)")
    if cursor.fetchone():
        cursor.execute("""
            CREATE TABLE gas_evaluations_new (
                eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER,
                operation_count INTEGER NOT NULL,
                total_gas_eth TEXT,
                total_gas_fiat TEXT,
                expected_profit TEXT,
                cost_benefit_ratio REAL,
                risk_warning INTEGER DEFAULT 0,
                evaluated_at INTEGER NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
            )
        """)
        cursor.execute("SELECT * FROM gas_evaluations")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        for row in rows:
            row_dict = dict(zip(col_names, row))
            new_row = []
            for col in col_names:
                if col in ("total_gas_eth", "total_gas_fiat", "expected_profit") and row_dict[col] is not None:
                    val = str(Decimal(str(row_dict[col])))
                else:
                    val = row_dict[col]
                new_row.append(val)
            placeholders = ",".join(["?"] * len(col_names))
            cursor.execute(f"INSERT INTO gas_evaluations_new ({','.join(col_names)}) VALUES ({placeholders})", new_row)
        cursor.execute("DROP TABLE gas_evaluations")
        cursor.execute("ALTER TABLE gas_evaluations_new RENAME TO gas_evaluations")

    conn.commit()
    conn.close()
    print("数据库迁移完成，所有金额字段已改为高精度 TEXT 存储。")

if __name__ == "__main__":
    migrate()