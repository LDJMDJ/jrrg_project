import csv
import io
import json
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "defi_backtest.db"
START_DATE = date(2020, 10, 1)
END_DATE = date(2026, 5, 1)
CRYPTOSYMBOL = "ETH"
QUOTESYMBOL = "USD"
CRYPTOCOMPARE_URL = "https://min-api.cryptocompare.com/data/v2/histoday"
ETHERSCAN_GAS_CSV_URL = "https://etherscan.io/chart/gasprice?output=csv"
REQUEST_HEADERS = {"User-Agent": "jrrg-project/1.0"}
EXCHANGE_CONFIGS = {
    "Coinbase": {"cryptocompare_exchange": "Coinbase", "gas_used": 125000},
    "Kraken": {"cryptocompare_exchange": "Kraken", "gas_used": 132000},
    "Bitfinex": {"cryptocompare_exchange": "Bitfinex", "gas_used": 138000},
    "Bitstamp": {"cryptocompare_exchange": "Bitstamp", "gas_used": 128000},
}


def _create_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS historical_trades;
        DROP TABLE IF EXISTS strategies;
        DROP TABLE IF EXISTS backtest_records;
        DROP TABLE IF EXISTS gas_evaluations;
        DROP TABLE IF EXISTS exchanges;

        CREATE TABLE historical_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            date TEXT NOT NULL,
            exchange TEXT NOT NULL,
            price REAL NOT NULL,
            gas_price REAL NOT NULL,
            gas_used INTEGER NOT NULL
        );

        CREATE INDEX idx_historical_time_date_exchange
            ON historical_trades(timestamp, date, exchange);

        CREATE TABLE strategies (
            strategy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT UNIQUE NOT NULL,
            strategy_type TEXT NOT NULL,
            description TEXT,
            params TEXT NOT NULL,
            built_in INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        CREATE TABLE backtest_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            selected_exchanges TEXT NOT NULL,
            execution_time INTEGER NOT NULL,
            initial_capital REAL NOT NULL,
            final_equity REAL,
            cumulative_return REAL,
            annualized_return REAL,
            max_drawdown REAL,
            total_gas_cost REAL,
            net_profit REAL,
            trade_count INTEGER,
            win_rate REAL,
            equity_curve TEXT,
            trade_points TEXT,
            status TEXT,
            error_message TEXT,
            FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
        );

        CREATE TABLE gas_evaluations (
            eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            operation_count INTEGER NOT NULL,
            total_gas_eth REAL NOT NULL,
            total_gas_fiat REAL,
            expected_profit REAL,
            cost_benefit_ratio REAL,
            risk_warning INTEGER DEFAULT 0,
            evaluated_at INTEGER NOT NULL,
            FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
        );

        CREATE TABLE exchanges (
            exchange_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_name TEXT UNIQUE NOT NULL,
            has_data INTEGER DEFAULT 1
        );
        """
    )
    conn.commit()


def _seed_exchanges(conn: sqlite3.Connection) -> list[str]:
    exchanges = list(EXCHANGE_CONFIGS.keys())
    conn.executemany(
        "INSERT INTO exchanges(exchange_name, has_data) VALUES(?, 1)",
        [(name,) for name in exchanges],
    )
    conn.commit()
    return exchanges


def _seed_strategies(conn: sqlite3.Connection) -> None:
    now_ts = int(datetime.now().timestamp())
    rows = [
        (
            "自动复投-默认策略",
            "auto_compound",
            "系统内置：按收益比例进行复投和止盈止损。",
            json.dumps(
                {
                    "compound_frequency": "daily",
                    "compound_ratio": 0.7,
                    "max_sell_amount": 0.05,
                    "min_sell_amount": -0.02,
                },
                ensure_ascii=False,
            ),
            1,
            now_ts,
            now_ts,
        ),
        (
            "多协议套利-默认策略",
            "multi_arbitrage",
            "系统内置：跨交易所价差套利。",
            json.dumps(
                {
                    "spread_threshold": 0.001,
                    "trade_amount": 1500.0,
                },
                ensure_ascii=False,
            ),
            1,
            now_ts,
            now_ts,
        ),
    ]
    conn.executemany(
        """
        INSERT INTO strategies(
            strategy_name, strategy_type, description, params, built_in, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def _http_get_text(url: str, retries: int = 3, sleep_seconds: float = 1.5) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=REQUEST_HEADERS)
            with urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = exc
            if attempt < retries - 1:
                time.sleep(sleep_seconds * (attempt + 1))
    raise RuntimeError(f"请求失败: {url}") from last_error


def _fetch_exchange_prices(exchange_name: str) -> dict[str, float]:
    start_ts = int(datetime.combine(START_DATE, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.combine(END_DATE, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    to_ts = end_ts
    prices: dict[str, float] = {}

    while True:
        params = urlencode(
            {
                "fsym": CRYPTOSYMBOL,
                "tsym": QUOTESYMBOL,
                "e": exchange_name,
                "limit": 2000,
                "toTs": to_ts,
                "extraParams": "jrrg_project",
            }
        )
        payload = json.loads(_http_get_text(f"{CRYPTOCOMPARE_URL}?{params}"))
        if payload.get("Response") != "Success":
            raise RuntimeError(f"CryptoCompare 获取 {exchange_name} 数据失败: {payload}")

        points = payload.get("Data", {}).get("Data", [])
        if not points:
            break

        earliest_ts = None
        for point in points:
            point_ts = int(point["time"])
            earliest_ts = point_ts if earliest_ts is None else min(earliest_ts, point_ts)
            if point_ts < start_ts or point_ts > end_ts:
                continue
            close_price = float(point.get("close") or 0.0)
            if close_price <= 0:
                continue
            point_date = datetime.fromtimestamp(point_ts, timezone.utc).strftime("%Y-%m-%d")
            prices[point_date] = close_price

        if earliest_ts is None or earliest_ts <= start_ts or len(points) < 2000:
            break
        to_ts = earliest_ts - 86400
        time.sleep(0.3)

    return prices


def _parse_gas_csv(text: str) -> dict[str, float]:
    reader = csv.DictReader(io.StringIO(text))
    gas_prices: dict[str, float] = {}
    for row in reader:
        date_text = (row.get("Date(UTC)") or row.get("Date (UTC)") or "").strip()
        gas_price_wei = (row.get("Value (Wei)") or row.get("gas_price") or "").strip()
        if not date_text or not gas_price_wei:
            continue
        parsed_date = datetime.strptime(date_text, "%m/%d/%Y").date()
        if parsed_date < START_DATE or parsed_date > END_DATE:
            continue
        gas_prices[parsed_date.isoformat()] = float(gas_price_wei) / 1_000_000_000
    return gas_prices


def _fetch_daily_gas_prices() -> dict[str, float]:
    return _parse_gas_csv(_http_get_text(ETHERSCAN_GAS_CSV_URL))


def _build_historical_rows(
    exchange_prices: dict[str, dict[str, float]],
    daily_gas_prices: dict[str, float],
) -> tuple[list[tuple[int, str, str, float, float, int]], list[str]]:
    rows: list[tuple[int, str, str, float, float, int]] = []
    skipped_dates: list[str] = []
    current_day = START_DATE

    while current_day <= END_DATE:
        date_text = current_day.isoformat()
        timestamp = int(datetime.combine(current_day, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        available_prices = [
            exchange_prices[exchange_name].get(date_text)
            for exchange_name in EXCHANGE_CONFIGS
            if exchange_prices[exchange_name].get(date_text) is not None
        ]
        gas_price = daily_gas_prices.get(date_text)
        if not available_prices or gas_price is None:
            skipped_dates.append(date_text)
            current_day += timedelta(days=1)
            continue

        fill_price = mean(available_prices)
        for exchange_name, exchange_config in EXCHANGE_CONFIGS.items():
            price = exchange_prices[exchange_name].get(date_text, fill_price)
            rows.append(
                (
                    timestamp,
                    date_text,
                    exchange_name,
                    round(price, 6),
                    round(gas_price, 6),
                    int(exchange_config["gas_used"]),
                )
            )
        current_day += timedelta(days=1)

    return rows, skipped_dates


def _seed_historical_trades(conn: sqlite3.Connection, exchanges: list[str]) -> None:
    print(
        f"开始拉取历史数据: {CRYPTOSYMBOL}/{QUOTESYMBOL}, "
        f"{START_DATE.isoformat()} -> {END_DATE.isoformat()}"
    )
    exchange_prices: dict[str, dict[str, float]] = {}
    for exchange_name in exchanges:
        source_exchange = EXCHANGE_CONFIGS[exchange_name]["cryptocompare_exchange"]
        print(f"拉取 {exchange_name} 收盘价...")
        exchange_prices[exchange_name] = _fetch_exchange_prices(source_exchange)
        print(f"{exchange_name} 收到 {len(exchange_prices[exchange_name])} 条日线")

    print("拉取 Ethereum 全网日均 Gas 单价...")
    daily_gas_prices = _fetch_daily_gas_prices()
    print(f"Gas 日线收到 {len(daily_gas_prices)} 条")

    rows, skipped_dates = _build_historical_rows(exchange_prices, daily_gas_prices)
    if skipped_dates:
        print("以下日期由于四个交易所均缺价或缺少全网日均 Gas 数据，被跳过：")
        for skipped_date in skipped_dates:
            print(skipped_date)

    conn.executemany(
        """
        INSERT INTO historical_trades(
            timestamp, date, exchange, price, gas_price, gas_used
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    print(f"historical_trades 已写入 {len(rows)} 条记录")


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _create_tables(conn)
        exchanges = _seed_exchanges(conn)
        _seed_strategies(conn)
        _seed_historical_trades(conn, exchanges)
        print(f"数据库初始化完成: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    initialize_database()
