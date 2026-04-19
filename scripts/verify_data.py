# -*- coding: utf-8 -*-
"""
数据质量校验脚本

功能：
1. 检测 K 线数据缺失
2. 检查价格异常（最高价 < 最低价等）
3. 验证时间连续性（交易日缺失检测）
4. 生成数据质量报告

Usage:
    # 校验所有股票
    python scripts/verify_data.py
    
    # 指定股票校验
    python scripts/verify_data.py --symbols 600519.SH,000001.SZ
    
    # 详细输出
    python scripts/verify_data.py --verbose
    
    # 仅检查最新数据
    python scripts/verify_data.py --recent 30

Author: 江小猪
Date: 2026-04-19
"""

import argparse
import datetime
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.storage import DataStorage
from src.data.master import MasterDataManager
from src.data.validator import DataValidator, PriceRangeRule, TimeContinuityRule, HighLowConsistentRule


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

LOG_DIR = PROJECT_ROOT / "logs"
REPORT_DIR = PROJECT_ROOT / "data" / "reports"


# ============== 日志设置 ==============
def setup_logging(verbose: bool = False):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_DIR / f"verify_data_{datetime.date.today().strftime('%Y%m%d')}.log", encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


# ============== 数据校验器 ==============
class DataVerifier:
    """数据质量校验器"""
    
    def __init__(self, storage: DataStorage, master: MasterDataManager, logger):
        self.storage = storage
        self.master = master
        self.logger = logger
        self.validator = DataValidator()
        
        # 注册校验规则
        self.validator.add_rule(PriceRangeRule())
        self.validator.add_rule(HighLowConsistentRule())
        self.validator.add_rule(TimeContinuityRule())
    
    def check_symbol_data(self, symbol: str, days: int = None) -> Dict:
        """检查单只股票的数据质量"""
        result = {
            "symbol": symbol,
            "status": "ok",
            "total_bars": 0,
            "issues": [],
            "warnings": []
        }
        
        try:
            # 加载数据
            end_date = datetime.date.today()
            if days:
                start_date = end_date - datetime.timedelta(days=days)
            else:
                start_date = end_date - datetime.timedelta(days=365)  # 默认检查一年
            
            bars = self.storage.load_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe="1d"
            )
            
            if bars is None or len(bars) == 0:
                result["status"] = "no_data"
                result["warnings"].append(f"没有找到 {symbol} 在 {start_date} ~ {end_date} 的数据")
                return result
            
            result["total_bars"] = len(bars)
            
            # 转换为 DataFrame 用于校验
            df = pd.DataFrame([{
                'symbol': b.symbol,
                'timestamp': b.timestamp,
                'open': b.open,
                'high': b.high,
                'low': b.low,
                'close': b.close,
                'volume': b.volume
            } for b in bars])
            
            # 执行校验
            validation_result = self.validator.validate("bars", df)
            
            if not validation_result.is_valid:
                result["status"] = "error"
                result["issues"].extend(validation_result.errors)
            
            if validation_result.warnings:
                result["warnings"].extend(validation_result.warnings)
            
            # 检查交易日连续性
            trading_days = self.master.get_trading_calendar(start_date, end_date)
            bar_dates = set(pd.to_datetime(df['timestamp']).dt.date)
            expected_dates = set(trading_days)
            
            missing_dates = expected_dates - bar_dates
            if missing_dates:
                result["warnings"].append(f"缺失 {len(missing_dates)} 个交易日数据")
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"检查过程出错: {str(e)}")
            return result
    
    def check_all_symbols(self, symbols: List[str] = None, days: int = None, verbose: bool = False) -> Dict:
        """检查所有股票数据质量"""
        self.logger.info(f"=" * 60)
        self.logger.info(f"开始数据质量校验")
        self.logger.info(f"=" * 60)
        
        # 获取股票列表
        if symbols is None:
            symbols = self.storage.get_existing_symbols("1d")
        
        self.logger.info(f"待校验股票数量: {len(symbols)}")
        
        # 统计
        stats = {
            "total": len(symbols),
            "ok": 0,
            "warning": 0,
            "error": 0,
            "no_data": 0
        }
        
        all_issues = []
        all_warnings = []
        
        # 逐个检查
        for i, symbol in enumerate(symbols):
            if verbose or (i + 1) % 100 == 0:
                self.logger.info(f"检查进度: {i + 1}/{len(symbols)}")
            
            result = self.check_symbol_data(symbol, days)
            
            # 统计
            stats[result["status"]] = stats.get(result["status"], 0) + 1
            
            if result["issues"]:
                all_issues.append(result)
            
            if result["warnings"]:
                all_warnings.append(result)
        
        # 打印汇总
        self.logger.info(f"=" * 60)
        self.logger.info(f"数据质量校验完成")
        self.logger.info(f"总计: {stats['total']}")
        self.logger.info(f"正常: {stats['ok']}")
        self.logger.info(f"警告: {stats['warning']}")
        self.logger.info(f"错误: {stats['error']}")
        self.logger.info(f"无数据: {stats['no_data']}")
        self.logger.info(f"=" * 60)
        
        # 输出问题列表
        if all_issues:
            self.logger.warning(f"\n发现 {len(all_issues)} 只股票存在数据问题:")
            for item in all_issues[:10]:
                self.logger.warning(f"  - {item['symbol']}: {', '.join(item['issues'][:3])}")
            if len(all_issues) > 10:
                self.logger.warning(f"  ... 还有 {len(all_issues) - 10} 只股票")
        
        return {
            "stats": stats,
            "issues": all_issues,
            "warnings": all_warnings
        }
    
    def generate_report(self, result: Dict, output_file: Path = None) -> str:
        """生成数据质量报告"""
        stats = result["stats"]
        
        report = []
        report.append("=" * 60)
        report.append("faster_qt 数据质量报告")
        report.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        report.append("")
        report.append("## 总体统计")
        report.append(f"  总股票数: {stats['total']}")
        report.append(f"  正常: {stats['ok']} ({stats['ok'] / stats['total'] * 100:.1f}%)")
        report.append(f"  警告: {stats['warning']} ({stats['warning'] / stats['total'] * 100:.1f}%)")
        report.append(f"  错误: {stats['error']} ({stats['error'] / stats['total'] * 100:.1f}%)")
        report.append(f"  无数据: {stats['no_data']} ({stats['no_data'] / stats['total'] * 100:.1f}%)")
        report.append("")
        
        # 问题详情
        if result["issues"]:
            report.append("## 数据问题列表")
            for item in result["issues"][:20]:
                report.append(f"\n### {item['symbol']}")
                for issue in item["issues"]:
                    report.append(f"  - {issue}")
        
        report_text = "\n".join(report)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            self.logger.info(f"报告已保存到: {output_file}")
        
        return report_text


# ============== 主函数 ==============
def main():
    parser = argparse.ArgumentParser(description='数据质量校验脚本')
    parser.add_argument('--symbols', default=None,
                        help='指定股票代码，逗号分隔')
    parser.add_argument('--days', type=int, default=365,
                        help='检查最近多少天的数据')
    parser.add_argument('--verbose', action='store_true',
                        help='详细输出')
    parser.add_argument('--output', default=None,
                        help='报告输出路径')
    parser.add_argument('--recent', type=int,
                        help='仅检查最近 N 天的数据')
    
    args = parser.parse_args()
    
    logger = setup_logging(args.verbose)
    
    # 初始化
    try:
        storage = DataStorage(
            db_url=f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}",
            redis_url=f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"
        )
        master = MasterDataManager(storage)
        logger.info("[OK] 数据库连接成功")
    except Exception as e:
        logger.error(f"[FAIL] 数据库连接失败: {e}")
        sys.exit(1)
    
    # 解析股票列表
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    
    # 解析天数
    days = args.recent if args.recent else args.days
    
    # 执行校验
    verifier = DataVerifier(storage, master, logger)
    result = verifier.check_all_symbols(symbols, days, args.verbose)
    
    # 生成报告
    output_file = Path(args.output) if args.output else REPORT_DIR / f"quality_report_{datetime.date.today().strftime('%Y%m%d')}.txt"
    report = verifier.generate_report(result, output_file)
    
    print("\n" + report)
    
    logger.info(f"\n[OK] 数据质量校验完成!")


if __name__ == "__main__":
    main()