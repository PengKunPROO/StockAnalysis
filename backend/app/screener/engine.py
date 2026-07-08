"""Screener engine: two-pass filter using tonghuashun (同花顺 Financial-API).

Pass 1: fuyao prices/snapshot 全市场分页过滤 change_pct/amount.
Pass 2: 对幸存者(≤30)逐个查 roe (financials) + 技术信号 (indicators).
name 用 fuyao ticker-list 补全。
"""
import asyncio
import time
from datetime import date, timedelta
from app.screener.fields import (
    get_fields, matches_snapshot, FIELD_BY_NAME, PASS2_FIELDS, TECH_FIELDS, SORTABLE,
)
from app.datasources import get_source_for_market

TECH_SIGNAL_NAME = {
    "macd_golden_cross": "MACD金叉",
    "rsi_oversold": "RSI超卖",
    "boll_breakout": "BOLL突破上轨",
}


class SkillTemplate:
    def __init__(self, name: str, label: str, description: str, fields: dict):
        self.name = name
        self.label = label
        self.description = description
        self.fields = fields


SKILLS: list[SkillTemplate] = [
    SkillTemplate("value", "价值选股", "高回报：ROE>15%（PE/PB 估值接口未上线，暂不可用）",
                 {"roe": {"min": 15}}),
    SkillTemplate("technical", "技术选股", "技术面转强：MACD金叉 + RSI超卖",
                 {"macd_golden_cross": True, "rsi_oversold": True}),
    SkillTemplate("short_strong", "短线强势", "量价齐升：涨幅>5%、成交额放大",
                 {"change_pct": {"min": 5}}),
    SkillTemplate("sector_rotation", "行业轮动", "行业数据接口暂不可用，请用基本面/行情筛选",
                 {}),
]


def list_skills() -> list[dict]:
    return [
        {"name": s.name, "label": s.label, "description": s.description, "fields": s.fields}
        for s in SKILLS
    ]


async def _fetch_name_map(source) -> dict[str, str]:
    """拉 ticker-list 建 code->name 映射（补全 snapshot 无 name 的问题）。"""
    try:
        tickers = await source.fetch_ticker_list(asset_type="a-share", limit=5000)
        return {t["code"]: t["name"] for t in tickers if t.get("code") and t.get("name")}
    except Exception:
        return {}


# 60s 内存缓存: 避免多次筛选重复拉全市场快照+名称映射 (bug5 提速)
_SNAP_CACHE = {"snap": None, "names": None, "ts": 0}


async def _get_snapshot_cached(source, ttl: int = 60):
    now = time.time()
    if _SNAP_CACHE["snap"] is not None and now - _SNAP_CACHE["ts"] < ttl:
        return _SNAP_CACHE["snap"], _SNAP_CACHE["names"]
    snap, names = await asyncio.gather(
        source.fetch_market_snapshot(limit=500),
        _fetch_name_map(source),
    )
    _SNAP_CACHE["snap"] = snap
    _SNAP_CACHE["names"] = names
    _SNAP_CACHE["ts"] = now
    return snap, names


def _roe_matches(roe: float | None, roe_val: dict) -> bool:
    if roe is None:
        return False
    mn = roe_val.get("min")
    mx = roe_val.get("max")
    if mn is not None and roe < mn:
        return False
    if mx is not None and roe > mx:
        return False
    return True


async def _apply_pass2(source, stocks: list[dict], values: dict,
                       roe_active: bool, tech_active: list[str]) -> list[dict]:
    """Pass2: 对幸存者逐个查 roe + 技术信号。"""
    from app.engine.data_engine import engine
    from app.indicators import compute_all, compute_fibonacci_levels
    from app.signals import compute_signals

    roe_val = values.get("roe", {}) if roe_active else {}
    end = str(date.today())
    start = str(date.today() - timedelta(days=200))
    out = []
    for s in stocks:
        # ROE 过滤
        if roe_active:
            try:
                fin, _ = await engine.get_financial(s["code"])
                if not _roe_matches(fin.get("roe") if fin else None, roe_val):
                    continue
                s["roe"] = round(fin["roe"], 2) if fin and fin.get("roe") is not None else None
            except Exception:
                if roe_active:
                    continue
        # 技术信号过滤
        if tech_active:
            try:
                klines, _ = await engine.get_klines(s["code"], "daily", start, end)
                if not klines:
                    continue
                indicators = await compute_all(klines[-90:])
                fibonacci = await compute_fibonacci_levels(klines)
                payload = compute_signals(klines, indicators, fibonacci)
                active_names = {sig["name"] for sig in payload["active_signals"]}
                required = {TECH_SIGNAL_NAME[f] for f in tech_active}
                if not required.issubset(active_names):
                    continue
                s["signals"] = sorted(active_names)
                s["score"] = payload["score"]["pct"]
            except Exception:
                continue
        out.append(s)
    return out


async def run_screener(values: dict, sort: str = "change_pct", limit: int = 50) -> dict:
    source = get_source_for_market("a_share")
    if source is None:
        return {"results": [], "count": 0, "warning": "无 A 股数据源"}

    # 全市场快照+名称映射 (60s 缓存, 避免多次筛选重复拉取 - bug5)
    snapshot, name_map = await _get_snapshot_cached(source)
    if not snapshot:
        return {"results": [], "count": 0, "warning": "同花顺行情快照暂不可用，请稍后重试"}

    # 补全 name
    for s in snapshot:
        if not s.get("name"):
            s["name"] = name_map.get(s["code"], s["code"].split(".")[-1])

    # Pass1: 快照过滤
    survivors = [s for s in snapshot if matches_snapshot(s, values)]

    # Pass2: roe + 技术信号（幸存者上限30保延迟可控）
    roe_val = values.get("roe")
    roe_active = isinstance(roe_val, dict) and (roe_val.get("min") is not None or roe_val.get("max") is not None)
    tech_active = [f for f in TECH_FIELDS if values.get(f)]
    if roe_active or tech_active:
        survivors = await _apply_pass2(source, survivors[:30], values, roe_active, tech_active)

    # 排序
    if sort in SORTABLE:
        survivors.sort(key=lambda s: (s.get(sort) if s.get(sort) is not None else -1e18), reverse=True)

    return {"results": survivors[:limit], "count": len(survivors)}
