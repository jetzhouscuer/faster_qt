# 数据字典

> 本文档定义了 faster_qt 系统中所有核心数据模型的字段规范。

---

## 1. 行情数据（Bar）

### 1.1 K线数据结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `timestamp` | DateTime | ✅ | K线时间 | `2024-01-15 09:30:00` |
| `timeframe` | String | ✅ | 周期 | `1m`, `5m`, `15m`, `1h`, `1d` |
| `open` | Decimal | ✅ | 开盘价 | `1850.50` |
| `high` | Decimal | ✅ | 最高价 | `1865.00` |
| `low` | Decimal | ✅ | 最低价 | `1848.00` |
| `close` | Decimal | ✅ | 收盘价 | `1860.20` |
| `volume` | Integer | ✅ | 成交量（股） | `1256000` |
| `amount` | Decimal | ❌ | 成交额（元） | `2334567890.50` |
| `factor` | Decimal | ❌ | 复权因子 | `1.0234` |

### 1.2 Tick 数据结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `timestamp` | DateTime | ✅ | 成交时间 | `2024-01-15 09:30:05` |
| `last_price` | Decimal | ✅ | 最新价 | `1860.20` |
| `last_volume` | Integer | ✅ | 最新成交量 | `100` |
| `bid_price_1~5` | Decimal | ❌ | 买1~买5价 | `1859.50` |
| `ask_price_1~5` | Decimal | ❌ | 卖1~卖5价 | `1860.80` |
| `bid_volume_1~5` | Integer | ❌ | 买1~买5量 | `5000` |
| `ask_volume_1~5` | Integer | ❌ | 卖1~卖5量 | `3200` |
| `total_volume` | Integer | ❌ | 今日总成交量 | `12560000` |
| `total_amount` | Decimal | ❌ | 今日总成交额 | `23345678900.00` |

---

## 2. 财务数据（Fundamental）

### 2.1 资产负债表

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `report_date` | Date | ✅ | 报告期 | `2024-03-31` |
| `total_assets` | Decimal | ✅ | 资产总计 | `2525000000000.00` |
| `total_liabilities` | Decimal | ✅ | 负债合计 | `1523000000000.00` |
| `equity` | Decimal | ✅ | 所有者权益 | `1002000000000.00` |
| `current_assets` | Decimal | ❌ | 流动资产 | `980000000000.00` |
| `current_liabilities` | Decimal | ❌ | 流动负债 | `650000000000.00` |
| `fixed_assets` | Decimal | ❌ | 固定资产 | `320000000000.00` |
| `intangible_assets` | Decimal | ❌ | 无形资产 | `45000000000.00` |

### 2.2 利润表

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `report_date` | Date | ✅ | 报告期 | `2024-03-31` |
| `revenue` | Decimal | ✅ | 营业收入 | `120000000000.00` |
| `operating_cost` | Decimal | ✅ | 营业成本 | `48000000000.00` |
| `operating_profit` | Decimal | ✅ | 营业利润 | `72000000000.00` |
| `total_profit` | Decimal | ✅ | 利润总额 | `72000000000.00` |
| `net_profit` | Decimal | ✅ | 净利润 | `54000000000.00` |
| `eps` | Decimal | ❌ | 每股收益 | `42.50` |

### 2.3 现金流表

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `report_date` | Date | ✅ | 报告期 | `2024-03-31` |
| `operating_cash_flow` | Decimal | ✅ | 经营活动现金流 | `68000000000.00` |
| `investing_cash_flow` | Decimal | ✅ | 投资活动现金流 | `-15000000000.00` |
| `financing_cash_flow` | Decimal | ✅ | 筹资活动现金流 | `-20000000000.00` |
| `free_cash_flow` | Decimal | ❌ | 自由现金流 | `53000000000.00` |

---

## 3. 因子数据（Factor）

### 3.1 因子值结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `factor_name` | String | ✅ | 因子名称 | `pe`, `pb`, `ma_5` |
| `timestamp` | DateTime | ✅ | 计算时间 | `2024-01-15 15:00:00` |
| `value` | Decimal | ✅ | 因子值 | `28.50` |

### 3.2 常用因子列表

| 因子名称 | 类别 | 计算方式 | 更新频率 |
|---------|------|---------|---------|
| `pe` | 估值 | 收盘价 / 每股收益 | 日 |
| `pb` | 估值 | 收盘价 / 每股净资产 | 日 |
| `ps` | 估值 | 收盘价 / 每股营收 | 日 |
| `pcf` | 估值 | 收盘价 / 每股现金流 | 日 |
| `roe` | 质量 | 净利润 / 净资产 | 季度 |
| `roa` | 质量 | 净利润 / 总资产 | 季度 |
| `gross_margin` | 质量 | (营收 - 成本) / 营收 | 季度 |
| `debt_to_equity` | 杠杆 | 总负债 / 所有者权益 | 季度 |
| `revenue_growth` | 成长 | (本期营收 - 上期营收) / 上期营收 | 季度 |
| `profit_growth` | 成长 | (本期净利润 - 上期净利润) / 上期净利润 | 季度 |
| `ma_5` | 量价 | 5日简单移动平均 | 日 |
| `ma_20` | 量价 | 20日简单移动平均 | 日 |
| `ma_60` | 量价 | 60日简单移动平均 | 日 |
| `ema_12` | 量价 | 12日指数移动平均 | 日 |
| `macd` | 量价 | DIF - DEA | 日 |
| `rsi_14` | 量价 | 14日相对强弱指数 | 日 |
| `bollinger_upper` | 量价 | MA20 + 2*STD20 | 日 |
| `bollinger_lower` | 量价 | MA20 - 2*STD20 | 日 |
| `atr_14` | 波动 | 14日平均真实波幅 | 日 |
| `volume_ratio` | 量能 | 今日成交量 / 5日均量 | 日 |

---

## 4. 订单数据（Order）

### 4.1 订单结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `order_id` | String | ✅ | 订单ID（系统生成） | `ORD_20240115_001` |
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `direction` | Enum | ✅ | 交易方向 | `LONG`, `SHORT`, `EXIT` |
| `order_type` | Enum | ✅ | 订单类型 | `MARKET`, `LIMIT`, `STOP` |
| `volume` | Decimal | ✅ | 委托数量 | `1000.00` |
| `price` | Decimal | ❌ | 委托价格（限价单） | `1850.00` |
| `filled_volume` | Decimal | ❌ | 成交数量 | `800.00` |
| `avg_price` | Decimal | ❌ | 成交均价 | `1848.50` |
| `status` | Enum | ✅ | 订单状态 | `PENDING`, `FILLED`, `CANCELLED`, `REJECTED` |
| `created_at` | DateTime | ✅ | 委托时间 | `2024-01-15 09:30:05` |
| `updated_at` | DateTime | ✅ | 更新时间 | `2024-01-15 09:30:10` |
| `error_msg` | String | ❌ | 错误信息 | `资金不足` |

### 4.2 订单状态流转

```
PENDING → FILLED     (全部成交)
PENDING → PARTIAL    (部分成交)
PENDING → CANCELLED  (用户撤单)
PENDING → REJECTED   (风控/合规拒绝)
PARTIAL → FILLED    (剩余成交)
PARTIAL → CANCELLED  (用户撤单)
```

### 4.3 交易方向枚举

| 枚举值 | 说明 | 含义 |
|-------|------|------|
| `LONG` | 买入/做多 | 开多仓 |
| `SHORT` | 卖出/做空 | 开空仓 |
| `EXIT` | 平仓 | 关闭现有仓位 |

### 4.4 订单类型枚举

| 枚举值 | 说明 |
|-------|------|
| `MARKET` | 市价单 |
| `LIMIT` | 限价单 |
| `STOP` | 止损单 |
| `STOP_LIMIT` | 止损限价单 |

---

## 5. 持仓数据（Position）

### 5.1 持仓结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `volume` | Decimal | ✅ | 持仓数量 | `10000.00` |
| `avg_cost` | Decimal | ✅ | 平均成本 | `1750.00` |
| `market_value` | Decimal | ✅ | 市值 | `18600000.00` |
| `unrealized_pnl` | Decimal | ✅ | 浮动盈亏 | `100000.00` |
| `unrealized_pnl_pct` | Decimal | ✅ | 浮动盈亏率 | `0.0571` |
| `today_volume` | Decimal | ❌ | 今日买入量 | `5000.00` |
| `frozen_volume` | Decimal | ❌ | 冻结数量 | `0.00` |
| `updated_at` | DateTime | ✅ | 更新时间 | `2024-01-15 15:00:00` |

### 5.2 持仓计算公式

```
市值 = 持仓数量 × 当前收盘价
浮动盈亏 = (当前收盘价 - 平均成本) × 持仓数量
浮动盈亏率 = 浮动盈亏 / (平均成本 × 持仓数量) × 100%
```

---

## 6. 账户数据（Account）

### 6.1 账户结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `account_id` | String | ✅ | 账户ID | `ACC_001` |
| `total_value` | Decimal | ✅ | 总资产 | `10000000.00` |
| `cash` | Decimal | ✅ | 可用资金 | `4500000.00` |
| `frozen_cash` | Decimal | ✅ | 冻结资金 | `1500000.00` |
| `market_value` | Decimal | ✅ | 持仓市值 | `4000000.00` |
| `daily_pnl` | Decimal | ✅ | 今日盈亏 | `85000.00` |
| `daily_return` | Decimal | ✅ | 今日收益率 | `0.0085` |
| `total_pnl` | Decimal | ❌ | 累计盈亏 | `1250000.00` |
| `total_return` | Decimal | ❌ | 累计收益率 | `0.1428` |
| `updated_at` | DateTime | ✅ | 更新时间 | `2024-01-15 15:00:00` |

---

## 7. 交易信号（Signal）

### 7.1 信号结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `signal_id` | String | ✅ | 信号ID | `SIG_20240115_001` |
| `symbol` | String | ✅ | 证券代码 | `600519.SH` |
| `direction` | Enum | ✅ | 信号方向 | `LONG`, `SHORT`, `EXIT` |
| `strength` | Decimal | ✅ | 信号强度 [0~1] | `0.85` |
| `strategy` | String | ✅ | 策略名称 | `trend_ma_cross` |
| `timestamp` | DateTime | ✅ | 信号时间 | `2024-01-15 09:35:00` |
| `price` | Decimal | ❌ | 参考价格 | `1850.00` |
| `reason` | String | ❌ | 信号原因 | `MA5 上穿 MA20` |

---

## 8. 绩效数据（Performance）

### 8.1 回测绩效结构

| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
|-------|---------|-----|------|------|
| `strategy_name` | String | ✅ | 策略名称 | `trend_ma_cross` |
| `backtest_id` | String | ✅ | 回测ID | `BT_20240115_001` |
| `start_date` | Date | ✅ | 回测开始 | `2023-01-01` |
| `end_date` | Date | ✅ | 回测结束 | `2024-01-01` |
| `initial_cash` | Decimal | ✅ | 初始资金 | `10000000.00` |
| `final_value` | Decimal | ✅ | 最终权益 | `11850000.00` |
| `total_return` | Decimal | ✅ | 总收益率 | `0.1850` |
| `annual_return` | Decimal | ✅ | 年化收益率 | `0.0925` |
| `sharpe_ratio` | Decimal | ✅ | 夏普比率 | `1.25` |
| `max_drawdown` | Decimal | ✅ | 最大回撤 | `-0.1250` |
| `max_drawdown_duration` | Integer | ❌ | 最大回撤持续天数 | `45` |
| `win_rate` | Decimal | ✅ | 胜率 | `0.5560` |
| `profit_loss_ratio` | Decimal | ✅ | 盈亏比 | `1.85` |
| `total_trades` | Integer | ✅ | 总交易次数 | `256` |
| `avg_holding_days` | Decimal | ❌ | 平均持仓天数 | `12.5` |
| `turnover_rate` | Decimal | ❌ | 换手率 | `2.35` |
| `created_at` | DateTime | ✅ | 生成时间 | `2024-01-15 18:00:00` |

---

## 9. 枚举类型定义

### 9.1 证券代码格式

```
{股票代码}.{交易所}
SH = 上海证券交易所
SZ = 深圳证券交易所
BJ = 北京证券交易所
HK = 香港交易所

示例：
600519.SH  = 贵州茅台（上交所）
000858.SZ  = 五粮液（深交所）
688981.SH = 中芯国际（科创板）
```

### 9.2 时间周期格式

| 格式 | 说明 |
|-----|------|
| `1m` | 1分钟 |
| `5m` | 5分钟 |
| `15m` | 15分钟 |
| `30m` | 30分钟 |
| `1h` | 1小时 |
| `1d` | 日线 |
| `1w` | 周线 |

### 9.3 市场板块分类

| 板块代码 | 说明 |
|---------|------|
| `MAIN` | 主板 |
| `GEM` | 创业板（ChiNext） |
| `STAR` | 科创板（STAR Market） |
| `BJ` | 北交所 |

---

*本文档由 faster_qt 项目组维护，最后更新：2026-04-19*
