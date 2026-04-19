# -*- coding: utf-8 -*-
"""
数据更新调度器

功能：
1. 配置定时任务（每日收盘后自动更新数据）
2. 管理任务状态
3. 记录执行日志

Usage:
    # 查看所有任务
    python scripts/schedule_update.py --list
    
    # 运行指定任务
    python scripts/schedule_update.py --run daily_bars
    
    # 添加到 Windows 计划任务
    python scripts/schedule_update.py --install
    
    # 测试运行
    python scripts/schedule_update.py --test

Author: 江小猪
Date: 2026-04-19
"""

import argparse
import datetime
import logging
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============== 配置 ==============
TASKS_CONFIG = {
    "daily_bars": {
        "name": "日线数据增量更新",
        "script": "scripts/fetch_daily_bars.py",
        "args": ["--mode", "incremental", "--days", "1"],
        "schedule": "30 16 * * 1-5",  # 每周一到周五 16:30
        "description": "每日 A 股收盘后更新日线数据"
    },
    "daily_financial": {
        "name": "财务数据更新",
        "script": "scripts/fetch_financial.py",
        "args": ["--type", "income"],
        "schedule": "45 16 * * 1-5",  # 每周一到周五 16:45
        "description": "每日更新财务数据"
    },
    "weekly_full": {
        "name": "每周全量数据更新",
        "script": "scripts/fetch_daily_bars.py",
        "args": ["--mode", "incremental", "--days", "7"],
        "schedule": "30 17 * * 5",  # 每周五 17:30
        "description": "每周五更新一周的数据"
    }
}

STATE_FILE = PROJECT_ROOT / "data" / "scheduler_state.json"
LOG_DIR = PROJECT_ROOT / "logs"

# ============== 日志设置 ==============
def setup_logging(task_name: str = None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if task_name:
        log_file = LOG_DIR / f"scheduler_{task_name}_{datetime.date.today().strftime('%Y%m%d')}.log"
    else:
        log_file = LOG_DIR / f"scheduler_{datetime.date.today().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


# ============== 任务状态管理 ==============
class TaskState:
    """任务状态管理"""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"tasks": {}, "last_run": None}
    
    def save(self):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def update_task_status(self, task_name: str, status: str, message: str = ""):
        self.data["tasks"][task_name] = {
            "status": status,
            "last_update": datetime.datetime.now().isoformat(),
            "message": message
        }
        self.data["last_run"] = datetime.datetime.now().isoformat()
        self.save()
    
    def get_task_status(self, task_name: str) -> Optional[Dict]:
        return self.data.get("tasks", {}).get(task_name)
    
    def get_all_status(self) -> Dict:
        return self.data.get("tasks", {})


# ============== 任务执行器 ==============
class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, task_config: Dict, state: TaskState, logger):
        self.config = task_config
        self.state = state
        self.logger = logger
    
    def run(self):
        """执行任务"""
        task_name = self.config["name"]
        script_path = PROJECT_ROOT / self.config["script"]
        
        self.logger.info(f"=" * 60)
        self.logger.info(f"开始执行任务: {task_name}")
        self.logger.info(f"脚本: {script_path}")
        self.logger.info(f"参数: {self.config['args']}")
        self.logger.info(f"=" * 60)
        
        self.state.update_task_status(task_name, "running", "任务执行中...")
        
        try:
            # 构建命令
            cmd = [sys.executable, str(script_path)] + self.config["args"]
            
            # 执行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200  # 超时 2 小时
            )
            
            if result.returncode == 0:
                self.logger.info(f"[OK] 任务执行成功")
                self.state.update_task_status(task_name, "success", "任务执行成功")
            else:
                self.logger.error(f"[FAIL] 任务执行失败: {result.stderr}")
                self.state.update_task_status(task_name, "failed", result.stderr[:500])
        
        except subprocess.TimeoutExpired:
            self.logger.error(f"[FAIL] 任务执行超时（2小时）")
            self.state.update_task_status(task_name, "timeout", "任务执行超时")
        
        except Exception as e:
            self.logger.error(f"[FAIL] 任务执行异常: {e}")
            self.state.update_task_status(task_name, "error", str(e))
        
        self.logger.info(f"=" * 60)


# ============== 调度器 ==============
class DataScheduler:
    """数据更新调度器"""
    
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.state = TaskState(STATE_FILE)
        self.logger = setup_logging()
    
    def add_task(self, task_key: str, task_config: Dict):
        """添加任务到调度器"""
        parts = task_config["schedule"].split()
        minute, hour = parts[0], parts[1]
        day_of_week = parts[4] if len(parts) > 4 else "*"
        
        def create_job(task_key, task_config):
            def job():
                logger = setup_logging(task_key)
                executor = TaskExecutor(task_config, self.state, logger)
                executor.run()
            return job
        
        self.scheduler.add_job(
            create_job(task_key, task_config),
            CronTrigger(minute=minute, hour=hour, day_of_week=day_of_week),
            id=task_key,
            name=task_config["name"],
            replace_existing=True
        )
        
        self.logger.info(f"添加任务: {task_config['name']}")
        self.logger.info(f"  时间: {task_config['schedule']}")
        self.logger.info(f"  描述: {task_config['description']}")
    
    def setup(self):
        """设置所有定时任务"""
        self.logger.info("设置定时任务...")
        
        for task_key, task_config in TASKS_CONFIG.items():
            self.add_task(task_key, task_config)
        
        self.logger.info(f"共添加 {len(TASKS_CONFIG)} 个定时任务")
    
    def run(self):
        """启动调度器"""
        self.setup()
        
        self.logger.info("=" * 60)
        self.logger.info("数据更新调度器启动")
        self.logger.info("按 Ctrl+C 停止")
        self.logger.info("=" * 60)
        
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            self.logger.info("调度器已停止")
            self.scheduler.shutdown()


# ============== Windows 计划任务集成 ==============
def install_windows_task(task_name: str, task_config: Dict):
    """安装 Windows 计划任务"""
    script_path = PROJECT_ROOT / task_config["script"]
    log_file = LOG_DIR / f"task_{task_name}.log"
    
    # 解析 cron 表达式
    parts = task_config["schedule"].split()
    minute, hour = parts[0], parts[1]
    day_of_week = parts[4] if len(parts) > 4 else "*"
    
    # Windows task schedule 需要特殊处理
    # 每周一到周五 16:30 = Mon-Fri at 16:30
    days_map = {"1": "MON", "2": "TUE", "3": "WED", "4": "THU", "5": "FRI"}
    days = "-".join([days_map.get(d, d) for d in day_of_week.split(",")])
    
    cmd = [
        "schtasks",
        "/create",
        "/tn", f"faster_qt\\{task_name}",
        "/tr", f'python "{script_path}" {" ".join(task_config["args"])} >> "{log_file}" 2>&1',
        "/sc", "weekly",
        "/d", days,
        "/st", f"{hour}:{minute}",
        "/f"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] 计划任务 '{task_name}' 安装成功")
        else:
            print(f"[FAIL] 计划任务 '{task_name}' 安装失败: {result.stderr}")
    except Exception as e:
        print(f"[FAIL] 安装失败: {e}")


def list_tasks():
    """列出所有任务状态"""
    state = TaskState(STATE_FILE)
    all_status = state.get_all_status()
    
    print("\n" + "=" * 60)
    print("定时任务状态")
    print("=" * 60)
    
    if not all_status:
        print("暂无任务状态记录")
        return
    
    for task_key, task_info in all_status.items():
        status_icon = {"running": "⏳", "success": "✅", "failed": "❌", "timeout": "⏱️", "error": "⚠️"}.get(
            task_info.get("status", ""), "❓"
        )
        print(f"\n{status_icon} {task_key}")
        print(f"   状态: {task_info.get('status', 'unknown')}")
        print(f"   更新时间: {task_info.get('last_update', 'N/A')}")
        print(f"   消息: {task_info.get('message', 'N/A')[:100]}...")


# ============== 主函数 ==============
def main():
    parser = argparse.ArgumentParser(description='数据更新调度器')
    parser.add_argument('--list', action='store_true', help='列出所有任务状态')
    parser.add_argument('--run', metavar='TASK', help='运行指定任务')
    parser.add_argument('--install', action='store_true', help='安装 Windows 计划任务')
    parser.add_argument('--test', action='store_true', help='测试运行')
    parser.add_argument('--schedule', action='store_true', help='启动定时调度器')
    
    args = parser.parse_args()
    
    if args.list:
        list_tasks()
        return
    
    if args.run:
        if args.run not in TASKS_CONFIG:
            print(f"[FAIL] 未知任务: {args.run}")
            print(f"可用任务: {', '.join(TASKS_CONFIG.keys())}")
            return
        
        logger = setup_logging(args.run)
        state = TaskState(STATE_FILE)
        executor = TaskExecutor(TASKS_CONFIG[args.run], state, logger)
        executor.run()
        return
    
    if args.install:
        print("安装 Windows 计划任务...")
        for task_key, task_config in TASKS_CONFIG.items():
            install_windows_task(task_key, task_config)
        return
    
    if args.schedule:
        scheduler = DataScheduler()
        scheduler.run()
        return
    
    if args.test:
        print("测试日线数据采集...")
        from scripts.fetch_daily_bars import DailyBarsFetcher
        from src.data.storage import DataStorage
        
        DB_URL = "postgresql://postgres:root@127.0.0.1:5432/faster_qt"
        REDIS_URL = "redis://127.0.0.1:6379"
        
        logger = setup_logging("test")
        storage = DataStorage(db_url=DB_URL, redis_url=REDIS_URL)
        fetcher = DailyBarsFetcher(storage, logger)
        
        # 测试采集贵州茅台
        df = fetcher.fetch_single_stock("600519.SH", "2024-01-01", "2024-12-31")
        if df is not None:
            print(f"[OK] 成功获取茅台日线数据: {len(df)} 条")
            print(df.head())
        else:
            print("[FAIL] 获取数据失败")
        return
    
    # 默认显示帮助
    parser.print_help()
    print("\n" + "=" * 60)
    print("Usage examples:")
    print("  python scripts/schedule_update.py --list")
    print("  python scripts/schedule_update.py --run daily_bars")
    print("  python scripts/schedule_update.py --schedule")
    print("  python scripts/schedule_update.py --test")
    print("=" * 60)


if __name__ == "__main__":
    main()