# 新闻特性重新设计

> 2026-07-05 | 诊断 agent 新闻工具 + 双市场数据源 + AI 摘要

## 0. 当前问题

原设计用 Hermes agent web_search 获取新闻,但实现被简化成了直接调 akshare API:
1. **诊断 agent 完全不知道新闻存在** — tools.py 无 get_news 工具,agent prompt 未列出新闻 API
2. **美股零支持** — us.* 代码直接返回"仅A股支持新闻获取"
3. **发布时不返回** — NewsArticle 丢弃了发布时间字段
4. **无 AI 摘要/情感分析** — 原始数据直接返回,无 relevance 过滤
5. **绕过 DataSourceProtocol** — 新闻抓取硬编码在 route handler 中
6. **stock_news 表永不过期** — scheduler 只清理 DailyKline

## 1. 目标

### 目标 A — 主界面展示
用户选股后,NewsPanel 展示当天个股相关最新进展:
- A 股: akshare.stock_news_em() → 东方财富实时新闻
- 美股: yfinance Ticker.news → Yahoo Finance 新闻
- 每条新闻包含: title, source, url, summary, published_at, **sentiment**

### 目标 B — 诊断分析支撑
诊断 agent 能调用新闻数据评估当天形势:
- `get_news` 工具返回最近新闻列表(含标题/摘要/情感)
- agent prompt 告知新闻 API 地址
- agent 可结合 K 线 + 指标 + 新闻做综合判断

## 2. 架构

```
datasources.fetch_news(code)
  ├─ akshare.AShareSource.fetch_news() → 东方财富 API
  └─ yfinance.USStockSource.fetch_news() → Yahoo Finance
       │
DataEngine.get_news(code) [cache-first via SQLite]
       ↓
GET /api/v1/news/stock/{code}      → 前端 NewsPanel 展示
       ↓
diagnosis tools: get_news(code)    → LLM 诊断分析调用
```

## 3. 数据模型

```python
@dataclass
class NewsArticle:
    title: str
    source: str
    url: str
    summary: str           # 原始摘要,最多 500 字
    published_at: str      # ISO 8601 时间戳
```

### DB 变更
stock_news 表增加 `published_at` 列(TEXT,可空):
```sql
ALTER TABLE stock_news ADD COLUMN published_at TEXT;
```

## 4. 协议扩展

`DataSourceProtocol` 新增:
```python
async def fetch_news(self, code: str, limit: int = 10) -> list[NewsArticle]: ...
```

实现:
- akshare: `akshare.stock_news_em(symbol)` → 提取列 → NewsArticle 列表
- yfinance: `yf.Ticker(symbol).news` → 映射 → NewsArticle 列表
- sample: 返回固定 3 条测试新闻,含不同情感

## 5. 诊断集成

### tools.py 新增 get_news 工具
```json
{
  "name": "get_news",
  "description": "获取股票最新财经新闻,含标题、摘要、来源、时间。用于分析近期事件影响、判断利好利空。",
  "parameters": {
    "code": {"type": "string", "description": "股票代码"},
    "limit": {"type": "integer", "description": "返回条数,默认5"}
  }
}
```

### diagnosis.py agent prompt 新增
```
- 新闻: curl -s --max-time 15 "http://localhost:8002/api/v1/news/stock/<代码>"
```

## 6. 前端增强

- 每条新闻显示发布时间 (相对时间:"2小时前")
- 添加 sentiment 标记(可选,通过 URL 参数 ?analyze=true 触发 AI 分析)
- 错误信息区分"A股/美股不支持"与"网络错误"

## 7. 数据库清理

scheduler.py cleanup_old_data() 增加 `DELETE FROM stock_news WHERE fetched_at < 30 days ago`

## 8. 验收

- [ ] 选 A 股后 NewsPanel 展示 5 条东方财富新闻,含发布时间
- [ ] 选美股后 NewsPanel 展示 yfinance 新闻
- [ ] 诊断 agent 能调用 get_news 获取新闻并综合分析
- [ ] agent prompt 包含新闻 API 地址
- [ ] scheduler 清理 30 天前的旧新闻
- [ ] akshare/yfinance/sample 三源均实现 fetch_news
- [ ] 刷新按钮有效(30 分钟内返回缓存,超时重新拉取)
- [ ] pytest 全部通过,前端 typecheck 通过
