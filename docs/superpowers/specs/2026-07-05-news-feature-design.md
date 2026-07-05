# 新闻分析特性设计

> 2026-07-05 | Hermes agent web_search | 内联影响分析

## 1. 目标

展示个股相关财经新闻，并提供 AI 影响分析。新闻每天更新，分析点击即得。

## 2. 架构

```
用户选股 → 后端调 Hermes agent web_search → 缓存新闻(当天有效)
  ↓
前端 NewsPanel 展示标题列表
  ↓
用户点击某条新闻 → 后端调 Hermes agent 分析影响 → 内联展开显示
```

## 3. 数据流

```
GET /api/v1/stock/{code}/news
  → 检查 DB 缓存 (今天的数据？)
    ├─ 有 → 直接返回
    └─ 无 → spawn Hermes agent:
         hermes chat -q "搜索 {股票名} 最近3天的重要财经新闻，返回JSON列表"
         → agent 使用 web_search → 返回新闻列表
         → 解析 JSON → 存入 DB → 返回

POST /api/v1/stock/{code}/news/analyze
  body: {title, source, content}
  → spawn Hermes agent:
       "分析这条新闻对 {股票名} 股价的影响：{title}。结合当前技术面和基本面数据。"
  → SSE 流式返回分析结果
```

## 4. 数据库

```sql
CREATE TABLE stock_news (
  id INTEGER PRIMARY KEY,
  stock_code TEXT NOT NULL,
  title TEXT NOT NULL,
  source TEXT,
  url TEXT,
  summary TEXT,
  fetched_at DATE NOT NULL,
  UNIQUE(stock_code, title, fetched_at)
);
```

每天每股票自动清理旧数据，只保留当天。

## 5. 前端组件

### NewsPanel.tsx
- 位置：K线图下方，指标卡片下方
- 高度：`max-height: 200px`，可滚动
- 每行：标题(截断) + 来源 + 日期 + [分析→] 按钮
- 点击 [分析→]：该行展开，显示加载动画 → SSE 流式分析结果
- [刷新] 按钮：强制重新搜索新闻

### CSS
```css
.news-panel {
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding: 8px 12px;
  max-height: 200px;
  overflow-y: auto;
}
.news-item {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; border-bottom: 1px solid var(--border);
  font-size: 12px; cursor: pointer;
}
.news-item:hover { color: var(--accent); }
.news-analysis {
  padding: 8px 12px; background: rgba(0,229,255,0.05);
  font-size: 12px; border-left: 2px solid var(--accent);
  margin: 4px 0 8px 12px;
}
```

## 6. Agent Prompt 增强

聊天 prompt 增加：
```
## 新闻分析能力
当用户询问新闻相关问题时，使用 web_search 搜索最新财经新闻：
- 搜索 "{股票名} 最新新闻 财经"
- 分析新闻对股价的潜在影响
- 区分短期情绪影响 vs 基本面影响
```

## 7. 验收

- [ ] 选股后新闻面板展示最新财经新闻
- [ ] 点击新闻展开内联 AI 影响分析
- [ ] [刷新] 按钮重新搜索
- [ ] 同一天不重复请求 API
- [ ] 跨天自动清理旧新闻
