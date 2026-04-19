# faster_qt

> 一个用于探索量化交易的系统，仅用于个人学习

---

## 项目简介

`faster_qt` 是一个面向**个人投资者**的量化交易研究框架，目标是：

1. **数据驱动** — 系统化采集、清洗、存储市场数据
2. **因子挖掘** — 构建量价、财务、另类因子库
3. **策略研发** — 回测验证策略思想，迭代优化
4. **实盘执行** — 连接券商通道，自动化交易
5. **风险管控** — 实时风控，守护本金安全

> ⚠️ **免责声明**：本项目仅供个人学习研究，不构成任何投资建议。实盘交易存在风险，请谨慎决策。

---

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd faster_qt
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate   # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置

复制配置示例文件并填写：

```bash
cp configs/system.example.json configs/system.json
# 编辑 configs/system.json，填入你的 API Key
```

### 5. 运行示例策略

```bash
python scripts/backtest_run.py --strategy trend_ma_cross --start 2023-01-01 --end 2024-12-31
```

---

## 项目结构

```
faster_qt/
├── data/           # 数据存储（行情、财务、因子）
├── docs/           # 设计文档
├── logs/           # 日志
├── configs/        # 配置文件
├── scripts/        # 一次性脚本
├── src/            # 核心源代码
│   ├── data/       # 数据层
│   ├── factors/    # 因子层
│   ├── strategy/   # 策略层
│   ├── execution/  # 执行层
│   ├── risk/       # 风控层
│   └── monitor/    # 监控层
└── tests/          # 测试
```

详见 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

---

## 核心模块

| 模块 | 描述 | 状态 |
|------|------|------|
| `data` | 数据采集、清洗、存储 | 🔨 建设中 |
| `factors` | 量价因子、财务因子、另类因子 | 🔨 建设中 |
| `strategy` | 策略基类、信号生成、组合管理 | 🔨 建设中 |
| `execution` | 订单管理、算法交易、券商适配 | 🔨 建设中 |
| `risk` | 仓位限制、亏损限制、合规校验 | 🔨 建设中 |
| `monitor` | 监控面板、报警、绩效归因 | 🔨 建设中 |

---

## 技术栈

| 类别 | 技术选型 |
|------|---------|
| 语言 | Python 3.10+ |
| 数据处理 | Pandas, NumPy, SciPy |
| 回测 | Backtrader, Zipline |
| 存储 | PostgreSQL, Redis |
| 消息队列 | Kafka, RabbitMQ |
| 可视化 | Plotly, Grafana |
| 部署 | Docker, K8s（可选）|

---

## 学习路径

1. **数据采集** — 接入 Tushare / AKShare，获取 A股行情和财务数据
2. **因子构建** — 实现均线、布林带、RSI 等基础因子
3. **策略回测** — 使用 Backtrader 进行历史数据验证
4. **风控机制** — 设置止损、仓位限制
5. **模拟交易** — Paper Trading 验证策略稳定性
6. **实盘对接** — 连接 QMT / 掘金量化 通道

---

## 注意事项

- 🔒 **数据安全**：敏感信息（API Key、账号密码）通过环境变量注入，不要硬编码
- 📊 **回测≠实盘**：历史业绩不代表未来表现，滑点、流动性、滑点需在回测中充分考虑
- ⚠️ **风险控制**：实盘前务必设置止损规则，系统性风险管理是长期生存的关键

---

## License

MIT License — 仅供个人学习使用
