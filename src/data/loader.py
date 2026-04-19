# -*- coding: utf-8 -*-
"""
统一数据加载器
为因子计算、策略回测提供统一的数据加载接口
支持 lookback 机制避免前视偏差
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Union

import pandas as pd

from .storage import DataStorage
from .master import MasterDataManager
from .models import Bar, Environment, TimeFrame

logger = logging.getLogger(__name__)


class DataLoader:
    """
    统一数据加载器
    
    为上层（因子计算、策略回测）提供统一的数据加载接口
    自动处理缓存、分层存储、lookback 等逻辑
    """

    # 缓存时间（秒）
    CACHE_TTL = {
        "bars": 60,        # K线缓存1分钟
        "fundamental": 3600,  # 财务数据缓存1小时
        "factor": 300,     # 因子缓存5分钟
    }

    def __init__(self, storage: DataStorage):
        self.storage = storage
        self.master = MasterDataManager(storage)

    # ===========================
    # K线数据加载
    # ===========================

    def load_bars(
        self,
        symbols: Union[str, List[str]],
        start: date,
        end: date,
        timeframe: str = "1d",
        environment: str = "BACKTEST",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        加载 K 线数据
        
        Args:
            symbols: 证券代码或代码列表
            start: 开始日期
            end: 结束日期
            timeframe: 时间周期
            environment: 运行环境
            use_cache: 是否使用 Redis 缓存
            
        Returns:
            DataFrame，按 timestamp 升序排列
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        if not symbols:
            return pd.DataFrame()

        all_data = []

        for symbol in symbols:
            # 尝试从缓存加载
            cache_key = f"bars:{symbol}:{timeframe}:{end}"
            if use_cache:
                cached = self.storage.redis_get(cache_key)
                if cached is not None:
                    df = pd.DataFrame(cached)
                    if not df.empty:
                        df["timestamp"] = pd.to_datetime(df["timestamp"])
                        all_data.append(df)
                        continue

            # 从数据库加载
            df = self.storage.load(
                category="bars",
                symbol=symbol,
                start=start,
                end=end,
                environment=environment,
            )

            if not df.empty:
                # 过滤 timeframe
                if "timeframe" in df.columns:
                    df = df[df["timeframe"] == timeframe]

                # 缓存结果
                if use_cache and not df.empty:
                    self.storage.redis_set(
                        cache_key,
                        df.to_dict(orient="records"),
                        expire_seconds=self.CACHE_TTL["bars"],
                    )

                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        # 合并并排序
        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values(["symbol", "timestamp"])
        result = result.reset_index(drop=True)

        return result

    def load_bars_with_lookback(
        self,
        symbol: str,
        reference_date: Union[date, datetime],
        lookback_days: int,
        timeframe: str = "1d",
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        ⭐ 核心方法：带 lookback 的 K 线加载
        
        这是避免前视偏差的关键方法！
        只加载 reference_date 当天及之前 lookback_days 天内的数据
        
        Args:
            symbol: 证券代码
            reference_date: 参考日期
            lookback_days: 回看天数
            timeframe: 时间周期
            environment: 运行环境
            
        Returns:
            DataFrame
            
        Example:
            # 加载 2024-03-15 之前 60 个交易日的数据
            # 用于计算均线因子（不会引入未来数据）
            load_bars_with_lookback("600519.SH", date(2024, 3, 15), 60)
        """
        # 计算实际开始日期（往前推 lookback_days 个交易日）
        start = self.master.get_trading_day(reference_date, -lookback_days)
        
        # 参考日期转换为 date
        if isinstance(reference_date, datetime):
            end_date = reference_date.date()
        else:
            end_date = reference_date

        return self.load_bars(
            symbols=symbol,
            start=start,
            end=end_date,
            timeframe=timeframe,
            environment=environment,
        )

    def load_latest_price(
        self,
        symbol: str,
    ) -> Optional[float]:
        """
        获取最新收盘价（从 Redis 缓存）
        
        用于实盘实时估值
        """
        cache_key = f"bars:{symbol}:1d:latest_price"
        return self.storage.redis_get(cache_key)

    # ===========================
    # 财务数据加载
    # ===========================

    def load_fundamental(
        self,
        symbols: Union[str, List[str]],
        fields: Optional[List[str]] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载财务数据
        
        Args:
            symbols: 证券代码或代码列表
            fields: 要加载的字段（None=全部）
            start: 开始日期（公告日期）
            end: 结束日期（公告日期）
            environment: 运行环境
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        if not symbols:
            return pd.DataFrame()

        # TODO: 实现财务数据加载
        # 需要从 fundamental_calendar 和 fundamental_data 表联合查询
        logger.warning("Fundamental data loading not fully implemented")
        return pd.DataFrame()

    def load_fundamental_with_lookback(
        self,
        symbol: str,
        reference_date: date,
        lookback_quarters: int = 8,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        ⭐ 带 lookback 的财务数据加载
        
        只返回在 reference_date 之前已发布的财报数据
        
        Args:
            symbol: 证券代码
            reference_date: 参考日期
            lookback_quarters: 回看季度数
            fields: 要加载的字段
        """
        # 获取可用的财报数据
        reports = self.master.get_available_fundamental_data(
            symbol=symbol,
            reference_date=reference_date,
            lookback_quarters=lookback_quarters,
        )

        if not reports:
            return pd.DataFrame()

        # 加载对应的财务数据
        # TODO: 实现具体财务数据加载逻辑
        
        return pd.DataFrame()

    # ===========================
    # 因子数据加载
    # ===========================

    def load_factor(
        self,
        factor_name: str,
        symbols: Union[str, List[str]],
        start: date,
        end: date,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载因子值
        
        Args:
            factor_name: 因子名称
            symbols: 证券代码或代码列表
            start: 开始日期
            end: 结束日期
            environment: 运行环境
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        if not symbols:
            return pd.DataFrame()

        # 构建查询
        conditions = [
            f"factor_name = :factor_name",
            f"environment = :env",
            f"timestamp >= :start",
            f"timestamp <= :end",
        ]
        params = {
            "factor_name": factor_name,
            "env": environment,
            "start": start,
            "end": end,
        }

        # 添加 symbol 条件
        if len(symbols) == 1:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbols[0]
        else:
            conditions.append("symbol = ANY(:symbols)")
            params["symbols"] = symbols

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT * FROM factor_values
            WHERE {where_clause}
            ORDER BY timestamp, symbol
        """

        df = self.storage.query(sql, params)
        
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        return df

    def load_factor_with_lookback(
        self,
        factor_name: str,
        symbol: str,
        reference_date: date,
        lookback_days: int,
    ) -> pd.DataFrame:
        """
        带 lookback 的因子加载（避免前视偏差）
        """
        start = self.master.get_trading_day(reference_date, -lookback_days)
        
        return self.load_factor(
            factor_name=factor_name,
            symbols=symbol,
            start=start,
            end=reference_date,
        )

    # ===========================
    # 持仓与账户数据加载
    # ===========================

    def load_positions(
        self,
        account_id: str,
        snapshot_date: Optional[date] = None,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载持仓快照
        
        Args:
            account_id: 账户ID
            snapshot_date: 快照日期（None=最新）
            environment: 运行环境
        """
        if snapshot_date:
            sql = """
                SELECT * FROM position_snapshots
                WHERE account_id = :account_id
                  AND snapshot_date = :date
                  AND environment = :env
                LIMIT 1
            """
            df = self.storage.query(sql, {
                "account_id": account_id,
                "date": snapshot_date,
                "env": environment,
            })
        else:
            sql = """
                SELECT * FROM position_snapshots
                WHERE account_id = :account_id
                  AND environment = :env
                ORDER BY snapshot_date DESC
                LIMIT 1
            """
            df = self.storage.query(sql, {
                "account_id": account_id,
                "env": environment,
            })

        return df

    def load_account_snapshots(
        self,
        account_id: str,
        start: date,
        end: date,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载账户快照序列（用于权益曲线绘制）
        """
        sql = """
            SELECT * FROM account_snapshots
            WHERE account_id = :account_id
              AND snapshot_date BETWEEN :start AND :end
              AND environment = :env
            ORDER BY snapshot_date
        """

        return self.storage.query(sql, {
            "account_id": account_id,
            "start": start,
            "end": end,
            "env": environment,
        })

    def load_orders(
        self,
        account_id: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载订单记录
        """
        conditions = ["account_id = :account_id", "environment = :env"]
        params: Dict[str, Any] = {
            "account_id": account_id,
            "env": environment,
        }

        if start:
            conditions.append("created_at >= :start")
            params["start"] = start

        if end:
            conditions.append("created_at <= :end")
            params["end"] = end

        if symbol:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbol

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT * FROM orders
            WHERE {where_clause}
            ORDER BY created_at DESC
        """

        return self.storage.query(sql, params)

    def load_trades(
        self,
        account_id: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        symbol: Optional[str] = None,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载成交记录
        """
        conditions = ["account_id = :account_id", "environment = :env"]
        params: Dict[str, Any] = {
            "account_id": account_id,
            "env": environment,
        }

        if start:
            conditions.append("traded_at >= :start")
            params["start"] = start

        if end:
            conditions.append("traded_at <= :end")
            params["end"] = end

        if symbol:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbol

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT * FROM trades
            WHERE {where_clause}
            ORDER BY traded_at DESC
        """

        return self.storage.query(sql, params)

    # ===========================
    # 多标的批量加载
    # ===========================

    def load_bars_batch(
        self,
        symbols: List[str],
        start: date,
        end: date,
        timeframe: str = "1d",
        environment: str = "BACKTEST",
    ) -> Dict[str, pd.DataFrame]:
        """
        批量加载多个标的的 K 线数据
        
        Returns:
            Dict {symbol: DataFrame}
        """
        result = {}
        
        for symbol in symbols:
            df = self.load_bars(
                symbols=symbol,
                start=start,
                end=end,
                timeframe=timeframe,
                environment=environment,
            )
            if not df.empty:
                result[symbol] = df

        return result

    def load_panel_data(
        self,
        symbols: List[str],
        start: date,
        end: date,
        fields: List[str],
        timeframe: str = "1d",
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        加载面板数据（宽表格式）
        
        用于多因子分析，每行一个时间点，每列一个标的
        
        Args:
            symbols: 证券代码列表
            start: 开始日期
            end: 结束日期
            fields: 要加载的字段（如 close, volume, factor values）
            timeframe: 时间周期
            
        Returns:
            DataFrame with MultiIndex (timestamp, symbol)
        """
        # 加载 K 线基础数据
        bars = self.load_bars(
            symbols=symbols,
            start=start,
            end=end,
            timeframe=timeframe,
            environment=environment,
        )

        if bars.empty:
            return pd.DataFrame()

        # 透视为面板格式
        pivot_fields = {}
        for field in fields:
            if field in bars.columns:
                pivot_fields[field] = bars.pivot_table(
                    index="timestamp",
                    columns="symbol",
                    values=field,
                )

        # 合并
        result = pd.concat(pivot_fields, axis=1)
        result.index.name = "timestamp"
        
        return result

    # ===========================
    # 工具方法
    # ===========================

    def get_trading_days(
        self,
        start: date,
        end: date,
        exchange: str = "SH",
    ) -> List[date]:
        """获取交易日列表"""
        from .models import Exchange
        return self.master.get_trading_days(start, end, Exchange(exchange))

    def is_trading_day(self, date: date, exchange: str = "SH") -> bool:
        """判断是否为交易日"""
        from .models import Exchange
        return self.master.is_trading_day(date, Exchange(exchange))

    def preload_to_cache(
        self,
        symbols: List[str],
        start: date,
        end: date,
        timeframe: str = "1d",
    ):
        """
        预加载数据到 Redis 缓存
        
        用于回测前加速
        """
        logger.info(f"Preloading {len(symbols)} symbols to cache...")
        
        count = 0
        for symbol in symbols:
            self.load_bars(
                symbols=symbol,
                start=start,
                end=end,
                timeframe=timeframe,
                use_cache=True,
            )
            count += 1

        logger.info(f"Preload done: {count}/{len(symbols)}")
