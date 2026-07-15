# AI 诊断聊天面板重新设计

> 日期: 2026-07-15
> 状态: 已确认
> 架构方案: 方案B - 后端结构化 SSE + 前端分区渲染

## 1. 需求概述

重新设计 DiagnosisPanel 组件，解决三个问题：
1. **Skill 每次注入**：追问时也注入整个 skill 内容，导致 hermes 回显 skill 原文。改为 toggle 开关，用户随时开关。
2. **Prompt 与回复混在同一个气泡**：改为标准聊天布局，用户消息右对齐、AI 回复左对齐，各自独立气泡。
3. **hermes 输出噪声**：skill 原文、启动日志、curl 命令混入 AI 回复。改为结构化 SSE，只渲染分析内容。

## 2. 已确认的设计决策

| 决策项 | 选择 |
|--------|------|
| Skill 控制 | Toggle 开关（chip 样式），随时开关 |
| 聊天布局 | 微信式：用户右对齐蓝色气泡，AI 左对齐表面色气泡 |
| hermes 输出过滤 | 只显示分析结果，skill 原文和日志不显示 |
| SSE 结构 | 方案B：结构化事件类型（log/analysis/status/done/error） |
| 嵌入位置 | 不变，仍嵌入在个股分析视图 K线下方 |
| UI 原型 | `docs/prototypes/diagnosis-chat-redesign.html` |

## 3. SSE 事件结构

当前 SSE 只有 `content` 和 `done` 两种事件。改为结构化：

```
data: {"type":"session","session_id":"xxx"}        // 会话开始
data: {"type":"status","status":"agent_starting"}  // 状态更新（显示在状态栏）
data: {"type":"log","content":"curl ..."}           // 日志类（前端隐藏）
data: {"type":"analysis","content":"## 技术分析\n"} // 分析内容（渲染到 AI 气泡）
data: {"type":"done"}                               // 结束
data: {"type":"error","content":"错误信息"}         // 错误
```

### 3.1 后端行分类逻辑 (`_classify_line`)

在 `diagnosis.py` 中新增 `_classify_line(line: str) -> tuple[str, str | None]`，返回 `(event_type, content)`：

| 分类 | 匹配规则 | 前端处理 |
|------|---------|---------|
| `log` | `curl` 命令、文件路径（`/` 或 `\` 开头）、配置内容（`Remote:`、`Project root:`）、skill 原文回显（`###` 纯英文标题、```` 代码块）、`import`/`pip`/`npm` 命令 | 不渲染到气泡，可选项：状态栏显示"获取数据中..." |
| `analysis` | 包含中文、Markdown 标题（`#` 中文标题）、表格（`|`）、列表（`-`）、数字+百分比+元、分析性结论 | 渲染到 AI 气泡，Markdown 格式 |
| `status` | `fetching_data` 等状态标记 | 显示在状态栏 |
| `skip` | 空行、ANSI 码、hermes 框架输出（`Session:`、`Duration:`、`Messages:`、`┊`） | 丢弃 |

分类优先级：先匹配 `skip`（丢弃），再匹配 `log`（日志），剩余的作为 `analysis`。

### 3.2 Skill 注入逻辑

```python
if req.use_skill and req.skill:
    skill_content = _resolve_skill_content(req.skill)
    prompt = f"{skill_content}\n\n你是股票分析 Agent..."
else:
    prompt = f"你是股票分析 Agent。可以通过终端运行 curl 获取数据..."
```

新增 `use_skill: bool = True` 字段到 `ChatRequest`。前端 toggle 开 = `use_skill=True`，关 = `use_skill=False`。

## 4. 前端组件设计

### 4.1 DiagnosisPanel.tsx 重构

组件结构：

```
DiagnosisPanel
├── chat-header
│   ├── title: "🧠 AI 诊断分析"
│   ├── spacer
│   ├── SkillChip (toggle + dropdown)
│   └── settings button (⚙)
├── chat-messages
│   ├── MsgBubble (user, right-aligned)
│   ├── MsgBubble (ai, left-aligned, markdown)
│   ├── MsgSystem (centered, muted)
│   └── streaming bubble (during AI response)
├── chat-status (loading indicator)
└── chat-input (auto-resize textarea + send)
```

### 4.2 SkillChip 组件

替换原来的 SkillPicker 组件：

- **chip 外观**：圆角胶囊（`border-radius: 20px`），包含发光圆点 + skill 名称 + 下拉箭头
- **active 状态**：青色边框 + 青色发光圆点 + accent-glow 背景
- **inactive 状态**：灰色边框 + 灰色圆点 + surface2 背景
- **点击 chip 整体**：切换 active/inactive（开/关 skill 注入）
- **点击名称或箭头**：打开下拉选择器
- **下拉选择器**：带搜索框、圆角阴影、淡入动画、选中项左侧青色竖线

### 4.3 消息气泡

- **用户消息**：`align-self: flex-end`，背景 `--user-msg`（蓝色），右下角小圆角
- **AI 消息**：`align-self: flex-start`，背景 `--ai-msg`（表面色），左下角小圆角，Markdown 渲染
- **系统消息**：居中，灰色小字（如"已切换至 xxx"）
- **流式输出**：AI 回复期间显示一个临时气泡，内容实时追加

### 4.4 SSE 事件处理 (diagnosis.ts)

```typescript
export async function chatStream(params: ChatParams, events: ChatEvents) {
  const res = await fetch('/api/v1/diagnosis/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...params, use_skill: params.use_skill }),
  })
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          switch (data.type) {
            case 'session': events.onSessionId?.(data.session_id); break
            case 'status': events.onStatus?.(data.status); break
            case 'analysis': events.onContent?.(data.content); break
            case 'log': events.onLog?.(data.content); break
            case 'error': events.onError?.(data.content); break
            case 'done': events.onDone?.(); break
          }
        } catch {}
      }
    }
  }
}
```

关键变化：
- 只渲染 `type=analysis` 的内容到 AI 气泡
- `type=log` 不渲染到气泡（可选：状态栏显示"获取数据中..."）
- `type=status` 显示在状态栏

### 4.5 ChatParams 扩展

```typescript
interface ChatParams {
  session_id?: string
  skill: string
  use_skill: boolean  // 新增：是否注入 skill 内容
  message: string
  stock_codes: { code: string; name: string }[]
}
```

## 5. 后端改动

### 5.1 ChatRequest 扩展

```python
class ChatRequest(BaseModel):
    session_id: str | None = None
    skill: str = "stock-analysis"
    use_skill: bool = True  # 新增
    message: str
    stock_codes: list[dict] | None = None
```

### 5.2 Prompt 构建

根据 `use_skill` 决定是否注入 skill 内容：

```python
skill_content = ""
if req.use_skill and req.skill:
    skill_content = _resolve_skill_content(req.skill)

prompt = f"""{skill_content}

你是股票分析 Agent。可以通过终端运行 curl 获取数据。后端运行在 localhost:8002。
...
"""
```

### 5.3 SSE 事件分类

在 `event_stream()` 中，替换当前的 `_filter_line` + 直接 yield，改为 `_classify_line` + 按类型 yield：

```python
event_type, content = _classify_line(line)
if event_type == "skip":
    continue
elif event_type == "log":
    yield f'data: {json.dumps({"type":"log","content":content}, ensure_ascii=False)}\n\n'
elif event_type == "analysis":
    full_output += content + "\n"
    yield f'data: {json.dumps({"type":"analysis","content":content}, ensure_ascii=False)}\n\n'
```

### 5.4 `_classify_line` 函数

```python
import re

LOG_PATTERNS = [
    r'^curl\s',
    r'^Remote:',
    r'^Project root:',
    r'^import\s',
    r'^pip\s',
    r'^npm\s',
    r'^```',  # code blocks
    r'^\|.*\|$',  # skip raw table headers from skill echo (but keep analysis tables)
    r'^[A-Z][a-z]+:',  # "Key:" "Value:" style config
]

SKIP_PATTERNS = [
    r'^Query:',
    r'^Initializing agent',
    r'^[─╭╰═╮╯]+',
    r'^Resume this session',
    r'^Session:',
    r'^Duration:',
    r'^Messages:',
    r'^name:',
    r'^description:',
    r'^mode:',
    r'^---',
    r'^hermes --resume',
    r'^\s*┊\s',
    r'^\s*$',
]

def _classify_line(line: str) -> tuple[str, str | None]:
    clean = ANSI_RE.sub('', line).rstrip('\n')
    # Skip
    for pat in SKIP_PATTERNS:
        if re.match(pat, clean):
            return "skip", None
    # Log
    for pat in LOG_PATTERNS:
        if re.match(pat, clean):
            return "log", clean
    # Everything else is analysis
    if clean:
        return "analysis", clean
    return "skip", None
```

## 6. 测试策略

### 6.1 后端测试

- `_classify_line` 单元测试：验证各种行被正确分类
- `use_skill=False` 时不注入 skill 内容
- SSE 事件包含 `type` 字段
- 保持现有测试兼容（ChatRequest 新增字段有默认值）

### 6.2 前端验证

- `tsc --noEmit` 通过
- `npm run build` 通过
- 手动验证：skill toggle 开关、消息气泡区分、流式输出只显示分析内容

## 7. 文件清单

```
backend/app/api/v1/diagnosis.py      # MODIFY: ChatRequest + _classify_line + SSE
frontend/src/api/diagnosis.ts         # MODIFY: chatStream 事件处理
frontend/src/components/DiagnosisPanel.tsx  # REWRITE: 聊天 UI + SkillChip
frontend/src/index.css                # MODIFY: skill-chip 样式
docs/prototypes/diagnosis-chat-redesign.html  # 已有原型
```

## 8. 实现顺序

1. 后端：`_classify_line` + `ChatRequest.use_skill` + SSE 事件分类
2. 前端：`diagnosis.ts` chatStream 适配新事件结构
3. 前端：`DiagnosisPanel.tsx` 重写（SkillChip + 聊天气泡 + 流式渲染）
4. 前端：`index.css` skill-chip 样式
5. 测试 + 验证
