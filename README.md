# DeFi 策略回测系统

本项目是一个可执行、可交互、可复现的 DeFi 策略回测课程项目。系统使用真实历史价格与 gas 数据，支持策略管理、策略回测、结果可视化和回测历史查询，避免了仅靠静态公式或表格推导的“伪仿真”实现。

## 项目结构

```text
jrrg_project/
├── src/                 # 核心逻辑包装层：数据模型、策略、数据访问、Gas 计算
├── simulator/           # 仿真引擎入口
├── tests/               # 单元测试与集成测试
├── data/                # 数据库、图片资源、数据目录说明与实验输出预留目录
├── frontend/            # Streamlit 前端入口
├── init_db.py           # 数据库初始化与真实历史数据拉取
├── requirements.txt     # 依赖列表
└── README.md            # 项目说明与复现指南
```

## 模块职责

- `src/strategy_manager.py`：根据策略参数生成交易信号。
- `simulator/backtest_engine.py`：执行自动复投和多交易所套利回测。
- `src/data_io_adapter.py`：负责 SQLite 读写、历史数据加载、结果持久化。
- `frontend/app.py`：课程化目录下的界面启动入口。
- `init_db.py`：从公共 API 拉取历史价格和 gas 数据并初始化数据库。

## 环境准备

建议使用 Python 3.10 及以上版本。
在项目根目录打开终端：

首次运行前先安装依赖：
```bash
pip install -r requirements.txt
```

## 测试与运行

1. 运行自动化测试
2. 启动前端页面


### 1. 自动化测试

运行测试命令：

```bash
python -m pytest -q
```

如果终端看到类似下面的结果，说明当前核心逻辑测试通过：

```text
20 passed
```

项目中的 `tests/` 目录覆盖了三类课程要求中的关键验证目标：

- 基础功能测试：
  - `test_gas_cost_matches_eth_formula`
  - `test_gas_cost_zero_for_no_trades`
  - `test_auto_compound_signal_boundary_equal_to_threshold`
  - `test_multi_arbitrage_signal_boundary_equal_to_threshold`
  - `test_gas_calculator_handles_large_numbers`
  - `test_auto_compound_preserves_growth_without_triggers`
  - `test_auto_compound_triggers_take_profit_on_rise`
  - `test_auto_compound_compound_ratio_reduces_exposure`
  - `test_auto_compound_gas_cost_reduces_net_profit`
  - `test_multi_arbitrage_no_spread_no_trade`
- 极端场景测试：
  - `test_auto_compound_triggers_stop_loss_after_price_crash`
  - `test_auto_compound_extreme_gas_cost_erodes_all_profit`
  - `test_multi_arbitrage_extreme_spread_high_profit`
  - `test_multi_arbitrage_requires_two_exchanges`
  - `test_auto_compound_signal_all_zeros_when_extreme_losses`
  - `test_multi_arbitrage_signal_all_ones_when_extreme_spreads`
- 对比分析测试：
  - `test_multi_arbitrage_thresholds_support_comparative_analysis`
  - `test_auto_compound_compound_ratio_comparison`

### 2. 启动前端页面

启动前端页面：

```bash
streamlit run frontend/app.py
```

启动成功后，终端通常会显示本地访问地址：

```text
http://localhost:8501
```

在浏览器打开这个地址即可进入系统界面。


## 数据说明

- SQLite 数据库文件位于 `data/defi_backtest.db`。
- 价格数据：使用公共 API 获取 2020-10-01 到 2026-05-01 的日收盘价。
- Gas 数据：使用公开来源的 ETH 历史 gas 单价。
- 单位说明：
  - `price` 使用 USD。
  - `gas_price` 使用 Gwei。
  - `gas_fee = gas_price * gas_used / 1e9`，结果单位为 ETH。
