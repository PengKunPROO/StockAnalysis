# Bug 修复计划 - 用同花顺 Financial-API 替代不可达的 eastmoney

> 2026-07-08 | 实测驱动 | 全部数据源已用有效 key 验证

## 实测诊断结论（5 bug 根因）

| Bug | 根因（实测确认） |
|---|---|
| 1 K线图消失 | fuyao historical kline **间歇超时**；前端请求 2 年范围触发慢拉取；`data_engine` 缓存范围校验过严（start 不匹配即不走缓存），网络超时后虽有 cached 兜底但无缓存的股票返回空 |
| 2 AI解读全无 | DeepSeek model `deepseek-v4-pro` 是**推理模型**，答案在 `delta.reasoning_content`、`content` 为空；SSE 只取 `content` -> 全空 |
| 3 选股器不可用 | 选股器全A快照**唯一源** `push2.eastmoney.com/api/qt/clist` 不可达（httpx+curl 均断连），akshare spot 同源不可达 |
| 4 市场情报不可用 | overview 广度/异动 + sectors 依赖 push2 clist 不可达 |
| 5 数据更新过慢 | fuyao historical 慢 + overview 串行多源 + 无缓存重复拉全A |

## 核心转向：同花顺 Financial-API 实测可达（替代 eastmoney）

**用有效 key 实测确认 fuyao.aicubes.cn 以下接口全部 code=0 返回真实数据：**

| 接口 | 路径 | 关键字段 | 用途 |
|---|---|---|---|
| 全市场分页快照 | `GET /api/a-share/prices/snapshot?limit=&offset=` | thscode/last_price/price_change_ratio_pct/volume/turnover/open/high/low | 选股器 Pass1 + 广度统计 |
| 涨停股票池 | `GET /api/a-share/special-data/limit-up-pool?page=&size=&sort_field=` | name/limit_up_time/limit_up_reason/continue_day_cnt/seal_money | 连板梯队 Tab |
| 连板天梯 | `GET /api/a-share/special-data/limit-up-ladder` | date/boards(30日矩阵) | 连板梯队 Tab |
| 龙虎榜 | `GET /api/a-share/special-data/dragon-tiger-list` | board_type/stock_items/hot_money_items(席位) | 龙虎榜 Tab |
| 异动列表 | `GET /api/a-share/special-data/anomaly-analysis-list` | stock_name/analysis_content/tag_name(实测531条) | 异动 Tab |
| 按股票异动 | `GET /api/a-share/special-data/anomaly-analysis-stock?thscodes=` | 批量(≤50) | 异动详情 |
| 热股榜 | `GET /api/a-share/special-data/hot-stock-list` | (参数 level 待查, code=1002) | 热度 |
| 标的列表 | `GET /api/meta/tickers/list?market=` | thscode/name/exchange | 选股 universe |
| 指数快照 | `GET /api/a-share-index/prices/snapshot?thscodes=` | last_price/change_pct | overview 指数卡 |
| 财务指标 | `GET /api/a-share/financials/indicators`（已有） | ROE/毛利率/负债率 | 选股 ROE |

**❌ 不可用**：`/api/a-share/valuations`（PE/PB 估值接口 404，文档标注"规划中未上线"）。-> 选股器 PE/PB 标"估值接口未上线"，ROE 仍可用。

**保留 eastmoney 的可达部分**：`kamt.kline`（北向资金，可达）。其余 eastmoney（push2 clist/push2ex/datacenter）全部替换为 fuyao。

## 修复方案（分阶段，每阶段测试看护）

### 阶段1：fuyao 客户端扩展 + 测试看护
- `backend/app/datasources/tonghuashun.py` 新增方法（或新建 `fuyao_client.py` 复用 `_get`）：`fetch_market_snapshot(limit,offset)`、`fetch_limit_up_pool(date)`、`fetch_limit_up_ladder()`、`fetch_dragon_tiger(date,board_type)`、`fetch_anomaly_list(tag)`、`fetch_anomaly_stock(thscodes)`、`fetch_hot_stock(level)`、`fetch_ticker_list(market)`。全部 try/except 降级。
- **测试看护**（用户重点要求）：`test_fuyao_endpoints.py` -- 每个方法 mock httpx 响应解析正确 + 降级返回空；加 `@pytest.mark.smoke` 真实调用测试（无 key 时 skip，可 `pytest -m smoke` 手动跑）。确认 `_get_json` 永不抛异常。

### 阶段2：选股器重写（fuyao snapshot）
- `screener/engine.py`：Pass1 改用 `fetch_market_snapshot` 分页拉全A（涨跌幅/换手/成交量/价格），PE/PB 字段 `available=False`（标注"估值接口未上线"），ROE 对幸存者（≤30）查 `fetch_financials`。
- 删除 `eastmoney.fetch_market_snapshot` 依赖。
- 测试：选股器用 mock fuyao snapshot 过滤通过；真实 smoke 测能返回结果。

### 阶段3：市场情报重写（6 Tab 全 fuyao）
- `intelligence.py` 重写：
  - overview：指数(fuyao index snapshot) + 广度(fuyao market snapshot 统计涨跌家数) + 情绪(limit-up-pool 算封板率/晋级率)
  - limit-up：`fetch_limit_up_pool` + `fetch_limit_up_ladder`（连板分桶）
  - dragon-tiger：`fetch_dragon_tiger`（含 hot_money 席位明细）
  - anomalies：`fetch_anomaly_list`（真实异动原因）
  - fund-flow：dragon-tiger 的 hot_money + snapshot 成交额排行（个股）+ 北向(eastmoney kamt 保留)
  - sectors：`fetch_index_snapshot`（沪深300等指数排行，替代行业板块；fuyao 无行业板块接口，诚实降级说明）
  - announcements：复用现有 news（akshare stock_news_em，已验证）+ corporate-actions
- 测试：每端点 mock fuyao 返回结构；smoke 测真实数据。

### 阶段4：K线 + AI + 性能
- **K线**：`data_engine.get_klines` 缓存兜底改为"网络失败时无条件返回已有缓存"（即使范围不全）；网络超时 20s→8s；前端 KlineChart 默认范围 2年→1年。
- **AI**：`signals.py` SSE 同时解析 `delta.content` 与 `delta.reasoning_content`，分别发 `type:'content'`/`type:'reasoning'`；前端 `streamSignalsAI` 把 reasoning 用浅色"思考"显示、content 正文（兼容 v4-pro，无需改 model）。
- **性能**：overview 用 `asyncio.gather` 并行；fuyao market snapshot 加 60s 内存缓存；各调用降超时到 8s。
- 测试：K线 mock 网络失败返回缓存；AI mock reasoning_content 解析；缓存命中测试。

### 阶段5：清理 + 全量验证
- `eastmoney.py` 精简：仅保留 `fetch_north_bound`（kamt 可达）；移除不可达的 clist/limit-up-pool/dragon-tiger/snapshot（已被 fuyao 替代）。
- 全量 `verify.sh` + **手动实测每个端点**（curl/TestClient 打真实数据）。
- 更新 AGENTS.md（数据源改为 fuyao 为主）。

## 测试看护原则（响应用户要求）
- 每个 fuyao 数据接口：mock 单元测试（解析+降级）+ smoke 真实测试（skipif 无 key）。
- 每个 API 端点：结构测试 + 降级路径测试。
- 纯计算已有覆盖（signals/atr/fib/screener 谓词）。
- 提交前：目标测试文件快速验证；阶段末：全量 verify + 手动实测。

## 提交粒度
阶段1 -> 2 -> 3 -> 4 -> 5，每阶段：实现 -> 测试 -> 实测 -> commit + push。

## 关键风险
- fuyao historical kline 间歇超时：阶段4 缓存兜底 + 降超时缓解；不可完全消除。
- hot-stock-list 参数（level）需实测确认。
- 板块轮动/资金流为降级实现（fuyao 无原生行业板块/资金流接口），UI 诚实标注。
