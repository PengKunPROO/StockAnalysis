"""Declarative screener field definitions (OCP - add a field here, it appears in UI).

字段可用性基于同花顺 Financial-API 实测能力：
- Pass1 (全市场快照过滤): change_pct, amount - fuyao prices/snapshot 全市场模式
- Pass2 (幸存者逐个查): roe (financials), macd_golden_cross/rsi_oversold/boll_breakout (indicators)
- 不可用: pe_ttm/pb/total_market_cap (估值接口未上线), turnover/amplitude (snapshot无此字段), industry (无行业接口)
"""
from typing import Literal
from pydantic import BaseModel


class FilterField(BaseModel):
    name: str
    label: str
    type: Literal["number_range", "boolean", "choice"]
    category: Literal["基本面", "技术信号", "行情表现", "行业概念"]
    unit: str = ""
    constraints: dict = {}
    available: bool = True


FIELDS: list[FilterField] = [
    # 行情表现 - Pass1 快照过滤（fuyao snapshot 可用）
    FilterField(name="change_pct", label="涨跌幅", type="number_range", category="行情表现",
                unit="%", constraints={"min": -20, "max": 20, "step": 0.5}),
    FilterField(name="amount", label="成交额", type="number_range", category="行情表现",
                constraints={"min": 0, "max": 100000, "step": 1, "direction": "gte"}),
    # 基本面 - Pass2 逐个查
    FilterField(name="roe", label="ROE", type="number_range", category="基本面",
                unit="%", constraints={"min": 0, "max": 100, "step": 1, "direction": "gte"}),
    # 技术信号 - Pass2 计算
    FilterField(name="macd_golden_cross", label="MACD金叉", type="boolean", category="技术信号"),
    FilterField(name="rsi_oversold", label="RSI超卖", type="boolean", category="技术信号"),
    FilterField(name="boll_breakout", label="BOLL突破上轨", type="boolean", category="技术信号"),
    # 不可用 - 同花顺暂未提供
    FilterField(name="pe_ttm", label="市盈率(TTM)", type="number_range", category="基本面",
                constraints={"min": 0, "max": 200, "step": 1}, available=False),
    FilterField(name="pb", label="市净率", type="number_range", category="基本面",
                constraints={"min": 0, "max": 50, "step": 0.5}, available=False),
    FilterField(name="total_market_cap", label="总市值", type="number_range", category="基本面",
                unit="亿", constraints={"min": 0, "max": 100000, "step": 50}, available=False),
    FilterField(name="turnover", label="换手率", type="number_range", category="行情表现",
                unit="%", constraints={"min": 0, "max": 50, "step": 1}, available=False),
    FilterField(name="amplitude", label="振幅", type="number_range", category="行情表现",
                unit="%", constraints={"min": 0, "max": 20, "step": 0.5}, available=False),
    FilterField(name="industry", label="行业", type="choice", category="行业概念",
                constraints={"options": []}, available=False),
]

FIELD_BY_NAME = {f.name: f for f in FIELDS}

# Pass1: fuyao 全市场 snapshot 直接可过滤的字段
SNAPSHOT_FIELDS = {"change_pct", "amount"}
# Pass2: 需逐个查的字段 (roe=financials, 其余=技术指标计算)
PASS2_FIELDS = {"roe", "macd_golden_cross", "rsi_oversold", "boll_breakout"}
TECH_FIELDS = {"macd_golden_cross", "rsi_oversold", "boll_breakout"}
SORTABLE = ["change_pct", "roe", "pe_ttm", "pb", "turnover", "amount", "total_market_cap"]


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
            if val.get("min") is not None or val.get("max") is not None:
                return False
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
