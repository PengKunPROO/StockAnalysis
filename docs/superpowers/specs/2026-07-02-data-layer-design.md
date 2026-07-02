# 股票分析软件 — 阶段1：数据层设计

> 创建日期: 2026-07-02
> 状态: 待审核
> 阶段: 1/6 — 数据层

## 项目背景

构建一个个人投资者使用的股票分析 Web 应用，覆盖 A 股和美股市场，提供技术面 + 基本面综合分析能力。分 6 个阶段迭代交付，本文档为阶段 1：数据层的详细设计。

### 阶段规划

| 阶段 | 子系统 | 核心内容 |
|------|--------|----------|
| 1 | 数据层 | 多源数据采集、PostgreSQL 缓存、统一 API |
| 2 | 个股分析 | K线图表、技术指标、基本面卡片、AI 诊断 |
| 3 | 筛选器 | 条件筛选、结果排序、导出 |
| 4 | 自选+看盘 | 自选股管理、多股同列、价格预警 |
| 5 | 策略回测 | 策略编写、历史回测、绩效报告 |
| 6 | 模拟交易 | 虚拟账户、下单、持仓跟踪 |

## 需求约束

- 个人投资者辅助决策
- A 股 + 美股双市场
- 技术面 + 基本面综合分析
- 免费数据源起步，可扩展付费接口
- 数据库存储原始数据，不做预计算，指标在分析层按需计算
- 核心是历史行情（复盘、选股），实时行情为可选功能

---

## 一、总体架构

```
┌─────────────────────────────────────────────────────────┐
│                     React 前端                          │
│                    （阶段2开始构建）                      │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API (JSON)
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI 接口层                          │
│  GET  /api/v1/stock/{code}/kline    日线/周线/月线      │
│  GET  /api/v1/stock/{code}/realtime  最新行情           │
│  GET  /api/v1/stock/{code}/financial 财务数据           │
│  GET  /api/v1/market/index           市场指数           │
│  GET  /api/v1/search?q=              股票搜索           │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   Data Engine                           │
│  - 接收请求 → 查缓存 → 未命中则调插件 → 写入缓存 → 返回  │
│  - 后台调度：定时拉取日线数据更新                        │
│  - 插件注册：启动时自动发现 datasources/ 下的插件       │
└──────┬───────────────┬───────────────┬──────────────────┘
       │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│ A股插件     │ │ 美股插件     │ │ (未来插件)   │
│ akshare     │ │ yfinance    │ │ tushare等   │
└──────┬──────┘ └──────┬──────┘ └─────────────┘
       │               │
┌──────▼───────────────▼──────────────────────────────────┐
│              PostgreSQL (缓存 + 持久化)                   │
│  stocks | stock_daily | stock_financial | sync_log       │
└─────────────────────────────────────────────────────────┘
```

### 关键设计决策

- **缓存优先**：所有请求先查 PostgreSQL，命中直接返回（毫秒级），未命中才调外部 API
- **统一接口**：每个数据源插件实现相同的 Protocol，接口层完全不感知数据来源
- **原始数据存储**：数据库只存原始行情和财报数据，不预计算技术指标或估值指标。策略计算的指标在分析层（阶段2）按需生成
- **向后兼容扩展**：新增数据源只需添加插件文件，无需修改引擎或接口层

---

## 二、技术栈

| 层 | 技术 | 原因 |
|----|------|------|
| 后端框架 | Python 3.11 + FastAPI | 异步支持好，自动生成 OpenAPI 文档 |
| 数据采集 | akshare (A股), yfinance (美股) | 成熟免费库，覆盖全面 |
| 数据库 | PostgreSQL 15+ | 按年分区、JSON 支持、扩展性好 |
| ORM / 迁移 | SQLAlchemy + Alembic | Python 生态标准选择 |
| 任务调度 | APScheduler | 轻量级，内嵌进程，无需 Redis |
| 容器化 | Docker Compose | 一键启动 PostgreSQL + 后端 |

---

## 三、数据源插件接口

### 统一协议 (Protocol)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataSourceProtocol(Protocol):
    """所有数据源插件必须实现的接口"""

    @property
    def name(self) -> str: ...

    @property
    def markets(self) -> list[str]: ...

    async def search_stocks(self, keyword: str) -> list[StockInfo]: ...

    async def fetch_kline(
        self, code: str, period: str,
        start: str, end: str
    ) -> list[KlineBar]: ...

    async def fetch_realtime(self, code: str) -> RealtimeQuote | None: ...

    async def fetch_financials(self, code: str) -> FinancialReport | None: ...

    async def fetch_index(self, code: str) -> RealtimeQuote | None: ...

    def health_check(self) -> bool: ...
```

### 统一数据模型

```python
@dataclass
class KlineBar:
    date: str           # "2026-07-01"
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float

@dataclass
class RealtimeQuote:
    code: str
    name: str
    price: float
    change_pct: float
    volume: int
    high: float
    low: float
    timestamp: str      # ISO 8601

@dataclass
class StockInfo:
    code: str           # 统一格式: sh.600519 / us.AAPL
    name: str
    market: str         # "a_share" / "us"
    industry: str

@dataclass
class FinancialReport:
    code: str
    report_date: str    # "2026-03-31" 报告期
    revenue: float | None
    net_profit: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    roe: float | None
    debt_ratio: float | None
```

### 股票代码统一格式

| 市场 | 格式 | 示例 |
|------|------|------|
| 上证 | `sh.XXXXXX` | `sh.600519` (贵州茅台) |
| 深证 | `sz.XXXXXX` | `sz.000001` (平安银行) |
| 美股 | `us.TICKER` | `us.AAPL`, `us.TSLA` |

插件内部负责将外部源的原生代码（如 akshare 的 `600519` → `sh.600519`，yfinance 的 `AAPL` → `us.AAPL`）转换为统一格式。

---

## 四、数据库设计

### stocks — 股票基础信息

```sql
CREATE TABLE stocks (
    code        VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    market      VARCHAR(10) NOT NULL,      -- 'a_share', 'us'
    industry    VARCHAR(50),
    list_date   DATE,
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stocks_name ON stocks USING gin(to_tsvector('simple', name));
CREATE INDEX idx_stocks_market ON stocks(market);
```

### stock_daily — 日线行情

```sql
CREATE TABLE stock_daily (
    code        VARCHAR(20) NOT NULL,
    trade_date  DATE NOT NULL,
    open        NUMERIC(12,4),
    high        NUMERIC(12,4),
    low         NUMERIC(12,4),
    close       NUMERIC(12,4),
    volume      BIGINT,
    amount      NUMERIC(20,2),
    PRIMARY KEY (code, trade_date)
) PARTITION BY RANGE (trade_date);

-- 创建 2020-2030 年分区（建表时自动创建）
CREATE INDEX idx_stock_daily_code_date ON stock_daily(code, trade_date DESC);
```

按年分区的优势：历史跨度大时查询效率高，旧分区可独立归档或删除。

### stock_financial — 财报数据

```sql
CREATE TABLE stock_financial (
    code           VARCHAR(20) NOT NULL,
    report_date    DATE NOT NULL,          -- 报告期
    revenue        NUMERIC(20,2),          -- 营业收入（元）
    net_profit     NUMERIC(20,2),          -- 净利润（元）
    pe_ratio       NUMERIC(12,4),          -- 市盈率
    pb_ratio       NUMERIC(12,4),          -- 市净率
    roe            NUMERIC(8,4),           -- ROE (%)
    debt_ratio     NUMERIC(8,4),           -- 资产负债率 (%)
    total_assets   NUMERIC(20,2),          -- 总资产
    total_equity   NUMERIC(20,2),          -- 股东权益
    PRIMARY KEY (code, report_date)
);

CREATE INDEX idx_stock_financial_code_date ON stock_financial(code, report_date DESC);
```

### sync_log — 同步日志

```sql
CREATE TABLE sync_log (
    id           SERIAL PRIMARY KEY,
    source       VARCHAR(20) NOT NULL,     -- 插件名称
    data_type    VARCHAR(20) NOT NULL,     -- 'kline', 'financial', 'stock_list'
    code         VARCHAR(20),              -- 股票代码（全量同步时为 NULL）
    status       VARCHAR(10) NOT NULL,     -- 'running', 'done', 'failed'
    rows_count   INTEGER DEFAULT 0,
    started_at   TIMESTAMP,
    finished_at  TIMESTAMP,
    error_msg    TEXT
);

CREATE INDEX idx_sync_log_source_status ON sync_log(source, status);
```

### 设计原则

- **原始数据存储**：所有字段直接来自数据源，不做衍生计算。技术指标 (MACD/RSI/KDJ) 和估值计算 (PEG/PS) 在分析层按需生成
- **增量更新**：用 `MAX(trade_date)` 判断缺口，只拉取缺失日期
- **可追溯**：`sync_log` 记录每次同步的状态和数据量

---

## 五、API 接口设计

所有接口前缀 `/api/v1/`，返回 JSON。

### 5.1 股票搜索

```
GET /api/v1/search?q=茅台&market=a_share

Response 200:
{
  "results": [
    {
      "code": "sh.600519",
      "name": "贵州茅台",
      "market": "a_share",
      "industry": "白酒"
    }
  ],
  "count": 1
}
```

### 5.2 K线数据

```
GET /api/v1/stock/sh.600519/kline?period=daily&start=2026-01-01&end=2026-07-01

Response 200:
{
  "code": "sh.600519",
  "name": "贵州茅台",
  "period": "daily",
  "data": [
    {"date": "2026-01-02", "open": 1650.00, "high": 1680.00, ...},
    ...
  ],
  "count": 120
}
```

### 5.3 最新行情

```
GET /api/v1/stock/sh.600519/realtime

Response 200:
{
  "code": "sh.600519",
  "name": "贵州茅台",
  "price": 1688.50,
  "change_pct": 2.35,
  "volume": 12345678,
  "high": 1695.00,
  "low": 1650.00,
  "timestamp": "2026-07-02T15:00:00"
}
```

免费数据源返回延迟 15 分钟的行情或最近交易日收盘价，切换付费源后返回实时数据。

### 5.4 财务数据

```
GET /api/v1/stock/sh.600519/financial

Response 200:
{
  "code": "sh.600519",
  "name": "贵州茅台",
  "reports": [
    {
      "report_date": "2026-03-31",
      "revenue": 46200000000,
      "net_profit": 24050000000,
      "pe_ratio": 28.5,
      "pb_ratio": 9.2,
      "roe": 25.8,
      "debt_ratio": 21.3,
      "total_assets": 285000000000,
      "total_equity": 210000000000
    }
  ]
}
```

### 5.5 市场指数

```
GET /api/v1/market/index?codes=sh.000001,us.IXIC

Response 200:
{
  "indices": [
    {"code": "sh.000001", "name": "上证指数", "price": 3350.25, "change_pct": 0.56},
    {"code": "us.IXIC", "name": "纳斯达克", "price": 18250.00, "change_pct": -0.32}
  ]
}
```

### 5.6 健康检查

```
GET /api/v1/health

Response 200:
{
  "status": "ok",
  "datasources": {
    "akshare": "healthy",
    "yfinance": "healthy"
  },
  "database": "connected"
}
```

### 错误响应格式

```json
// 404
{"error": "未找到股票 sh.999999", "request_id": "a1b2c3d4"}

// 422
{"error": "参数错误", "detail": [{"field": "period", "msg": "必须是 daily/weekly/monthly"}], "request_id": "..."}

// 500
{"error": "内部错误", "request_id": "a1b2c3d4"}
```

---

## 六、数据引擎与同步策略

### 缓存查询流程

```
请求进入 → Data Engine
  ├─ 查 PostgreSQL stock_daily
  │   ├─ 数据完整 (覆盖请求时间范围) → 直接返回 (< 10ms)
  │   └─ 数据不完整 → 调用插件补充缺失部分 → 写入 DB → 返回
  └─ 无数据 → 调用插件全量拉取 → 写入 DB → 返回
```

### 后台同步任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 增量日线更新 | 每个交易日 15:30 | 拉取当日 K 线 |
| 全量日线补齐 | 每周日 02:00 | 检查并补齐遗漏的历史数据 |
| 财报更新 | 每日 06:00 | 检查最新财报 |
| 股票列表刷新 | 每周一 04:00 | 同步最新上市/退市股票 |
| 插件健康检查 | 每 30 分钟 | 检测所有插件的可用性 |

### 降级策略

- akshare 不可用 → yfinance 仍可服务美股请求
- 外部 API 限流 (429) → 指数退避重试 3 次，仍失败则返回缓存旧数据 + `warning: "数据可能不是最新"`
- 网络超时 (5s) → 标记插件为 degraded，返回空数据 + `warning: "数据源暂不可用"`
- 数据格式异常 → 记录 `sync_log` 错误，跳过异常条目，继续处理剩余数据
- 插件彻底不可用 → `health_check` 自动排除，避免无意义重试

---

## 七、项目目录结构

```
hermesStockAgent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 入口，启动事件注册
│   │   ├── config.py            # 配置管理（环境变量 + .env）
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py    # 路由注册
│   │   │       ├── stocks.py    # K线、行情接口
│   │   │       ├── financial.py # 财务数据接口
│   │   │       ├── search.py    # 搜索接口
│   │   │       ├── index.py     # 指数接口
│   │   │       └── health.py    # 健康检查
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── data_engine.py   # 数据引擎核心
│   │   │   └── scheduler.py     # APScheduler 定时任务
│   │   ├── datasources/
│   │   │   ├── __init__.py      # 插件自动发现与注册
│   │   │   ├── base.py          # DataSourceProtocol 定义
│   │   │   ├── akshare.py       # A股插件
│   │   │   └── yfinance.py      # 美股插件
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── kline.py         # KlineBar, RealtimeQuote
│   │   │   ├── stock.py         # StockInfo
│   │   │   └── financial.py     # FinancialReport
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── database.py      # SQLAlchemy engine + session
│   │       ├── models.py        # ORM 模型
│   │       └── queries.py       # 业务查询函数
│   ├── alembic/
│   │   └── versions/            # 数据库迁移文件
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # 阶段2开始构建
│   ├── src/
│   │   ├── components/          # React 组件
│   │   ├── pages/               # 页面
│   │   ├── api/                 # API 调用封装
│   │   └── App.tsx
│   └── package.json
├── docs/
│   └── superpowers/
│       └── specs/               # 设计文档
├── docker-compose.yml           # PostgreSQL + 后端
├── .env.example                 # 环境变量模板
├── .hermes.md                   # Hermes 项目规则
└── README.md
```

---

## 八、错误处理矩阵

| 场景 | HTTP 状态码 | 响应内容 |
|------|-------------|----------|
| 股票不存在 | 404 | `{"error": "未找到股票 sh.999999"}` |
| 参数格式错误 | 422 | `{"error": "...", "detail": [...]}` |
| 数据源不可用 | 200 | 正常数据 + `{"warning": "数据可能不是最新"}` |
| 数据库连接失败 | 503 | `{"error": "服务暂不可用"}` |
| 未预期异常 | 500 | `{"error": "内部错误", "request_id": "..."}` |

---

## 九、验收标准

- [ ] `docker-compose up` 一键启动 PostgreSQL + FastAPI 后端
- [ ] Swagger 文档 (`/docs`) 可交互测试所有接口
- [ ] 能搜索 A 股和美股股票
- [ ] 能获取 A 股日线数据（如贵州茅台 600519）
- [ ] 能获取美股日线数据（如 Apple AAPL）
- [ ] 能获取财报数据
- [ ] 能获取指数行情（上证、纳斯达克）
- [ ] 重复查询同一股票数据走缓存（响应 < 50ms）
- [ ] 后台定时任务自动同步数据
- [ ] 某个数据源故障不影响另一个市场的查询
- [ ] 健康检查接口返回各组件状态

---

## 十、风险与待定事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| akshare API 不稳定 | A 股数据中断 | yfinance 提供部分 A 股数据作为补充；后续接入 tushare |
| yfinance 被限流 | 美股数据中断 | 降低请求频率，用缓存减少外部调用 |
| 免费数据源数据质量 | 个别数据缺失或错误 | sync_log 追踪异常，手动补录机制 |
| PostgreSQL 需要额外安装 | 启动门槛提高 | Docker Compose 一键部署 |

---

## 十一、后续阶段预览

阶段2（个股分析）将在数据层之上构建：

- K 线图表渲染（ECharts / lightweight-charts）
- 技术指标计算与展示（MACD, RSI, KDJ, BOLL）
- 基本面卡片
- **AI 诊断模块**：通过 Hermes skill 注入分析 prompt，对个股进行技术面 + 基本面综合诊断
- 自选股侧边栏

---

> 下一步：用户审核本设计文档后，进入 writing-plans 阶段制定实现计划。
