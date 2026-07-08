"""Declarative screener field definitions (OCP - add a field here, it appears in UI)."""
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


# Field registry - the single source of truth for what the screener can filter on.
# `accessor` maps field name -> a key in the market snapshot dict (for snapshot fields).
# Technical fields have no accessor (computed per-stock in pass 2).
FIELDS: list[FilterField] = [
    # 基本面
    FilterField(name="roe", label="ROE", type="number_range", category="基本面",
                unit="%", constraints={"min": 0, "max": 100, "step": 1, "direction": "gte"}),
    FilterField(name="pe_ttm", label="市盈率(TTM)", type="number_range", category="基本面",
                constraints={"min": 0, "max": 200, "step": 1}),
    FilterField(name="pb", label="市净率", type="number_range", category="基本面",
                constraints={"min": 0, "max": 50, "step": 0.5}),
    FilterField(name="total_market_cap", label="总市值", type="number_range", category="基本面",
                unit="亿", constraints={"min": 0, "max": 100000, "step": 50, "scale": 1e-8}),
    # 行情表现
    FilterField(name="change_pct", label="涨跌幅", type="number_range", category="行情表现",
                unit="%", constraints={"min": -20, "max": 20, "step": 0.5}),
    FilterField(name="turnover", label="换手率", type="number_range", category="行情表现",
                unit="%", constraints={"min": 0, "max": 50, "step": 1, "direction": "gte"}),
    FilterField(name="amplitude", label="振幅", type="number_range", category="行情表现",
                unit="%", constraints={"min": 0, "max": 20, "step": 0.5, "direction": "gte"}),
    FilterField(name="amount", label="成交额", type="number_range", category="行情表现",
                unit="亿", constraints={"min": 0, "max": 500, "step": 1, "scale": 1e-8, "direction": "gte"}),
    # 技术信号 (computed per-stock in pass 2 for survivors)
    FilterField(name="macd_golden_cross", label="MACD金叉", type="boolean", category="技术信号"),
    FilterField(name="rsi_oversold", label="RSI超卖", type="boolean", category="技术信号"),
    FilterField(name="boll_breakout", label="BOLL突破上轨", type="boolean", category="技术信号"),
    # 行业概念 - not available in bulk snapshot
    FilterField(name="industry", label="行业", type="choice", category="行业概念",
                constraints={"options": []}, available=False),
]

FIELD_BY_NAME = {f.name: f for f in FIELDS}

# Fields derivable directly from the market snapshot (pass 1, bulk).
SNAPSHOT_FIELDS = {"roe", "pe_ttm", "pb", "total_market_cap",
                   "change_pct", "turnover", "amplitude", "amount"}

# Fields requiring per-stock technical computation (pass 2).
TECH_FIELDS = {"macd_golden_cross", "rsi_oversold", "boll_breakout"}

SORTABLE = ["change_pct", "roe", "pe_ttm", "pb", "turnover", "amount", "total_market_cap"]


def get_fields() -> list[FilterField]:
    return FIELDS


def matches_snapshot(stock: dict, values: dict) -> bool:
    """Check a stock against all snapshot-derivable field filters."""
    for name, val in values.items():
        if name not in SNAPSHOT_FIELDS:
            continue
        field = FIELD_BY_NAME.get(name)
        if not field:
            continue
        raw = stock.get(name)
        if raw is None:
            # missing data (e.g. PE for a loss-making stock) -> exclude on filtered
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
