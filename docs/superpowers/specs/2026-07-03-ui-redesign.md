# UI 3.0 设计 — ChatGPT 风格 + Agent 数据获取

> 2026-07-03 | 浅色 TradingView 专业风 | shadcn/ui + Tailwind

## 1. 架构

```
┌─────────────────────────────────────────────────────────┐
│ TopBar: [☰] [搜索框              ] [⚙Skill] [🌙]      │
├──────────┬──────────────────────────────────────────────┤
│ Sidebar  │  PriceHeader: 名称 代码 ¥价 +涨跌幅%        │
│ (Sheet   │  ┌──────────────────────────────────────┐   │
│  折叠)   │  │    K线图 (lightweight-charts)         │   │
│          │  │    成交量副图                          │   │
│ 自选列表 │  └──────────────────────────────────────┘   │
│          │  IndicatorCards 横排: VOL | MACD | RSI |.. │
│          │  ────────────────────────────────────────   │
│          │  Chat Messages (左对齐, Markdown渲染)       │
│          │  ┌ ChatInput: [Skill▼] [____] [发送] ──┐   │
└──────────┴──────────────────────────────────────────────┘
```

- **TopBar**: 汉堡菜单(切侧栏) + 搜索 + Skill管理按钮
- **Sidebar**: shadcn Sheet 组件，可折叠，自选股列表
- **Chart**: 全宽 lightweight-charts，自适应高度
- **Cards**: Grid 横排信息卡，自适应列数
- **Chat**: 左对齐气泡，完整 Markdown 渲染(表格/粗体/标题/列表)
- **Input**: Skill 选择器 + 输入框 + 发送按钮

## 2. Agent 数据获取

不再预注入数据，改为告诉 Hermes 有哪些 curl 端点可用：

```
prompt = f'''
{skill_content}

你是股票分析Agent。可以通过终端运行 curl 获取数据：

搜索: curl -s "http://localhost:8002/api/v1/search?q=<关键词>"
K线:   curl -s "http://localhost:8002/api/v1/stock/<sh.600519>/kline?period=daily&start=2026-01-01&end=2026-07-03"
实时:  curl -s "http://localhost:8002/api/v1/stock/<sh.600519>/realtime"
财务:  curl -s "http://localhost:8002/api/v1/stock/<sh.600519>/financial"
指标:  curl -s "http://localhost:8002/api/v1/stock/<sh.600519>/indicators?days=60"

规则:
1. 需要数据时主动 curl，不要猜测
2. 股票代码格式: sh.600519, sz.000001
3. 数据返回 JSON，提取字段后分析
4. 分析完用 Markdown 表格呈现关键指标

用户问题: {message}
股票: {stock_list}
'''
```

**数据流:**
```
Hermes agent
  └─ terminal: curl localhost:8002/api/v1/...
       └─ data_engine.py
            ├─ DB cache hit → 直接返回
            └─ cache miss → Tonghuashun API → 写DB → 返回
```

## 3. 技术栈

| 层 | 技术 |
|----|------|
| 框架 | React 18 + TypeScript |
| 组件 | shadcn/ui (Card, Input, Select, Button, ScrollArea, Sheet, Separator) |
| 样式 | Tailwind CSS v4 + CSS Variables 主题 |
| 图表 | lightweight-charts v5 |
| 状态 | React Context + useReducer + localStorage |

## 4. 配色 Token

```css
--background: #f5f5f5;
--foreground: #1a1a2e;
--card: #ffffff;
--card-foreground: #1a1a2e;
--border: #e0e0e0;
--muted: #6b7280;
--accent: #2962ff;
--up: #089981;
--down: #f23645;
--sidebar: #fafafa;
--chat-user: #2962ff;
--chat-ai: #ffffff;
```

## 5. 关键交互

- **搜索**: 顶部输入，实时下拉结果，点击选股 → 自动加入自选
- **自选栏**: 点击股票切换，右侧 Sheet 可折叠
- **指标卡**: 横排 grid，宽屏时自动增加列数
- **聊天**: 左对齐流式输出，Markdown 实时渲染，自动滚动到底部
- **Skill**: 齿轮按钮 → Modal 管理（上传/删除/预览）
- **所有按钮**: hover tooltip 说明功能

## 6. 移除项

- ~~Prompt/Query 回显在聊天中~~ — 后端过滤 `Query:` 行
- ~~ANSI 转义码~~ — 后端 `ANSI_RE` 正则过滤
- ~~中间对齐~~ — 所有消息左对齐
- ~~max-width: 1126px~~ — 100vw 全宽

## 7. 验收

- [ ] 搜索股票 → K线+指标卡正确展示
- [ ] AI 对话 → 流式 Markdown + 表格完美渲染
- [ ] 多个 Skill 可选择、上传、删除
- [ ] 刷新页面 → 状态保持(localStorage)
- [ ] 2K 屏幕 → 全宽无空白
- [ ] 移动端 → 侧栏自动隐藏
