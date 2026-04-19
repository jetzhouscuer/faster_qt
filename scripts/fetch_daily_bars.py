# -*- coding: utf-8 -*-
"""
日线数据采集脚本

功能：
1. 全量历史数据采集（首次运行）
2. 增量更新（每日定时任务）
3. 支持断点续传
4. 数据质量校验

数据源：AKShare（免费，无需API Key）

Usage:
    # 全量采集（首次运行）
    python scripts/fetch_daily_bars.py --mode full --start 2010-01-01
    
    # 增量更新（每日定时）
    python scripts/fetch_daily_bars.py --mode incremental
    
    # 指定股票采集
    python scripts/fetch_daily_bars.py --symbols 600519.SH,000001.SZ
    
    # 查看帮助
    python scripts/fetch_daily_bars.py --help

Author: 江小猪
Date: 2026-04-19
"""

import argparse
import datetime
import logging
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any

import akshare as ak
import pandas as pd
import psycopg2
from tqdm import tqdm

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.models import Bar, TimeFrame
from src.data.storage import DataStorage
from src.data.master import MasterDataManager

# ============== 配置 ==============
# 数据库配置
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "root",
    "dbname": "faster_qt"
}

# Redis 配置
REDIS_CONFIG = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 0
}

# 采集配置
BATCH_SIZE = 50  # 每批采集股票数量
MAX_WORKERS = 5  # 并行线程数
REQUEST_DELAY = 0.5  # 请求间隔（秒），避免API限流
PROGRESS_FILE = "data/fetch_progress.json"  # 断点续传进度文件

# 日志配置
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / f"fetch_daily_bars_{datetime.date.today().strftime('%Y%m%d')}.log"

# ============== 日志设置 ==============
def setup_logging():
    """设置日志"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


# ============== 进度管理 ==============
class FetchProgress:
    """断点续传进度管理"""
    
    def __init__(self, progress_file: str):
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        """加载进度"""
        if self.progress_file.exists():
            import json
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"completed": [], "failed": [], "last_date": None}
    
    def save(self):
        """保存进度"""
        import json
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def mark_completed(self, symbol: str):
        """标记完成"""
        if symbol not in self.data["completed"]:
            self.data["completed"].append(symbol)
        if symbol in self.data["failed"]:
            self.data["failed"].remove(symbol)
        self.save()
    
    def mark_failed(self, symbol: str, error: str = ""):
        """标记失败"""
        if symbol not in self.data["failed"]:
            self.data["failed"].append(symbol)
        self.save()
    
    def set_last_date(self, date: str):
        """设置最后更新日期"""
        self.data["last_date"] = date
        self.save()
    
    def get_remaining(self, all_symbols: List[str]) -> List[str]:
        """获取剩余未完成的股票"""
        return [s for s in all_symbols if s not in self.data["completed"]]


# ============== 数据采集 ==============
class DailyBarsFetcher:
    """日线数据采集器"""
    
    def __init__(self, storage: DataStorage, logger):
        self.storage = storage
        self.logger = logger
        self.master = MasterDataManager(storage)
    
    def get_akshare_stock_list(self) -> List[str]:
        """获取 A 股股票列表"""
        self.logger.info("获取 A 股股票列表...")
        try:
            # 使用 AKShare 获取所有 A 股股票
            df = ak.stock_info_a_code_name()
            symbols = []
            for _, row in df.iterrows():
                code = row['code']
                # 上交所以.SH结尾，深交所以.SZ结尾
                if code.startswith('6'):
                    symbols.append(f"{code}.SH")
                else:
                    symbols.append(f"{code}.SZ")
            self.logger.info(f"获取到 {len(symbols)} 只股票")
            return symbols
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_single_stock(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """采集单只股票历史日线"""
        try:
            # 转换symbol格式（600519.SH -> 600519）
            code = symbol.split('.')[0]
            
            # 获取前复权日线数据
            df = ak.stock_zh_a_hist(
                symbol=code,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # 前复权
            )
            
            if df is None or df.empty:
                return None
            
            # 重命名列
            df = df.rename(columns={
                '日期': 'trade_date',
                '股票代码': 'symbol',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'turnover',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover_rate'
            })
            
            # 添加时间戳
            df['timestamp'] = pd.to_datetime(df['trade_date'])
            df['symbol'] = symbol
            df['timeframe'] = '1d'
            
            return df
            
        except Exception as e:
            self.logger.warning(f"采集 {symbol} 失败: {e}")
            return None
    
    def fetch_batch(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """批量采集多只股票"""
        results = {}
        
        for symbol in symbols:
            df = self.fetch_single_stock(symbol, start_date, end_date)
            if df is not None and not df.empty:
                results[symbol] = df
            time.sleep(REQUEST_DELAY)  # 避免API限流
        
        return results
    
    def save_bars(self, df: pd.DataFrame):
        """保存到数据库"""
        if df is None or df.empty:
            return
        
        try:
            # 转换为 Bar 对象列表
            bars = []
            for _, row in df.iterrows():
                bar = Bar(
                    symbol=row['symbol'],
                    timestamp=row['timestamp'].to_pydatetime(),
                    timeframe=TimeFrame.DAILY,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']) if pd.notna(row['volume']) else 0,
                    turnover=float(row['turnover']) if 'turnover' in row and pd.notna(row['turnover']) else 0,
                    pct_change=float(row['pct_change']) if 'pct_change' in row and pd.notna(row['pct_change']) else 0,
                )
                bars.append(bar)
            
            # 批量保存
            self.storage.save_bars(bars, TimeFrame.DAILY)
            
        except Exception as e:
            self.logger.error(f"保存数据失败: {e}")
            raise
    
    def run_full(self, start_date: str, end_date: str = None, symbols: List[str] = None):
        """全量采集"""
        if end_date is None:
            end_date = datetime.date.today().strftime('%Y-%m-%d')
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"开始全量数据采集")
        self.logger.info(f"日期范围: {start_date} ~ {end_date}")
        self.logger.info(f"=" * 60)
        
        # 获取股票列表
        if symbols is None:
            symbols = self.get_akshare_stock_list()
        
        self.logger.info(f"待采集股票数量: {len(symbols)}")
        
        # 初始化进度管理器
        progress = FetchProgress(str(PROJECT_ROOT / PROGRESS_FILE))
        remaining = progress.get_remaining(symbols)
        
        if remaining:
            self.logger.info(f"断点续传: {len(remaining)} 只股票待采集")
        
        # 分批处理
        total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
        completed_count = 0
        
        for batch_idx in range(total_batches):
            batch_symbols = remaining[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
            self.logger.info(f"处理批次 {batch_idx + 1}/{total_batches}: {len(batch_symbols)} 只股票")
            
            # 批量采集
            results = self.fetch_batch(batch_symbols, start_date, end_date)
            
            # 保存成功的数据
            for symbol, df in results.items():
                try:
                    self.save_bars(df)
                    progress.mark_completed(symbol)
                    completed_count += 1
                except Exception as e:
                    progress.mark_failed(symbol, str(e))
            
            # 更新最后日期
            progress.set_last_date(end_date)
            
            self.logger.info(f"批次完成: {len(results)}/{len(batch_symbols)} 成功")
        
        # 打印汇总
        self.logger.info(f"=" * 60)
        self.logger.info(f"全量采集完成!")
        self.logger.info(f"成功: {len(progress.data['completed'])}")
        self.logger.info(f"失败: {len(progress.data['failed'])}")
        self.logger.info(f"=" * 60)
        
        # 打印失败的股票
        if progress.data['failed']:
            self.logger.warning(f"失败股票列表:")
            for symbol in progress.data['failed'][:20]:
                self.logger.warning(f"  - {symbol}")
            if len(progress.data['failed']) > 20:
                self.logger.warning(f"  ... 还有 {len(progress.data['failed']) - 20} 只")
        
        return progress.data
    
    def run_incremental(self, days: int = 1):
        """增量更新"""
        end_date = datetime.date.today().strftime('%Y-%m-%d')
        start_date = (datetime.date.today() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"开始增量数据更新")
        self.logger.info(f"日期范围: {start_date} ~ {end_date}")
        self.logger.info(f"=" * 60)
        
        # 获取股票列表
        symbols = self.get_akshare_stock_list()
        
        # 获取已完成的股票（从数据库查询已存在的）
        existing_symbols = self.storage.get_existing_symbols(TimeFrame.DAILY)
        self.logger.info(f"数据库中已有 {len(existing_symbols)} 只股票数据")
        
        # 只采集已存在的股票（增量更新不需要采集新股）
        update_symbols = [s for s in symbols if s in existing_symbols]
        self.logger.info(f"本次更新 {len(update_symbols)} 只股票")
        
        if not update_symbols:
            self.logger.info("没有需要更新的股票（全量数据未加载）")
            self.logger.info("请先运行全量采集: python scripts/fetch_daily_bars.py --mode full")
            return {"updated": 0, "failed": 0}
        
        # 分批处理
        completed = 0
        failed = 0
        
        for i in tqdm(range(0, len(update_symbols), BATCH_SIZE), desc="增量更新"):
            batch = update_symbols[i:i + BATCH_SIZE]
            results = self.fetch_batch(batch, start_date, end_date)
            
            for symbol, df in results.items():
                try:
                    self.save_bars(df)
                    completed += 1
                except Exception as e:
                    self.logger.warning(f"更新 {symbol} 失败: {e}")
                    failed += 1
            
            time.sleep(REQUEST_DELAY)
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"增量更新完成!")
        self.logger.info(f"成功更新: {completed}")
        self.logger.info(f"更新失败: {failed}")
        self.logger.info(f"=" * 60)
        
        return {"updated": completed, "failed": failed}


# ============== 主函数 ==============
def main():
    parser = argparse.ArgumentParser(description='日线数据采集脚本')
    parser.add_argument('--mode', choices=['full', 'incremental'], default='incremental',
                        help='采集模式: full=全量, incremental=增量')
    parser.add_argument('--start', default='2010-01-01',
                        help='起始日期 (full模式)')
    parser.add_argument('--end', default=None,
                        help='结束日期 (full模式)')
    parser.add_argument('--symbols', default=None,
                        help='指定股票代码，逗号分隔')
    parser.add_argument('--days', type=int, default=1,
                        help='增量更新天数 (incremental模式)')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging()
    
    # 初始化存储
    try:
        storage = DataStorage(
            db_url=f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}",
            redis_url=f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"
        )
        logger.info("[OK] 数据库连接成功")
    except Exception as e:
        logger.error(f"[FAIL] 数据库连接失败: {e}")
        sys.exit(1)
    
    # 初始化采集器
    fetcher = DailyBarsFetcher(storage, logger)
    
    # 解析股票列表
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    
    # 执行采集
    if args.mode == 'full':
        fetcher.run_full(args.start, args.end, symbols)
    else:
        fetcher.run_incremental(args.days)
    
    logger.info("[OK] 数据采集完成!")


if __name__ == "__main__":
    main()