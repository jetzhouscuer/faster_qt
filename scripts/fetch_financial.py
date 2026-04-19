# -*- coding: utf-8 -*-
"""
财务数据采集脚本

功能：
1. 采集上市公司财务数据（利润表、资产负债表、现金流量表）
2. 支持季度/年报数据
3. 增量更新

数据源：AKShare（免费，无需API Key）

Usage:
    # 采集全部财务数据
    python scripts/fetch_financial.py --type all
    
    # 仅采集利润表
    python scripts/fetch_financial.py --type income
    
    # 指定股票采集
    python scripts/fetch_financial.py --symbols 600519.SH,000001.SZ

Author: 江小猪
Date: 2026-04-19
"""

import argparse
import datetime
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict

import akshare as ak
import pandas as pd

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.storage import DataStorage
from src.data.master import MasterDataManager


# ============== 配置 ==============
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "root",
    "dbname": "faster_qt"
}

REDIS_CONFIG = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 0
}

BATCH_SIZE = 30
MAX_WORKERS = 3
REQUEST_DELAY = 1.0

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / f"fetch_financial_{datetime.date.today().strftime('%Y%m%d')}.log"


# ============== 日志设置 ==============
def setup_logging():
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


# ============== 财务数据采集器 ==============
class FinancialFetcher:
    """财务数据采集器"""
    
    def __init__(self, storage: DataStorage, logger):
        self.storage = storage
        self.logger = logger
        self.master = MasterDataManager(storage)
    
    def get_stock_list(self) -> List[str]:
        """获取股票列表"""
        self.logger.info("获取 A 股股票列表...")
        try:
            df = ak.stock_info_a_code_name()
            symbols = []
            for _, row in df.iterrows():
                code = row['code']
                if code.startswith('6'):
                    symbols.append(f"{code}.SH")
                else:
                    symbols.append(f"{code}.SZ")
            self.logger.info(f"获取到 {len(symbols)} 只股票")
            return symbols
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_income_statement(self, symbol: str) -> Optional[pd.DataFrame]:
        """采集利润表"""
        try:
            code = symbol.split('.')[0]
            # 东方财富利润表
            df = ak.stock_financial_report_sina(
                symbol=code,
                symbol_name="利润表"
            )
            
            if df is None or df.empty:
                return None
            
            df['symbol'] = symbol
            df['report_type'] = 'income'
            return df
            
        except Exception as e:
            self.logger.warning(f"采集 {symbol} 利润表失败: {e}")
            return None
    
    def fetch_balance_sheet(self, symbol: str) -> Optional[pd.DataFrame]:
        """采集资产负债表"""
        try:
            code = symbol.split('.')[0]
            df = ak.stock_financial_report_sina(
                symbol=code,
                symbol_name="资产负债表"
            )
            
            if df is None or df.empty:
                return None
            
            df['symbol'] = symbol
            df['report_type'] = 'balance_sheet'
            return df
            
        except Exception as e:
            self.logger.warning(f"采集 {symbol} 资产负债表失败: {e}")
            return None
    
    def fetch_cash_flow(self, symbol: str) -> Optional[pd.DataFrame]:
        """采集现金流量表"""
        try:
            code = symbol.split('.')[0]
            df = ak.stock_financial_report_sina(
                symbol=code,
                symbol_name="现金流量表"
            )
            
            if df is None or df.empty:
                return None
            
            df['symbol'] = symbol
            df['report_type'] = 'cash_flow'
            return df
            
        except Exception as e:
            self.logger.warning(f"采集 {symbol} 现金流量表失败: {e}")
            return None
    
    def save_financial_data(self, df: pd.DataFrame, report_type: str):
        """保存财务数据到数据库"""
        if df is None or df.empty:
            return
        
        try:
            self.storage.save_financial_data(df, report_type)
        except Exception as e:
            self.logger.error(f"保存财务数据失败: {e}")
            raise
    
    def run_fetch(self, symbols: List[str] = None, fetch_type: str = 'all'):
        """执行采集"""
        if symbols is None:
            symbols = self.get_stock_list()
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"开始财务数据采集")
        self.logger.info(f"股票数量: {len(symbols)}")
        self.logger.info(f"采集类型: {fetch_type}")
        self.logger.info(f"=" * 60)
        
        completed = 0
        failed = []
        
        for i, symbol in enumerate(symbols):
            if (i + 1) % 50 == 0:
                self.logger.info(f"进度: {i + 1}/{len(symbols)}")
            
            try:
                if fetch_type in ['all', 'income']:
                    df = self.fetch_income_statement(symbol)
                    if df is not None:
                        self.save_financial_data(df, 'income')
                
                if fetch_type in ['all', 'balance_sheet']:
                    df = self.fetch_balance_sheet(symbol)
                    if df is not None:
                        self.save_financial_data(df, 'balance_sheet')
                
                if fetch_type in ['all', 'cash_flow']:
                    df = self.fetch_cash_flow(symbol)
                    if df is not None:
                        self.save_financial_data(df, 'cash_flow')
                
                completed += 1
                
            except Exception as e:
                failed.append(symbol)
                self.logger.warning(f"{symbol} 采集失败: {e}")
            
            time.sleep(REQUEST_DELAY)
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"财务数据采集完成!")
        self.logger.info(f"成功: {completed}")
        self.logger.info(f"失败: {len(failed)}")
        self.logger.info(f"=" * 60)
        
        return {"completed": completed, "failed": len(failed)}


# ============== 主函数 ==============
def main():
    parser = argparse.ArgumentParser(description='财务数据采集脚本')
    parser.add_argument('--type', choices=['all', 'income', 'balance_sheet', 'cash_flow'], 
                        default='all', help='采集类型')
    parser.add_argument('--symbols', default=None,
                        help='指定股票代码，逗号分隔')
    
    args = parser.parse_args()
    
    logger = setup_logging()
    
    try:
        storage = DataStorage(
            db_url=f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}",
            redis_url=f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"
        )
        logger.info("[OK] 数据库连接成功")
    except Exception as e:
        logger.error(f"[FAIL] 数据库连接失败: {e}")
        sys.exit(1)
    
    fetcher = FinancialFetcher(storage, logger)
    
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    
    fetcher.run_fetch(symbols, args.type)
    
    logger.info("[OK] 财务数据采集完成!")


if __name__ == "__main__":
    main()