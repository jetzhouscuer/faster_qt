# -*- coding: utf-8 -*-
"""
数据层核心数据模型定义
所有核心数据结构在此定义，确保类型一致性
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
import pandas as pd


# ===========================
# 枚举类型定义
# ===========================


class SecurityType(str, Enum):
    """证券类型"""
    STOCK = "STOCK"           # 股票
    INDEX = "INDEX"          # 指数
    FUND = "FUND"            # 基金
    FUTURES = "FUTURES"      # 期货
    OPTIONS = "OPTIONS"       # 期权
    BOND = "BOND"            # 债券


class Exchange(str, Enum):
    """交易所"""
    SH = "SH"    # 上海
    SZ = "SZ"    # 深圳
    BJ = "BJ"    # 北京
    HK = "HK"    # 香港


class Board(str, Enum):
    """板块（股票特有）"""
    MAIN = "MAIN"            # 主板
    GEM = "GEM"             # 创业板（ChiNext）
    STAR = "STAR"           # 科创板（STAR Market）


class Direction(str, Enum):
    """交易方向"""
    LONG = "LONG"           # 买入/做多
    SHORT = "SHORT"         # 卖出/做空
    EXIT = "EXIT"           # 平仓


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "MARKET"       # 市价单
    LIMIT = "LIMIT"         # 限价单
    STOP = "STOP"           # 止损单
    STOP_LIMIT = "STOP_LIMIT"  # 止损限价单


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"     # 待成交
    FILLED = "FILLED"       # 已成交
    PARTIAL = "PARTIAL"     # 部分成交
    CANCELLED = "CANCELLED" # 已撤销
    REJECTED = "REJECTED"   # 已拒绝


class EventType(str, Enum):
    """账户流水事件类型"""
    DEPOSIT = "DEPOSIT"             # 入金
    WITHDRAW = "WITHDRAW"           # 出金
    BUY = "BUY"                     # 买入
    SELL = "SELL"                   # 卖出
    DIVIDEND = "DIVIDEND"           # 股息
    INTEREST = "INTEREST"           # 利息
    FEE = "FEE"                     # 手续费
    STAMP_DUTY = "STAMP_DUTY"       # 印花税
    TRANSFER = "TRANSFER"           # 转账


class Environment(str, Enum):
    """运行环境"""
    BACKTEST = "BACKTEST"   # 回测
    PAPER = "PAPER"         # 模拟交易
    LIVE = "LIVE"           # 实盘


class TimeFrame(str, Enum):
    """K线周期"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    DAILY = "1d"
    WEEKLY = "1w"


# ===========================
# 主数据模型
# ===========================


@dataclass
class SymbolInfo:
    """证券基础信息"""
    symbol: str                           # 证券代码 "600519.SH"
    name: str                             # 证券名称 "贵州茅台"
    type: SecurityType                    # 类型
    exchange: Exchange                    # 交易所
    board: Optional[Board] = None         # 板块（股票）
    sector: Optional[str] = None          # 行业（中信一级）
    market_value: Optional[float] = None  # 总市值
    float_shares: Optional[float] = None  # 流通股本
    listing_date: Optional[date] = None   # 上市日期
    delist_date: Optional[date] = None   # 退市日期
    is_active: bool = True                # 是否在交易

    @property
    def symbol_code(self) -> str:
        """获取代码部分（不含交易所后缀）"""
        return self.symbol.split(".")[0]

    @property
    def is_stock(self) -> bool:
        """是否为股票"""
        return self.type == SecurityType.STOCK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "type": self.type.value,
            "exchange": self.exchange.value,
            "board": self.board.value if self.board else None,
            "sector": self.sector,
            "is_active": self.is_active,
        }


@dataclass
class TradingCalendar:
    """交易日历"""
    trade_date: date
    exchange: Exchange
    is_trading_day: bool
    market_open: Optional[datetime] = None
    market_close: Optional[datetime] = None
    pre_open: Optional[datetime] = None
    pre_close: Optional[datetime] = None


@dataclass
class FundamentalReport:
    """财务报告期信息"""
    symbol: str
    report_type: str          # Q1 / Q2 / Q3 / Q4 / FY
    report_date: date         # 报告期截止日
    fiscal_year: int          # 财政年度
    fiscal_quarter: Optional[int] = None
    announcement_date: date    # 公告发布日期（数据可用日期）
    is_estimated: bool = False


# ===========================
# 行情数据模型
# ===========================


@dataclass
class Bar:
    """K线数据"""
    symbol: str
    timestamp: datetime
    timeframe: TimeFrame
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: Optional[float] = None
    factor: Optional[float] = None  # 复权因子

    def to_series(self) -> pd.Series:
        """转换为 pandas Series"""
        return pd.Series({
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
            "factor": self.factor,
        })

    @property
    def price_range(self) -> float:
        """价格振幅"""
        return (self.high - self.low) / self.low if self.low > 0 else 0

    @property
    def change_pct(self) -> float:
        """涨跌幅（复权后）"""
        return (self.close - self.open) / self.open if self.open > 0 else 0


@dataclass
class Tick:
    """Tick数据（逐笔成交）"""
    symbol: str
    timestamp: datetime
    last_price: float
    last_volume: int
    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0
    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0
    bid_volume_1: int = 0
    bid_volume_2: int = 0
    bid_volume_3: int = 0
    bid_volume_4: int = 0
    bid_volume_5: int = 0
    ask_volume_1: int = 0
    ask_volume_2: int = 0
    ask_volume_3: int = 0
    ask_volume_4: int = 0
    ask_volume_5: int = 0
    total_volume: int = 0
    total_amount: float = 0

    @property
    def spread(self) -> float:
        """买卖价差"""
        return self.ask_price_1 - self.bid_price_1

    @property
    def mid_price(self) -> float:
        """中间价"""
        return (self.ask_price_1 + self.bid_price_1) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "last_price": self.last_price,
            "bid_price_1": self.bid_price_1,
            "ask_price_1": self.ask_price_1,
            "bid_volume_1": self.bid_volume_1,
            "ask_volume_1": self.ask_volume_1,
        }


# ===========================
# 财务数据模型
# ===========================


@dataclass
class FundamentalData:
    """财务数据"""
    symbol: str
    report_date: date

    # 利润表
    revenue: Optional[float] = None              # 营业收入
    operating_cost: Optional[float] = None        # 营业成本
    operating_profit: Optional[float] = None      # 营业利润
    total_profit: Optional[float] = None          # 利润总额
    net_profit: Optional[float] = None            # 净利润
    eps: Optional[float] = None                  # 每股收益

    # 资产负债表
    total_assets: Optional[float] = None         # 资产总计
    total_liabilities: Optional[float] = None    # 负债合计
    equity: Optional[float] = None               # 所有者权益
    current_assets: Optional[float] = None        # 流动资产
    current_liabilities: Optional[float] = None  # 流动负债

    # 现金流
    operating_cash_flow: Optional[float] = None   # 经营活动现金流
    investing_cash_flow: Optional[float] = None   # 投资活动现金流
    financing_cash_flow: Optional[float] = None   # 筹资活动现金流

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ===========================
# 持仓与账户数据模型
# ===========================


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    volume: float              # 持仓数量
    avg_cost: float            # 平均成本
    market_value: float        # 市值
    unrealized_pnl: float      # 浮动盈亏
    frozen_volume: float = 0   # 冻结数量
    today_buy_volume: float = 0  # 今日买入
    today_sell_volume: float = 0  # 今日卖出

    @property
    def unrealized_pnl_pct(self) -> float:
        """浮动盈亏率"""
        cost = self.avg_cost * self.volume
        return self.unrealized_pnl / cost if cost > 0 else 0

    @property
    def market_price(self) -> float:
        """当前市价"""
        return self.market_value / self.volume if self.volume > 0 else 0


@dataclass
class AccountInfo:
    """账户信息"""
    account_id: str
    total_value: float         # 总资产
    cash: float               # 可用资金
    frozen_cash: float = 0    # 冻结资金
    market_value: float = 0   # 持仓市值
    daily_pnl: float = 0      # 今日盈亏
    daily_return: float = 0   # 今日收益率
    total_pnl: float = 0      # 累计盈亏
    total_return: float = 0   # 累计收益率

    @property
    def risk_level(self) -> float:
        """风险度（持仓市值/总资产）"""
        return self.market_value / self.total_value if self.total_value > 0 else 0

    @property
    def available_cash(self) -> float:
        """实际可用资金"""
        return self.cash


@dataclass
class AccountLedger:
    """账户流水（核心！不可篡改）"""
    ledger_id: Optional[int] = None
    account_id: str = ""
    timestamp: Optional[datetime] = None
    event_type: EventType = EventType.TRANSFER
    symbol: Optional[str] = None
    direction: Optional[Direction] = None
    volume: float = 0
    price: float = 0
    amount: float = 0
    balance: float = 0  # 发生后余额
    commission: float = 0
    stamp_duty: float = 0
    position_cost: float = 0  # 持仓成本（交易后）
    remark: Optional[str] = None
    environment: Environment = Environment.BACKTEST


# ===========================
# 订单与交易数据模型
# ===========================


@dataclass
class Order:
    """订单"""
    order_id: str
    account_id: str
    symbol: str
    direction: Direction
    order_type: OrderType
    volume: float
    price: float = 0
    filled_volume: float = 0
    avg_price: float = 0
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    environment: Environment = Environment.BACKTEST

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    @property
    def is_pending(self) -> bool:
        return self.status == OrderStatus.PENDING

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def remaining_volume(self) -> float:
        """剩余未成交数量"""
        return self.volume - self.filled_volume


@dataclass
class Trade:
    """成交记录"""
    trade_id: str
    order_id: str
    account_id: str
    symbol: str
    direction: Direction
    volume: float
    price: float
    amount: float
    commission: float = 0
    stamp_duty: float = 0
    traded_at: Optional[datetime] = None
    strategy_name: Optional[str] = None
    backtest_id: Optional[str] = None
    environment: Environment = Environment.BACKTEST

    def __post_init__(self):
        if self.traded_at is None:
            self.traded_at = datetime.now()


# ===========================
# 信号与风控数据模型
# ===========================


@dataclass
class Signal:
    """交易信号"""
    signal_id: str
    symbol: str
    direction: Direction
    strength: float          # 信号强度 [0, 1]
    strategy: str
    timestamp: Optional[datetime] = None
    price: Optional[float] = None
    reason: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class RiskResult:
    """风控检查结果"""
    passed: bool
    reason: Optional[str] = None
    rule_name: Optional[str] = None


@dataclass
class RiskContext:
    """风控上下文"""
    account: AccountInfo
    positions: Dict[str, Position]
    pending_orders: List[Order]
    market_data: Dict[str, float]  # symbol -> last_price


# ===========================
# 数据质量模型
# ===========================


@dataclass
class QualityResult:
    """数据质量校验结果"""
    passed: bool
    category: str
    check_rule: str
    record_count: int = 0
    error_count: int = 0
    error_rate: float = 0
    error_samples: List[Any] = field(default_factory=list)
    details: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.passed:
            return f"✅ {self.category}.{self.check_rule}: 通过 ({self.record_count}条)"
        return f"❌ {self.category}.{self.check_rule}: 失败 (错误{self.error_count}/{self.record_count}, 率{self.error_rate:.2%})"


# ===========================
# 因子数据模型
# ===========================


@dataclass
class FactorICRecord:
    """因子IC追踪记录"""
    factor_name: str
    test_date: date
    ic_value: float
    ir_value: float
    rank_ic: float
    long_return: float = 0
    short_return: float = 0
    spread_return: float = 0
    sample_count: int = 0


# ===========================
# 工具函数
# ===========================


def generate_order_id() -> str:
    """生成订单ID"""
    return f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def generate_trade_id() -> str:
    """生成成交ID"""
    return f"TRD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def generate_signal_id() -> str:
    """生成信号ID"""
    return f"SIG_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def bars_to_dataframe(bars: List[Bar]) -> pd.DataFrame:
    """将 Bar 列表转换为 DataFrame"""
    if not bars:
        return pd.DataFrame()
    return pd.DataFrame([b.to_series() for b in bars])
