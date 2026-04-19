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
│  │  交易所行情 │ 财务数据 │ 宏观数据 │ 新闻舆情 │ 另类数据                  │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        数据层（Data Layer）                          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │    │
│  │  │ 行情采集  │  │ 财务采集  │  │ 新闻采集  │  │ 数据清洗  │          │    │
│  │  │ (Fetcher)│  │ (Fund.)  │  │ (Alt.)   │  │(Cleaner) │          │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │    │
│  │       └──────────────┼──────────────┼──────────────┘               │    │
│  │                      ▼                                               │    │
│  │              ┌──────────────────┐                                    │    │
│  │              │   数据存储 (Storage) │                                   │    │
│  │              │ PostgreSQL+TimescaleDB │                                │    │
│  │              │      + Redis Cache     │                                │    │
│  │              └──────────────────┘                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       因子层（Factor Layer）                         │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │    │
│  │  │ 量价因子  │  │ 财务因子  │  │ 另类因子  │  │ 因子缓存  │          │    │
│  │  │ (Price)  │  │ (Fund.)  │  │ (Alt.)   │  │(Cache)  │          │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │    │
│  │       └──────────────┼──────────────┼──────────────┘               │    │
│  │                      ▼                                               │    │
│  │              ┌──────────────────┐                                    │    │
│  │              │   因子数据库 (FactorDB)  │                              │    │
│  │              │    (PostgreSQL)        │                               │    │
│  │              └──────────────────┘                                    │    │
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
│  │           │                              │                            │    │
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
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │    │
│  │       └──────────────┼──────────────┼──────────────┘               │    │
│  │                      ▼                                               │    │
│  │              ┌──────────────────┐                                    │    │
│  │              │   交易通道 (Broker) │                                   │    │
│  │              │  QMT / 掘金 / XTP  │                                   │    │
│  │              └──────────────────┘                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       风控层（Risk Layer）                           │    │
│  │                                                                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │  │ 仓位限制  │  │ 亏损限制  │  │ 合规校验  │  │ 流动性管理│           │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │    │
│  │                                                                       │    │
│  │              ┌──────────────────┐                                    │    │
│  │              │   风控引擎 (Risk)  │                                   │    │
│  │              │   实时 Pre-Trade   │                                  │    │
│  │              │   + Post-Trade     │                                  │    │
│  │              └──────────────────┘                                    │    │
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
| **数据层** | 采集、清洗、存储市场数据 | Fetcher, Cleaner, Storage, Loader | PostgreSQL + TimescaleDB, Redis, Kafka |
| **因子层** | 计算与管理量化因子 | PriceFactors, FundFactors, AltFactors, FactorCache | NumPy, Pandas, Numba |
| **策略层** | 策略研发、回测、信号生成 | Backtester, SignalEngine, Portfolio | Backtrader, Zipline, 自研 |
| **执行层** | 订单路由、算法交易、通道对接 | OMS, BrokerAdapter, Algos | Python, C++ (高频) |
| **风控层** | 实时风控、合规校验 | RiskManager, PositionLimit, LossLimit | 规则引擎 |
| **监控层** | 日志、性能、报警 | Dashboard, Logger, Alerter, Performance | Grafana, Prometheus, Plotly |

---

## 3. 核心模块详细设计

### 3.1 数据层（Data Layer）

#### 3.1.1 模块职责

- **数据采集**：从交易所、第三方数据源获取行情、财务、另类数据
- **数据清洗**：处理缺失值、去噪、复权、归一化
- **数据存储**：按时间序列存储，支持高效查询
- **数据加载**：为因子计算、策略回测提供统一的数据加载接口

#### 3.1.2 数据源矩阵

| 数据类型 | 数据源 | 更新频率 | 存储位置 |
|---------|-------|---------|---------|
| 日线行情 | Tushare / AKShare | 日终 | `data/cleaned/daily/` |
| 分钟线 | 掘金量化 / QMT | 实时/历史 | `data/cleaned/minute/` |
| 财务数据 | Tushare / 财报 | 季度 | `data/raw/fundamental/` |
| 指数成分 | 中证指数公司 | 不定期 | `data/raw/index/` |
| 资金流向 | 东方财富 | 日终 | `data/raw/flow/` |
| 新闻舆情 | 东方财富/同花顺 | 实时 | `data/raw/alternative/` |

#### 3.1.3 核心类设计

```python
# 数据层核心类

class DataSource(ABC):
    """数据源抽象基类"""
    @abstractmethod
    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_latest(self, symbol: str) -> pd.Series:
        pass


class DataLoader:
    """统一数据加载器"""
    def __init__(self, storage: DataStorage):
        self.storage = storage

    def load_bars(self, symbols: List[str], start: date, end: date,
                  freq: str = "1d") -> pd.DataFrame:
        """加载K线数据"""
        pass

    def load_fundamental(self, symbols: List[str],
                         fields: List[str]) -> pd.DataFrame:
        """加载财务数据"""
        pass


class DataStorage:
    """数据存储引擎"""
    def __init__(self, db_url: str, redis_url: str):
        self.db = create_engine(db_url)  # PostgreSQL + TimescaleDB
        self.cache = Redis.from_url(redis_url)

    def save(self, category: str, data: pd.DataFrame):
        """存储数据到时序数据库"""
        pass

    def load(self, category: str, symbol: str,
             start: date, end: date) -> pd.DataFrame:
        """从时序数据库加载数据"""
        pass
```

#### 3.1.4 数据流程

```
数据请求 → DataLoader → 检查 Redis Cache
                            ↓
                      Cache Hit? → 直接返回
                            ↓ No
                      DataStorage 查询 PostgreSQL
                            ↓
                      数据存在? → 写入 Redis → 返回
                            ↓ No
                      DataSource 实时采集 → 清洗 → 存储 → 返回
```

---

### 3.2 因子层（Factor Layer）

#### 3.2.1 因子分类

| 类别 | 子类 | 示例因子 | 计算频率 |
|------|------|---------|---------|
| **量价因子** | 趋势类 | MA, EMA, MACD, DMA | 日/分钟 |
| | 波动类 | Bollinger, ATR, STD | 日/分钟 |
| | 动量类 | RSI, ROC, CCI | 日/分钟 |
| | 成交量类 | VOL, VMAP, OBV | 日/分钟 |
| **财务因子** | 估值类 | PE, PB, PS, PCF | 季度 |
| | 成长类 | 营收增速, 利润增速, ROE | 季度 |
| | 质量类 | 资产负债率, 现金流/负债 | 季度 |
| **另类因子** | 情绪类 | 新闻情绪打分, 研报情绪 | 日 |
| | 资金流类 | 主力净流入, 超大单净流入 | 日 |
| | 舆情类 | 社交媒体热度, 搜索指数 | 日 |

#### 3.2.2 因子计算规范

```python
# 因子基类

class BaseFactor(ABC):
    """因子抽象基类"""
    name: str  # 因子名称
    category: str  # 因子类别
    update_freq: str  # 更新频率（日/分钟/季度）

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算因子"""
        pass

    def validate(self, factor_value: pd.Series) -> bool:
        """因子值校验（去极值、归一化）"""
        pass


# 示例：均线因子

class MAFactor(BaseFactor):
    name = "ma_5"
    category = "price_trend"
    update_freq = "1d"

    def __init__(self, window: int = 5):
        self.window = window

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        return data["close"].rolling(self.window).mean()
```

#### 3.2.3 因子存储

```sql
-- 因子数据表（TimescaleDB 超表）

CREATE TABLE factor_values (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    factor_name TEXT NOT NULL,
    value       DOUBLE PRECISION,
    PRIMARY KEY (time, symbol, factor_name)
);

SELECT create_hypertable('factor_values', 'time');
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
        self.positions: Dict[str, float] = {}  # 持仓 {symbol: volume}
        self.signals: List[Signal] = []  # 信号列表

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
        self.direction = direction  # LONG / SHORT / EXIT
        self.strength = strength  # 信号强度 [0, 1]
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
        # 1. 加载历史数据
        bars = self.data_loader.load_bars(symbols, start, end)

        # 2. 遍历K线
        for bar in bars:
            # 3. 策略生成信号
            orders = self.strategy.on_bar(bar)

            # 4. 风控前置检查
            orders = self.risk_precheck(orders)

            # 5. 执行订单（模拟）
            self.execute_orders(orders, bar)

            # 6. 更新持仓
            self.update_positions(bar)

        # 7. 生成回测报告
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
        # 1. 风控预检
        if not self.risk_manager.pre_check(order):
            return False

        # 2. 发送到券商
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
        self.api = None  # QMT API 实例

    def send_order(self, order: Order) -> bool:
        # 调用 QMT下单接口
        pass


class GmAdapter(BrokerAdapter):
    """掘金量化券商适配器"""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.api = None  # 掘金 API 实例

    def send_order(self, order: Order) -> bool:
        # 调用掘金下单接口
        pass
```

#### 3.4.3 算法交易

```python
class BaseAlgo(ABC):
    """算法交易基类"""

    @abstractmethod
    def execute(self, order: Order, market_data: MarketData):
        """执行算法"""
        pass


class TWAPAlgo(BaseAlgo):
    """TWAP（时间加权平均）算法"""

    def __init__(self, duration_minutes: int = 60):
        self.duration = duration_minutes
        self.slice_count = duration_minutes  # 每分钟一个slice
        self.executed = 0

    def execute(self, order: Order, market_data: MarketData):
        slice_size = order.volume / (self.slice_count - self.executed)
        child_order = Order(
            symbol=order.symbol,
            direction=order.direction,
            volume=slice_size,
            order_type=OrderType.LIMIT,
            price=market_data.best_bid  # TWAP 使用均价
        )
        self.order_manager.submit_order(child_order)
        self.executed += 1


class VWAPAlgo(BaseAlgo):
    """VWAP（成交量加权平均）算法"""

    def execute(self, order: Order, market_data: MarketData):
        # 基于历史成交量分布执行
        pass


class IcebergAlgo(BaseAlgo):
    """冰山订单算法"""

    def __init__(self, display_ratio: float = 0.1):
        self.display_ratio = display_ratio  # 显示比例

    def execute(self, order: Order, market_data: MarketData):
        display_size = order.volume * self.display_ratio
        child_order = Order(...)
        # 只显示部分成交量
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
        """检查订单"""
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
        # 更新盈亏、持仓等状态
        self.update_positions(trade)
        self.update_pnl(trade)

        # 检查是否触发止损
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
# 日志分级

class Logger:
    """统一日志记录器"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def debug(self, msg: str, **kwargs):
        """调试日志"""
        self.logger.debug(self._format(msg, kwargs))

    def info(self, msg: str, **kwargs):
        """信息日志"""
        self.logger.info(self._format(msg, kwargs))

    def warning(self, msg: str, **kwargs):
        """警告日志"""
        self.logger.warning(self._format(msg, kwargs))

    def error(self, msg: str, **kwargs):
        """错误日志"""
        self.logger.error(self._format(msg, kwargs))

    def _format(self, msg: str, kwargs: dict) -> str:
        """统一格式化：时间 | 级别 | 模块 | 消息 | 扩展字段"""
        extra = json.dumps(kwargs) if kwargs else ""
        return f"{self.get_timestamp()} | {msg} | {extra}"


# 日志示例
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
        """发送报警"""

        if channels is None:
            channels = ["feishu"]  # 默认飞书

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
    CRITICAL = "critical"  # 触发硬止损、策略停止等


# 报警规则
alerter = Alerter()

# 1. 日亏损超限
if daily_pnl < -0.03:
    alerter.send_alert(
        level=AlertLevel.CRITICAL,
        title="⚠️ 日亏损超限",
        message=f"当日亏损 {daily_pnl:.2%}，已触发 -3% 止损线，请及时处理！"
    )

# 2. 订单成交率低
if fill_rate < 0.95:
    alerter.send_alert(
        level=AlertLevel.WARNING,
        title="📉 成交率异常",
        message=f"订单成交率 {fill_rate:.2%}，低于 95%，请检查通道"
    )

# 3. 策略信号异常
if signal_count > 1000:
    alerter.send_alert(
        level=AlertLevel.ERROR,
        title="🔥 信号风暴",
        message=f"单日信号数 {signal_count}，疑似信号异常，请检查"
    )
```

---

## 4. 数据模型

### 4.1 核心数据模型（Entity Relationship）

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Symbol    │       │    Bar      │       │   Factor    │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ symbol_id   │──┐    │ symbol_id   │──┐    │ symbol_id   │──┐
│ symbol_code  │  │    │ timestamp   │  │    │ factor_name │  │
│ symbol_name  │  └───▶│ open         │  └───▶│ timestamp   │  │
│ market       │       │ high         │       │ value       │  │
│ sector       │       │ low          │       └─────────────┘  │
└─────────────┘       │ close        │                        │
                      │ volume       │       ┌─────────────┐  │
                      │ amount       │       │   Order     │  │
                      └─────────────┘       ├─────────────┤  │
                                            │ order_id    │  │
                      ┌─────────────┐       │ symbol_id   │  │
                      │  Position   │       │ direction   │  │
                      ├─────────────┤       │ volume      │  │
                      │ position_id │       │ price       │  │
                      │ symbol_id   │──────▶│ status      │  │
                      │ volume      │       │ created_at  │  │
                      │ avg_cost    │       └─────────────┘  │
                      │ market_value│                           │
                      └─────────────┘                           │
                                            ┌─────────────┐  │
                      ┌─────────────┐       │   Trade     │  │
                      │  Account    │       ├─────────────┤  │
                      ├─────────────┤       │ trade_id    │  │
                      │ account_id  │       │ order_id    │  │
                      │ total_value │       │ symbol_id   │  │
                      │ cash        │       │ volume      │  │
                      │ frozen_cash │       │ price       │  │
                      │ daily_pnl   │       │ commission  │  │
                      └─────────────┘       │ traded_at   │  │
                                            └─────────────┘  │
```

### 4.2 数据表设计

```sql
-- K线数据（TimescaleDB 超表）

CREATE TABLE bars (
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    open        NUMERIC(10, 3),
    high        NUMERIC(10, 3),
    low         NUMERIC(10, 3),
    close       NUMERIC(10, 3),
    volume      BIGINT,
    amount      NUMERIC(20, 3),
    PRIMARY KEY (symbol, timeframe, timestamp)
);

SELECT create_hypertable('bars', 'timestamp');

-- 订单数据

CREATE TABLE orders (
    order_id        TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,  -- LONG / SHORT
    order_type      TEXT NOT NULL,  -- MARKET / LIMIT
    volume          NUMERIC(10, 2),
    price           NUMERIC(10, 3),
    filled_volume   NUMERIC(10, 2) DEFAULT 0,
    avg_price       NUMERIC(10, 3),
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

-- 成交数据

CREATE TABLE trades (
    trade_id        TEXT PRIMARY KEY,
    order_id        TEXT REFERENCES orders(order_id),
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    volume          NUMERIC(10, 2),
    price           NUMERIC(10, 3),
    commission      NUMERIC(10, 3),
    traded_at       TIMESTAMPTZ NOT NULL
);

-- 持仓数据

CREATE TABLE positions (
    symbol          TEXT PRIMARY KEY,
    volume          NUMERIC(10, 2),
    avg_cost        NUMERIC(10, 3),
    market_value    NUMERIC(20, 3),
    unrealized_pnl  NUMERIC(20, 3),
    updated_at      TIMESTAMPTZ NOT NULL
);

-- 账户数据

CREATE TABLE accounts (
    account_id      TEXT PRIMARY KEY,
    total_value     NUMERIC(20, 3),
    cash            NUMERIC(20, 3),
    frozen_cash     NUMERIC(20, 3),
    daily_pnl       NUMERIC(20, 3),
    daily_return    NUMERIC(10, 6),
    updated_at      TIMESTAMPTZ NOT NULL
);
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
├── Redis (实时缓存)
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

---

## 7. 版本规划

| 版本 | 目标 | 里程碑 |
|------|------|--------|
| v0.1 | 基础框架搭建 | 项目结构、Git仓库、文档 |
| v0.2 | 数据层完成 | Tushare/AKShare 数据接入 |
| v0.3 | 因子层完成 | 基础量价因子库 |
| v0.4 | 回测引擎完成 | Backtrader 集成 |
| v0.5 | 首个策略上线 | 均线交叉策略 |
| v0.6 | 风控模块完成 | 实时风控引擎 |
| v0.7 | 实盘对接 | QMT/掘金适配器 |
| v1.0 | 正式版本 | 完整流程打通 |

---

*本文档由 faster_qt 项目组维护，最后更新：2026-04-19*
