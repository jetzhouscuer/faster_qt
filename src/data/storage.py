# -*- coding: utf-8 -*-
"""
数据存储引擎
统一管理 PostgreSQL + TimescaleDB 和 Redis 的读写操作
"""

import io
import json
import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Union

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class DataStorage:
    """
    统一数据存储引擎
    
    支持分层存储：
    - Redis: 实时热数据（最新行情、因子缓存）
    - TimescaleDB: 时序数据（K线、因子值）
    - PostgreSQL: 关系数据（主数据、持仓、订单）
    - MinIO/Parquet: 历史归档
    """

    def __init__(
        self,
        db_url: str,
        redis_url: str,
        minio_url: Optional[str] = None,
        minio_access_key: Optional[str] = None,
        minio_secret_key: Optional[str] = None,
    ):
        """
        Args:
            db_url: PostgreSQL 连接 URL
            redis_url: Redis 连接 URL
            minio_url: MinIO 服务器地址（可选，用于历史归档）
            minio_access_key: MinIO Access Key
            minio_secret_key: MinIO Secret Key
        """
        self.db_url = db_url
        self.redis_url = redis_url
        self.minio_url = minio_url
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key

        # 初始化数据库连接
        self._engine: Engine = create_engine(
            db_url,
            poolclass=NullPool,  # 避免连接池在高并发下的问题
            echo=False,
        )
        self._session_factory = sessionmaker(bind=self._engine)

        # 初始化 Redis（延迟导入避免未安装时的报错）
        self._redis = None
        self._redis_client = None

        # MinIO 客户端（可选）
        self._minio_client = None

        logger.info(f"DataStorage initialized with db={db_url[:20]}...")

    # ===========================
    # Redis 操作
    # ===========================

    @property
    def redis(self):
        """延迟初始化 Redis 连接"""
        if self._redis_client is None:
            import redis
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
            )
        return self._redis_client

    def redis_set(
        self,
        key: str,
        value: Union[str, Dict, List],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        设置 Redis 值
        
        Args:
            key: 键
            value: 值（会自动 JSON 序列化）
            expire_seconds: 过期时间（秒）
        """
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            self.redis.set(key, value)
            if expire_seconds:
                self.redis.expire(key, expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis SET failed: key={key}, error={e}")
            return False

    def redis_get(self, key: str, default: Any = None) -> Any:
        """获取 Redis 值（自动 JSON 反序列化）"""
        try:
            value = self.redis.get(key)
            if value is None:
                return default
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Redis GET failed: key={key}, error={e}")
            return default

    def redis_hset(self, name: str, mapping: Dict[str, Any]) -> bool:
        """设置 Redis Hash"""
        try:
            self.redis.hset(name, mapping=mapping)
            return True
        except Exception as e:
            logger.error(f"Redis HSET failed: name={name}, error={e}")
            return False

    def redis_hget(self, name: str, key: str, default: Any = None) -> Any:
        """获取 Redis Hash 字段"""
        try:
            value = self.redis.hget(name, key)
            if value is None:
                return default
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Redis HGET failed: name={name}, key={key}, error={e}")
            return default

    def redis_hgetall(self, name: str) -> Dict[str, Any]:
        """获取 Redis Hash 所有字段"""
        try:
            return self.redis.hgetall(name)
        except Exception as e:
            logger.error(f"Redis HGETALL failed: name={name}, error={e}")
            return {}

    def redis_publish(self, channel: str, message: Union[str, Dict]) -> int:
        """发布到 Redis Pub/Sub 频道"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, default=str)
            return self.redis.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis PUBLISH failed: channel={channel}, error={e}")
            return 0

    def redis_exists(self, key: str) -> bool:
        """检查 Redis key 是否存在"""
        try:
            return bool(self.redis.exists(key))
        except Exception:
            return False

    def redis_delete(self, key: str) -> bool:
        """删除 Redis key"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE failed: key={key}, error={e}")
            return False

    # ===========================
    # 数据库操作
    # ===========================

    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话（上下文管理器）"""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def execute(self, sql: str, params: Optional[Dict] = None) -> Any:
        """执行原生 SQL"""
        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            if result.returns_rows:
                return result.fetchall()
            return result.rowcount

    def query(self, sql: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """执行查询并返回 DataFrame"""
        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            columns = result.keys()
            data = result.fetchall()
            return pd.DataFrame(data, columns=columns)

    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        """检查表是否存在"""
        inspector = inspect(self._engine)
        schemas = [schema] if schema else self._engine.dialect.get_schema_names(self._engine)
        for s in schemas:
            if table_name in inspector.get_table_names(schema=s):
                return True
        return False

    # ===========================
    # 通用读写接口
    # ===========================

    def save(
        self,
        category: str,
        data: pd.DataFrame,
        environment: str = "BACKTEST",
        if_exists: str = "append",
    ) -> bool:
        """
        保存数据到 TimescaleDB（时序数据）或 PostgreSQL（关系数据）
        
        Args:
            category: 数据类别（bars, positions, orders 等）
            data: DataFrame 数据
            environment: 运行环境标识
            if_exists: 表存在时的行为（append/replace/fail）
        """
        if data.empty:
            logger.warning(f"Empty DataFrame for category={category}, skip save")
            return True

        try:
            df = data.copy()
            if "environment" not in df.columns:
                df["environment"] = environment

            table_name = self._get_table_name(category)
            
            with self.get_session() as session:
                df.to_sql(
                    name=table_name,
                    con=session.connection(),
                    schema="public",
                    if_exists=if_exists,
                    index=False,
                    method="multi",
                    chunksize=1000,
                )

            logger.info(f"Saved {len(df)} rows to {table_name}")
            return True

        except Exception as e:
            logger.error(f"Save failed: category={category}, error={e}")
            return False

    def load(
        self,
        category: str,
        symbol: Optional[str] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
        environment: str = "BACKTEST",
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        加载数据
        
        Args:
            category: 数据类别
            symbol: 证券代码（可选）
            start: 开始日期
            end: 结束日期
            environment: 运行环境
            limit: 返回行数限制
        """
        try:
            table_name = self._get_table_name(category)
            
            # 构建查询条件
            conditions = ["environment = :env"]
            params: Dict[str, Any] = {"env": environment}

            if symbol and "symbol" in self._get_table_columns(category):
                conditions.append("symbol = :symbol")
                params["symbol"] = symbol

            if start and "timestamp" in self._get_table_columns(category):
                conditions.append("timestamp >= :start")
                params["start"] = start

            if end and "timestamp" in self._get_table_columns(category):
                conditions.append("timestamp <= :end")
                params["end"] = end

            where_clause = " AND ".join(conditions)
            limit_clause = f"LIMIT {limit}" if limit else ""

            sql = f"""
                SELECT * FROM {table_name}
                WHERE {where_clause}
                ORDER BY timestamp DESC
                {limit_clause}
            """

            return self.query(sql, params)

        except Exception as e:
            logger.error(f"Load failed: category={category}, error={e}")
            return pd.DataFrame()

    def load_with_lookback(
        self,
        category: str,
        symbol: str,
        reference_date: Union[date, datetime],
        lookback_days: int,
        environment: str = "BACKTEST",
    ) -> pd.DataFrame:
        """
        ⭐ 核心方法：带 lookback 的数据加载（避免前视偏差）
        
        只加载 reference_date 当天及之前 lookback_days 天内的数据
        
        Args:
            category: 数据类别
            symbol: 证券代码
            reference_date: 参考日期
            lookback_days: 回看天数
            environment: 运行环境
        """
        from .master import MasterDataManager
        
        # 获取回看的开始日期（跳过非交易日）
        mm = MasterDataManager(self)
        start = mm.get_trading_day(reference_date, -lookback_days)
        
        if isinstance(reference_date, datetime):
            end_date = reference_date.date()
        else:
            end_date = reference_date

        return self.load(
            category=category,
            symbol=symbol,
            start=start,
            end=end_date,
            environment=environment,
        )

    def get_latest_date(self, category: str, symbol: Optional[str] = None) -> Optional[date]:
        """获取某类数据的最新日期"""
        try:
            table_name = self._get_table_name(category)
            
            conditions = []
            params: Dict[str, Any] = {}
            
            if symbol:
                conditions.append("symbol = :symbol")
                params["symbol"] = symbol

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            sql = f"""
                SELECT MAX(timestamp::date) as max_date
                FROM {table_name}
                WHERE {where_clause}
            """

            result = self.query(sql, params)
            if result.empty or result["max_date"].iloc[0] is None:
                return None
            return result["max_date"].iloc[0]

        except Exception as e:
            logger.error(f"Get latest date failed: category={category}, error={e}")
            return None

    # ===========================
    # 辅助方法
    # ===========================

    def _get_table_name(self, category: str) -> str:
        """获取数据类别对应的表名"""
        table_mapping = {
            "bars": "bars",
            "ticks": "ticks",
            "orders": "orders",
            "trades": "trades",
            "positions": "positions",
            "account_snapshots": "account_snapshots",
            "position_snapshots": "position_snapshots",
            "factor_values": "factor_values",
            "factor_ic": "factor_ic",
            "symbols": "symbols",
            "trading_calendar": "trading_calendar",
            "fundamental_calendar": "fundamental_calendar",
        }
        return table_mapping.get(category, category)

    def _get_table_columns(self, category: str) -> List[str]:
        """获取表的所有列名"""
        table_name = self._get_table_name(category)
        try:
            inspector = inspect(self._engine)
            return [col["name"] for col in inspector.get_columns(table_name)]
        except Exception:
            return []

    # ===========================
    # 归档操作
    # ===========================

    def archive_old_data(
        self,
        category: str,
        before_date: date,
        archive_path: str,
    ) -> bool:
        """
        将指定日期之前的数据归档到 Parquet 文件
        
        Args:
            category: 数据类别
            before_date: 归档截止日期
            archive_path: 归档文件路径
        """
        try:
            # 1. 读取要归档的数据
            data = self.load(category, start=None, end=before_date)
            
            if data.empty:
                logger.info(f"No data to archive for category={category}")
                return True

            # 2. 写入 Parquet 文件
            partition_key = f"{category}/{before_date.strftime('%Y%m%d')}.parquet"
            full_path = f"{archive_path}/{partition_key}"
            
            # 使用 pandas 直接写入
            data.to_parquet(full_path, index=False)
            
            # 3. 删除已归档的数据
            table_name = self._get_table_name(category)
            with self.get_session() as session:
                session.execute(
                    text(f"DELETE FROM {table_name} WHERE timestamp < :before"),
                    {"before": before_date}
                )

            logger.info(f"Archived {len(data)} rows to {full_path}")
            return True

        except Exception as e:
            logger.error(f"Archive failed: category={category}, error={e}")
            return False

    # ===========================
    # 批量操作优化
    # ===========================

    def bulk_save(
        self,
        category: str,
        data_list: List[Dict[str, Any]],
        environment: str = "BACKTEST",
    ) -> bool:
        """批量保存数据（用于高频写入）"""
        if not data_list:
            return True

        df = pd.DataFrame(data_list)
        df["environment"] = environment
        return self.save(category, df)

    def bulk_save_bars(
        self,
        bars: List[Dict[str, Any]],
        environment: str = "BACKTEST",
    ) -> bool:
        """
        批量保存 K 线数据（优化版）
        
        使用 COPY 协议快速写入，适合大量历史数据初始化
        """
        if not bars:
            return True

        df = pd.DataFrame(bars)
        df["environment"] = environment

        try:
            table_name = "bars"
            
            # 使用 PostgreSQL COPY 协议（通过 to_sql 的 method='copy'）
            # 或者直接用 pandas 的 to_sql
            with self.get_session() as session:
                df.to_sql(
                    name=table_name,
                    con=session.connection(),
                    if_exists="append",
                    index=False,
                    method="multi",
                    chunksize=5000,
                )

            logger.info(f"Bulk saved {len(df)} bars")
            return True

        except Exception as e:
            logger.error(f"Bulk save bars failed: error={e}")
            return False

    # ===========================
    # 清理与维护
    # ===========================

    def close(self):
        """关闭所有连接"""
        if self._engine:
            self._engine.dispose()
        if self._redis_client:
            self._redis_client.close()
        logger.info("DataStorage connections closed")
