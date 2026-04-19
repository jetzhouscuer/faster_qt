# 系统架构设计文档

> 本文档定义了 faster_qt 量化交易系统的整体架构设计，作为后续开发的技术蓝图。

---

## 1. 系统概述

### 1.1 项目定位

**faster_qt** 是一个面向个人投资者的量化交易研究框架，专注于 A 股市场，目标是实现从**数据采集 → 因子研究 → 策略回测 → 实盘执行 → 风险监控**的全链路自动化。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **模块化** | 各层之间通过明确定义的接口通信，便于独立开发、测试、替换 |
| **低耦合** | 核心逻辑不依赖具体券商 API，通过适配器模式隔离 |
| **可观测** | 全链路日志、指标埋点，便于问题排查和性能分析 |
| **回测≠实盘** | 架构上明确区分回测环境与实盘环境，避免混合导致的风控漏洞 |
| **数据优先** | 因子、策略、绩效均基于统一的数据模型，避免数据不一致 |
| **数据质量是生命线** | 量化系统的收益来源本质是对数据的认知差，数据质量直接决定策略上限 |

---

## 2. 整体架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           faster_qt 量化交易系统                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                          外部数据源                                   │    │
│  │  交易所直连 │ Tushare │ AKShare │ 掘金/QMT │ 宏观数据 │ 另类数据        │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        数据层（Data Layer） ⭐基石                      │    │
│  │                                                                       │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │    │
│  │  │ 历史数据采集  │ │ 增量数据采集  │ │ 实时数据流   │ │ 数据质量校验  │ │    │
│  │  │Historical    │ │ Incremental  │ │ RealtimeFeed │ │Quality Check │ │    │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ │    │
│  │         └────────────────┴────────────────┴─────────────────┘         │    │
│  │                               ▼                                        │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │    │
│  │  │                       主数据层（Master Data）                      │ │    │
│  │  │   symbols │ trading_calendar │ fundamental_calendar │ broker_info  │ │    │
│  │  └──────────────────────────────────────────────────────────────────┘ │    │
│  │                               ▼                                        │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │    │
│  │  │                    存储层（Storage Layer）                         │ │    │
│  │  │  TimescaleDB(K线/因子) │ Redis(热缓存) │ MinIO/Parquet(归档)   │ │    │
│  │  └──────────────────────────────────────────────────────────────────┘ │    │
│  │                               ▼                                        │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │    │
│  │  │                   数据服务层（Data Service）                        │ │    │
│  │  │      DataLoader │ FactorEngine │ RealtimePusher │ DataValidator   │ │    │
│  │  └──────────────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       因子层（Factor Layer）                           │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │    │
│  │  │ 量价因子  │  │ 财务因子  │  │ 另类因子  │  │ 因子IC追踪│              │    │
│  │  │ (Price)  │  │ (Fund.)  │  │ (Alt.)   │  │(IC Track)│              │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       策略层（Strategy Layer）                        │    │
│  │                                                                       │    │
│  │  ┌──────────────────┐         ┌──────────────────┐                   │    │
│  │  │    回测引擎       │         │    模拟交易       │                   │    │
│  │  │  (Backtester)    │         │ (Paper Trading)  │                   │    │
│  │  └────────┬─────────┘         └────────┬─────────┘                   │    │
│  │           └──────────────┬───────────────┘                            │    │
│  │                          ▼                                              │    │
│  │               ┌──────────────────┐                                   │    │
│  │               │   信号生成模块     │                                    │    │
│  │               │  (Signal Engine)  │                                    │    │
│  │               └────────┬─────────┘                                    │    │
│  │                        ▼                                               │    │
│  │  ┌─────────────────────────────────────────────────────────────┐     │    │
│  │  │                    策略列表                                    │     │    │
│  │  │  趋势策略 │ 套利策略 │ 价值策略 │ 事件驱动 │ 多因子策略            │     │    │
│  │  └─────────────────────────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       执行层（Execution Layer）                      │    │
│  │                                                                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │  │ 订单管理  │  │ 券商适配  │  │ 算法交易  │  │ 仓位管理  │           │    │
│  │  │  (OMS)   │  │(Broker)  │  │ (Algos)  │  │(Position)│           │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       风控层（Risk Layer）                           │    │
│  │                                                                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │  │ 仓位限制  │  │ 亏损限制  │  │ 合规校验  │  │ 流动性管理│           │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       监控层（Monitor Layer）                        │    │
│  │                                                                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │  │ 监控面板  │  │ 日志审计  │  │ 绩效归因  │  │ 报警通知  │           │    │
│  │  │(Dashboard)│  │ (Logger) │  │(Perf.)   │  │ (Alerts) │           │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 分层说明

| 层级 | 职责 | 关键模块 | 技术选型 |
|------|------|---------|---------|
| **数据层** ⭐ | 采集、清洗、存储、校验市场数据 | Historical/Incremental/Realtime Fetcher, Master Data, Storage, DataService | PostgreSQL + TimescaleDB, Redis, Kafka |
| **因子层** | 计算与管理量化因子 | PriceFactors, FundFactors, AltFactors, FactorIC Tracker | NumPy, Pandas, Numba |
| **策略层** | 策略研发、回测、信号生成 | Backtester, SignalEngine, Portfolio | Backtrader, Zipline, 自研 |
| **执行层** | 订单路由、算法交易、通道对接 | OMS, BrokerAdapter, Algos | Python, C++ (高频) |
| **风控层** | 实时风控、合规校验 | RiskManager, PositionLimit, LossLimit | 规则引擎 |
| **监控层** | 日志、性能、报警 | Dashboard, Logger, Alerter, Performance | Grafana, Prometheus, Plotly |

---

## 3. 核心模块详细设计

### 3.1 数据层（Data Layer）⭐ 基石

> **数据是量化系统的基石**。数据质量直接决定策略上限，而量化系统的收益本质是对数据的认知差。本层设计围绕"高质量数据闭环"展开。

#### 3.1.1 模块职责

- **主数据管理**：维护证券基础信息、交易日历、财务报告期
- **数据采集**：历史全量采集 + 增量实时采集 + 交易所直连
- **数据清洗**：复权处理、缺失值填充、去噪、格式标准化
- **数据校验**：完整性、一致性、时效性校验
- **数据存储**：分层存储（热数据/冷数据/归档）
- **数据服务**：统一加载接口、因子计算引擎、实时推送

#### 3.1.2 数据源矩阵

| 数据类型 | 数据源 | 更新频率 | 延迟 | 存储位置 | 重要性 |
|---------|-------|---------|------|---------|--------|
| **日线行情** | Tushare / AKShare | 日终（T+1） | 15:30后 | `data/cleaned/daily/` | ⭐⭐⭐ |
| **分钟线** | 掘金量化 / QMT | 实时 | <1s | `data/cleaned/minute/` | ⭐⭐⭐ |
| **Tick数据** | 掘金量化 / QMT | 实时 | <1s | `data/raw/tick/` | ⭐⭐ |
| **财务数据** | Tushare / 财报 | 季度 | 公告日后1天 | `data/cleaned/fundamental/` | ⭐⭐⭐ |
| **指数成分** | 中证指数公司 | 不定期 | 不定期 | `data/raw/index/` | ⭐⭐ |
| **资金流向** | 东方财富 | 日终 | 17:00后 | `data/raw/flow/` | ⭐⭐ |
| **北向资金** | 港交所 | 日终 | 17:30后 | `data/raw/north_flow/` | ⭐⭐ |
| **舆情数据** | 东方财富/同花顺 | 实时 | 分钟级 | `data/raw/sentiment/` | ⭐ |
| **龙虎榜** | 上交所/深交所 | 日终 | 20:00后 | `data/raw/top_trades/` | ⭐ |
| **大宗交易** | 沪深交易所 | 日终 | 15:00后 | `data/raw/block_trade/` | ⭐ |

#### 3.1.3 主数据层（Master Data）

主数据是量化系统的"黄页"，所有业务表通过 symbol 关联主数据，确保数据一致性。

```python
class MasterDataManager:
    """主数据管理器"""

    def __init__(self, storage: DataStorage):
        self.storage = storage

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """获取证券基本信息"""
        pass

    def is_trading_day(self, date: date, exchange: str = "SH") -> bool:
        """判断是否为交易日"""
        pass

    def get_next_trading_day(self, date: date, n: int = 1) -> date:
        """获取未来第N个交易日"""
        pass

    def get_fundamental_calendar(self, symbol: str,
                                  fiscal_year: int) -> List[FundamentalReport]:
        """获取财务报告期日历（用于前视偏差规避）"""
        pass

    def get_index_components(self, index_code: str,
                             date: date) -> List[str]:
        """获取指数成分股（考虑调样延迟）"""
        pass
```

#### 3.1.4 数据采集模块

```python
class DataSource(ABC):
    """数据源抽象基类"""
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称"""
        pass

    @abstractmethod
    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """拉取历史数据"""
        pass

    @abstractmethod
    def get_latest(self, symbol: str) -> pd.Series:
        """获取最新数据"""
        pass


class IncrementalFetcher:
    """增量数据采集器（用于日终增量更新）"""

    def __init__(self, sources: List[DataSource], storage: DataStorage):
        self.sources = sources
        self.storage = storage

    def daily_update(self, trade_date: date):
        """日终增量更新流程"""
        for source in self.sources:
            # 1. 获取该数据源的最新日期
            latest = self.storage.get_latest_date(source.category)

            # 2. 从上次更新日期+1天开始拉取
            data = source.fetch(symbols="*", start=latest + 1, end=trade_date)

            # 3. 数据质量校验
            validated = DataValidator.validate(source.category, data)

            # 4. 存储
            self.storage.save(source.category, validated)


class RealtimeFeed:
    """实时数据流（用于实盘）"""

    def __init__(self, broker_adapter: BrokerAdapter,
                 redis_client: Redis):
        self.broker = broker_adapter
        self.redis = redis_client
        self.subscribers: Dict[str, Callable] = {}

    def start(self, symbols: List[str]):
        """启动实时行情订阅"""
        self.broker.subscribe(symbols, callback=self._on_tick)

    def _on_tick(self, tick: TickData):
        """行情回调"""
        # 1. 发布到 Redis Pub/Sub
        self.redis.publish(f"tick:{tick.symbol}", tick.to_json())

        # 2. 更新 Redis Hash（最新价）
        self.redis.hset(f"realtime:{tick.symbol}",
                        mapping=tick.to_dict())

        # 3. 触发订阅者回调
        for callback in self.subscribers.get(tick.symbol, []):
            callback(tick)

    def subscribe(self, symbol: str, callback: Callable):
        """订阅特定股票行情"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)
```

#### 3.1.5 数据质量校验

```python
class DataQualityRule(ABC):
    """数据质量规则抽象"""

    @abstractmethod
    def check(self, data: pd.DataFrame) -> QualityResult:
        """执行校验"""
        pass


class DataValidator:
    """数据校验器"""

    RULES = {
        "bars": [
            PriceRangeRule(),       # 价格区间校验（避免0或异常值）
            VolumePositiveRule(),    # 成交量必须>0
            HighLowConsistentRule(), # high >= low
            CloseInRangeRule(),     # close在[low, high]区间
            TimeContinuityRule(),   # 时间连续性（检测缺失K线）
        ],
        "fundamental": [
            ValuePositiveRule(),    # 财务数据正值校验
            YoYChangeReasonableRule(), # 同比变化合理性
        ]
    }

    @classmethod
    def validate(cls, category: str,
                 data: pd.DataFrame) -> QualityResult:
        """执行指定类别的所有校验规则"""
        results = []
        for rule in cls.RULES.get(category, []):
            result = rule.check(data)
            results.append(result)

        passed = all(r.passed for r in results)
        return QualityResult(
            passed=passed,
            details=results,
            summary={
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed)
            }
        )


class TimeContinuityRule(DataQualityRule):
    """时间连续性校验（核心！检测K线缺失）"""

    def check(self, data: pd.DataFrame) -> QualityResult:
        expected_freq = infer_frequency(data["timestamp"])
        expected_times = generate_expected_times(
            data["timestamp"].min(),
            data["timestamp"].max(),
            expected_freq
        )
        actual_times = set(data["timestamp"])
        missing = set(expected_times) - actual_times

        if missing:
            return QualityResult(
                passed=False,
                reason=f"缺失 {len(missing)} 个K线，"
                       f"示例: {list(missing)[:5]}"
            )
        return QualityResult(passed=True)


class PriceRangeRule(DataQualityRule):
    """价格区间校验"""

    def check(self, data: pd.DataFrame) -> QualityResult:
        # 股价不应为0或负数
        invalid = data[(data["close"] <= 0) | (data["open"] <= 0)]
        if not invalid.empty:
            return QualityResult(
                passed=False,
                reason=f"存在 {len(invalid)} 条价格为0的记录"
            )

        # 股价不应超过合理区间（如茅台不会<100或>3000）
        # 此处应配置个股的合理价格区间
        return QualityResult(passed=True)
```

#### 3.1.6 数据存储架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据存储分层架构                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   热数据层 (Hot)      温数据层 (Warm)      冷数据层 (Cold)     归档层    │
│   ┌───────────┐     ┌───────────┐      ┌───────────┐    ┌──────────┐  │
│   │  Redis    │     │TimescaleDB│      │TimescaleDB│   │  MinIO   │  │
│   │ 内存数据库 │     │ 最近1年    │      │  1年前    │    │ Parquet  │  │
│   │ 实时行情   │     │ 日线/因子  │      │ 日线/因子  │    │ 历史归档  │  │
│   └───────────┘     └───────────┘      └───────────┘    └──────────┘  │
│                                                                         │
│   数据流向:                                                             │
│   实时 → Redis → TimescaleDB(最近1年) → MinIO/Parquet(归档)            │
│         ↓                                                              │
│      因子计算 → 结果存回 Redis/TimescaleDB                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

```python
class DataStorage:
    """统一数据存储引擎"""

    def __init__(self, db_url: str, redis_url: str, minio_url: str):
        self.db = create_engine(db_url)      # PostgreSQL + TimescaleDB
        self.cache = Redis.from_url(redis_url)  # Redis
        self.archive = MinioClient(minio_url)   # MinIO 历史归档

    # ============ 写入操作 ============

    def save(self, category: str, data: pd.DataFrame,
             environment: str = "BACKTEST"):
        """存储数据（根据频率自动分层）"""
        df = data.copy()
        df["environment"] = environment  # 隔离回测/实盘数据

        if self._is_realtime(category):
            # 实时数据 → Redis
            self._save_realtime(category, df)
        elif self._is_hot_data(category):
            # 热数据 → Redis + TimescaleDB
            self._save_hot(category, df)
        else:
            # 冷数据 → TimescaleDB
            self._save_cold(category, df)

    def _archive_if_needed(self, category: str, data: pd.DataFrame):
        """超过1年的数据自动归档到MinIO"""
        if self._is_old_data(data):
            partition = self._get_partition_key(data)
            self.archive.put_object(
                bucket=f"{category}_archive",
                object_name=f"{partition}.parquet",
                data=io.BytesIO(data.to_parquet()),
                length=len(data)
            )

    # ============ 读取操作 ============

    def load(self, category: str, symbol: str = None,
             start: date = None, end: date = None,
             environment: str = "BACKTEST") -> pd.DataFrame:
        """加载数据（自动从合适的层级读取）"""

        if self._is_realtime(category):
            return self._load_from_redis(category, symbol)

        if end and (date.today() - end).days <= 30:
            # 最近30天 → 尝试Redis + TimescaleDB
            return self._load_hot(category, symbol, start, end)
        else:
            # 30天以前 → TimescaleDB + MinIO
            return self._load_cold(category, symbol, start, end)

    def load_with_lookback(self, category: str, symbol: str,
                           reference_date: date,
                           lookback_days: int,
                           environment: str = "BACKTEST") -> pd.DataFrame:
        """
        关键方法：带lookback的数据加载（避免前视偏差）
        
        回测时，必须使用 reference_date 当天及之前的数据
        """
        start = self._get_trading_day(reference_date, -lookback_days)
        return self.load(category, symbol, start, reference_date, environment)
```

#### 3.1.7 实时数据流架构（实盘核心）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          实盘实时数据流架构                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   交易所 ───WebSocket──▶ 券商柜台(QMT/掘金) ──API──▶ DataFeed Server    │
│                                              │                         │
│                                              ▼                         │
│                                    ┌─────────────────┐               │
│                                    │  Redis Pub/Sub   │               │
│                                    │  (行情分发)      │               │
│                                    └────────┬────────┘               │
│                                             │                         │
│                        ┌────────────────────┼────────────────────┐    │
│                        ▼                    ▼                    ▼    │
│                 ┌──────────┐        ┌──────────┐         ┌──────────┐  │
│                 │ 策略进程  │        │ 风控进程  │         │ 监控进程  │  │
│                 │(Strategy)│        │ (Risk)   │         │(Monitor) │  │
│                 └──────────┘        └──────────┘         └──────────┘  │
│                                                                         │
│   DataFeed Server 同时：                                                │
│   1. 写入 TimescaleDB（历史积累）                                       │
│   2. 更新 Redis Hash（最新价）                                          │
│   3. 发布到 Redis Pub/Sub（实时分发）                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3.1.8 数据流程图（完整）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据全流程图                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ╔══════════════════╗                                                       │
│  ║   外部数据源      ║                                                       │
│  ╚════════╤═════════╝                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────┐                                                  │
│  │   历史全量采集        │  一次性 / 首次部署                               │
│  │  (HistoricalFetch)  │ ──▶ PostgreSQL / MinIO                          │
│  └─────────────────────┘                                                  │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────────┐                                                  │
│  │   增量数据采集        │  日终定时任务（Tushare/AKShare）                  │
│  │ (IncrementalFetch)  │                                                  │
│  └──────────┬──────────┘                                                  │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────┐     ┌─────────────────┐                         │
│  │   数据质量校验        │────▶│ 校验报告输出    │                         │
│  │  (DataValidator)    │     │ (失败则告警)    │                         │
│  └──────────┬──────────┘     └─────────────────┘                         │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────┐                                                  │
│  │   数据清洗           │  复权 / 缺失填充 / 去噪                          │
│  │   (DataCleaner)    │                                                  │
│  └──────────┬──────────┘                                                  │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────┐                                                  │
│  │   主数据对齐        │  symbol_id → symbol_code                          │
│  │ (MasterAlignment)  │  交易日历对齐 / 财务报告期对齐                      │
│  └──────────┬──────────┘                                                  │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        分层存储                                        │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │ │
│  │  │   Redis    │  │TimescaleDB │  │ TimescaleDB│  │   MinIO    │     │ │
│  │  │ (实时热数据)│  │ (最近1年)  │  │  (1年前)   │  │  (历史归档) │     │ │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        数据服务层                                     │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │ │
│  │  │ DataLoader │  │FactorEngine│  │RealtimePush│  │DataMonitor │     │ │
│  │  │ (统一加载)  │  │ (因子计算)  │  │ (实时推送)  │  │ (状态监控)  │     │ │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│             │                                                              │
│             ▼                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                 │
│  │   因子层     │   │   策略层     │   │   风控层     │                 │
│  │ (FactorLayer)│──▶│(StrategyLayer)│──▶│ (RiskLayer)  │                 │
│  └──────────────┘   └──────────────┘   └──────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 3.2 因子层（Factor Layer）

#### 3.2.1 因子分类

| 类别 | 子类 | 示例因子 | 计算频率 | 数据来源 |
|------|------|---------|---------|---------|
| **量价因子** | 趋势类 | MA, EMA, MACD, DMA | 日/分钟 | bars |
| | 波动类 | Bollinger, ATR, STD | 日/分钟 | bars |
| | 动量类 | RSI, ROC, CCI | 日/分钟 | bars |
| | 成交量类 | VOL, VMAP, OBV | 日/分钟 | bars |
| **财务因子** | 估值类 | PE, PB, PS, PCF | 季度 | fundamental |
| | 成长类 | 营收增速, 利润增速, ROE | 季度 | fundamental |
| | 质量类 | 资产负债率, 现金流/负债 | 季度 | fundamental |
| **另类因子** | 情绪类 | 新闻情绪, 研报情绪 | 日 | alternative |
| | 资金流类 | 主力净流入, 超大单净流入 | 日 | flow |
| | 舆情类 | 社交媒体热度, 搜索指数 | 日 | alternative |

#### 3.2.2 因子计算规范

```python
class BaseFactor(ABC):
    """因子抽象基类"""
    name: str  # 因子名称
    category: str  # 因子类别
    update_freq: str  # 更新频率（日/分钟/季度）
    dependencies: List[str]  # 依赖的数据类别

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算因子"""
        pass

    def validate(self, factor_value: pd.Series) -> bool:
        """因子值校验（去极值、归一化）"""
        pass


class FactorEngine:
    """因子计算引擎"""

    def __init__(self, storage: DataStorage,
                 ic_tracker: 'FactorICTracker'):
        self.storage = storage
        self.ic_tracker = ic_tracker

    def calculate_factor(self, factor: BaseFactor,
                         symbols: List[str],
                         start: date, end: date) -> pd.DataFrame:
        """计算因子（带缓存+增量计算）"""
        # 1. 检查因子缓存
        cached = self._get_cached_factor(factor.name, symbols, end)
        if cached is not None:
            return cached

        # 2. 加载依赖数据
        data = self._load_dependency_data(factor.dependencies,
                                          symbols, start, end)

        # 3. 计算因子
        result = factor.calculate(data)

        # 4. 因子后处理（去极值、标准化）
        result = self._post_process(result)

        # 5. 存储因子值
        self._save_factor(factor.name, result)

        # 6. 更新因子IC追踪
        self.ic_tracker.update(factor.name, result, end)

        return result


class FactorICTracker:
    """因子IC追踪器（核心！用于因子有效性监控）"""

    def __init__(self, storage: DataStorage):
        self.storage = storage

    def update(self, factor_name: str, factor_values: pd.Series,
               calc_date: date):
        """更新因子IC"""
        # 计算IC（因子值与下期收益的相关系数）
        returns = self._get_forward_returns(factor_values.index, calc_date)
        ic = factor_values.corr(returns, method="spearman")  # Rank IC

        # 计算IR（IC均值/IC标准差）
        recent_ic = self._get_recent_ic(factor_name, window=20)
        ir = ic / recent_ic.std() if len(recent_ic) > 1 else 0

        record = {
            "factor_name": factor_name,
            "test_date": calc_date,
            "ic_value": ic,
            "ir_value": ir,
            "rank_ic": ic
        }
        self.storage.save("factor_ic", pd.DataFrame([record]))

    def is_effective(self, factor_name: str) -> bool:
        """判断因子是否有效（IC_IR > 0.5）"""
        recent_ir = self._get_recent_ir(factor_name, window=60)
        return recent_ir > 0.5
```

#### 3.2.3 因子存储

```sql
-- 因子数据表（TimescaleDB 超表）

CREATE TABLE factor_values (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    factor_name TEXT NOT NULL,
    value       DOUBLE PRECISION,
    environment TEXT NOT NULL,               -- BACKTEST / PAPER / LIVE
    PRIMARY KEY (time, symbol, factor_name, environment)
);

SELECT create_hypertable('factor_values', 'time');

-- 因子IC追踪表

CREATE TABLE factor_ic (
    factor_name     TEXT NOT NULL,
    test_date       DATE NOT NULL,
    ic_value        NUMERIC(10, 6),
    ir_value        NUMERIC(10, 6),
    rank_ic         NUMERIC(10, 6),
    long_return     NUMERIC(10, 6),
    short_return    NUMERIC(10, 6),
    spread_return   NUMERIC(10, 6),
    sample_count    INTEGER,
    PRIMARY KEY (factor_name, test_date)
);

CREATE INDEX idx_ic_factor_date ON factor_ic(factor_name, test_date DESC);
```

---

### 3.3 策略层（Strategy Layer）

#### 3.3.1 策略基类设计

```python
class BaseStrategy(ABC):
    """策略抽象基类"""

    def __init__(self, name: str, params: dict):
        self.name = name
        self.params = params
        self.positions: Dict[str, float] = {}
        self.signals: List[Signal] = []

    @abstractmethod
    def on_bar(self, bar: Bar) -> List[Order]:
        """每个bar回调，返回订单列表"""
        pass

    @abstractmethod
    def get_signals(self, data: pd.DataFrame) -> pd.Series:
        """生成交易信号"""
        pass

    def calculate_position_size(self, signal: Signal,
                                 price: float) -> float:
        """计算仓位"""
        pass


class Signal:
    """交易信号"""
    def __init__(self, symbol: str, direction: Direction,
                 strength: float, timestamp: datetime):
        self.symbol = symbol
        self.direction = direction
        self.strength = strength
        self.timestamp = timestamp
```

#### 3.3.2 回测引擎

```python
class Backtester:
    """回测引擎"""

    def __init__(self, strategy: BaseStrategy,
                 data_loader: DataLoader,
                 initial_cash: float = 1000000):
        self.strategy = strategy
        self.data_loader = data_loader
        self.initial_cash = initial_cash
        self.results: BacktestResult = None

    def run(self, start: date, end: date,
            symbols: List[str]) -> BacktestResult:
        """运行回测"""
        bars = self.data_loader.load_bars(symbols, start, end)

        for bar in bars:
            orders = self.strategy.on_bar(bar)
            orders = self.risk_precheck(orders)
            self.execute_orders(orders, bar)
            self.update_positions(bar)

        return self.generate_report()

    def generate_report(self) -> BacktestResult:
        """生成回测报告"""
        return BacktestResult(
            total_return=self.equity[-1] / self.equity[0] - 1,
            sharpe_ratio=calculate_sharpe(self.returns),
            max_drawdown=calculate_max_drawdown(self.equity),
            win_rate=calculate_win_rate(self.trades),
            total_trades=len(self.trades),
            equity_curve=self.equity
        )
```

#### 3.3.3 策略列表

| 策略类型 | 策略名称 | 说明 | 状态 |
|---------|---------|------|------|
| 趋势跟踪 | `trend_ma_cross` | 均线金叉死叉 | 🔨 开发中 |
| 趋势跟踪 | `trend_breakout` | 布林带突破 | 📋 待开发 |
| 均值回归 | `mean_reversion` | 期货跨期套利 | 📋 待开发 |
| 多因子 | `factor_value` | 价值因子选股 | 📋 待开发 |
| 事件驱动 | `event_st` | ST 摘帽事件 | 📋 待开发 |

---

### 3.4 执行层（Execution Layer）

#### 3.4.1 订单管理

```python
class Order:
    """订单"""
    def __init__(self, symbol: str, direction: Direction,
                 volume: float, price: float = 0,
                 order_type: OrderType = OrderType.MARKET):
        self.order_id = generate_order_id()
        self.symbol = symbol
        self.direction = direction
        self.volume = volume
        self.price = price
        self.order_type = order_type
        self.status = OrderStatus.PENDING
        self.created_at = datetime.now()


class OrderManager:
    """订单管理器（OMS）"""

    def __init__(self, risk_manager: RiskManager):
        self.pending_orders: Dict[str, Order] = {}
        self.filled_orders: List[Order] = []
        self.risk_manager = risk_manager

    def submit_order(self, order: Order) -> bool:
        """提交订单"""
        if not self.risk_manager.pre_check(order):
            return False

        self.pending_orders[order.order_id] = order
        self.broker_adapter.send_order(order)
        return True

    def on_order_return(self, ret: OrderReturn):
        """处理订单回报"""
        order = self.pending_orders.get(ret.order_id)
        if order:
            order.status = ret.status
            if ret.status == OrderStatus.FILLED:
                self.filled_orders.append(order)
                del self.pending_orders[order.order_id]
```

#### 3.4.2 券商适配器

```python
class BrokerAdapter(ABC):
    """券商适配器抽象基类"""

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def send_order(self, order: Order) -> bool:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        pass


class QMAdapter(BrokerAdapter):
    """QMT（迅投）券商适配器"""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.api = None

    def send_order(self, order: Order) -> bool:
        pass


class GmAdapter(BrokerAdapter):
    """掘金量化券商适配器"""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.api = None

    def send_order(self, order: Order) -> bool:
        pass
```

#### 3.4.3 算法交易

```python
class BaseAlgo(ABC):
    """算法交易基类"""

    @abstractmethod
    def execute(self, order: Order, market_data: MarketData):
        pass


class TWAPAlgo(BaseAlgo):
    """TWAP（时间加权平均）算法"""

    def __init__(self, duration_minutes: int = 60):
        self.duration = duration_minutes
        self.slice_count = duration_minutes
        self.executed = 0

    def execute(self, order: Order, market_data: MarketData):
        slice_size = order.volume / (self.slice_count - self.executed)
        child_order = Order(
            symbol=order.symbol,
            direction=order.direction,
            volume=slice_size,
            order_type=OrderType.LIMIT,
            price=market_data.best_bid
        )
        self.order_manager.submit_order(child_order)
        self.executed += 1


class VWAPAlgo(BaseAlgo):
    """VWAP（成交量加权平均）算法"""

    def execute(self, order: Order, market_data: MarketData):
        pass


class IcebergAlgo(BaseAlgo):
    """冰山订单算法"""

    def __init__(self, display_ratio: float = 0.1):
        self.display_ratio = display_ratio

    def execute(self, order: Order, market_data: MarketData):
        pass
```

---

### 3.5 风控层（Risk Layer）

#### 3.5.1 风控规则矩阵

| 规则类型 | 规则名称 | 阈值 | 触发动作 |
|---------|---------|------|---------|
| 仓位限制 | 单票仓位上限 | 10% | 拒绝下单 |
| 仓位限制 | 行业仓位上限 | 30% | 拒绝下单 |
| 亏损限制 | 单日最大亏损 | -3% | 停止交易，报警 |
| 亏损限制 | 单笔最大亏损 | -2% | 拒绝下单 |
| 亏损限制 | 最大回撤 | -15% | 策略暂停 |
| 流动性限制 | 最小成交量 | 日均成交>5000万 | 拒绝下单 |
| 流动性限制 | 持仓周期上限 | 20日 | 强制平仓 |
| 合规限制 | 创业板持仓 | ≤总仓位30% | 拒绝下单 |
| 合规限制 | 科创板持仓 | ≤总仓位20% | 拒绝下单 |

#### 3.5.2 风控引擎

```python
class RiskRule(ABC):
    """风控规则抽象基类"""

    @abstractmethod
    def check(self, order: Order,
              context: RiskContext) -> RiskResult:
        pass


class RiskManager:
    """风控管理器"""

    def __init__(self, rules: List[RiskRule]):
        self.rules = rules
        self.daily_pnl = 0.0
        self.max_drawdown = 0.0

    def pre_check(self, order: Order) -> bool:
        """下单前风控检查（Pre-Trade）"""
        context = self.build_context(order)

        for rule in self.rules:
            result = rule.check(order, context)
            if not result.passed:
                logger.warning(f"风控拒绝: {result.reason}")
                return False

        return True

    def post_check(self, trade: Trade):
        """成交后风控检查（Post-Trade）"""
        self.update_positions(trade)
        self.update_pnl(trade)

        if self.daily_pnl < -self.daily_loss_limit:
            self.trigger_stop_loss()

    def build_context(self, order: Order) -> RiskContext:
        """构建风控上下文"""
        return RiskContext(
            account=self.get_account_info(),
            positions=self.get_positions(),
            pending_orders=self.get_pending_orders(),
            market=self.get_market_data(order.symbol)
        )


class PositionLimitRule(RiskRule):
    """仓位限制规则"""

    def __init__(self, max_position_pct: float = 0.1):
        self.max_position_pct = max_position_pct

    def check(self, order: Order, context: RiskContext) -> RiskResult:
        current_pos = context.positions.get(order.symbol, 0)
        new_pos_pct = (current_pos + order.volume) / context.account.total_value

        if new_pos_pct > self.max_position_pct:
            return RiskResult(
                passed=False,
                reason=f"仓位 {new_pos_pct:.2%} 超过上限 {self.max_position_pct:.2%}"
            )

        return RiskResult(passed=True)


class DailyLossLimitRule(RiskRule):
    """日亏损限制规则"""

    def __init__(self, max_daily_loss: float = -0.03):
        self.max_daily_loss = max_daily_loss

    def check(self, order: Order, context: RiskContext) -> RiskResult:
        estimated_loss = self.estimate_order_loss(order, context)

        if context.account.daily_pnl + estimated_loss < self.max_daily_loss:
            return RiskResult(
                passed=False,
                reason=f"预计日亏损 {context.account.daily_pnl + estimated_loss:.2%} "
                       f"超过限制 {self.max_daily_loss:.2%}"
            )

        return RiskResult(passed=True)
```

---

### 3.6 监控层（Monitor Layer）

#### 3.6.1 监控指标体系

| 类别 | 指标名称 | 描述 | 告警阈值 |
|------|---------|------|---------|
| **交易指标** | 订单成交率 | 成交订单/总订单 | < 95% |
| | 平均滑点 | 平均成交价 vs 委托价 | > 0.5% |
| | 日交易次数 | 每日成交笔数 | > 100 |
| **绩效指标** | 日收益率 | 当日收益率 | < -3% |
| | 最大回撤 | 历史最大回撤 | > -15% |
| | 夏普比率 | 风险调整收益 | < 0.5 |
| **风控指标** | 风险度 | (持仓市值/总资产) | > 80% |
| | 空余资金 | 可用资金 | < 10% |
| **系统指标** | 延迟 | 订单提交到成交耗时 | > 5s |
| | CPU使用率 | 系统资源 | > 80% |

#### 3.6.2 日志规范

```python
class Logger:
    """统一日志记录器"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def debug(self, msg: str, **kwargs):
        self.logger.debug(self._format(msg, kwargs))

    def info(self, msg: str, **kwargs):
        self.logger.info(self._format(msg, kwargs))

    def warning(self, msg: str, **kwargs):
        self.logger.warning(self._format(msg, kwargs))

    def error(self, msg: str, **kwargs):
        self.logger.error(self._format(msg, kwargs))

    def _format(self, msg: str, kwargs: dict) -> str:
        extra = json.dumps(kwargs) if kwargs else ""
        return f"{self.get_timestamp()} | {msg} | {extra}"


logger = Logger("execution")
logger.info("订单提交", order_id="ORD_001", symbol="600519",
            volume=1000, price=1800.0)
logger.warning("风控拒绝", order_id="ORD_002", reason="仓位超限")
logger.error("成交失败", order_id="ORD_003", error="网络超时")
```

#### 3.6.3 报警机制

```python
class Alerter:
    """报警模块"""

    def __init__(self):
        self.channels = {
            "feishu": FeishuWebhook(),
            "email": EmailSender(),
        }

    def send_alert(self, level: AlertLevel, title: str,
                   message: str, channels: List[str] = None):
        if channels is None:
            channels = ["feishu"]

        alert = Alert(
            level=level,
            title=title,
            message=message,
            timestamp=datetime.now()
        )

        for channel in channels:
            self.channels[channel].send(alert)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


alerter = Alerter()

if daily_pnl < -0.03:
    alerter.send_alert(
        level=AlertLevel.CRITICAL,
        title="⚠️ 日亏损超限",
        message=f"当日亏损 {daily_pnl:.2%}，已触发 -3% 止损线，请及时处理！"
    )

if fill_rate < 0.95:
    alerter.send_alert(
        level=AlertLevel.WARNING,
        title="📉 成交率异常",
        message=f"订单成交率 {fill_rate:.2%}，低于 95%，请检查通道"
    )

if signal_count > 1000:
    alerter.send_alert(
        level=AlertLevel.ERROR,
        title="🔥 信号风暴",
        message=f"单日信号数 {signal_count}，疑似信号异常，请检查"
    )
```

---

## 4. 数据模型（核心！）

### 4.1 核心数据模型（Entity Relationship）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           核心数据实体关系图                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                                                            │
│  │  symbols   │◀──Master Data（所有业务表的主数据）                         │
│  │ (主数据)    │                                                            │
│  ├─────────────┤                                                            │
│  │ symbol     │ 证券代码 "600519.SH"                                         │
│  │ name       │ 证券名称 "贵州茅台"                                           │
│  │ type       │ 类型 STOCK/INDEX/FUND                                       │
│  │ exchange   │ 交易所 SH/SZ/BJ                                             │
│  │ board      │ 板块 MAIN/GEM/STAR                                          │
│  │ sector     │ 行业（中信）                                                 │
│  │ listed_date│ 上市日期                                                     │
│  │ delisted   │ 退市日期                                                     │
│  │ is_active  │ 是否在交易                                                   │
│  └──────┬──────┘                                                            │
│         │                                                                    │
│         │ 1:N                                                               │
│         ▼                                                                    │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │    bars     │     │fundamental  │     │  positions  │                   │
│  │   (K线)     │     │  (财务)     │     │   (持仓)    │                   │
│  ├─────────────┤     ├─────────────┤     ├─────────────┤                   │
│  │ symbol FK  │     │ symbol FK   │     │ symbol FK   │                   │
│  │ timestamp  │     │ report_date │     │ volume      │                   │
│  │ open/high  │     │ revenue     │     │ avg_cost    │                   │
│  │ low/close  │     │ net_profit  │     │ market_value│                   │
│  │ volume     │     │ ...        │     │ unrealized  │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                    │                    │                         │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                    account_ledger (账户流水)                  │           │
│  │  ─────────────────────────────────────────────────────────  │           │
│  │  event_type: DEPOSIT/WITHDRAW/BUY/SELL/DIVIDEND/FEE         │           │
│  │  symbol: 股票代码（交易相关）                                  │           │
│  │  direction: LONG/SHORT                                       │           │
│  │  volume/price/amount/commission                             │           │
│  │  balance: 发生后资金余额（不可篡改）                          │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   orders    │────▶│   trades    │     │  factor_ic  │                   │
│  │   (订单)    │     │   (成交)    │     │ (因子IC追踪) │                   │
│  ├─────────────┤     ├─────────────┤     ├─────────────┤                   │
│  │ order_id   │     │ trade_id   │     │ factor_name │                   │
│  │ symbol     │     │ order_id FK│     │ test_date   │                   │
│  │ direction  │     │ symbol     │     │ ic_value   │                   │
│  │ volume     │     │ volume     │     │ ir_value   │                   │
│  │ price      │     │ price      │     │ rank_ic    │                   │
│  │ status     │     │ commission │     └─────────────┘                   │
│  │ created_at │     │ traded_at   │                                        │
│  └─────────────┘     └─────────────┘                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 主数据表设计

```sql
-- ============ 证券主数据 ============

CREATE TABLE symbols (
    symbol          TEXT PRIMARY KEY,      -- "600519.SH"
    name            TEXT NOT NULL,         -- "贵州茅台"
    type            TEXT NOT NULL,         -- STOCK / INDEX / FUND / FUTURES / OPTION
    exchange        TEXT NOT NULL,         -- SH / SZ / BJ / HK
    board           TEXT,                   -- MAIN / GEM / STAR（股票特有）
    sector           TEXT,                   -- 所属行业（中信一级）
    market_value    NUMERIC(20, 2),         -- 总市值（用于过滤大盘/小盘）
    float_shares    NUMERIC(20, 2),         -- 流通股本
    listing_date    DATE,                   -- 上市日期
    delist_date     DATE,                   -- 退市日期
    is_active       BOOLEAN DEFAULT TRUE,  -- 是否在交易
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, listing_date)           -- 同一股票不同上市阶段
);

CREATE INDEX idx_symbol_exchange ON symbols(exchange);
CREATE INDEX idx_symbol_board ON symbols(board);
CREATE INDEX idx_symbol_sector ON symbols(sector);
CREATE INDEX idx_symbol_active ON symbols(is_active);


-- ============ 交易日历 ============

CREATE TABLE trading_calendar (
    trade_date     DATE NOT NULL,
    exchange       TEXT NOT NULL,         -- SH / SZ
    is_trading_day BOOLEAN NOT NULL,       -- 是否交易
    market_open     TIMESTAMPTZ,           -- 开市时间
    market_close    TIMESTAMPTZ,           -- 收市时间
    pre_open        TIMESTAMPTZ,           -- 盘前开始
    pre_close       TIMESTAMPTZ,           -- 盘前结束
    PRIMARY KEY (trade_date, exchange)
);

CREATE INDEX idx_calendar_exchange_date ON trading_calendar(exchange, trade_date);
CREATE INDEX idx_calendar_trading ON trading_calendar(is_trading_day);


-- ============ 财务报告期日历 ============

CREATE TABLE fundamental_calendar (
    symbol          TEXT NOT NULL,
    report_type     TEXT NOT NULL,         -- Q1 / Q2 / Q3 / Q4 / FY（一季报/年报等）
    report_date     DATE NOT NULL,         -- 报告期截止日（财报自然日期）
    fiscal_year     INTEGER NOT NULL,      -- 财政年度
    fiscal_quarter  INTEGER,               -- 财政季度（1-4）
    announcement_date DATE NOT NULL,       -- 公告发布日期（数据可用日期）
    is_estimated    BOOLEAN DEFAULT FALSE, -- 是否为预测数据
    PRIMARY KEY (symbol, report_type, report_date)
);

CREATE INDEX idx_fund_cal_symbol ON fundamental_calendar(symbol);
CREATE INDEX idx_fund_cal_date ON fundamental_calendar(announcement_date);
CREATE INDEX idx_fund_cal_fiscal ON fundamental_calendar(fiscal_year, fiscal_quarter);
```

### 4.3 K线与行情数据表

```sql
-- ============ K线数据（TimescaleDB 超表）============

CREATE TABLE bars (
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,          -- 1m / 5m / 15m / 30m / 1h / 1d / 1w
    timestamp       TIMESTAMPTZ NOT NULL,
    open            NUMERIC(10, 3),
    high            NUMERIC(10, 3),
    low             NUMERIC(10, 3),
    close           NUMERIC(10, 3),
    volume          BIGINT,
    amount          NUMERIC(20, 3),
    factor          NUMERIC(10, 6),        -- 复权因子（用于还原真实价格）
    environment     TEXT NOT NULL DEFAULT 'BACKTEST',  -- BACKTEST / PAPER / LIVE
    PRIMARY KEY (symbol, timeframe, timestamp, environment)
);

SELECT create_hypertable('bars', 'timestamp', 
    chunk_time_interval => INTERVAL '30 days');

CREATE INDEX idx_bars_symbol_time ON bars(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_bars_env ON bars(environment);


-- ============ Tick 数据（高频行情）============

CREATE TABLE ticks (
    symbol          TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    last_price      NUMERIC(10, 3),
    last_volume     BIGINT,
    bid_price_1     NUMERIC(10, 3),
    bid_price_2     NUMERIC(10, 3),
    bid_price_3     NUMERIC(10, 3),
    bid_price_4     NUMERIC(10, 3),
    bid_price_5     NUMERIC(10, 3),
    ask_price_1     NUMERIC(10, 3),
    ask_price_2     NUMERIC(10, 3),
    ask_price_3     NUMERIC(10, 3),
    ask_price_4     NUMERIC(10, 3),
    ask_price_5     NUMERIC(10, 3),
    bid_volume_1    BIGINT,
    bid_volume_2    BIGINT,
    bid_volume_3    BIGINT,
    bid_volume_4    BIGINT,
    bid_volume_5    BIGINT,
    ask_volume_1    BIGINT,
    ask_volume_2    BIGINT,
    ask_volume_3    BIGINT,
    ask_volume_4    BIGINT,
    ask_volume_5    BIGINT,
    total_volume    BIGINT,
    total_amount    NUMERIC(20, 3),
    environment     TEXT NOT NULL DEFAULT 'BACKTEST',
    PRIMARY KEY (symbol, timestamp, environment)
);

SELECT create_hypertable('ticks', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_ticks_symbol_time ON ticks(symbol, timestamp DESC);
```

### 4.4 账户与持仓数据表

```sql
-- ============ 账户流水（核心！资金变化可追溯）============

CREATE TABLE account_ledger (
    ledger_id       BIGSERIAL PRIMARY KEY,
    account_id      TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    event_type      TEXT NOT NULL,        -- DEPOSIT / WITHDRAW / BUY / SELL /
                                           -- DIVIDEND / INTEREST / FEE / TRANSFER
    symbol          TEXT,                  -- 股票代码（交易相关事件）
    direction       TEXT,                  -- LONG / SHORT（交易相关）
    volume          NUMERIC(15, 2),        -- 成交量（交易相关）
    price           NUMERIC(10, 3),        -- 成交价（交易相关）
    amount          NUMERIC(20, 4),        -- 发生金额（正负）
    balance         NUMERIC(20, 4),        -- 发生后资金余额
    commission      NUMERIC(15, 4),        -- 手续费
    stamp_duty      NUMERIC(15, 4),        -- 印花税（仅卖出）
    position_cost   NUMERIC(20, 4),        -- 持仓成本（交易后）
    remark          TEXT,
    environment     TEXT NOT NULL DEFAULT 'BACKTEST',
    UNIQUE(account_id, ledger_id)         -- 确保流水不可篡改
);

CREATE INDEX idx_ledger_account_time ON account_ledger(account_id, timestamp DESC);
CREATE INDEX idx_ledger_event ON account_ledger(event_type);
CREATE INDEX idx_ledger_symbol ON account_ledger(symbol);


-- ============ 持仓快照（每日结算）============

CREATE TABLE position_snapshots (
    snapshot_id     BIGSERIAL PRIMARY KEY,
    account_id      TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    snapshot_date   DATE NOT NULL,
    volume          NUMERIC(15, 2),        -- 持仓数量
    avg_cost        NUMERIC(10, 4),        -- 平均成本
    market_value    NUMERIC(20, 4),        -- 市值
    unrealized_pnl  NUMERIC(20, 4),        -- 浮动盈亏
    realized_pnl    NUMERIC(20, 4),        -- 已实现盈亏（当日）
    today_buy_volume NUMERIC(15, 2),       -- 今日买入量
    today_sell_volume NUMERIC(15, 2),      -- 今日卖出量
    frozen_volume   NUMERIC(15, 2),        -- 冻结数量
    environment     TEXT NOT NULL DEFAULT 'BACKTEST',
    UNIQUE(account_id, symbol, snapshot_date, environment)
);

CREATE INDEX idx_pos_snap_date ON position_snapshots(snapshot_date);
CREATE INDEX idx_pos_snap_account ON position_snapshots(account_id);


-- ============ 账户快照 ============

CREATE TABLE account_snapshots (
    snapshot_id     BIGSERIAL PRIMARY KEY,
    account_id      TEXT NOT NULL,
    snapshot_date   DATE NOT NULL,
    total_value     NUMERIC(20, 4),        -- 总资产
    cash            NUMERIC(20, 4),        -- 可用资金
    frozen_cash     NUMERIC(20, 4),        -- 冻结资金
    market_value    NUMERIC(20, 4),        -- 持仓市值
    daily_pnl       NUMERIC(20, 4),        -- 今日盈亏
    daily_return    NUMERIC(12, 6),        -- 今日收益率
    total_pnl       NUMERIC(20, 4),        -- 累计盈亏
    total_return    NUMERIC(12, 6),        -- 累计收益率
    environment     TEXT NOT NULL DEFAULT 'BACKTEST',
    UNIQUE(account_id, snapshot_date, environment)
);
```

### 4.5 订单与成交数据表

```sql
-- ============ 订单数据 ============

CREATE TABLE orders (
    order_id        TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,         -- LONG / SHORT / EXIT
    order_type      TEXT NOT NULL,         -- MARKET / LIMIT / STOP / STOP_LIMIT
    volume          NUMERIC(15, 2),
    price           NUMERIC(10, 3),        -- 委托价格
    filled_volume   NUMERIC(15, 2) DEFAULT 0,
    avg_price       NUMERIC(10, 3),       -- 成交均价
    status          TEXT NOT NULL,         -- PENDING / FILLED / PARTIAL / CANCELLED / REJECTED
    rejection_reason TEXT,                 -- 拒绝原因（风控拒绝等）
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    strategy_name   TEXT,                  -- 策略名称
    backtest_id     TEXT,                  -- 回测ID（用于关联）
    environment     TEXT NOT NULL DEFAULT 'BACKTEST'
);

CREATE INDEX idx_orders_account ON orders(account_id);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_orders_status ON orders(status);


-- ============ 成交数据 ============

CREATE TABLE trades (
    trade_id        TEXT PRIMARY KEY,
    order_id        TEXT REFERENCES orders(order_id),
    account_id      TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,         -- LONG / SHORT
    volume          NUMERIC(15, 2),
    price           NUMERIC(10, 3),
    amount          NUMERIC(20, 4),        -- 成交金额
    commission      NUMERIC(15, 4),
    stamp_duty      NUMERIC(15, 4),
    traded_at       TIMESTAMPTZ NOT NULL,
    strategy_name   TEXT,
    backtest_id     TEXT,
    environment     TEXT NOT NULL DEFAULT 'BACKTEST'
);

CREATE INDEX idx_trades_account ON trades(account_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_time ON trades(traded_at);
CREATE INDEX idx_trades_order ON trades(order_id);
```

### 4.6 因子数据表

```sql
-- ============ 因子值存储 ============

CREATE TABLE factor_values (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    factor_name TEXT NOT NULL,
    value       DOUBLE PRECISION,
    rank_value  INTEGER,                    -- 横截面排名（可选）
    environment TEXT NOT NULL DEFAULT 'BACKTEST',
    PRIMARY KEY (time, symbol, factor_name, environment)
);

SELECT create_hypertable('factor_values', 'time',
    chunk_time_interval => INTERVAL '30 days');

CREATE INDEX idx_factor_name_time ON factor_values(factor_name, time DESC);
CREATE INDEX idx_factor_symbol ON factor_values(symbol, time DESC);


-- ============ 因子 IC 追踪 ============

CREATE TABLE factor_ic (
    factor_name     TEXT NOT NULL,
    test_date       DATE NOT NULL,
    ic_value        NUMERIC(10, 6),         -- Pearson IC
    ir_value       NUMERIC(10, 6),         -- IC / IC_std
    rank_ic        NUMERIC(10, 6),         -- Spearman Rank IC
    long_return    NUMERIC(10, 6),         -- 多头组合收益
    short_return   NUMERIC(10, 6),         -- 空头组合收益
    spread_return  NUMERIC(10, 6),         -- 多空收益差
    sample_count   INTEGER,                -- 样本数量
    top_count      INTEGER,                 -- 多头股票数量
    bottom_count   INTEGER,                 -- 空头股票数量
    PRIMARY KEY (factor_name, test_date)
);

CREATE INDEX idx_ic_factor_date ON factor_ic(factor_name, test_date DESC);
CREATE INDEX idx_ic_ir ON factor_ic(ir_value DESC);


-- ============ 因子换手率追踪 ============

CREATE TABLE factor_turnover (
    factor_name     TEXT NOT NULL,
    test_date       DATE NOT NULL,
    avg_turnover    NUMERIC(10, 6),        -- 平均换手率
    max_turnover    NUMERIC(10, 6),        -- 最大换手率
    min_turnover    NUMERIC(10, 6),        -- 最小换手率
    PRIMARY KEY (factor_name, test_date)
);
```

### 4.7 数据质量日志表

```sql
-- ============ 数据质量日志 ============

CREATE TABLE data_quality_log (
    log_id          BIGSERIAL PRIMARY KEY,
    category        TEXT NOT NULL,         -- bars / fundamental / flow 等
    check_rule      TEXT NOT NULL,         -- 执行的校验规则
    check_date      DATE NOT NULL,
    passed          BOOLEAN NOT NULL,
    record_count    INTEGER,               -- 总记录数
    error_count     INTEGER,               -- 错误记录数
    error_rate      NUMERIC(10, 6),        -- 错误率
    error_samples   JSONB,                 -- 错误样例（JSON数组）
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dql_category ON data_quality_log(category, check_date DESC);
CREATE INDEX idx_dql_passed ON data_quality_log(passed, check_date DESC);
```

---

## 5. 部署架构

### 5.1 开发环境

```
本地开发
├── Python 3.10+ (conda/venv)
├── VSCode / PyCharm
├── PostgreSQL (本地)
├── Redis (本地)
└── Docker Desktop (可选)
```

### 5.2 回测环境

```
回测服务器
├── Python 应用 (Docker)
├── PostgreSQL (数据存储)
├── Redis (因子缓存)
├── MinIO (对象存储，回测结果)
└── Jupyter Lab (策略研发)
```

### 5.3 实盘环境

```
实盘服务器
├── Python 应用 (Docker, 多策略隔离)
├── PostgreSQL (主数据库)
├── Redis (实时缓存 + Pub/Sub)
├── 券商交易通道 (QMT/掘金)
├── 飞书Webhook (报警)
└── Grafana + Prometheus (监控)
```

### 5.4 Docker 部署

```yaml
# docker-compose.yml

version: '3.8'

services:
  app:
    build: .
    container_name: faster_qt
    restart: unless-stopped
    environment:
      - DB_URL=${DB_URL}
      - REDIS_URL=${REDIS_URL}
      - BROKER_TYPE=${BROKER_TYPE}
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    depends_on:
      - postgres
      - redis

  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: faster_qt_db
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    container_name: faster_qt_redis

  prometheus:
    image: prom/prometheus
    container_name: faster_qt_prometheus

  grafana:
    image: grafana/grafana
    container_name: faster_qt_grafana

volumes:
  pgdata:
```

---

## 6. 开发规范

### 6.1 Git 分支管理

```
main           # 主分支（生产代码）
├── develop     # 开发分支
│   ├── feature/xxx  # 功能分支
│   ├── bugfix/xxx   # Bug修复分支
│   └── hotfix/xxx   # 紧急修复分支
└── release/xxx      # 发布分支
```

### 6.2 代码审查清单

| 检查项 | 说明 |
|-------|------|
| 单元测试 | 新增代码必须有单元测试覆盖 |
| 命名规范 | 遵循 PEP8 / Google Style |
| 类型注解 | 公开接口必须添加类型注解 |
| 文档 | 复杂逻辑必须添加 docstring |
| 敏感信息 | API Key 等敏感信息通过环境变量注入 |

### 6.3 策略上线检查清单

| 检查项 | 说明 |
|-------|------|
| 回测区间 | 至少覆盖 3 年历史数据 |
| 样本外测试 | 预留最近 1 年数据作为样本外验证 |
| 滑点设置 | 股票≥0.1%，期货≥0.5% |
| 成交率模拟 | 按实际通道设置成交率 |
| 收益率统计 | 必须年化，夏普≥1.0 |
| 最大回撤 | 必须< 20% |
| 风控规则 | 单日亏损限制生效 |
| 前视偏差 | 使用 lookback 加载数据，避免使用未来数据 |

---

## 7. 版本规划

| 版本 | 目标 | 里程碑 |
|------|------|--------|
| v0.1 | 基础框架搭建 | 项目结构、Git仓库、文档、主数据层设计 |
| v0.2 | **数据层核心完成** | Tushare/AKShare 数据接入、存储层、主数据表 |
| v0.3 | 因子层完成 | 基础量价因子库、因子IC追踪 |
| v0.4 | 回测引擎完成 | Backtrader 集成、lookback加载 |
| v0.5 | 首个策略上线 | 均线交叉策略 |
| v0.6 | 风控模块完成 | 实时风控引擎 |
| v0.7 | 实盘对接 | QMT/掘金适配器、实时数据流 |
| v1.0 | 正式版本 | 完整流程打通 |

---

## 附录A：量化系统核心问题清单

| # | 问题 | 数据层解决方案 |
|---|-----|---------------|
| 1 | **前视偏差** | `fundamental_calendar.announcement_date` 标识数据可用时间；`DataLoader.load_with_lookback()` 确保只使用历史数据 |
| 2 | **停牌股处理** | `symbols.is_active` + `trading_calendar` 交叉验证；停牌日不生成交易信号 |
| 3 | **财务数据对齐** | `fundamental_calendar` 表统一管理报告期，不同公司不同 fiscal_quarter |
| 4 | **因子衰减监控** | `factor_ic` 表追踪 IC_IR，连续 < 0.3 则因子失效告警 |
| 5 | **回测-实盘数据隔离** | 所有表加 `environment` 字段，BACKTEST/PAPER/LIVE 三重隔离 |
| 6 | **数据缺失检测** | `TimeContinuityRule` 校验 K 线连续性，缺失则告警 |
| 7 | **复权价格还原** | `bars.factor` 复权因子，支持前复权/后复权切换 |
| 8 | **资金流水追溯** | `account_ledger` 表记录每笔资金变化，支持任意时间点余额回溯 |

---

*本文档由 faster_qt 项目组维护，最后更新：2026-04-19*
