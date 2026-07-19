"""Declarative screener field definitions (OCP - add a field here, it appears in UI).

Factor availability based on 同花顺 Financial-API + eastmoney.py capabilities:
- Pass1 (全市场快照过滤): change_pct, amount, amplitude, open, high, low
  amplitude computed from (high-low)/prev_close*100
- Pass2 (幸存者逐个查):
  - Financials (同花顺): roe, debt_ratio
  - Technical (K线计算): macd_golden_cross, rsi_oversold, boll_breakout,
    kdj_golden_cross, near_high_drop, change_5d, change_20d
  - News (同花顺龙虎榜/热榜): on_dragon_tiger, hot_rank
"""
from typing import Literal
from pydantic import BaseModel


class FilterField(BaseModel):
    name: str
    label: str
    type: Literal["number_range", "boolean", "choice"]
    category: Literal["基本面", "技术信号", "行情表现", "消息面"]
    unit: str = ""
    constraints: dict = {}
    available: bool = True
    description: str = ""
    source: str = ""
    pass_phase: int = 1


FIELDS: list[FilterField] = [
    # ── 行情表现 - Pass1 快照过滤（同花顺 snapshot 可用）──────────────────────
    FilterField(name="change_pct", label="涨跌幅", type="number_range",
                category="行情表现", unit="%",
                constraints={"min": -20, "max": 20, "step": 0.5},
                description="当日涨跌幅%。正数上涨、负数下跌。短线选股常用。",
                source="同花顺 snapshot", pass_phase=1),
    FilterField(name="amount", label="成交额", type="number_range",
                category="行情表现", unit="元",
                constraints={"min": 0, "max": 10000000000, "step": 1, "direction": "gte"},
                description="当日成交额（元）。1亿=100000000。衡量交投活跃度，低于5000万通常流动性差。",
                source="同花顺 snapshot", pass_phase=1),
    FilterField(name="amplitude", label="振幅", type="number_range",
                category="行情表现", unit="%",
                constraints={"min": 0, "max": 20, "step": 0.5},
                description="(最高价-最低价)/昨收价*100。衡量当日波动幅度，>5%为活跃。",
                source="同花顺 snapshot (computed)", pass_phase=1),

    # ── 基本面 - 财务因子（Pass2，同花顺 financials）────────────────────────────
    FilterField(name="roe", label="ROE", type="number_range",
                category="基本面", unit="%",
                constraints={"min": 0, "max": 100, "step": 1},
                description="净资产收益率%。净利润/股东权益*100。>15%为优秀，>20%为卓越。",
                source="同花顺 financials", pass_phase=2),
    FilterField(name="debt_ratio", label="资产负债率", type="number_range",
                category="基本面", unit="%",
                constraints={"min": 0, "max": 100, "step": 1},
                description="总负债/总资产*100。<60%为安全，金融行业除外。",
                source="同花顺 financials", pass_phase=2),

    # ── 技术信号 - Pass2 K线计算因子 ──────────────────────────────────────────
    FilterField(name="macd_golden_cross", label="MACD金叉", type="boolean",
                category="技术信号",
                description="DIF线上穿DEA线，看涨信号。配合成交量放大更有效。",
                source="K线计算 (indicators)", pass_phase=2),
    FilterField(name="rsi_oversold", label="RSI超卖", type="boolean",
                category="技术信号",
                description="RSI<30，超卖可能反弹。<20为极度超卖。",
                source="K线计算 (indicators)", pass_phase=2),
    FilterField(name="boll_breakout", label="BOLL突破上轨", type="boolean",
                category="技术信号",
                description="收盘价突破布林带上轨，强势突破信号。",
                source="K线计算 (indicators)", pass_phase=2),
    FilterField(name="kdj_golden_cross", label="KDJ金叉", type="boolean",
                category="技术信号",
                description="K线上穿D线，短线看涨信号。低位金叉更可靠。",
                source="K线计算 (indicators)", pass_phase=2),
    FilterField(name="near_high_drop", label="距52周高点跌幅", type="number_range",
                category="技术信号", unit="%",
                constraints={"min": 0, "max": 100, "step": 1},
                description="(52周最高价-现价)/52周最高价*100。>30%为深度回调，可能超跌。",
                source="K线计算 (indicators)", pass_phase=2),
    FilterField(name="change_5d", label="近5日涨跌幅", type="number_range",
                category="技术信号", unit="%",
                constraints={"min": -50, "max": 50, "step": 0.5},
                description="近5个交易日累计涨跌幅%。短线趋势参考。",
                source="K线计算 (indicators)", pass_phase=2),
    FilterField(name="change_20d", label="近20日涨跌幅", type="number_range",
                category="技术信号", unit="%",
                constraints={"min": -100, "max": 100, "step": 1},
                description="近20个交易日累计涨跌幅%。中线趋势参考。",
                source="K线计算 (indicators)", pass_phase=2),

    # ── 消息面 - Pass2 因子（同花顺龙虎榜/热榜）───────────────────────────────
    FilterField(name="on_dragon_tiger", label="龙虎榜上榜", type="boolean",
                category="消息面",
                description="当日是否上榜龙虎榜。游资/机构活跃信号，需盘后才有数据。",
                source="同花顺 dragon-tiger", pass_phase=2),
    FilterField(name="hot_rank", label="热榜排名", type="number_range",
                category="消息面", unit="名",
                constraints={"min": 1, "max": 1000, "step": 1, "direction": "lte"},
                description="同花顺热股榜排名。越小越热门，<100为高热度。",
                source="同花顺 hot-stock", pass_phase=2),
]

FIELD_BY_NAME = {f.name: f for f in FIELDS}

# Pass1: fuyao 全市场 snapshot 直接可过滤的字段
SNAPSHOT_FIELDS = {"change_pct", "amount", "amplitude"}
# Pass2: 需逐个查的字段 (financials + technical + news)
PASS2_FIELDS = {
    # financial
    "roe", "debt_ratio",
    # technical
    "macd_golden_cross", "rsi_oversold", "boll_breakout", "kdj_golden_cross",
    "near_high_drop", "change_5d", "change_20d",
    # news
    "on_dragon_tiger", "hot_rank",
}
TECH_FIELDS = {
    "macd_golden_cross", "rsi_oversold", "boll_breakout", "kdj_golden_cross",
    "near_high_drop", "change_5d", "change_20d",
}
NEWS_FIELDS = {"on_dragon_tiger", "hot_rank"}
SORTABLE = ["change_pct", "amount", "amplitude", "roe", "debt_ratio",
            "near_high_drop", "change_5d", "change_20d", "hot_rank"]


def get_fields() -> list[FilterField]:
    return FIELDS


def matches_snapshot(stock: dict, values: dict) -> bool:
    """Check a stock against Pass1 snapshot-derivable field filters."""
    for name, val in values.items():
        if name not in SNAPSHOT_FIELDS:
            continue
        field = FIELD_BY_NAME.get(name)
        if not field or not field.available:
            continue
        raw = stock.get(name)
        if raw is None:
            continue
        scale = field.constraints.get("scale", 1)
        v = raw * scale
        mn = val.get("min")
        mx = val.get("max")
        if mn is not None and v < mn:
            return False
        if mx is not None and v > mx:
            return False
    return True
