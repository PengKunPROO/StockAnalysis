# 股票分析软件 — 阶段2：个股分析与AI诊断

> 创建日期: 2026-07-02
> 状态: 待审核
> 阶段: 2/6 — 个股分析与AI诊断
> 依赖: 阶段1（数据层）已完成

## 项目背景

在阶段1数据层基础上，构建个股分析界面和AI诊断系统。用户可查看K线图、技术指标、基本面数据，并通过多轮对话与AI进行深度分析——包括单股诊断、多股对比、策略讨论。

核心差异化：**Function Calling 驱动的 AI 诊断引擎**，搭配**可配置的 Skill 系统**。AI 按需调用工具获取数据，不同分析场景加载不同 Skill 文件作为系统提示词。

## 需求约束

- React + lightweight-charts 前端
- AI 诊断支持多轮对话、多股票比较
- Skill 文件通过 UI 上传管理（非配置文件）
- AI 通过 Function Calling 按需获取数据（非预注入）
- Tool-call 循环最多 5 轮，防止死循环
- SSE 流式输出 AI 回复
- 技术指标在服务端计算（纯函数，不依赖数据库）

---

## 一、总体架构

```
┌──────────────────────────────────────────────────────────┐
│                    React 前端                            │
│                                                          │
│  SearchBar → StockDetail                                │
│  ┌──────────────┬──────────────────────────────────┐    │
│  │ KlineChart   │        DiagnosisPanel            │    │
│  │ +指标叠加     │  Skill▼ [添加股票+] [历史会话]    │    │
│  │              │  ┌──────────────────────────────┐│    │
│  │ InfoCards    │  │ 流式 AI 对话...                ││    │
│  │ 基本面+技术面 │  └──────────────────────────────┘│    │
│  └──────────────┴──────────────────────────────────┘    │
│  WatchlistSidebar (抽屉)  SkillManager (弹窗)           │
└──────────────────────┬───────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼───────────────────────────────────┐
│                   FastAPI 后端                            │
│                                                          │
│  /api/v1/stock/{code}/indicators    新增：指标计算        │
│  /api/v1/diagnosis/chat             新增：AI对话(SSE)     │
│  /api/v1/diagnosis/sessions         新增：会话管理        │
│  /api/v1/skills                     新增：Skill CRUD      │
│  /api/v1/watchlist                  新增：自选股          │
│                                                          │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────┐  │
│  │指标计算引擎 │ │ AI诊断引擎    │ │ Skill 文件管理器   │  │
│  │macd/rsi/kdj│ │ Function Call│ │ backend/skills/*.md│  │
│  │ /boll      │ │ + SSE 流式   │ │                   │  │
│  └────────────┘ └──────┬───────┘ └───────────────────┘  │
│                        │                                 │
│                 ┌──────▼──────┐                          │
│                 │ LLM API     │                          │
│                 │ (可配置)     │                          │
│                 └─────────────┘                          │
└──────────────────────────────────────────────────────────┘
```

---

## 二、技术栈

| 层 | 技术 | 原因 |
|----|------|------|
| 前端框架 | React 18 + TypeScript | 类型安全，生态丰富 |
| 构建工具 | Vite | 快速 HMR |
| 图表库 | lightweight-charts (TradingView) | 专业金融图表，体积小 |
| HTTP 客户端 | fetch + EventSource (SSE) | 零依赖 |
| 状态管理 | React Context + useReducer | 轻量够用 |
| 后端 | FastAPI（已有） | 阶段1 技术栈延续 |
| 指标计算 | numpy + pandas | Python 科学计算标准库 |
| LLM 调用 | httpx + sse-starlette | 异步 HTTP + 服务端推送 |
| 会话存储 | SQLite（已有 stock.db） | 与阶段1 统一 |

---

## 三、项目结构（新增/修改）

```
hermesStockAgent/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── indicators.py    # 新增：技术指标接口
│   │   │   ├── diagnosis.py     # 新增：AI诊断对话接口
│   │   │   ├── skills_api.py    # 新增：Skill管理接口
│   │   │   ├── watchlist.py     # 新增：自选股接口
│   │   │   └── router.py        # 修改：注册新路由
│   │   ├── indicators/          # 新增：指标计算引擎
│   │   │   ├── __init__.py
│   │   │   ├── macd.py
│   │   │   ├── rsi.py
│   │   │   ├── kdj.py
│   │   │   └── boll.py
│   │   ├── diagnosis/           # 新增：AI诊断引擎
│   │   │   ├── __init__.py
│   │   │   ├── engine.py        # Function Calling 循环
│   │   │   ├── tools.py         # Tool 定义 + 执行
│   │   │   ├── sessions.py      # 会话管理
│   │   │   └── skills.py        # Skill 文件管理
│   │   └── db/
│   │       └── models.py        # 修改：添加诊断相关表
│   ├── skills/                  # 新增：Skill 文件存储目录
│   │   └── .gitkeep
│   └── requirements.txt         # 修改：添加依赖
├── frontend/                    # 新增：React 前端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/                 # API 调用封装
│   │   │   ├── client.ts        # fetch 封装
│   │   │   ├── stocks.ts        # 行情/指标API
│   │   │   ├── diagnosis.ts     # 诊断对话API (SSE)
│   │   │   ├── skills.ts        # Skill管理API
│   │   │   └── watchlist.ts     # 自选股API
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── KlineChart.tsx
│   │   │   ├── InfoCards.tsx
│   │   │   ├── DiagnosisPanel.tsx
│   │   │   ├── WatchlistSidebar.tsx
│   │   │   ├── SkillManager.tsx
│   │   │   └── ChatMessage.tsx
│   │   ├── contexts/
│   │   │   └── AppContext.tsx
│   │   └── types/
│   │       └── index.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
└── docs/superpowers/
    ├── specs/2026-07-02-data-layer-design.md
    └── specs/2026-07-02-analysis-design.md  ← 本文档
```

---

## 四、Skill 管理系统

### 4.1 Skill 文件格式

存放在 `backend/skills/` 目录，Markdown + YAML frontmatter：

```markdown
---
name: 价值投资分析
description: 基于格雷厄姆价值投资框架
mode: fundamental
---

# 价值投资分析 Skill

## 角色
你是一位资深价值投资者，遵循格雷厄姆和巴菲特的方法论。

## 分析框架
1. 财务健康度检查（ROE > 15%? 负债率合理? 现金流健康?）
2. 估值分析（PE/PB 历史分位、DCF 估值）
3. 护城河评估（品牌、转换成本、网络效应）
4. 管理层评估（资本配置能力、诚信记录）
5. 给出买入/持有/卖出建议及理由

## 注意事项
- 对比分析时要列出关键差异
- 风险评估必须量化
- 引用具体财务数据佐证观点
```

### 4.2 Skill 管理 API

| 方法 | 路径 | 请求/响应 |
|------|------|-----------|
| GET | `/api/v1/skills` | 返回 `[{name, description, mode}]` |
| POST | `/api/v1/skills/upload` | `multipart/form-data` 上传 `.md` 文件 |
| DELETE | `/api/v1/skills/{name}` | 删除指定 skill 文件 |
| GET | `/api/v1/skills/{name}` | 返回完整 Markdown 内容（预览用） |

### 4.3 前端 Skill 管理 UI

- 诊断面板上方：Skill 下拉选择器（当前会话使用）
- 选择器右侧 ⚙️ 齿轮按钮 → 打开 SkillManager 弹窗
- 弹窗内容：
  - 已安装 Skill 列表（名称 / 描述 / 模式标签）
  - [导入 Skill] 按钮 → 系统文件选择器（过滤 `.md`）
  - 每个 skill 行：[预览] [删除]
  - 预览 → 展开显示完整 Markdown 内容

---

## 五、AI 诊断引擎（Function Calling）

### 5.1 会话模型

```
Session {
  id: UUID
  skill_name: "价值投资分析"
  model: "deepseek-v4-pro"
  watched_stocks: ["sh.600519", "sz.000858"]
  messages: [{role, content, tool_calls?, tool_call_id?}]
  created_at, updated_at
}
```

### 5.2 数据库新增表

```sql
CREATE TABLE diagnosis_sessions (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_stocks (
    session_id TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    PRIMARY KEY (session_id, stock_code),
    FOREIGN KEY (session_id) REFERENCES diagnosis_sessions(id)
);

CREATE TABLE diagnosis_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
    content TEXT,
    tool_calls TEXT,       -- JSON string for assistant tool calls
    tool_call_id TEXT,     -- for tool result messages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES diagnosis_sessions(id)
);
```

### 5.3 Function Calling 流程

```
POST /api/v1/diagnosis/chat
{
  session_id?: "uuid",     // 新建时省略，后端创建
  skill: "价值投资分析",
  model: "deepseek-v4-pro",
  message: "茅台和五粮液谁的ROE更高？",
  stock_codes?: ["sh.600519", "sz.000858"]  // 可选：添加关注股票
}
```

**后端处理循环（最多 5 轮 tool-call）：**

```
1. 构建 system prompt:
   - skill 文件内容
   - 可用 tools 定义 (JSON Schema)
   - 关注股票列表摘要

2. messages = [system, ...history, user_message]

3. 调 LLM API (带 tools)
   ↓
4. LLM 返回:
   有 tool_calls? → 执行工具 → 结果追加到 messages → 回到步骤3
       (round++, 超过5轮则返回 "请手动查询数据" 错误)
   无 tool_calls? → SSE 流式推送 content → 结束

5. 保存消息到数据库
```

### 5.4 Tool 定义

传给 LLM 的 tools 数组：

```json
[
  {
    "type": "function",
    "function": {
      "name": "get_kline",
      "description": "获取股票K线数据。返回OHLCV数组。用于分析趋势、形态、支撑阻力位。",
      "parameters": {
        "type": "object",
        "properties": {
          "code": {"type": "string", "description": "股票代码，如 sh.600519"},
          "period": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
          "start": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
          "end": {"type": "string", "description": "结束日期 YYYY-MM-DD"}
        },
        "required": ["code", "period", "start", "end"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_indicators",
      "description": "获取股票技术指标：MACD、RSI(14)、KDJ、BOLL(20)。用于分析买卖信号、超买超卖、趋势强度。",
      "parameters": {
        "type": "object",
        "properties": {
          "code": {"type": "string", "description": "股票代码"}
        },
        "required": ["code"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_financials",
      "description": "获取最新财务数据：营收、净利润、ROE、PE、PB、资产负债率、总资产等。用于基本面分析。",
      "parameters": {
        "type": "object",
        "properties": {
          "code": {"type": "string", "description": "股票代码"}
        },
        "required": ["code"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_realtime",
      "description": "获取最新行情：当前价格、涨跌幅、成交量。用于了解实时市场状态。",
      "parameters": {
        "type": "object",
        "properties": {
          "code": {"type": "string", "description": "股票代码"}
        },
        "required": ["code"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "search_stocks",
      "description": "搜索股票。当用户提及的股票不在关注列表时，用此工具查找股票代码。",
      "parameters": {
        "type": "object",
        "properties": {
          "keyword": {"type": "string", "description": "股票名称或代码关键词"}
        },
        "required": ["keyword"]
      }
    }
  }
]
```

### 5.5 Tool 执行

每个 tool 映射到已有的 `DataEngine` 方法：

| Tool Name | Handler |
|-----------|---------|
| `get_kline` | `engine.get_klines(code, period, start, end)` |
| `get_indicators` | `indicators.compute_all(code)` → 调 engine + 计算 |
| `get_financials` | `engine.get_financial(code)` |
| `get_realtime` | `engine.get_realtime(code)` |
| `search_stocks` | `engine.search(keyword)` |

### 5.6 LLM 配置

```python
# 在 config.py 中
class Settings:
    # 诊断专用 LLM 配置
    diagnosis_llm_provider: str = "deepseek"
    diagnosis_llm_model: str = "deepseek-v4-pro"
    diagnosis_llm_api_key: str = ""        # 从环境变量读取
    diagnosis_llm_base_url: str = ""       # 可选自定义 endpoint
    diagnosis_max_tool_rounds: int = 5
```

- 前端会话可选择 model（从配置的可用模型列表）
- API Key 优先使用 `DEEPSEEK_API_KEY` 环境变量

### 5.7 会话管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/diagnosis/chat` | 发送消息，SSE 流式返回 |
| GET | `/api/v1/diagnosis/sessions` | 历史会话列表 |
| GET | `/api/v1/diagnosis/sessions/{id}` | 获取会话详情+消息历史 |
| DELETE | `/api/v1/diagnosis/sessions/{id}` | 删除会话 |

---

## 六、技术指标计算引擎

### 6.1 接口

```
GET /api/v1/stock/{code}/indicators?period=daily&days=60

Response 200:
{
  "code": "sh.600519",
  "period": "daily",
  "data": [
    {
      "date": "2026-06-01",
      "macd": {"dif": 12.5, "dea": 10.2, "macd": 2.3},
      "rsi": {"rsi14": 62.3},
      "kdj": {"k": 65.2, "d": 58.1, "j": 79.4},
      "boll": {"upper": 1720.5, "mid": 1650.0, "lower": 1579.5}
    },
    ...
  ]
}
```

### 6.2 实现

纯函数，输入 pandas DataFrame / KlineBar 列表，输出指标数组。不依赖数据库。

```python
# indicators/macd.py
def compute_macd(klines: list[dict], fast=12, slow=26, signal=9) -> list[dict]:
    closes = [k["close"] for k in klines]
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    macd = [(d - e) * 2 for d, e in zip(dif, dea)]
    return [
        {"date": klines[i]["date"], "dif": dif[i], "dea": dea[i], "macd": macd[i]}
        for i in range(len(klines))
    ]
```

RSI、KDJ、BOLL 同理，各约30行代码。

---

## 七、前端设计

### 7.1 组件树与路由

```
<App>
  <AppProvider>              ← Context: stock, session, watchlist
    <SearchBar />            ← 顶部固定
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/stock/:code" element={<StockDetail />} />
    </Routes>
    <WatchlistSidebar />     ← 右侧抽屉
    <SkillManager />         ← 弹窗（按需打开）
  </AppProvider>
</App>
```

### 7.2 核心组件

**SearchBar** — 顶部搜索框
- 输入关键词 → 下拉菜单显示匹配股票
- 选择后导航到 `/stock/{code}`

**KlineChart** — lightweight-charts 实例
- 主图：K线蜡烛图 + MA 均线叠加
- 副图：成交量柱状图
- 指标切换：[MACD] [RSI] [KDJ] [BOLL] — 切换副图显示
- 时间周期：[日线] [周线] [月线]

**InfoCards** — 信息卡片区
- 基本信息卡片：最新价、涨跌幅、市值、PE、PB
- 技术指标卡片：MACD 信号、RSI 数值/超买超卖、KDJ、布林带位置
- 基本面卡片：ROE、营收增速、净利润率、负债率

**DiagnosisPanel** — AI 诊断对话面板
- 顶部工具栏：Skill 下拉 + Model 下拉 + 关注股票标签 + [历史会话]
- 消息列表：区分 user/assistant 气泡，assistant 消息支持流式渲染
- 输入区：多行文本 + 发送按钮
- 空状态：引导文字 + 快速提问按钮

**WatchlistSidebar** — 自选股抽屉
- 自选股列表（代码/名称/最新价/涨跌幅）
- 点击切换到该股
- [+添加] 按钮

**SkillManager** — 弹窗
- 表格：名称 | 描述 | 模式标签 | [预览] [删除]
- 底部 [导入 Skill] 按钮

### 7.3 状态管理

```typescript
// AppContext
{
  // 当前查看的股票
  currentStock: { code, name } | null

  // AI 诊断会话
  diagnosisSession: {
    id: string | null,
    skill: string,
    model: string,
    watchedStocks: {code, name}[],
    messages: Message[],
    loading: boolean,
  }

  // 自选股
  watchlist: {code, name, price?, changePct?}[]
}
```

### 7.4 SSE 流式对话

```typescript
// frontend/src/api/diagnosis.ts
export async function* chatStream(params: ChatParams): AsyncGenerator<string> {
  const response = await fetch('/api/v1/diagnosis/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.done) return;
        if (data.session_id) yield `__session__${data.session_id}`;
        yield data.content;
      }
    }
  }
}
```

---

## 八、API 端点汇总

### 已有（阶段1）

| 方法 | 路径 |
|------|------|
| GET | `/api/v1/search?q=` |
| GET | `/api/v1/stock/{code}/kline` |
| GET | `/api/v1/stock/{code}/realtime` |
| GET | `/api/v1/stock/{code}/financial` |
| GET | `/api/v1/market/index` |
| GET | `/api/v1/health` |

### 新增（阶段2）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/stock/{code}/indicators` | 技术指标计算 |
| POST | `/api/v1/diagnosis/chat` | AI诊断对话（SSE） |
| GET | `/api/v1/diagnosis/sessions` | 历史会话列表 |
| GET | `/api/v1/diagnosis/sessions/{id}` | 会话详情 |
| DELETE | `/api/v1/diagnosis/sessions/{id}` | 删除会话 |
| GET | `/api/v1/skills` | Skill 列表 |
| POST | `/api/v1/skills/upload` | 上传 Skill |
| DELETE | `/api/v1/skills/{name}` | 删除 Skill |
| GET | `/api/v1/skills/{name}` | Skill 内容 |
| GET | `/api/v1/watchlist` | 自选股列表 |
| POST | `/api/v1/watchlist` | 添加自选股 |
| DELETE | `/api/v1/watchlist/{code}` | 移除自选股 |

---

## 九、验收标准

- [ ] 前端可搜索股票 → 进入个股详情页
- [ ] K线图正常渲染，可切换日/周/月
- [ ] MA/MACD/RSI/KDJ/BOLL 指标可切换显示
- [ ] 基本面和技术面信息卡片显示正确
- [ ] Skill 管理：可上传 .md 文件 → 出现在下拉列表
- [ ] AI 诊断：选 Skill → 添加股票 → 发消息 → SSE 流式返回
- [ ] AI 可比对多只股票（Function Calling 按需查数据）
- [ ] 诊断会话可保存 → 历史列表可查看/继续/删除
- [ ] 自选股列表可增删，点击切换
- [ ] Tool-call 循环不超过 5 轮

---

## 十、风险与待定

| 风险 | 缓解 |
|------|------|
| LLM API 不可用 | 前端显示错误提示，不阻塞图表浏览 |
| Function Calling 结果不准确 | Tool 返回结构化数据，限制 token |
| SSE 连接中断 | 前端自动重连，显示连接状态 |
| lightweight-charts 数据量过大 | 限制前端渲染数据点（最多 500 条） |

---

> 下一步：审核后进入 writing-plans
