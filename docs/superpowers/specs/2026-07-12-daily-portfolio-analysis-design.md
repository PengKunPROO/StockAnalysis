# 每日持仓分析与操作指导系统 - 设计文档

> 日期: 2026-07-12
> 状态: 设计确认中
> 架构方案: 方案C - 分层架构 + 上下文记忆

## 1. 需求概述

动态长期地对用户的持仓、每日操作进行分析，结合K线走势、市场新闻、资金动向等股票分析因素，每日开盘前自动生成操作指导报告。

核心区别：不是单次快照分析，而是结合用户历史持仓、仓位、股票数量、操作记录进行持续性追踪分析，具备跨日记忆能力。

## 2. 已确认的设计决策

| 决策项 | 选择 |
|--------|------|
| 持仓录入方式 | 手动录入（UI 添加持仓、记录买卖交易） |
| 报告生成时机 | 自动生成+手动查看（APScheduler 每日 08:30 定时生成） |
| 分析深度 | 全维度（组合分析 + 逐股分析 + 历史操作模式识别） |
| AI 引擎 | 混合方案（规则计算组合层面 + DeepSeek function-calling 逐股分析 + skill 增强 prompt） |
| Session 污染 | 不走 diagnosis session 系统，直接 httpx 调 DeepSeek API，结果存 ReportSection |
| 数据来源 | 持仓/交易记录存本地 SQLite；行情/财务/新闻通过 DataEngine 调同花顺 API |
| UI 风格 | 暗黑科技风，第 4 个 TabView「持仓管理」，可拖拽分隔条调整面板大小 |
| 测试要求 | 严谨测试保证，新增功能必须新增测试 |

## 3. 数据模型

新增 5 个 SQLAlchemy 模型，追加到 `backend/app/db/models.py`：

### 3.1 Holding（当前持仓快照）

```python
class Holding(Base):
    __tablename__ = "holdings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)      # 股票代码 sh.600519
    name = Column(String(100), nullable=False)      # 股票名称
    shares = Column(Integer, nullable=False)         # 持有股数
    avg_cost = Column(Numeric(12, 4), nullable=False) # 平均成本价
    buy_date = Column(Date)                          # 首次买入日
    status = Column(String(10), default="open")     # open / closed
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

### 3.2 Transaction（交易记录）

```python
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    action = Column(String(10), nullable=False)     # buy / sell
    shares = Column(Integer, nullable=False)
    price = Column(Numeric(12, 4), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)  # shares * price
    traded_at = Column(DateTime, nullable=False)     # 实际交易时间
    note = Column(Text)                               # 可选备注
    created_at = Column(DateTime, server_default=func.now())
```

### 3.3 DailyReport（每日报告元数据）

```python
class DailyReport(Base):
    __tablename__ = "daily_reports"
    id = Column(String(36), primary_key=True)        # UUID
    report_date = Column(Date, nullable=False, unique=True)
    status = Column(String(10), default="pending")  # pending/running/completed/failed
    total_market_value = Column(Numeric(20, 2))      # 当日总市值
    total_cost = Column(Numeric(20, 2))             # 总成本
    total_pnl = Column(Numeric(20, 2))              # 总盈亏金额
    pnl_pct = Column(Numeric(8, 4))                  # 盈亏百分比
    summary = Column(Text)                           # AI 生成的整体操作指导
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

### 3.4 ReportSection（报告分节内容）

```python
class ReportSection(Base):
    __tablename__ = "report_sections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(36), ForeignKey("daily_reports.id"), nullable=False)
    section_type = Column(String(30), nullable=False)
    # section_type: portfolio_analysis / stock_analysis / operation_pattern / action_plan
    stock_code = Column(String(20), nullable=True)   # 仅 stock_analysis 用
    content = Column(Text)                            # JSON 或 Markdown
    section_order = Column(Integer, default=0)
    status = Column(String(10), default="success")  # success/failed/skipped
```

### 3.5 ReportContext（跨日记忆）

```python
class ReportContext(Base):
    __tablename__ = "report_contexts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(36), ForeignKey("daily_reports.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    advice_type = Column(String(20), nullable=False)
    # advice_type: buy / sell / hold / watch / stop_loss
    key_price = Column(Numeric(12, 4))               # 关键价位（止损/目标）
    advice_text = Column(Text)                       # 建议内容
    executed = Column(Boolean, default=False)        # 用户是否执行
    execution_result = Column(String(20), nullable=True)
    # execution_result: profit / loss / expired / null(未执行)
    created_at = Column(DateTime, server_default=func.now())
```

### 3.6 表关系

```
DailyReport (1) ---> (N) ReportSection
DailyReport (1) ---> (N) ReportContext
Holding 与 Transaction 通过 code 关联（非 FK，逻辑关联）
```

## 4. 分析管道架构

新建 `app/portfolio/analyzer.py`，三阶段管道：

### 4.1 阶段1 - 组合规则计算（纯 Python，无网络）

输入：Holding 表 + Transaction 表 + 实时行情（DataEngine.get_realtime）

输出：
- 仓位分布（每只股票市值占比）
- 行业暴露（通过 Stock.industry 字段聚合）
- 集中度指标（HHI 指数、最大持仓占比、前3大占比）
- 历史操作统计：
  - 胜率（盈利交易数 / 总已平仓交易数）
  - 平均持仓天数
  - 平均盈亏比
  - 连续亏损/盈利 streak
  - 最近 10 笔交易记录
- 仓位汇总（总市值、总成本、总盈亏）

写入 `ReportSection(section_type="portfolio_analysis")`

### 4.2 阶段2 - 逐股 DeepSeek 分析（并行，每只股票独立调用）

输入：
- 该股 K线 + 指标 + 财务 + 新闻 + 实时行情（复用 `tools.py` 的 `execute_tool`）
- 该股在组合中的仓位上下文（占比、成本、盈亏）
- 前日 `ReportContext` 中对该股的判断

System prompt 注入：
- 从 `skills_manager.get_skill_content()` 加载的金融分析 skill 内容
- 附加指令：分析技术面、基本面、资金面，给出操作建议（加仓/减仓/持有/清仓/观望），附买入区间、止损价、目标价

工具函数：复用现有 6 个 tools（get_kline, get_indicators, get_financials, get_realtime, search_stocks, get_news）

容错：单只股票分析失败不影响其他股票，标记 `status="failed"`

每只股票结果写入 `ReportSection(section_type="stock_analysis", stock_code=xxx)`

### 4.3 阶段3 - DeepSeek 综合总结

输入：
- 阶段1 的组合分析 JSON
- 阶段2 所有逐股分析摘要
- 前日 `ReportContext` 记忆
- 用户近期操作模式统计

System prompt 注入：金融分析 skill 内容

输出：
- 今日操作指导摘要（Markdown）
- 行动计划列表（每只股票的操作建议 + 优先级）
- 风险提示

写入 `ReportSection(section_type="action_plan")` 和 `DailyReport.summary`

同时，将本次报告中每只股票的建议操作 + 关键价位写入 `ReportContext`，供次日对比。

### 4.4 调度

APScheduler 新增任务，在 `scheduler.py` 中注册：

```python
scheduler.add_job(
    generate_daily_report,
    "cron", hour=8, minute=30,
    id="daily_report_generate",
    replace_existing=True,
)
```

### 4.5 不产生垃圾 Session

管道不经过 `diagnosis/engine.py` 的 `run_chat`（该方法会创建 DiagnosisSession + DiagnosisMessage）。而是直接用 httpx 调 DeepSeek API，结果存入 ReportSection。与 `signals.py` 的 `ai_interpret` 路径一致。

工具函数仍复用 `tools.py` 的 `execute_tool`，但不经过 session 存储。Skill 内容通过 `skills_manager.get_skill_content()` 加载后注入 system prompt。

## 5. API 端点设计

新建路由模块 `app/api/v1/portfolio.py`，前缀 `/api/v1/portfolio`：

### 5.1 持仓管理

| Method | Path | 说明 |
|--------|------|------|
| GET | `/portfolio/holdings` | 获取当前所有持仓（含实时市值计算） |
| POST | `/portfolio/holdings` | 添加持仓（code, name, shares, avg_cost, buy_date） |
| PATCH | `/portfolio/holdings/{id}` | 修改持仓（调整数量/成本） |
| DELETE | `/portfolio/holdings/{id}` | 删除持仓 |

### 5.2 交易记录

| Method | Path | 说明 |
|--------|------|------|
| GET | `/portfolio/transactions` | 获取交易记录列表（?code=xxx&limit=50&page=1 筛选+分页） |
| POST | `/portfolio/transactions` | 记录一笔交易（buy/sell） |
| DELETE | `/portfolio/transactions/{id}` | 删除交易记录 |

关键逻辑：
- 记录 buy 交易时自动更新 Holding（新增或加仓，重算 avg_cost）
- 记录 sell 交易时自动扣减 Holding.shares，若 shares=0 则标记 status="closed"
- 反删交易时回滚 Holding 变更

### 5.3 报告

| Method | Path | 说明 |
|--------|------|------|
| GET | `/portfolio/reports` | 获取报告列表（?limit=30 最近30天） |
| GET | `/portfolio/reports/today` | 获取今日报告（不存在返回 404） |
| GET | `/portfolio/reports/{date}` | 获取指定日期报告（含所有 sections） |
| POST | `/portfolio/reports/generate` | 手动触发生成（返回报告 ID，后台异步执行） |

### 5.4 报告上下文记忆

| Method | Path | 说明 |
|--------|------|------|
| GET | `/portfolio/reports/{date}/context` | 获取该日报告的记忆条目 |
| PATCH | `/portfolio/reports/context/{id}` | 标记某条建议是否执行（executed + execution_result） |

### 5.5 约定

- 所有端点 `async def`，Pydantic v2 请求/响应模型
- 优雅降级：数据源失败返回 warning 不 500
- 注册到 `router.py`：`router.include_router(portfolio.router)`

## 6. 前端 UI 设计

### 6.1 新增 Tab

`TopTabBar.tsx` 新增第 4 个 Tab：`{ key: 'portfolio', label: '持仓管理', icon: '📊' }`

### 6.2 页面布局

```
┌─────────────────────────────────────────────────────┐
│ 仪表盘卡片行（总市值 | 总成本 | 总盈亏 | 今日变动 | 仓位分布环形图）│
├──────────────────────┼──────────────────────────────┤
│ 持仓列表表格          │ 每日操作指导报告               │
│ (可滚动)             │ (可滚动)                      │
├── splitter-v ────────┤                              │
│ 交易录入表单          │ - 报告状态栏                   │
│                      │ - 组合分析（胜率/盈亏比/集中度） │
├── splitter-v ────────┤ - 逐股分析卡片（可展开）        │
│ 交易记录列表          │ - 今日行动计划                 │
│ (分页+滚动)          │ - 前日建议追踪                 │
│                      │ - 整体操作指导摘要             │
│                      │ - 风险提示                    │
└──────────────────────┴──────────────────────────────┘
       ↕ splitter-h（左右可拖拽调整宽度）
```

### 6.3 组件

新建 `PortfolioView.tsx` 组件，包含子组件：
- `PortfolioDashboard` - 仪表盘卡片行
- `HoldingsTable` - 持仓列表表格
- `TransactionForm` - 交易录入表单
- `TransactionHistory` - 交易记录列表（分页+滚动）
- `DailyReportView` - 每日报告视图（含分节内容）
- `ResizableSplitter` - 可拖拽分隔条组件

### 6.4 视觉风格

- 暗黑科技风（深蓝黑底 #0b1120 + 青色霓虹 #06d6a0）
- 复用现有 CSS 变量系统（--surface, --border, --accent, --up, --down 等）
- 涨红跌绿（A股惯例：--up=#ef4444 红, --down=#22c55e 绿）
- 可拖拽分隔条：hover 变青色，dragging 变青色 + 背景反色
- 分隔条最小宽度限制 350px（左右），80-120px（上下）

### 6.5 原型

已制作 HTML 原型：`docs/prototypes/portfolio-ui-prototype.html`
- 包含完整模拟数据和交互
- 验证了分隔条拖拽功能正常
- 验证了面板缩放后布局自适应

## 7. 测试策略

### 7.1 后端测试

新建 `backend/tests/test_portfolio.py`：

**数据模型测试：**
- Holding CRUD 操作
- Transaction CRUD 操作
- Transaction 创建时自动更新 Holding（buy 加仓/新建、sell 扣减/关闭）
- Transaction 删除时回滚 Holding

**分析管道测试：**
- 阶段1 组合规则计算（胜率、盈亏比、集中度、行业暴露）- 纯函数，用 mock 数据
- 阶段2 逐股分析 - mock DeepSeek API 返回，验证 tool 调用和结果存储
- 阶段3 综合总结 - mock DeepSeek API 返回，验证 summary 和 action_plan 生成
- 单只股票分析失败不影响其他股票
- ReportContext 跨日记忆写入和读取

**API 端点测试：**
- GET/POST/PATCH/DELETE /portfolio/holdings
- GET/POST/DELETE /portfolio/transactions（含分页）
- GET /portfolio/reports（列表）
- GET /portfolio/reports/{date}（含 sections）
- POST /portfolio/reports/generate（手动触发）
- GET/PATCH /portfolio/reports/{date}/context

**调度器测试：**
- 模拟 08:30 触发报告生成
- 重复生成同一日期报告时覆盖旧报告

### 7.2 前端验证

- `npx tsc --noEmit` 类型检查通过
- `npm run build` 构建通过
- `verify.sh` 完整测试套件通过
- 手动验证：分隔条拖拽、面板缩放自适应、报告渲染

### 7.3 集成测试

- 添加持仓 -> 记录交易 -> 触发报告生成 -> 查看报告 -> 标记建议执行 -> 次日报告引用前日记忆
- 端到端流程验证（使用 TestClient，mock 外部 API）

## 8. 文件结构

```
backend/app/
├── db/models.py              # 追加 5 个新模型
├── db/queries.py             # 追加持仓/交易/报告查询函数
├── api/v1/portfolio.py       # 新增路由模块
├── api/v1/router.py          # 注册 portfolio router
├── portfolio/                # 新增目录
│   ├── __init__.py
│   ├── analyzer.py           # 三阶段分析管道
│   ├── calculator.py         # 组合规则计算（纯函数）
│   └── report.py             # 报告生成编排
├── engine/scheduler.py       # 追加 08:30 定时任务
└── config.py                 # 无需修改

backend/tests/
└── test_portfolio.py         # 新增测试文件

frontend/src/
├── components/
│   ├── PortfolioView.tsx     # 主视图组件
│   ├── PortfolioDashboard.tsx
│   ├── HoldingsTable.tsx
│   ├── TransactionForm.tsx
│   ├── TransactionHistory.tsx
│   ├── DailyReportView.tsx
│   └── ResizableSplitter.tsx
├── api/
│   └── portfolio.ts           # API 调用函数
├── contexts/AppContext.tsx    # 追加 portfolio view
└── components/TopTabBar.tsx   # 追加第4个 Tab
```

## 9. 实现顺序

1. DB 模型追加 + queries 函数 + 测试
2. API 端点（持仓+交易 CRUD）+ 测试
3. 组合规则计算（calculator.py）+ 测试
4. 逐股 DeepSeek 分析 + 综合总结（analyzer.py）+ 测试
5. 调度器注册定时任务
6. 前端 API 调用函数
7. 前端组件（PortfolioView + 子组件）
8. TopTabBar 追加 Tab
9. verify.sh 完整测试
10. 手动集成验证

## 10. 风险与注意事项

- **DeepSeek API 超时**：逐股分析并行调用，每只独立超时 120s，失败标记 failed 不阻塞
- **avg_cost 重算**：加仓时需按加权平均重算（(原shares*原cost + 新shares*新price) / 总shares）
- **Sample 数据污染**：管道中 DataEngine 返回 sample 数据时标记 warning，不用于 AI 分析
- **DB 表自动创建**：新模型追加后 `Base.metadata.create_all` 自动建表（SQLite dev 模式）
- **报告幂等性**：同一日期重复生成时，先删旧 sections 再重新生成
- **分隔条拖拽**：需设置 min-width/min-height 防止面板塌缩；window resize 时重置固定像素为百分比
