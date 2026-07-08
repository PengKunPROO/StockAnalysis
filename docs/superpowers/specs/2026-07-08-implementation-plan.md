# 四模块股票分析系统 — 实施计划

> 基于 `2026-07-08-handoff.md` 与 `.superpowers/brainstorm/922-1783443237/content/*` mockup
> 目标：多视图 SPA + 操作建议 + 选股器 + 市场情报，全部模块全深度实现
> 原则：每个 Phase 产出可测试、可提交的单元；先纯计算（无网络、易测），后网络数据源

---

## 架构决策（已定）

1. **多视图 SPA**：`App.tsx` 改为 TopTab 切换（个股分析 / 选股器 / 市场情报），Sidebar 持久常驻，NewsPanel 仅个股分析页显示。
2. **操作建议双轨**：规则信号 Tab（纯计算 JSON）+ AI解读 Tab（DeepSeek httpx SSE 流式，**不复用 hermes 子进程**，直接调 `diagnosis_llm_base_url` 的 `/chat/completions` stream，规则信号 JSON 注入上下文）。
3. **选股器 OCP**：`FilterField` 声明式 + `ScreenerStrategyRegistry` 策略注册表；新策略加注册即自动出现在前端。
4. **PE/PB 与情报补充数据**：新建 `eastmoney.py` 爬虫（push2.eastmoney.com 公开端点，无鉴权），**全程 try/except 降级**——失败返回空 + warning，绝不抛异常。
5. **测试策略**：纯计算（ATR/斐波那契/信号规则/筛选逻辑）单元测试全覆盖、无网络；网络端点结构测试（200 + 字段存在），真实数据按 `FUYAO_API_KEY`/网络可用性 skip/mock。
6. **配色**：复用现有 CSS 变量（`--bg/--surface/--accent/--up/--down/--gold`），红涨绿跌 A 股习惯（`--up=#ef4444`）。
7. **verify.sh**：随结构变化更新完整性检查（App.tsx 导入 + 新组件 CSS 类）。

---

## Phase 1 — SPA 骨架 + 增强指标（ATR / 斐波那契）

### 后端
- **`backend/app/indicators/atr.py`**：`compute_atr(klines, period=14) -> list[float|None]`（TR = max(H-L, |H-prevC|, |L-prevC|)，ATR = TR 的 RMA/EMA）。
- **`backend/app/indicators/fibonacci.py`**：`compute_fibonacci(klines, lookback=60) -> dict`（取窗口最高/最低，返回 0/23.6/38.2/50/61.8/78.6% 回撤位 + 方向）。
- **`backend/app/indicators/__init__.py`**：`compute_all` 增加 `atr`、`fibonacci`（fibonacci 只放最后一根 bar 的 dict）。
- **`backend/app/api/v1/indicators.py`**：响应增加 `atr`（序列）、`fibonacci`（单值 dict）；保持现有 `days`/`period` 参数与 200/422 契约不变。

### 前端
- **`frontend/src/contexts/AppContext.tsx`**：state 增加 `activeView: 'stock' | 'screener' | 'intel'`，dispatch `SET_VIEW`。
- **`frontend/src/components/TopTabBar.tsx`**（新）：三 Tab 切换，复用 `.topbar` 主题样式。
- **`frontend/src/App.tsx`**：重构为 `Sidebar + main(TopBar + TopTabBar + view路由 + StatusBar) + 条件 NewsPanel`。个股分析视图保留现有 `InfoCards/KlineChart/DiagnosisPanel`，并预留 `SignalsPanel` 位置。选股器/情报 Tab 先渲染占位（Phase 3/4 填充）。
- **`frontend/src/index.css`**：新增 `.top-tab-bar`、`.view-route` 等类。

### 测试
- `backend/tests/test_indicators.py`：补 ATR（与已知序列对照）、fibonacci（回撤位数学正确性）、ATR 长度等于输入。
- `frontend`：`npx tsc --noEmit` 通过。

### 提交
`feat: multi-view SPA shell + ATR/fibonacci indicators`

---

## Phase 2 — 操作建议模块（规则引擎 + AI解读 + K线价位线）

### 后端
- **`backend/app/signals/__init__.py`**
- **`backend/app/signals/rules.py`**（核心，纯计算、易测）：
  - `compute_signals(klines, indicators) -> dict`，返回：
    - `active_signals: list[{name, direction, strength(强/中/弱), detail, date}]`
      - MACD 金叉/死叉（DIF 上/下穿 DEA，看最后两根）
      - RSI 超买(>70)/超卖(<30)
      - KDJ 金叉/死叉（K 穿 D）
      - BOLL 突破上轨/下轨/触下轨
    - `score: {value:int(-100..100), label:'偏空'/'中性'/'偏多', pct:int}`
    - `key_levels: [{price, type:'阻力'/'支撑'/'斐波', source, note}]`（BOLL 上下轨 + 斐波那契位）
    - `risk: {atr, stop_loss(price, pct), take_profit(price, pct), kelly_pct, risk_reward_ratio}`
      - 止损 = 收盘 - 1×ATR；止盈 = 收盘 + 1.7×ATR 或布林上轨；凯利 = 简化 f*=p-(1-p) （p 由 score.pct 映射，封顶 50%）；盈亏比 = (止盈-价)/(价-止损)
    - `summary: str`（拼接的关键区间 + 仓位文本，非 LLM）
- **`backend/app/api/v1/signals.py`**（新 router）：
  - `GET /api/v1/signals/{code}` → `{code, ...compute_signals, updated_at}`（实时计算，依赖 engine.get_klines + compute_all）。
  - `POST /api/v1/signals/{code}/ai` → SSE `text/event-stream`：
    - 先 `yield` 规则信号 JSON（前端可即时展示骨架）
    - 调 DeepSeek `chat/completions`（stream=True，OpenAI 兼容格式），system 注入"你是 A 股分析顾问，基于以下规则信号给出主观解读与含价格区间的操作建议，禁用 Markdown，客观+风险提示"，user 注入规则信号 JSON + 最近指标。
    - 无 API key 时 `yield {error:'AI 未配置'}` 并结束（不抛 500）。
  - 端口引用与 diagnosis 一致（8002）——不破坏 verify.sh 端口一致性检查（其 grep 仅扫 diagnosis.py）。
- **`backend/app/api/v1/router.py`**：注册 signals router。

### 前端
- **`frontend/src/api/signals.ts`**（新）：`getSignals(code)`、`streamSignalsAI(code, onChunk)`（fetch + ReadableStream 解析 SSE，复用 diagnosis.ts 的流式模式）。
- **`frontend/src/components/SignalsPanel.tsx`**（新，对照 signals-panel.html）：
  - 双 Tab：规则信号 / AI解读。
  - 规则信号：活跃信号列表（▲▼ + 强度 badge）、信号强度进度条、关键价位卡、风险管理表、底部总结。
  - AI解读：SSE 流式渲染纯文本，禁用 Markdown，加载态 + 风险提示。
- **`frontend/src/components/KlineChart.tsx`**：增加 `addSeries(LineSeries)` 画支撑/阻力/斐波价位线（来自 signals 的 key_levels），随股票切换更新；新增"显示价位线"开关。
- **`frontend/src/App.tsx`**：个股分析视图在 KlineChart 下方插入 `<SignalsPanel />`。

### 测试
- `backend/tests/test_signals.py`（新）：纯计算全覆盖——金叉/死叉构造数据触发、RSI 超买超卖、BOLL 突破、ATR 数学、凯利封顶、盈亏比、score 方向；API `/signals/{code}` 返回 200 + 全字段；`/ai` 无 key 时不 500。
- 前端 tsc 通过。

### 提交
`feat: 操作建议 — 规则信号引擎 + DeepSeek SSE AI解读 + K线价位线`

---

## Phase 3 — 选股器模块（OCP 策略注册表 + 东财爬虫）

### 后端
- **`backend/app/datasources/eastmoney.py`**（新爬虫，全 try/except）：
  - `_em_secid(code)`：`sh.600519 → 1.600519`，`sz.000001 → 0.000001`。
  - `fetch_valuation(code)` → `{pe_ttm, pb, total_market_cap, float_market_cap}`（push2 `api/qt/stock/get`，fields 选 `pe_ttm,pb,fundStock,..."）。
  - `fetch_fund_flow(code)` → 近 N 日主力净流入序列。
  - `fetch_sector_rank(board='industry'|'concept')` → 行业/概念涨跌幅排行（push2 `api/qt/clist/get`）。
  - `fetch_north_bound()` → 沪股通/深股通净流入。
  - `fetch_announcements(code, limit)` → 公告列表。
  - 每个方法 `except: return None/[]`。
- **`backend/app/screener/__init__.py`** + **`fields.py`** + **`strategies.py`**：
  - `FilterField(BaseModel)`: `name,label,type(number_range|boolean|choice),category(基本面|技术信号|行情表现|行业概念),constraints,depends_on`。
  - `ScreenerStrategyRegistry`: `register/get/list`; 内置 4 策略（价值选股/技术选股/短线强势/行业轮动）各自声明字段集 + `evaluate(stock, fields)` 谓词。
  - 筛选执行：从 `Stock` 表（watchlist 全集）+ 实时行情/财务/估值合成 `StockResult`，逐字段过谓词。
- **`backend/app/api/v1/screener.py`**（新）：
  - `GET /api/v1/screener/fields` → `{fields: [FilterField], categories: [...]}`（动态渲染依据）。
  - `GET /api/v1/screener/skills` → `{skills: [{name, label, description, fields:[names]}]}`。
  - `POST /api/v1/screener/run` → body `{fields: {name: value}, sort?, limit?}` → `{results: [StockResult], count, warning?}`。
- **router.py** 注册。

### 前端
- **`frontend/src/api/screener.ts`**（新）。
- **`frontend/src/components/ScreenerView.tsx`**（新，对照 screener-detail.html）：
  - 4 个分类 Tab 拉 fields 动态渲染输入控件；选股 Skills 快捷区（点 Skill 填充字段）；"开始筛选" → 结果表格；行点击 → `dispatch SET_STOCK + SET_VIEW('stock')` 跳个股分析。
  - 保存策略到 localStorage。
- **`frontend/src/App.tsx`**：选股器 Tab 渲染 `<ScreenerView/>`。

### 测试
- `backend/tests/test_screener.py`：FilterField 序列化、Registry 注册/列举、各策略 evaluate 构造数据通过/不通过、`/fields`&`/skills` 200、`/run` 用 stub 数据返回结构；eastmoney 爬虫方法在网络不可用时返回 None/[]（不抛）。
- 前端 tsc 通过。

### 提交
`feat: 选股器 — OCP 策略注册表 + 东财估值/资金爬虫`

---

## Phase 4 — 市场情报模块（6 Tab + 总览仪表盘）

### 后端
- **`backend/app/api/v1/intelligence.py`**（新）：
  - `GET /api/v1/intelligence/overview` → 5 指数卡 + 涨跌/涨停/炸板统计 + 情绪指标（恐惧贪婪/赚钱效应/打板成功率/连板晋级率）。
  - `GET /api/v1/intelligence/limit-up` → 涨停连板梯队（同花顺 limit-up-pool + 连板高度分桶 + 首板/2板/.../高位板）。
  - `GET /api/v1/intelligence/fund-flow?scope=stock|industry|concept` → 资金流向（东财爬虫 + 北向）。
  - `GET /api/v1/intelligence/sectors?type=industry|concept` → 板块轮动排行（东财 clist）。
  - `GET /api/v1/intelligence/dragon-tiger?date` → 龙虎榜 + 席位明细（同花顺 dragon-tiger-list）。
  - `GET /api/v1/intelligence/anomalies` → 异动流（同花顺 anomaly-analysis-stock + 类型分类）。
  - `GET /api/v1/intelligence/announcements` → 热点公告（东财 + 可选 AI 摘要 SSE，复用 Phase 2 DeepSeek 模式）。
  - 全程降级：数据源失败返回空数组 + `warning`，HTTP 200。
- **router.py** 注册。

### 前端
- **`frontend/src/api/intelligence.ts`**（新）。
- **`frontend/src/components/IntelligenceView.tsx`**（新，对照 intelligence-v2.html）：
  - 顶部固定市场总览仪表盘（指数卡行 + 统计条 + 情绪指标条）。
  - 6 Tab：连板梯队 / 资金流 / 板块轮动 / 龙虎榜 / 异动 / 公告，各子组件懒渲染。
  - Tab 4 龙虎榜席位可展开；Tab 5 异动类型筛选；Tab 6 公告 AI 摘要流式。
- **`frontend/src/App.tsx`**：情报 Tab 渲染 `<IntelligenceView/>`。

### 测试
- `backend/tests/test_intelligence.py`：各端点 200 + 字段结构；降级路径（mock 失败返回空+warning）；连板分桶逻辑纯计算测。
- 前端 tsc 通过。

### 提交
`feat: 市场情报 — 6 Tab + 总览仪表盘`

---

## Phase 5 — 集成验证与收尾

- 更新 **`verify.sh`**：完整性检查改为——App.tsx 含 `TopTabBar`/`SignalsPanel`；index.css 含 `.signals-panel`/`.screener-view`/`.intelligence-view`；保留 `kline-container`/`news-panel`/`chat-panel`/`.info-cards`。
- 全量 `bash verify.sh`（pytest + tsc + vite build + 完整性 + 端口一致性）。
- 更新 **`AGENTS.md`**：补 signals/screener/intelligence 路由、新数据源、新组件清单。
- 最终提交：`docs + verify alignment`（如有），推送 origin/main。

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 东财爬虫网络不可用（同 akshare） | 全 try/except 降级；端点 200 + warning；爬虫单测断言"失败不抛" |
| DeepSeek API key 未配置 | `/signals/{code}/ai` 返回结构化 error 非 500；AI 测试 skip |
| 多视图重构破坏 verify.sh | Phase 1 即同步更新 verify.sh，每 Phase 末跑 verify |
| 信号规则误判（边界） | 纯计算单测用构造序列精确触发，覆盖金叉/死叉/超买/超卖各分支 |
| 单次会话过大、上下文被压缩 | 严格按 Phase 顺序、每 Phase 独立提交；压缩后可凭 commit 与本计划续作 |

## 执行顺序（提交粒度）
Phase 1 → 2 → 3 → 4 → 5，每 Phase：后端(逻辑→API→测试) → 前端(client→组件→集成) → `verify.sh` → `git commit`。各 Phase 完成即推送。
