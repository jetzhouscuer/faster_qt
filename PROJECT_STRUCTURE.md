# faster_qt 项目结构

```
faster_qt/
├── README.md                 # 项目简介
├── PROJECT_STRUCTURE.md      # 本文件
├── .gitignore               # Git 忽略配置
│
├── data/                    # 数据存储目录
│   ├── raw/                 # 原始数据（未清洗）
│   │   ├── market/          # 行情数据（K线、tick）
│   │   ├── fundamental/      # 财务基本面数据
│   │   └── alternative/     # 另类数据（新闻、舆情）
│   │
│   ├── cleaned/             # 清洗后的数据
│   │   ├── daily/           # 日线数据
│   │   └── minute/          # 分钟级数据
│   │
│   ├── factors/              # 因子数据
│   │   ├── price/           # 量价因子
│   │   ├── fundamental/      # 财务因子
│   │   └── alternative/      # 另类因子
│   │
│   ├── backtest/            # 回测数据输出
│   │   ├── signals/         # 交易信号
│   │   ├── orders/          # 订单记录
│   │   └── equity/          # 权益曲线
│   │
│   └── live/                # 实盘数据
│       ├── signals/         # 实时信号
│       ├── orders/          # 实盘订单
│       └── positions/       # 持仓记录
│
├── docs/                    # 文档目录
│   ├── design/              # 设计文档
│   │   ├── SYSTEM_ARCHITECTURE.md    # 系统架构设计
│   │   ├── DATA_DICTIONARY.md        # 数据字典
│   │   ├── API_SPEC.md               # 接口规范
│   │   └── DEPLOYMENT.md             # 部署文档
│   │
│   └── api/                 # API 文档（自动生成）
│
├── logs/                    # 日志目录
│   ├── backtest/            # 回测日志
│   ├── live/                # 实盘日志
│   └── system/              # 系统日志
│
├── configs/                 # 配置文件目录
│   ├── strategy/            # 策略配置
│   ├── risk/                # 风控配置
│   ├── broker/              # 券商/通道配置
│   └── system.json          # 系统级配置
│
├── scripts/                 # 脚本目录
│   ├── data_fetch.py        # 数据采集脚本
│   ├── factor_build.py      # 因子构建脚本
│   ├── backtest_run.py      # 回测运行脚本
│   └── deploy.sh            # 部署脚本
│
├── src/                     # 源代码目录
│   ├── data/                # 数据层
│   │   ├── fetcher.py       # 数据获取模块
│   │   ├── cleaner.py       # 数据清洗模块
│   │   ├── storage.py       # 数据存储模块
│   │   └── loader.py         # 数据加载模块
│   │
│   ├── factors/             # 因子层
│   │   ├── price_factors.py # 量价因子
│   │   ├── fund_factors.py  # 财务因子
│   │   ├── alt_factors.py    # 另类因子
│   │   └── factor_cache.py  # 因子缓存
│   │
│   ├── strategy/            # 策略层
│   │   ├── base.py          # 策略基类
│   │   ├── portfolio.py     # 组合管理
│   │   ├── signal_gen.py    # 信号生成
│   │   └── strategies/      # 具体策略实现
│   │       ├── trend.py     # 趋势策略
│   │       ├── arbitrage.py # 套利策略
│   │       └── value.py     # 价值策略
│   │
│   ├── execution/            # 执行层
│   │   ├── order_manager.py # 订单管理
│   │   ├── broker_adapter.py # 券商适配器
│   │   ├── algos/           # 算法交易
│   │   │   ├── twap.py      # TWAP 算法
│   │   │   ├── vwap.py      # VWAP 算法
│   │   │   └── iceberg.py   # 冰山订单
│   │   └── execution.py     # 执行引擎
│   │
│   ├── risk/                # 风控层
│   │   ├── risk_manager.py  # 风控管理器
│   │   ├── position_limit.py # 仓位限制
│   │   ├── loss_limit.py    # 亏损限制
│   │   └── compliance.py    # 合规校验
│   │
│   ├── monitor/             # 监控层
│   │   ├── dashboard.py     # 监控面板
│   │   ├── logger.py        # 日志记录
│   │   ├── alerter.py       # 报警模块
│   │   └── performance.py   # 绩效归因
│   │
│   └── utils/               # 工具模块
│       ├── config.py        # 配置管理
│       ├── date_utils.py   # 日期工具
│       ├── math_utils.py   # 数学工具
│       └── validators.py    # 数据校验
│
└── tests/                   # 测试目录
    ├── unit/                # 单元测试
    │   ├── test_factors.py
    │   ├── test_strategy.py
    │   └── test_risk.py
    │
    └── integration/         # 集成测试
        ├── test_backtest.py
        └── test_live.py
```

---

## 目录说明

### data/ — 数据存储
所有数据文件，按**原始数据 → 清洗数据 → 因子数据 → 回测/实盘数据**的流程组织。

### docs/ — 文档
系统设计文档、接口规范、部署文档等。

### logs/ — 日志
回测日志、实盘日志、系统日志，便于问题排查和审计。

### configs/ — 配置
策略参数、风控规则、券商通道等配置文件，**敏感信息（如 API Key）通过环境变量注入，不硬编码**。

### scripts/ — 脚本
数据采集、因子构建、回测运行等一次性脚本。

### src/ — 核心代码
6 大核心模块：
| 模块 | 职责 |
|------|------|
| `data` | 数据采集、清洗、存储、加载 |
| `factors` | 因子计算与管理 |
| `strategy` | 策略研发与信号生成 |
| `execution` | 订单管理与交易执行 |
| `risk` | 实时风控与合规校验 |
| `monitor` | 监控面板、报警、绩效归因 |

### tests/ — 测试
单元测试 + 集成测试，确保代码质量。

---

## 命名规范

- **文件命名**：`snake_case`（如 `risk_manager.py`）
- **类命名**：`PascalCase`（如 `RiskManager`）
- **函数命名**：`snake_case`（如 `calculate_sharpe_ratio`）
- **常量命名**：`UPPER_SNAKE_CASE`（如 `MAX_POSITION_SIZE`）

---

*本文档由脚本自动生成，最后更新：2026-04-19*
