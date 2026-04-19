# -*- coding: utf-8 -*-
"""
数据采集模块
支持多种数据源的接入：Tushare、AKShare、掘金量化等
"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

import pandas as pd

from .models import Bar, Tick, FundamentalData, TimeFrame
from .storage import DataStorage
from .validator import DataValidator

logger = logging.getLogger(__name__)


# ===========================
# 数据源抽象基类
# ===========================


class DataSource(ABC):
    """
    数据源抽象基类
    
    所有数据源（AKShare、Tushare、掘金等）都需要实现此接口
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称"""
        pass

    @property
    def supported_categories(self) -> List[str]:
        """支持的数据类别"""
        return ["bars"]

    @abstractmethod
    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        """
        获取 K 线数据
        
        Args:
            symbol: 证券代码
            start: 开始日期
            end: 结束日期
            timeframe: 时间周期
            
        Returns:
            DataFrame，包含 open/high/low/close/volume/amount 字段
        """
        pass

    def get_latest_bars(
        self,
        symbol: str,
        n: int = 1,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        """获取最新 N 条 K 线"""
        end = date.today()
        start = end - timedelta(days=n * 2)  # 多取一些保险
        return self.fetch_bars(symbol, start, end, timeframe)

    def fetch_fundamental(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """获取财务数据（可选实现）"""
        raise NotImplementedError(f"{self.source_name} does not support fundamental data")

    def fetch_market_info(self, symbol: str) -> Dict[str, Any]:
        """获取市场信息（可选实现）"""
        raise NotImplementedError(f"{self.source_name} does not support market info")


# ===========================
# AKShare 数据源实现
# ===========================


class AKShareSource(DataSource):
    """
    AKShare 数据源
    
    AKShare 是开源的 A 股数据接口，免费使用
    官网: https://akshare.akfamily.xyz/
    """

    def __init__(self, storage: Optional[DataStorage] = None):
        self._storage = storage
        self._ak = None

    @property
    def source_name(self) -> str:
        return "akshare"

    @property
    def supported_categories(self) -> List[str]:
        return ["bars", "fundamental", "flow", "index"]

    @property
    def ak(self):
        """延迟导入 AKShare"""
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak

    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        """
        使用 AKShare 获取 K 线数据
        
        Args:
            symbol: 证券代码，如 "600519"（无需后缀）
            start: 开始日期
            end: 结束日期
            timeframe: 时间周期
        """
        try:
            # AKShare 股票代码格式处理
            code = symbol.split(".")[0]
            
            if timeframe == "1d":
                df = self.ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",  # 前复权
                )
            else:
                # 分钟数据
                period_map = {
                    "1m": "1", "5m": "5", "15m": "15",
                    "30m": "30", "60m": "60"
                }
                df = self.ak.stock_zh_a_hist(
                    symbol=code,
                    period=period_map.get(timeframe, "1"),
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )

            if df is None or df.empty:
                return pd.DataFrame()

            # 标准化列名
            df = self._normalize_bars(df, symbol)
            return df

        except Exception as e:
            logger.error(f"AKShare fetch_bars failed: symbol={symbol}, error={e}")
            return pd.DataFrame()

    def _normalize_bars(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """标准化 K 线数据格式"""
        # AKShare 列名映射
        column_map = {
            "日期": "timestamp",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "change_pct",
        }

        df = df.rename(columns=column_map)
        
        # 确保必要的列存在
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing column {col} in AKShare data")
                return pd.DataFrame()

        # 添加 symbol 列
        df["symbol"] = symbol
        
        # 转换时间格式
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # 添加 timeframe
        df["timeframe"] = "1d"
        
        # 添加复权因子（AKShare 前复权数据，复权因子为 1）
        df["factor"] = 1.0

        # 选择并排序列
        columns = [
            "symbol", "timestamp", "timeframe",
            "open", "high", "low", "close", "volume", "amount", "factor"
        ]
        df = df[[c for c in columns if c in df.columns]]

        return df

    def fetch_fundamental(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """获取财务数据"""
        try:
            code = symbol.split(".")[0]
            
            # 资产负债
            df_debt = self.ak.stock_zcfz_em(symbol=code)
            
            # 利润表
            df_profit = self.ak.stock_lrb_em(symbol=code)
            
            # 现金流量
            df_cash = self.ak.stock_xjll_em(symbol=code)

            # 合并
            # TODO: 实现真正的财务数据合并逻辑
            
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"AKShare fetch_fundamental failed: symbol={symbol}, error={e}")
            return pd.DataFrame()

    def fetch_market_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        try:
            code = symbol.split(".")[0]
            df = self.ak.stock_individual_info_em(symbol=code)
            
            if df is None or df.empty:
                return {}
            
            return dict(zip(df["item"], df["value"]))

        except Exception as e:
            logger.error(f"AKShare fetch_market_info failed: symbol={symbol}, error={e}")
            return {}


# ===========================
# Tushare 数据源实现
# ===========================


class TushareSource(DataSource):
    """
    Tushare 数据源
    
    需要设置 token
    官网: https://tushare.pro/
    """

    def __init__(self, token: str, storage: Optional[DataStorage] = None):
        self.token = token
        self._storage = storage
        self._ts = None

    @property
    def source_name(self) -> str:
        return "tushare"

    @property
    def supported_categories(self) -> List[str]:
        return ["bars", "fundamental", "flow", "index", "moneyflow"]

    @property
    def ts(self):
        """延迟导入 Tushare"""
        if self._ts is None:
            import tushare as ts
            ts.set_token(self.token)
            self._ts = ts.pro_api()
        return self._ts

    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        """使用 Tushare 获取 K 线数据"""
        try:
            # 转换代码格式
            ts_code = self._to_ts_code(symbol)
            
            # Tushare 的 timeframe 映射
            freq_map = {
                "1d": "D", "1m": "1", "5m": "5",
                "15m": "15", "30m": "30", "1h": "60",
            }
            freq = freq_map.get(timeframe, "D")

            df = self.ts.ts_daily(
                ts_code=ts_code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # 标准化
            df = df.rename(columns={
                "ts_code": "symbol",
                "trade_date": "timestamp",
            })
            df["symbol"] = symbol
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["timeframe"] = timeframe
            df["factor"] = 1.0

            return df

        except Exception as e:
            logger.error(f"Tushare fetch_bars failed: symbol={symbol}, error={e}")
            return pd.DataFrame()

    def fetch_fundancial(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """获取财务数据"""
        try:
            ts_code = self._to_ts_code(symbol)
            
            # 利润表
            df_profit = self.ts.income(
                ts_code=ts_code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )

            return df_profit if df_profit is not None else pd.DataFrame()

        except Exception as e:
            logger.error(f"Tushare fetch_fundamental failed: symbol={symbol}, error={e}")
            return pd.DataFrame()

    def _to_ts_code(self, symbol: str) -> str:
        """转换为 Tushare 格式"""
        code, exchange = symbol.split(".")
        exchange_map = {"SH": "SH", "SZ": "SZ", "BJ": "BJ"}
        return f"{code}.{exchange_map.get(exchange, 'SH')}"


# ===========================
# 增量采集器
# ===========================


class IncrementalFetcher:
    """
    增量数据采集器
    
    用于日终定时任务，只采集自上次采集后的增量数据
    """

    def __init__(
        self,
        sources: Dict[str, DataSource],
        storage: DataStorage,
        validator: Optional[DataValidator] = None,
    ):
        """
        Args:
            sources: 数据源字典 {category: source}
            storage: 数据存储
            validator: 数据校验器
        """
        self.sources = sources
        self.storage = storage
        self.validator = validator or DataValidator()

    def daily_update(
        self,
        categories: Optional[List[str]] = None,
        trade_date: Optional[date] = None,
    ) -> Dict[str, bool]:
        """
        执行日终增量更新
        
        Args:
            categories: 要更新的类别（None=全部）
            trade_date: 交易日期（默认今天）
            
        Returns:
            更新结果字典 {category: success}
        """
        if trade_date is None:
            trade_date = date.today()

        results = {}
        categories = categories or list(self.sources.keys())

        for category in categories:
            source = self.sources.get(category)
            if not source:
                logger.warning(f"No source for category={category}")
                results[category] = False
                continue

            try:
                # 获取该类别的最新日期
                latest = self.storage.get_latest_date(category)
                
                if latest:
                    # 从最新日期+1天开始
                    from .master import MasterDataManager
                    mm = MasterDataManager(self.storage)
                    start = mm.get_next_trading_day(latest)
                else:
                    # 首次采集，回溯1年
                    start = trade_date - timedelta(days=365)

                # 采集数据
                logger.info(
                    f"Fetching {category} from {start} to {trade_date}"
                )
                data = source.fetch_bars(
                    symbol="*",  # TODO: 需要传入具体股票列表
                    start=start,
                    end=trade_date,
                )

                if data.empty:
                    logger.info(f"No new data for category={category}")
                    results[category] = True
                    continue

                # 数据校验
                quality_result = self.validator.validate(category, data)
                if not quality_result.passed:
                    logger.warning(
                        f"Data quality check failed for {category}: "
                        f"{quality_result.details}"
                    )
                    # 可以选择是否在质量检查失败时停止
                    # raise DataQualityError(...)

                # 存储
                success = self.storage.save(category, data)
                results[category] = success

                logger.info(
                    f"Updated {category}: {len(data)} rows saved"
                )

            except Exception as e:
                logger.error(f"Daily update failed for {category}: {e}")
                results[category] = False

        return results


# ===========================
# 历史全量采集器
# ===========================


class HistoricalFetcher:
    """
    历史全量数据采集器
    
    用于首次部署或重建数据仓库
    """

    def __init__(
        self,
        sources: Dict[str, DataSource],
        storage: DataStorage,
        validator: Optional[DataValidator] = None,
    ):
        self.sources = sources
        self.storage = storage
        self.validator = validator or DataValidator()

    def fetch_all(
        self,
        symbols: List[str],
        category: str,
        start: date,
        end: date,
        batch_size: int = 50,
    ) -> Dict[str, int]:
        """
        批量采集历史数据
        
        Args:
            symbols: 股票代码列表
            category: 数据类别
            start: 开始日期
            end: 结束日期
            batch_size: 每批处理的股票数量
            
        Returns:
            采集结果 {symbol: row_count}
        """
        source = self.sources.get(category)
        if not source:
            logger.error(f"No source for category={category}")
            return {}

        results = {}
        total = len(symbols)

        for i in range(0, total, batch_size):
            batch = symbols[i:i + batch_size]
            logger.info(
                f"Fetching batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}: "
                f"{len(batch)} symbols"
            )

            all_data = []

            for symbol in batch:
                try:
                    data = source.fetch_bars(
                        symbol=symbol,
                        start=start,
                        end=end,
                    )
                    if not data.empty:
                        all_data.append(data)
                        results[symbol] = len(data)
                except Exception as e:
                    logger.error(f"Fetch failed for {symbol}: {e}")
                    results[symbol] = 0

            if all_data:
                # 合并并保存
                combined = pd.concat(all_data, ignore_index=True)
                
                # 校验
                self.validator.validate(category, combined)
                
                # 保存
                self.storage.save(category, combined, if_exists="append")

            logger.info(
                f"Batch done: {min(i + batch_size, total)}/{total}"
            )

        return results
