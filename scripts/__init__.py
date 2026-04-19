# -*- coding: utf-8 -*-
"""
faster_qt 数据采集脚本集

包含：
- fetch_daily_bars.py    日线数据采集
- fetch_financial.py     财务数据采集
- schedule_update.py     定时任务调度器
- verify_data.py         数据质量校验
- init_database.py       数据库初始化

Usage:
    # 全量采集日线数据
    python scripts/fetch_daily_bars.py --mode full --start 2010-01-01
    
    # 增量更新日线数据
    python scripts/fetch_daily_bars.py --mode incremental
    
    # 采集财务数据
    python scripts/fetch_financial.py --type all
    
    # 启动定时调度器
    python scripts/schedule_update.py --schedule
    
    # 数据质量校验
    python scripts/verify_data.py

Author: 江小猪
Date: 2026-04-19
"""

__version__ = "0.1.0"