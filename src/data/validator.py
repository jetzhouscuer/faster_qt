# -*- coding: utf-8 -*-
"""
数据质量校验模块
确保入库数据符合质量标准，避免"垃圾进垃圾出"
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np

from .models import QualityResult

logger = logging.getLogger(__name__)


# ===========================
# 校验规则基类
# ===========================


class DataQualityRule(ABC):
    """
    数据质量规则抽象基类
    
    每个规则实现一种校验逻辑，如：
    - 价格区间校验
    - 成交量非负校验
    - 时间连续性校验
    """

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """规则名称"""
        pass

    @abstractmethod
    def check(self, data: pd.DataFrame) -> QualityResult:
        """
        执行校验
        
        Args:
            data: 待校验的数据
            
        Returns:
            QualityResult: 校验结果
        """
        pass

    def _create_result(
        self,
        passed: bool,
        category: str,
        record_count: int,
        error_count: int,
        error_samples: List[Any] = None,
        details: List[str] = None,
    ) -> QualityResult:
        """创建标准化的校验结果"""
        return QualityResult(
            passed=passed,
            category=category,
            check_rule=self.rule_name,
            record_count=record_count,
            error_count=error_count,
            error_rate=error_count / record_count if record_count > 0 else 0,
            error_samples=error_samples or [],
            details=details or [],
        )


# ===========================
# K线数据校验规则
# ===========================


class PriceRangeRule(DataQualityRule):
    """
    价格区间校验
    
    检查：
    1. 收盘价不为0或负数
    2. 开盘价不为0或负数
    3. 价格在合理范围内（需配置个股阈值）
    """

    def __init__(self, min_price: float = 0.01, max_price: float = 100000):
        self.min_price = min_price
        self.max_price = max_price

    @property
    def rule_name(self) -> str:
        return "price_range"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "bars", 0, 0)

        errors = []
        
        # 检查 OHLC 是否 > 0
        for col in ["open", "high", "low", "close"]:
            if col in data.columns:
                invalid = data[data[col] <= 0]
                if not invalid.empty:
                    errors.append(f"{col} <= 0: {len(invalid)} 条")
                    errors.extend(
                        f"  {col}={row[col]}, symbol={row.get('symbol')}, time={row.get('timestamp')}"
                        for _, row in invalid.head(3).iterrows()
                    )

        # 检查价格是否在合理范围
        for col in ["open", "high", "low", "close"]:
            if col in data.columns:
                out_of_range = data[
                    (data[col] < self.min_price) | (data[col] > self.max_price)
                ]
                if not out_of_range.empty:
                    errors.append(f"{col} 超出范围[{self.min_price}, {self.max_price}]: {len(out_of_range)} 条")

        passed = len(errors) == 0
        return self._create_result(
            passed=passed,
            category="bars",
            record_count=len(data),
            error_count=len(errors),
            details=errors[:10],  # 只保留前10条
        )


class HighLowConsistentRule(DataQualityRule):
    """
    最高价/最低价一致性校验
    
    检查：
    1. high >= low
    2. high >= open
    3. high >= close
    4. low <= open
    5. low <= close
    """

    @property
    def rule_name(self) -> str:
        return "high_low_consistent"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "bars", 0, 0)

        errors = []
        required_cols = ["high", "low", "open", "close"]
        if not all(col in data.columns for col in required_cols):
            return self._create_result(
                True, "bars", len(data), 0,
                details=["缺少必要列，跳过校验"]
            )

        # 检查 high >= low
        invalid_hl = data[data["high"] < data["low"]]
        if not invalid_hl.empty:
            errors.append(f"high < low: {len(invalid_hl)} 条")
            errors.extend(
                f"  high={row['high']}, low={row['low']}, symbol={row.get('symbol')}"
                for _, row in invalid_hl.head(3).iterrows()
            )

        # 检查 high >= open 且 high >= close
        invalid_h = data[(data["high"] < data["open"]) | (data["high"] < data["close"])]
        if not invalid_h.empty:
            errors.append(f"high < open/close: {len(invalid_h)} 条")

        # 检查 low <= open 且 low <= close
        invalid_l = data[(data["low"] > data["open"]) | (data["low"] > data["close"])]
        if not invalid_l.empty:
            errors.append(f"low > open/close: {len(invalid_l)} 条")

        passed = len(errors) == 0
        return self._create_result(
            passed=passed,
            category="bars",
            record_count=len(data),
            error_count=len(errors),
            details=errors[:10],
        )


class VolumePositiveRule(DataQualityRule):
    """
    成交量非负校验
    
    检查：
    1. volume > 0（交易日的成交量应该 > 0）
    2. volume 为整数
    """

    @property
    def rule_name(self) -> str:
        return "volume_positive"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "bars", 0, 0)

        if "volume" not in data.columns:
            return self._create_result(
                True, "bars", len(data), 0,
                details=["缺少 volume 列，跳过校验"]
            )

        errors = []

        # 检查成交量 <= 0
        invalid = data[data["volume"] <= 0]
        if not invalid.empty:
            errors.append(f"volume <= 0: {len(invalid)} 条")
            errors.extend(
                f"  volume={row['volume']}, symbol={row.get('symbol')}, time={row.get('timestamp')}"
                for _, row in invalid.head(5).iterrows()
            )

        # 检查成交量是否为整数
        non_integer = data[data["volume"] != data["volume"].astype(int)]
        if not non_integer.empty:
            errors.append(f"volume 非整数: {len(non_integer)} 条")

        passed = len(errors) == 0
        return self._create_result(
            passed=passed,
            category="bars",
            record_count=len(data),
            error_count=len(errors),
            details=errors[:10],
        )


class TimeContinuityRule(DataQualityRule):
    """
    时间连续性校验（核心！）
    
    检测 K 线是否连续，检查：
    1. 是否有缺失的 K 线（如停牌日、熔断等）
    2. 时间间隔是否符合预期（如日线应该每天一条）
    
    这是量化系统常见的数据问题，必须检测
    """

    def __init__(self, expected_minutes: int = None):
        """
        Args:
            expected_minutes: 期望的时间间隔（分钟）
                - 1m: 1
                - 5m: 5
                - 15m: 15
                - 30m: 30
                - 1h: 60
                - 1d: 1440 (或 240 for A股交易时间)
        """
        self.expected_minutes = expected_minutes

    @property
    def rule_name(self) -> str:
        return "time_continuity"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "bars", 0, 0)

        if "timestamp" not in data.columns:
            return self._create_result(
                True, "bars", len(data), 0,
                details=["缺少 timestamp 列，跳过校验"]
            )

        errors = []
        
        # 按 symbol 和 timeframe 分组检查
        for (symbol, timeframe), group in data.groupby(
            ["symbol", data.get("timeframe", "1d")]
        ):
            if len(group) < 2:
                continue

            # 按时间排序
            group = group.sort_values("timestamp")
            timestamps = pd.to_datetime(group["timestamp"])

            # 计算时间差
            diffs = timestamps.diff().dropna()

            # 期望的时间差（分钟）
            if self.expected_minutes:
                expected = timedelta(minutes=self.expected_minutes)
            else:
                # 自动推断：使用众数时间差
                expected = diffs.mode()[0] if len(diffs.mode()) > 0 else timedelta(days=1)

            # 找出异常间隔
            expected_min = expected * 0.8  # 允许 20% 的误差
            expected_max = expected * 1.2

            abnormal = diffs[(diffs < expected_min) | (diffs > expected_max)]
            
            if not abnormal.empty:
                errors.append(
                    f"symbol={symbol}, timeframe={timeframe}: "
                    f"发现 {len(abnormal)} 个异常时间间隔"
                )

        passed = len(errors) == 0
        return self._create_result(
            passed=passed,
            category="bars",
            record_count=len(data),
            error_count=len(errors),
            details=errors,
        )


class CloseInRangeRule(DataQualityRule):
    """
    收盘价在最高/最低价范围内
    
    检查 close 是否在 [low, high] 区间内
    """

    @property
    def rule_name(self) -> str:
        return "close_in_range"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "bars", 0, 0)

        required_cols = ["close", "high", "low"]
        if not all(col in data.columns for col in required_cols):
            return self._create_result(
                True, "bars", len(data), 0,
                details=["缺少必要列，跳过校验"]
            )

        invalid = data[(data["close"] < data["low"]) | (data["close"] > data["high"])]
        
        passed = invalid.empty
        return self._create_result(
            passed=passed,
            category="bars",
            record_count=len(data),
            error_count=len(invalid),
            details=[
                f"close 不在 [low, high] 范围内: {len(invalid)} 条"
            ] if not passed else [],
        )


# ===========================
# 财务数据校验规则
# ===========================


class FundamentalValuePositiveRule(DataQualityRule):
    """
    财务数据正值校验
    
    某些财务指标（如营收、净利润）应为正数或零
    """

    def __init__(self, required_positive: List[str] = None):
        """
        Args:
            required_positive: 必须为正的字段列表
        """
        self.required_positive = required_positive or [
            "revenue", "total_assets", "equity"
        ]

    @property
    def rule_name(self) -> str:
        return "fundamental_value_positive"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "fundamental", 0, 0)

        errors = []
        
        for col in self.required_positive:
            if col in data.columns:
                invalid = data[data[col] < 0]
                if not invalid.empty:
                    errors.append(f"{col} < 0: {len(invalid)} 条")

        passed = len(errors) == 0
        return self._create_result(
            passed=passed,
            category="fundamental",
            record_count=len(data),
            error_count=len(errors),
            details=errors,
        )


class YoYChangeReasonableRule(DataQualityRule):
    """
    同比变化合理性校验
    
    财务指标的同比变化不应超过合理范围（如-100% ~ +1000%）
    用于检测异常财务数据
    """

    def __init__(
        self,
        min_yoy: float = -1.0,    # 最低同比 -100%
        max_yoy: float = 10.0,    # 最高同比 +1000%
    ):
        self.min_yoy = min_yoy
        self.max_yoy = max_yoy

    @property
    def rule_name(self) -> str:
        return "yoy_change_reasonable"

    def check(self, data: pd.DataFrame) -> QualityResult:
        if data.empty:
            return self._create_result(True, "fundamental", 0, 0)

        if "report_date" not in data.columns or "symbol" not in data.columns:
            return self._create_result(
                True, "fundamental", len(data), 0,
                details=["缺少必要列，跳过校验"]
            )

        # TODO: 实现同比计算
        # 需要先按 symbol 和 report_date 排序，然后计算同比变化
        # 目前先返回通过
        return self._create_result(
            True, "fundamental", len(data), 0,
            details=["同比校验待实现"]
        )


# ===========================
# 数据校验器
# ===========================


class DataValidator:
    """
    数据校验器
    
    根据数据类别自动执行对应的校验规则集
    """

    # 各类别的校验规则
    RULES: Dict[str, List[DataQualityRule]] = {
        "bars": [
            PriceRangeRule(),
            HighLowConsistentRule(),
            VolumePositiveRule(),
            CloseInRangeRule(),
            # TimeContinuityRule(),  # 可选，比较慢
        ],
        "fundamental": [
            FundamentalValuePositiveRule(),
            YoYChangeReasonableRule(),
        ],
        "ticks": [
            PriceRangeRule(min_price=0.001),
        ],
    }

    @classmethod
    def validate(
        cls,
        category: str,
        data: pd.DataFrame,
        raise_on_error: bool = False,
    ) -> QualityResult:
        """
        执行校验
        
        Args:
            category: 数据类别（bars/fundamental/ticks）
            data: 待校验数据
            raise_on_error: 是否在校验失败时抛出异常
            
        Returns:
            综合校验结果（所有规则的聚合）
        """
        if data.empty:
            return QualityResult(
                passed=True,
                category=category,
                check_rule="overall",
                record_count=0,
                error_count=0,
            )

        rules = cls.RULES.get(category, [])
        if not rules:
            logger.warning(f"No rules defined for category={category}")
            return QualityResult(
                passed=True,
                category=category,
                check_rule="overall",
                record_count=len(data),
                error_count=0,
            )

        all_errors = []
        total_record_count = len(data)

        for rule in rules:
            result = rule.check(data)
            
            if not result.passed:
                all_errors.append(result)
                logger.warning(f"Rule {rule.rule_name} failed: {result.details}")

        # 汇总结果
        total_errors = sum(e.error_count for e in all_errors)
        passed = total_errors == 0

        summary = QualityResult(
            passed=passed,
            category=category,
            check_rule="overall",
            record_count=total_record_count,
            error_count=total_errors,
            error_rate=total_errors / total_record_count if total_record_count > 0 else 0,
            error_samples=[e.details for e in all_errors],
            details=[f"{e.check_rule}: {e.error_count} errors" for e in all_errors],
        )

        if not passed and raise_on_error:
            raise DataQualityError(
                f"Data quality check failed for {category}: "
                f"{total_errors} errors in {total_record_count} records"
            )

        return summary

    @classmethod
    def add_rule(cls, category: str, rule: DataQualityRule):
        """动态添加校验规则"""
        if category not in cls.RULES:
            cls.RULES[category] = []
        cls.RULES[category].append(rule)


class DataQualityError(Exception):
    """数据质量异常"""
    pass


# ===========================
# 校验报告生成
# ===========================


class QualityReport:
    """数据质量报告"""

    def __init__(self):
        self.results: List[QualityResult] = []

    def add_result(self, result: QualityResult):
        self.results.append(result)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def total_records(self) -> int:
        return sum(r.record_count for r in self.results)

    @property
    def total_errors(self) -> int:
        return sum(r.error_count for r in self.results)

    def summary(self) -> str:
        """生成报告摘要"""
        lines = [
            "=" * 60,
            "数据质量校验报告",
            "=" * 60,
            f"总体状态: {'✅ 通过' if self.passed else '❌ 失败'}",
            f"总记录数: {self.total_records}",
            f"总错误数: {self.total_errors}",
            f"错误率: {self.total_errors / self.total_records if self.total_records > 0 else 0:.2%}",
            "-" * 60,
            "明细:",
        ]

        for r in self.results:
            status = "✅" if r.passed else "❌"
            lines.append(
                f"  {status} {r.category}.{r.check_rule}: "
                f"{r.error_count}/{r.record_count} 错误"
            )
            if not r.passed and r.details:
                for detail in r.details[:3]:
                    lines.append(f"      - {detail}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return f"QualityReport(passed={self.passed}, errors={self.total_errors})"
