# AI 自然语言选股系统 - 设计文档

> 日期: 2026-07-19
> 状态: 已确认
> 架构方案: hermes 子进程 + skill 增强 + 现有选股引擎结合

## 1. 需求概述

用户用自然语言描述选股意图（如"找超跌反弹股，基本面要好"），AI 结合 skill 中的专业选股逻辑，自动调用后端 API 筛选股票，返回候选列表 + 入选理由。

核心价值：用户只需要模糊意图，AI 补充专业知识（来自 skill），组合出完整的筛选条件并执行。

## 2. 已确认的设计决策

| 决策项 | 选择 |
|--------|------|
| 交互方式 | 选股器 Tab 里加 AI 辅助输入框 |
| AI 执行方式 | hermes 子进程（原生支持 skill + curl 数据） |
| Skill 体系 | 混合：基模知识为基础，有 skill 就增强 |
| Skill 来源 | 基模自带 + 社区上传 + skill-creator 生成 |
| SSE 结构 | 复用诊断面板的结构化事件（type=analysis/log/status/done） |
| 嵌入位置 | 选股器 Tab 顶部，结果展开在下方 |

## 3. 数据流

```
用户输入 "找超跌反弹股"
    ↓
POST /api/v1/screener/ai-scan (SSE)
    ↓
后端构建 prompt:
  - 注入 skill 内容（如有）
  - 注入可用 API 端点说明
  - 注入用户意图
    ↓
hermes chat -q prompt (子进程)
    ↓
hermes 分析意图，curl 调用后端 API:
  1. GET /api/v1/screener/run?fields=... (用现有选股引擎筛)
  2. GET /api/v1/stock/{code}/kline (补充技术分析)
  3. GET /api/v1/stock/{code}/financial (补充基本面)
  4. GET /api/v1/intelligence/... (市场情绪数据)
    ↓
SSE 流式返回:
  - type=analysis: 分析过程 + 候选股票 + 入选理由
  - type=log: curl 命令（前端隐藏）
  - type=status: 状态更新
  - type=done: 结束
    ↓
前端展示:
  - 流式分析过程
  - 候选股票列表（代码/名称/现价/入选理由/一键加入自选）
```

## 4. 后端设计

### 4.1 新增 API 端点

`POST /api/v1/screener/ai-scan` - SSE 流式端点

请求体：
```python
class AIScanRequest(BaseModel):
    message: str               # 用户自然语言意图
    skill: str = ""            # skill 名称（空=不用 skill）
    use_skill: bool = True     # 是否注入 skill
    stock_codes: list[dict] = []  # 可选：限定范围
```

### 4.2 Prompt 构建

```python
skill_content = ""
if req.use_skill and req.skill:
    skill_content = _resolve_skill_content(req.skill)

prompt = f"""{skill_content}

你是 A 股选股 Agent。可以通过终端运行 curl 获取数据。后端运行在 localhost:8002。

## 可用数据 API (每次 curl 加 --max-time 15):
- 全市场快照: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/overview"
- 选股器: curl -s --max-time 15 "http://localhost:8002/api/v1/screener/run?fields=..." 
- K线: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/kline?period=daily&start=YYYY-MM-DD&end=YYYY-MM-DD"
- 实时: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/realtime"
- 财务: curl -s --max-time 15 "http://localhost:8002/api/v1/stock/<代码>/financial"
- 涨停池: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/limit-up"
- 龙虎榜: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/dragon-tiger"
- 热榜: curl -s --max-time 15 "http://localhost:8002/api/v1/intelligence/fund-flow"

## 选股器 API 参数说明:
fields 参数是 JSON，可用因子:
- change_pct: 涨跌幅(%)，如 {"min":-5} 表示跌超5%
- amount: 成交额(元)，如 {"min":100000000} 表示超1亿
- amplitude: 振幅(%)
- rsi_oversold: RSI超卖(boolean)
- macd_golden_cross: MACD金叉(boolean)
- boll_breakout: 布林突破(boolean)
- roe: ROE(%)，如 {"min":15}
- debt_ratio: 负债率(%)，如 {"max":50}
- near_high_drop: 距52周高点跌幅(%)，如 {"min":30}
- change_5d: 5日涨跌幅(%)
- change_20d: 20日涨跌幅(%)
- on_dragon_tiger: 龙虎榜上榜(boolean)
- hot_rank: 热榜排名

示例: curl -s "http://localhost:8002/api/v1/screener/run?fields=%7B%22rsi_oversold%22:true,%22near_high_drop%22:%7B%22min%22:30%7D%7D&limit=20"

## 规则:
1. 分析用户意图，确定需要哪些筛选因子
2. 如果有 skill，优先参考 skill 中的选股逻辑和阈值建议
3. 先用选股器 API 粗筛，再对结果逐个 curl 获取详细数据
4. 每只候选股票给出入选理由（技术面/基本面/消息面）
5. 返回 5-15 只候选股票，按推荐度排序
6. 不编造数据，curl 失败明确说明
7. 排除 ST 股、退市风险股

## 输出格式:
最终输出一个 Markdown 表格:
| 代码 | 名称 | 现价 | 涨跌幅 | 入选理由 |
然后给出整体分析和操作建议。

用户意图: {req.message}
"""
```

### 4.3 SSE 事件

复用诊断面板的结构化事件（`_classify_line` + `type=analysis/log/status/done`）。后端代码结构：

```python
@router.post("/ai-scan")
async def ai_scan(req: AIScanRequest):
    # 构建 prompt
    # 启动 hermes 子进程
    # SSE 流式返回（复用 diagnosis.py 的 _classify_line 逻辑）
    return StreamingResponse(event_stream(), ...)
```

## 5. 前端设计

### 5.1 选股器 Tab 改动

在现有 ScreenerView.tsx 顶部加一个 AI 选股区域：

```
┌─────────────────────────────────────────────────┐
│ 🔍 AI 选股                                       │
│ ┌─────────────────────────────────────────────┐ │
│ │ 输入选股意图，如"找超跌反弹股，基本面好"...    │ │
│ └─────────────────────────────────────────────┘ │
│ [SkillChip toggle]                    [开始选股] │
│                                                 │
│ (结果区域 - 流式展示)                            │
│ ┌─────────────────────────────────────────────┐ │
│ │ ## 选股分析                                  │ │
│ │ 根据您的意图，我从以下几个维度筛选...          │ │
│ │                                             │ │
│ │ | 代码 | 名称 | 现价 | 涨跌幅 | 入选理由 |    │ │
│ │ | sh.600519 | 贵州茅台 | 1750 | -2.1% | ... | │
│ │                                             │ │
│ │ ### 整体分析                                 │ │
│ │ 当前市场处于超卖区域...                       │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ (现有选股器: 因子选择 + 策略模板 + 结果列表)      │
└─────────────────────────────────────────────────┘
```

### 5.2 新增组件

- `AIScreenerPanel.tsx` - AI 选股输入 + 流式结果展示
- 复用 `SkillChip` 组件（toggle + dropdown）
- 复用 `chatStream` 函数（diagnosis.ts 里的 SSE 处理）

### 5.3 交互

1. 用户在输入框输入意图
2. 可选：通过 SkillChip 选择/开关选股 skill
3. 点击"开始选股"
4. 流式展示分析过程（Markdown 渲染）
5. 结果表格中的股票可一键加入自选

## 6. Skill 体系

### 6.1 基模自带选股 skill

项目内置 3 个选股 skill，放在 `backend/skills/` 目录：

1. `oversold-bounce.md` - 超跌反弹选股（RSI超卖+基本面排除垃圾股+成交额门槛）
2. `value-discovery.md` - 价值发现选股（低估值+高ROE+低负债+稳定增长）
3. `breakout-screener.md` - 技术突破选股（MACD金叉+量能放大+布林突破）

每个 skill 包含：
- 选股逻辑说明
- 建议因子和阈值
- 排除条件
- 分析框架

### 6.2 skill-creator 集成

已安装 skill-creator 到 Hermes 全局 skill 目录。用户可以：
- 在 AI 诊断面板里说"帮我创建一个选股 skill"
- skill-creator 引导用户描述策略
- 自动生成 SKILL.md + 测试用例
- 生成的 skill 可在选股器的 SkillChip 中选择使用

### 6.3 社区/上传

现有 SkillManager 已支持 .md 文件上传。用户可从网上下载选股 skill 上传。

## 7. 文件清单

```
backend/app/api/v1/screener.py     # MODIFY: 新增 /ai-scan 端点
backend/skills/                    # CREATE: 内置选股 skill
│   ├── oversold-bounce.md
│   ├── value-discovery.md
│   └── breakout-screener.md
frontend/src/components/AIScreenerPanel.tsx  # CREATE
frontend/src/components/ScreenerView.tsx    # MODIFY: 嵌入 AIScreenerPanel
frontend/src/api/screener.ts               # MODIFY: 新增 aiScan 函数
frontend/src/index.css                      # MODIFY: AI 选股区域样式
```

## 8. 实现顺序

1. 后端：`POST /screener/ai-scan` SSE 端点 + prompt 构建
2. 后端：3 个内置选股 skill 文件
3. 前端：`AIScreenerPanel.tsx` 组件
4. 前端：`ScreenerView.tsx` 嵌入 AI 面板
5. 前端：CSS 样式
6. 测试 + 验证

## 9. 测试策略

- 后端：AI scan 端点返回 SSE 流（mock hermes 子进程）
- 后端：prompt 包含 skill 内容（use_skill=true/false）
- 前端：tsc + build 通过
- 集成：手动测试（输入"找超跌反弹股"看是否返回候选列表）
