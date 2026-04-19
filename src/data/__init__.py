# -*- coding: utf-8 -*-
"""
数据层核心模块

提供量化系统的数据基础设施：
- 数据模型定义
- 数据存储引擎
- 主数据管理
- 数据质量校验
- 数据采集模块
- 统一数据加载器
"""

from .models import (
    # 枚举类型
    SecurityType,
    Exchange,
    Board,
    Direction,
    OrderType,
    OrderStatus,
    EventType,
    Environment,
    TimeFrame,
    # 数据模型
    SymbolInfo,
    TradingCalendar,
    Bar,
    Tick,
    FundamentalData,
    Position,
    AccountInfo,
    AccountLedger,
    Order,
    Trade,
    Signal,
    RiskResult,
    RiskContext,
    QualityResult,
    FactorICRecord,
    # 工具函数
    generate_order_id,
    generate_trade_id,
    generate_signal_id,
    bars_to_dataframe,
)

from .storage import DataStorage

from .master import MasterDataManager

from .validator import DataValidator, DataQualityRule, DataQualityError, QualityReport

from .fetcher import (
    DataSource,
    AKShareSource,
    TushareSource,
    IncrementalFetcher,
    HistoricalFetcher,
)

from .loader import DataLoader

__all__ = [
    # 模型
    "SecurityType",
    "Exchange",
    "Board",
    "Direction",
    "OrderType",
    "OrderStatus",
    "EventType",
    "Environment",
    "TimeFrame",
    "SymbolInfo",
    "TradingCalendar",
    "Bar",
    "Tick",
    "FundamentalData",
    "Position",
    "AccountInfo",
    "AccountLedger",
    "Order",
    "Trade",
    "Signal",
    "RiskResult",
    "RiskContext",
    "QualityResult",
    "FactorICRecord",
    "generate_order_id",
    "generate_trade_id",
    "generate_signal_id",
    "bars_to_dataframe",
    # 存储
    "DataStorage",
    # 主数据
    "MasterDataManager",
    # 校验
    "DataValidator",
    "DataQualityRule",
    "DataQualityError",
    "QualityReport",
    # 采集
    "DataSource",
    "AKShareSource",
    "TushareSource",
    "IncrementalFetcher",
    "HistoricalFetcher",
    # 加载
    "DataLoader",
]
