"""Screener engine v2: two-pass filter with expanded factors.

Pass 1: fuyao prices/snapshot 全市场过滤 snapshot 字段
Pass 2: 对幸存者(≤50)逐个查:
  - Financial (同花顺 financials): roe, debt_ratio
  - Technical (K线计算): macd_golden_cross, rsi_oversold, boll_breakout, kdj_golden_cross,
    near_high_drop, change_5d, change_20d
  - News (同花顺 dragon-tiger/hot-stock + 东财资金流): on_dragon_tiger, hot_rank, main_net_flow
Each surviving stock gets factor_details for data validation.
"""
import asyncio
import time
from datetime import date, timedelta
from app.screener.fields import (
    get_fields, matches_snapshot, FIELD_BY_NAME,
    SNAPSHOT_FIELDS, PASS2_FIELDS, TECH_FIELDS, NEWS_FIELDS, SORTABLE,
)
from app.datasources import get_source_for_market

TECH_SIGNAL_NAME = {
    "macd_golden_cross": "MACD金叉",
    "rsi_oversold": "RSI超卖",
    "boll_breakout": "BOLL突破上轨",
    "kdj_golden_cross": "KDJ金叉",
}


class SkillTemplate:
    def __init__(self, name: str, label: str, description: str, fields: dict):
        self.name = name
        self.label = label
        self.description = description
        self.fields = fields


SKILLS: list[SkillTemplate] = [
    SkillTemplate("oversold_bounce", "短线超跌反弹",
                 "RSI超卖 + 距52周高点跌幅>30% + 成交额>1亿",
                 {"rsi_oversold": True, "near_high_drop": {"min": 30}, "amount": {"min": 100000000}}),
    SkillTemplate("cigarette_butt", "烟蒂股",
                 "ROE>8% + 负债率<60% + 涨幅<2%",
                 {"roe": {"min": 8}, "debt_ratio": {"max": 60}, "change_pct": {"max": 2}}),
    SkillTemplate("value", "长线价值",
                 "ROE>15% + 负债率<50%",
                 {"roe": {"min": 15}, "debt_ratio": {"max": 50}}),
    SkillTemplate("technical", "技术转强",
                 "MACD金叉 + 成交额>2亿",
                 {"macd_golden_cross": True, "amount": {"min": 200000000}}),
    SkillTemplate("news_driven", "消息面驱动",
                 "龙虎榜上榜 + 主力净流入>0",
                 {"on_dragon_tiger": True, "main_net_flow": {"min": 0}}),
    SkillTemplate("breakout", "强势突破",
                 "涨幅>3% + 振幅>5% + 成交额>3亿 + BOLL突破上轨",
                 {"change_pct": {"min": 3}, "amplitude": {"min": 5}, "amount": {"min": 300000000}, "boll_breakout": True}),
]


def list_skills() -> list[dict]:
    return [
        {"name": s.name, "label": s.label, "description": s.description, "fields": s.fields}
        for s in SKILLS
    ]


async def _fetch_name_map(source) -> dict[str, str]:
    try:
        tickers = await source.fetch_ticker_list(asset_type="a-share", limit=5000)
        return {t["code"]: t["name"] for t in tickers if t.get("code") and t.get("name")}
    except Exception:
        return {}


_SNAP_CACHE = {"snap": None, "names": None, "ts": 0}


async def _get_snapshot_cached(source, ttl: int = 60):
    now = time.time()
    if _SNAP_CACHE["snap"] is not None and now - _SNAP_CACHE["ts"] < ttl:
        return _SNAP_CACHE["snap"], _SNAP_CACHE["names"]
    snap, names = await asyncio.gather(
        source.fetch_market_snapshot(limit=5000),
        _fetch_name_map(source),
    )
    _SNAP_CACHE["snap"] = snap
    _SNAP_CACHE["names"] = names
    _SNAP_CACHE["ts"] = now
    return snap, names


def _range_matches(val: float | None, filter: dict) -> tuple[bool, float | None]:
    """Check if value matches min/max filter. Returns (pass, actual_value)."""
    if val is None:
        return False, None
    mn = filter.get("min")
    mx = filter.get("max")
    if mn is not None and val < mn:
        return False, val
    if mx is not None and val > mx:
        return False, val
    return True, val


def _bool_matches(val: bool, filter_val) -> tuple[bool, bool]:
    """Check boolean filter. Returns (pass, actual)."""
    if filter_val is True:
        return (val == True), val
    return True, val


async def _fetch_tech_data(code: str) -> dict:
    """Fetch K-line data and compute technical indicators for a stock."""
    from app.engine.data_engine import engine as data_engine
    from app.indicators import compute_all, compute_fibonacci_levels
    from app.signals import compute_signals

    end = str(date.today())
    start = str(date.today() - timedelta(days=300))
    klines, _ = await data_engine.get_klines(code, "daily", start, end)
    if not klines or len(klines) < 20:
        return {}

    indicators = await compute_all(klines[-90:])
    fibonacci = await compute_fibonacci_levels(klines)
    payload = compute_signals(klines, indicators, fibonacci)
    active_names = {sig["name"] for sig in payload["active_signals"]}

    result = {
        "macd_golden_cross": "MACD金叉" in active_names,
        "rsi_oversold": "RSI超卖" in active_names,
        "boll_breakout": "BOLL突破上轨" in active_names,
        "kdj_golden_cross": "KDJ金叉" in active_names,
        "score": payload["score"]["pct"],
        "signals": sorted(active_names),
    }

    # near_high_drop: (52周高 - 现价) / 52周高 * 100
    close = klines[-1]["close"]
    klines_252 = klines[-252:] if len(klines) >= 252 else klines
    high_52w = max(k["high"] for k in klines_252)
    if high_52w > 0:
        result["near_high_drop"] = round((high_52w - close) / high_52w * 100, 2)

    # change_5d, change_20d
    if len(klines) >= 6:
        result["change_5d"] = round((close - klines[-6]["close"]) / klines[-6]["close"] * 100, 2)
    if len(klines) >= 21:
        result["change_20d"] = round((close - klines[-21]["close"]) / klines[-21]["close"] * 100, 2)

    return result


async def _fetch_financial_data(code: str) -> dict:
    """Fetch financial data for a stock."""
    from app.engine.data_engine import engine as data_engine
    try:
        fin, _ = await data_engine.get_financial(code)
        if fin:
            return {
                "roe": fin.get("roe"),
                "debt_ratio": fin.get("debt_ratio"),
            }
    except Exception:
        pass
    return {}


async def _fetch_news_data(source, code: str) -> dict:
    """Fetch news/sentiment data for a stock."""
    result = {}
    # Dragon tiger
    try:
        dt_data = await source.fetch_dragon_tiger("", board_type="all")
        if dt_data:
            on_dt = any(d.get("code") == code for d in dt_data[:100])
            result["on_dragon_tiger"] = on_dt
    except Exception:
        result["on_dragon_tiger"] = False

    # Hot stock rank
    try:
        hot = await source.fetch_hot_stock(level="day")
        for i, h in enumerate(hot[:200]):
            if h.get("code") == code:
                result["hot_rank"] = i + 1
                break
        else:
            result["hot_rank"] = None
    except Exception:
        result["hot_rank"] = None

    # Main net flow (eastmoney) - skip if unavailable
    result["main_net_flow"] = None

    return result


async def _apply_pass2(source, stocks: list[dict], values: dict) -> list[dict]:
    """Pass2: filter survivors by financial, technical, and news factors."""
    # Determine which Pass2 factors are active
    fin_active = [f for f in ["roe", "debt_ratio"] if f in values and isinstance(values[f], dict)]
    tech_bool_active = [f for f in ["macd_golden_cross", "rsi_oversold", "boll_breakout", "kdj_golden_cross"]
                         if values.get(f) is True]
    tech_range_active = [f for f in ["near_high_drop", "change_5d", "change_20d"]
                          if f in values and isinstance(values[f], dict)]
    news_active = [f for f in ["on_dragon_tiger", "hot_rank", "main_net_flow"]
                   if f in values]

    needs_fin = bool(fin_active)
    needs_tech = bool(tech_bool_active or tech_range_active)
    needs_news = bool(news_active)

    out = []
    for s in stocks:
        factor_details = {}
        passed = True

        # Financial
        if needs_fin:
            fin_data = await _fetch_financial_data(s["code"])
            for f in fin_active:
                actual = fin_data.get(f)
                ok, _ = _range_matches(actual, values[f])
                factor_details[f] = {"actual": actual, "threshold": values[f], "pass": ok}
                if not ok:
                    passed = False
            s.update({k: v for k, v in fin_data.items() if v is not None})

        # Technical
        if needs_tech and passed:
            tech_data = await _fetch_tech_data(s["code"])
            if not tech_data:
                # K-line data unavailable, skip if tech required
                for f in tech_bool_active + tech_range_active:
                    factor_details[f] = {"actual": None, "threshold": values.get(f), "pass": False}
                passed = False
            else:
                for f in tech_bool_active:
                    actual = tech_data.get(f, False)
                    ok, _ = _bool_matches(actual, True)
                    factor_details[f] = {"actual": actual, "threshold": True, "pass": ok}
                    if not ok:
                        passed = False
                for f in tech_range_active:
                    actual = tech_data.get(f)
                    ok, _ = _range_matches(actual, values[f])
                    factor_details[f] = {"actual": actual, "threshold": values[f], "pass": ok}
                    if not ok:
                        passed = False
                s.update({k: v for k, v in tech_data.items() if v is not None})

        # News (degrade gracefully)
        if needs_news and passed:
            news_data = await _fetch_news_data(source, s["code"])
            for f in news_active:
                if isinstance(values.get(f), dict):
                    actual = news_data.get(f)
                    ok, _ = _range_matches(actual, values[f])
                    factor_details[f] = {"actual": actual, "threshold": values[f], "pass": ok}
                    if not ok:
                        passed = False
                elif values.get(f) is True:
                    actual = news_data.get(f, False)
                    ok, _ = _bool_matches(actual, True)
                    factor_details[f] = {"actual": actual, "threshold": True, "pass": ok}
                    if not ok:
                        passed = False
            s.update({k: v for k, v in news_data.items() if v is not None})

        s["factor_details"] = factor_details
        if passed:
            out.append(s)

    return out


async def run_screener(values: dict, sort: str = "change_pct", limit: int = 50) -> dict:
    source = get_source_for_market("a_share")
    if source is None:
        return {"results": [], "count": 0, "warning": "无 A 股数据源"}

    snapshot, name_map = await _get_snapshot_cached(source)
    if not snapshot:
        return {"results": [], "count": 0, "warning": "同花顺行情快照暂不可用，请稍后重试"}

    # 补全 name
    for s in snapshot:
        if not s.get("name"):
            s["name"] = name_map.get(s["code"], s["code"].split(".")[-1])

    # Pass1: 快照过滤
    survivors = [s for s in snapshot if matches_snapshot(s, values)]

    # Pass1 factor_details for snapshot fields
    for s in survivors:
        details = {}
        for name in SNAPSHOT_FIELDS:
            if name in values:
                raw = s.get(name)
                if isinstance(values[name], dict):
                    ok, _ = _range_matches(raw, values[name])
                    details[name] = {"actual": raw, "threshold": values[name], "pass": ok}
        s["factor_details"] = details

    # Check if Pass2 is needed
    pass2_fields = set(values.keys()) & PASS2_FIELDS - SNAPSHOT_FIELDS
    has_pass2 = any(FIELD_BY_NAME.get(f) and FIELD_BY_NAME[f].available for f in pass2_fields)

    if has_pass2:
        survivors = await _apply_pass2(source, survivors[:50], values)

    # 排序
    if sort in SORTABLE:
        survivors.sort(key=lambda s: (s.get(sort) if s.get(sort) is not None else -1e18), reverse=True)

    return {"results": survivors[:limit], "count": len(survivors)}
