# -*- coding: utf-8 -*-
"""
主数据管理模块
负责证券基础信息、交易日历、财务报告期的管理
是量化系统的"黄页"，所有业务表通过 symbol 关联主数据
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Set

import pandas as pd

from .models import (
    SymbolInfo, TradingCalendar, FundamentalReport,
    SecurityType, Exchange, Board, Environment
)
from .storage import DataStorage

logger = logging.getLogger(__name__)


class MasterDataManager:
    """
    主数据管理器
    
    职责：
    1. 维护证券基础信息（symbols 表）
    2. 维护交易日历（trading_calendar 表）
    3. 维护财务报告期（fundamental_calendar 表）
    4. 提供便捷的查询接口
    """

    def __init__(self, storage: DataStorage):
        self.storage = storage

    # ===========================
    # 证券基础信息
    # ===========================

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        获取证券基本信息
        
        Args:
            symbol: 证券代码，如 "600519.SH"
            
        Returns:
            SymbolInfo 或 None（若不存在）
        """
        df = self.storage.load(
            category="symbols",
            symbol=symbol,
            limit=1,
        )
        
        if df.empty:
            return None

        row = df.iloc[0]
        return SymbolInfo(
            symbol=row["symbol"],
            name=row["name"],
            type=SecurityType(row["type"]),
            exchange=Exchange(row["exchange"]),
            board=Board(row["board"]) if row.get("board") else None,
            sector=row.get("sector"),
            market_value=row.get("market_value"),
            float_shares=row.get("float_shares"),
            listing_date=row.get("listing_date"),
            delist_date=row.get("delist_date"),
            is_active=row.get("is_active", True),
        )

    def get_symbols_by_filter(
        self,
        exchange: Optional[Exchange] = None,
        board: Optional[Board] = None,
        sector: Optional[str] = None,
        is_active: bool = True,
    ) -> List[str]:
        """
        根据条件筛选证券代码
        
        Args:
            exchange: 交易所筛选
            board: 板块筛选
            sector: 行业筛选
            is_active: 是否在交易
            
        Returns:
            符合条件的证券代码列表
        """
        sql = "SELECT symbol FROM symbols WHERE 1=1"
        params: Dict = {}

        if exchange:
            sql += " AND exchange = :exchange"
            params["exchange"] = exchange.value

        if board:
            sql += " AND board = :board"
            params["board"] = board.value

        if sector:
            sql += " AND sector = :sector"
            params["sector"] = sector

        if is_active:
            sql += " AND is_active = TRUE"
            sql += " AND (delist_date IS NULL OR delist_date > CURRENT_DATE)"

        df = self.storage.query(sql, params)
        return df["symbol"].tolist()

    def get_all_symbols(self, is_active: bool = True) -> List[str]:
        """获取所有证券代码"""
        return self.get_symbols_by_filter(is_active=is_active)

    def get_index_components(
        self,
        index_code: str,
        trade_date: Optional[date] = None,
    ) -> List[str]:
        """
        获取指数成分股
        
        注意：实际实现需要接入中证/深证指数公司的数据
        这里先返回内存中维护的映射表
        
        Args:
            index_code: 指数代码，如 "000300.SH"（沪深300）
            trade_date: 交易日期（成分股可能随日期变化）
            
        Returns:
            成分股代码列表
        """
        # TODO: 实现真正的指数成分获取
        # 目前返回空列表，实际使用时需要接入数据源
        logger.warning(f"Index components lookup not implemented for {index_code}")
        return []

    def is_trading_stock(self, symbol: str, trade_date: date) -> bool:
        """
        判断某股票在某日期是否可交易
        
        检查条件：
        1. 股票在交易
        2. 日期为交易日
        3. 股票未停牌
        """
        # 检查股票是否在交易
        info = self.get_symbol_info(symbol)
        if not info or not info.is_active:
            return False

        # 检查是否在上市日期之后
        if info.listing_date and trade_date < info.listing_date:
            return False

        # 检查是否已退市
        if info.delist_date and trade_date >= info.delist_date:
            return False

        # 检查是否为交易日
        return self.is_trading_day(trade_date, info.exchange)

    # ===========================
    # 交易日历
    # ===========================

    def is_trading_day(
        self,
        trade_date: date,
        exchange: Exchange = Exchange.SH,
    ) -> bool:
        """
        判断是否为交易日
        
        Args:
            trade_date: 日期
            exchange: 交易所（SH/SZ）
        """
        df = self.storage.load(
            category="trading_calendar",
            start=trade_date,
            end=trade_date,
        )
        
        if df.empty:
            # 如果日历表为空，默认周六周日非交易
            return trade_date.weekday() < 5

        row = df.iloc[0]
        return row.get("is_trading_day", False)

    def get_trading_day(
        self,
        reference_date: date,
        offset: int = 0,
        exchange: Exchange = Exchange.SH,
    ) -> date:
        """
        获取指定日期前后第N个交易日
        
        Args:
            reference_date: 参考日期
            offset: 偏移天数（正数=未来，负数=过去）
            exchange: 交易所
            
        Returns:
            偏移后的交易日
            
        Example:
            # 获取2024-01-01之后的第5个交易日
            get_trading_day(date(2024, 1, 1), 5)
            
            # 获取2024-01-10之前的第1个交易日
            get_trading_day(date(2024, 1, 10), -1)
        """
        if offset == 0:
            return reference_date

        direction = 1 if offset > 0 else -1
        current_date = reference_date
        remaining = abs(offset)

        while remaining > 0:
            current_date += timedelta(days=direction)
            
            # 跳过周末
            if current_date.weekday() >= 5:
                continue
                
            # 检查是否为交易日
            if self.is_trading_day(current_date, exchange):
                remaining -= 1

        return current_date

    def get_trading_days(
        self,
        start_date: date,
        end_date: date,
        exchange: Exchange = Exchange.SH,
    ) -> List[date]:
        """
        获取两个日期之间的所有交易日
        
        Returns:
            交易日列表（升序）
        """
        if start_date > end_date:
            return []

        result: List[date] = []
        current = start_date

        while current <= end_date:
            if self.is_trading_day(current, exchange):
                result.append(current)
            current += timedelta(days=1)

        return result

    def get_next_trading_day(
        self,
        reference_date: date,
        n: int = 1,
        exchange: Exchange = Exchange.SH,
    ) -> date:
        """获取未来第N个交易日（便捷方法）"""
        return self.get_trading_day(reference_date, n, exchange)

    def get_previous_trading_day(
        self,
        reference_date: date,
        n: int = 1,
        exchange: Exchange = Exchange.SH,
    ) -> date:
        """获取之前第N个交易日（便捷方法）"""
        return self.get_trading_day(reference_date, -n, exchange)

    # ===========================
    # 财务报告期管理
    # ===========================

    def get_fundamental_reports(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[FundamentalReport]:
        """
        获取财务报告期列表
        
        用于：
        1. 前视偏差规避：获取某日期之前已发布的财报
        2. 财务数据对齐：不同公司报告期不同，需要对齐
        
        Args:
            symbol: 证券代码
            start_date: 开始日期（公告日期）
            end_date: 结束日期（公告日期）
        """
        df = self.storage.load(
            category="fundamental_calendar",
            symbol=symbol,
            start=start_date,
            end=end_date,
        )
        
        if df.empty:
            return []

        return [
            FundamentalReport(
                symbol=row["symbol"],
                report_type=row["report_type"],
                report_date=row["report_date"],
                fiscal_year=row["fiscal_year"],
                fiscal_quarter=row.get("fiscal_quarter"),
                announcement_date=row["announcement_date"],
                is_estimated=row.get("is_estimated", False),
            )
            for _, row in df.iterrows()
        ]

    def get_latest_fundamental_date(
        self,
        symbol: str,
        before_date: date,
    ) -> Optional[date]:
        """
        获取某日期之前最近发布的财报日期
        
        ⭐ 这是避免前视偏差的关键方法！
        
        Example:
            # 获取2024-03-31之前最近发布的年报日期
            # 用于获取2024年一季报数据时，判断能否使用2023年年报
            get_latest_fundamental_date("600519.SH", date(2024, 3, 31))
        """
        reports = self.get_fundamental_reports(
            symbol,
            end_date=before_date,
        )
        
        if not reports:
            return None
        
        # 按公告日期排序，返回最新的
        reports.sort(key=lambda x: x.announcement_date, reverse=True)
        return reports[0].announcement_date

    def get_available_fundamental_data(
        self,
        symbol: str,
        reference_date: date,
        lookback_quarters: int = 8,
    ) -> List[FundamentalReport]:
        """
        获取参考日期可用的财报数据（用于回测）
        
        自动排除：
        1. 公告日期在参考日期之后的财报（避免前视偏差）
        2. 预测数据（除非没有真实数据）
        
        Args:
            symbol: 证券代码
            reference_date: 参考日期
            lookback_quarters: 向前回看多少个季度
        """
        # 获取过去 N 个季度的财报
        start_date = self.get_trading_day(reference_date, -lookback_quarters * 90)
        
        reports = self.get_fundamental_reports(
            symbol,
            start_date=start_date,
            end_date=reference_date,
        )
        
        # 只保留公告日期在参考日期之前的（已发布）
        available = [
            r for r in reports
            if r.announcement_date <= reference_date and not r.is_estimated
        ]
        
        # 按报告期降序排列
        available.sort(key=lambda x: x.report_date, reverse=True)
        
        return available

    # ===========================
    # 批量操作
    # ===========================

    def sync_symbols(self, symbols_data: List[Dict]) -> bool:
        """
        同步证券基础信息
        
        Args:
            symbols_data: 证券信息列表，如 [{"symbol": "600519.SH", "name": "贵州茅台", ...}]
        """
        if not symbols_data:
            return True

        df = pd.DataFrame(symbols_data)
        
        # 确保必填字段
        required = ["symbol", "name", "type", "exchange"]
        if not all(col in df.columns for col in required):
            logger.error("Missing required fields in symbols_data")
            return False

        return self.storage.save("symbols", df, if_exists="replace")

    def sync_trading_calendar(
        self,
        calendar_data: List[Dict],
        exchange: Exchange = Exchange.SH,
    ) -> bool:
        """
        同步交易日历
        
        Args:
            calendar_data: 日历数据，如 [{"trade_date": "2024-01-02", "is_trading_day": True}, ...]
            exchange: 交易所
        """
        if not calendar_data:
            return True

        df = pd.DataFrame(calendar_data)
        df["exchange"] = exchange.value
        
        required = ["trade_date", "is_trading_day"]
        if not all(col in df.columns for col in required):
            logger.error("Missing required fields in calendar_data")
            return False

        return self.storage.save("trading_calendar", df, if_exists="replace")

    def sync_fundamental_calendar(
        self,
        fundamental_data: List[Dict],
    ) -> bool:
        """
        同步财务报告期
        
        Args:
            fundamental_data: 财报期数据
        """
        if not fundamental_data:
            return True

        df = pd.DataFrame(fundamental_data)
        
        required = ["symbol", "report_type", "report_date", "fiscal_year", "announcement_date"]
        if not all(col in df.columns for col in required):
            logger.error("Missing required fields in fundamental_data")
            return False

        return self.storage.save("fundamental_calendar", df, if_exists="append")

    # ===========================
    # 缓存加速
    # ===========================

    def cache_symbol_info(self, symbol: str, ttl: int = 3600) -> bool:
        """将证券信息缓存到 Redis"""
        info = self.get_symbol_info(symbol)
        if info is None:
            return False
        
        key = f"symbol:info:{symbol}"
        return self.storage.redis_set(key, info.to_dict(), expire_seconds=ttl)

    def get_cached_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """从 Redis 缓存获取证券信息"""
        key = f"symbol:info:{symbol}"
        data = self.storage.redis_get(key)
        
        if data is None:
            return self.get_symbol_info(symbol)
        
        return SymbolInfo(**data)

    def warmup_cache(self, symbols: Optional[List[str]] = None) -> int:
        """
        预热缓存
        
        Args:
            symbols: 要缓存的证券列表（None=全部）
            
        Returns:
            缓存的证券数量
        """
        if symbols is None:
            symbols = self.get_all_symbols()

        count = 0
        for symbol in symbols:
            if self.cache_symbol_info(symbol):
                count += 1

        logger.info(f"Cache warmed: {count}/{len(symbols)} symbols")
        return count
