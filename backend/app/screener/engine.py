"""Screener engine: two-pass filter over the A-share market snapshot.

Pass 1: bulk-filter ~5000 stocks on snapshot-derivable fields (PE/PB/ROE/change/turnover).
Pass 2: for survivors (capped), compute per-stock technical signals (MACD/RSI/BOLL).
"""
from datetime import date, timedelta
from app.screener.fields import (
    get_fields, matches_snapshot, FIELD_BY_NAME, TECH_FIELDS, SORTABLE,
)
from app.datasources.eastmoney import fetch_market_snapshot

# Technical field -> active signal name produced by the signal engine
TECH_SIGNAL_NAME = {
    "macd_golden_cross": "MACD金叉",
    "rsi_oversold": "RSI超卖",
    "boll_breakout": "BOLL突破上轨",
}

DISPLAY_SCALE = {  # raw yuan -> display unit
    "total_market_cap": 1e-8,   # -> 亿
    "float_market_cap": 1e-8,
    "amount": 1e-8,             # -> 亿
}


class SkillTemplate:
    def __init__(self, name: str, label: str, description: str, fields: dict):
        self.name = name
        self.label = label
        self.description = description
        self.fields = fields  # {field_name: {"min","max"} | True}


SKILLS: list[SkillTemplate] = [
    SkillTemplate("value", "价值选股", "低估值、高回报：PE<30, PB<5, ROE>15%",
                 {"pe_ttm": {"min": 0, "max": 30}, "pb": {"min": 0, "max": 5}, "roe": {"min": 15}}),
    SkillTemplate("technical", "技术选股", "技术面转强：MACD金叉 + RSI超卖",
                 {"macd_golden_cross": True, "rsi_oversold": True}),
    SkillTemplate("short_strong", "短线强势", "量价齐升：涨幅>5%, 换手>5%, 成交额>2亿",
                 {"change_pct": {"min": 5}, "turnover": {"min": 5}, "amount": {"min": 2}}),
    SkillTemplate("sector_rotation", "行业轮动", "板块轮动选股（行业数据暂不可用，请先用基本面筛选）",
                 {}),
]


def list_skills() -> list[dict]:
    return [
        {"name": s.name, "label": s.label, "description": s.description, "fields": s.fields}
        for s in SKILLS
    ]


async def _apply_technical(stocks: list[dict], tech_fields: list[str], values: dict) -> list[dict]:
    """Pass 2: compute technical signals for survivors, keep those matching."""
    from app.engine.data_engine import engine
    from app.indicators import compute_all, compute_fibonacci_levels
    from app.signals import compute_signals

    end = str(date.today())
    start = str(date.today() - timedelta(days=200))
    out = []
    for s in stocks:
        try:
            klines, _ = await engine.get_klines(s["code"], "daily", start, end)
            if not klines:
                continue
            indicators = await compute_all(klines[-90:])
            fibonacci = await compute_fibonacci_levels(klines)
            payload = compute_signals(klines, indicators, fibonacci)
            active_names = {sig["name"] for sig in payload["active_signals"]}
            # require ALL active technical fields to be present
            required = {TECH_SIGNAL_NAME[f] for f in tech_fields if values.get(f)}
            if required and not required.issubset(active_names):
                continue
            s["signals"] = sorted(active_names)
            s["score"] = payload["score"]["pct"]
            out.append(s)
        except Exception:
            continue
    return out


def _to_display(stock: dict) -> dict:
    """Scale raw yuan fields to display units (亿)."""
    out = dict(stock)
    for k, scale in DISPLAY_SCALE.items():
        if out.get(k) is not None:
            out[k] = round(out[k] * scale, 2)
    return out


async def run_screener(values: dict, sort: str = "change_pct", limit: int = 50) -> dict:
    snapshot = await fetch_market_snapshot(limit=2000)
    if not snapshot:
        return {"results": [], "count": 0, "warning": "东方财富数据源暂不可用，请稍后重试"}

    # Pass 1: snapshot-derivable filters
    survivors = [s for s in snapshot if matches_snapshot(s, values)]

    # Pass 2: technical fields (cap survivors to keep latency bounded)
    tech_active = [f for f in TECH_FIELDS if values.get(f)]
    if tech_active:
        survivors = await _apply_technical(survivors[:30], tech_active, values)

    # Sort
    if sort in SORTABLE:
        survivors.sort(key=lambda s: (s.get(sort) if s.get(sort) is not None else -1e18), reverse=True)

    results = [_to_display(s) for s in survivors[:limit]]
    return {"results": results, "count": len(survivors)}
