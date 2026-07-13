# 选股器重构设计规格

> 2026-07-14 | 选股器 v2 | 因子体系 + 策略模板 + 数据校验 + 消息面 + 自定义因子

## 问题

当前选股器：
- 可用因子仅6个，PE/PB/换手率/市值/行业标记"暂不可用"但仍显示在UI
- 4个预设策略中行业轮动是空壳
- 没有因子说明，用户不知道每个因子含义
- 没有数据校验，选出的股是否符合条件无法确认
- 没有消息面因子（龙虎榜/热榜/资金流/新闻）

## 设计方案

### 数据源策略
- Pass1 快照层：同花顺 prices/snapshot（全量5000条，快且稳）
- Pass2 逐个查层：东财 push2 stock/get（PE/PB/换手率/市值）+ 同花顺 financials（ROE/负债率）+ K线计算（技术指标）
- Pass2 消息面层：同花顺 dragon-tiger/hot-stock + 东财资金流

### 因子体系（20+可用因子）

#### 快照因子（Pass1，同花顺全市场快照）
| name | label | type | 说明 |
|------|-------|------|------|
| change_pct | 涨跌幅 | number_range | 当日涨跌幅% |
| amount | 成交额 | number_range | 当日成交额（元）|
| amplitude | 振幅 | number_range | (最高-最低)/昨收*100 |
| open | 开盘价 | number_range | |
| high | 最高价 | number_range | |
| low | 最低价 | number_range | |

#### 估值因子（Pass2，东财 push2 stock/get）
**状态：东财 push2 端点不可达（服务器断连），标记为不可用，前端灰显**
| name | label | type | 说明 |
|------|-------|------|------|
| pe_ttm | 市盈率(TTM) | number_range | 股价/每股收益(TTM)，available=false |
| pb | 市净率 | number_range | 股价/每股净资产，available=false |
| total_mv | 总市值 | number_range | 单位：元，available=false |
| turnover_rate | 换手率 | number_range | 成交量/流通股本*100，available=false |

#### 财务因子（Pass2，同花顺 financials）
| name | label | type | 说明 |
|------|-------|------|------|
| roe | ROE | number_range | 净资产收益率% |
| debt_ratio | 资产负债率 | number_range | 总负债/总资产*100 |

#### 技术因子（Pass2，K线计算）
| name | label | type | 说明 |
|------|-------|------|------|
| macd_golden_cross | MACD金叉 | boolean | DIF上穿DEA |
| rsi_oversold | RSI超卖 | boolean | RSI<30 |
| boll_breakout | BOLL突破上轨 | boolean | 收盘价突破布林上轨 |
| kdj_golden_cross | KDJ金叉 | boolean | K上穿D |
| near_high_drop | 距52周高点跌幅 | number_range | (52周高-现价)/52周高*100 |
| change_5d | 近5日涨跌幅 | number_range | 5日累计涨跌幅% |
| change_20d | 近20日涨跌幅 | number_range | 20日累计涨跌幅% |

#### 消息面因子（Pass2）
| name | label | type | 说明 |
|------|-------|------|------|
| on_dragon_tiger | 龙虎榜上榜 | boolean | 近3日是否上龙虎榜 |
| hot_rank | 热榜排名 | number_range | 同花顺热股榜排名 |
| main_net_flow | 主力净流入 | number_range | 东财个股资金流近5日净流入 |

### 6个策略模板

1. **短线超跌反弹**：RSI超卖 + 距52周高点跌幅>30% + 成交额>1亿
2. **烟蒂股**：PB<1.5（不可用，标记）+ ROE>8% + 负债率<60% -> 调整为：ROE>8% + 负债率<60% + 涨幅<2%
3. **长线价值**：ROE>15% + PE<25（不可用）+ PB<3（不可用）-> 调整为：ROE>15% + 负债率<50%
4. **技术转强**：MACD金叉 + RSI<50 + 成交额>2亿
5. **消息面驱动**：龙虎榜上榜 + 主力净流入>0
6. **强势突破**：涨幅>3% + 振幅>5% + 成交额>3亿 + BOLL突破上轨

### 因子说明
每个 FilterField 增加 `description` 字段，前端 tooltip 悬停显示。

### 数据校验
结果表格每行可展开，显示所有因子的实际值 vs 筛选阈值，绿✓/红✗标记是否达标。

### 自定义派生因子
**状态：跳过（依赖估值因子 PE/PB，而东财 push2 不可达）。未来估值因子就位后再实现。**

### 架构

```
FilterField (BaseModel)
  ├── name, label, type, category, unit, constraints, available
  ├── description (新增, tooltip说明)
  ├── source (新增, 数据来源标识)
  └── pass_phase (新增, 1=快照 2=逐个查)

ScreenerEngine
  ├── Pass1: 同花顺快照过滤 (快照因子)
  ├── Pass2a: 东财push2批量估值 (估值因子)
  ├── Pass2b: 同花顺财务 (财务因子)
  ├── Pass2c: K线计算 (技术因子)
  ├── Pass2d: 消息面查询 (消息面因子)
  └── Pass2e: 派生因子计算 (自定义因子)

StrategyRegistry
  ├── 内置6个策略
  └── 用户可自定义 (localStorage保存)

API
  GET /screener/fields          -> 因子列表(含description)
  GET /screener/skills          -> 策略列表
  POST /screener/run            -> 执行筛选, 返回结果+因子明细
```

### 东财 push2 stock/get 端点
```
GET https://push2.eastmoney.com/api/qt/stock/get
params: secid=1.600519 (沪) / 0.000001 (深)
        fields=f2,f3,f8,f9,f12,f14,f20,f23,f57,f58
f2=最新价, f8=换手率, f9=PE(TTM), f23=PB, f20=总市值
```

### Pass2 上限提升
当前Pass2上限30只，改为50只（东财push2单只查询快，可批量并发）。
