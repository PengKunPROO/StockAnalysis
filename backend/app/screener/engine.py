"""Screener engine: two-pass filter using tonghuashun (同花顺 Financial-API).

Pass 1: fuyao prices/snapshot 全市场(5000条)过滤 change_pct/amount/amplitude.
Pass 2: 对幸存者(≤100)逐个查:
  - 财务因子 (roe, debt_ratio) via engine.get_financial()
  - 技术因子 (macd_golden_cross, rsi_oversold, boll_breakout, kdj_golden_cross) via compute_signals;
    near_high_drop, change_5d, change_20d via K-line calculation
  - 消息面因子 (on_dragon_tiger, hot_rank) via source.fetch_dragon_tiger/hot_stock
name 用 fuyao ticker-list 补全.
每只幸存股票返回 factor_details: {factor_name: {actual, threshold, pass}}.
消息面数据源失败优雅降级，不影响其他因子.
"""
import asyncio
import time
from datetime import date, timedelta
from app.screener.fields import (
    get_fields, matches_snapshot, FIELD_BY_NAME, PASS2_FIELDS, TECH_FIELDS, NEWS_FIELDS, SORTABLE,
    SNAPSHOT_FIELDS,
)
from app.datasources import get_source_for_market

# Boolean technical signal name -> signal name used by compute_signals
TECH_BOOL_SIGNALS = {
    "macd_golden_cross": "MACD金叉",
    "rsi_oversold": "RSI超卖",
    "boll_breakout": "BOLL突破上轨",
    "kdj_golden_cross": "KDJ金叉",
}

# Numeric technical fields computed from K-lines
TECH_NUMERIC_FIELDS = {"near_high_drop", "change_5d", "change_20d"}

# Financial fields
FINANCIAL_FIELDS = {"roe", "debt_ratio"}


class SkillTemplate:
    def __init__(self, name: str, label: str, description: str, fields: dict):
        self.name = name
        self.label = label
        self.description = description
        self.fields = fields


SKILLS: list[SkillTemplate] = [
    SkillTemplate(
        "oversold_bounce", "短线超跌反弹",
        "RSI超卖(<30) + 距52周高点跌幅>30% + 成交额>1亿。适合捕捉超跌后的技术性反弹。",
        {"rsi_oversold": True, "near_high_drop": {"min": 30}, "amount": {"min": 100000000}},
    ),
    SkillTemplate(
        "cigarette_butt", "烟蒂股",
        "ROE>8% + 负债率<60% + 涨幅<2%。低估值+稳健基本面，适合逆向投资者。",
        {"roe": {"min": 8}, "debt_ratio": {"max": 60}, "change_pct": {"max": 2},
         "amount": {"min": 50000000}},
    ),
    SkillTemplate(
        "value", "长线价值",
        "高回报低杠杆：ROE>15% + 负债率<50% + 成交额>5000万(排除流动性差的小票)。",
        {"roe": {"min": 15}, "debt_ratio": {"max": 50}, "amount": {"min": 50000000}},
    ),
    SkillTemplate(
        "technical", "技术转强",
        "MACD金叉 + 成交额>2亿。技术面转强且资金关注。",
        {"macd_golden_cross": True, "amount": {"min": 200000000}},
    ),
    SkillTemplate(
        "news_driven", "消息面驱动",
        "龙虎榜上榜 + 热榜排名<200。游资/机构活跃且市场关注度高。",
        {"on_dragon_tiger": True, "hot_rank": {"max": 200}},
    ),
    SkillTemplate(
        "breakout", "强势突破",
        "涨幅>3% + 振幅>5% + 成交额>3亿 + BOLL突破上轨。量价齐升的强势突破。",
        {"change_pct": {"min": 3}, "amplitude": {"min": 5},
         "amount": {"min": 300000000}, "boll_breakout": True},
    ),
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


# 60s 内存缓存: 避免多次筛选重复拉全市场快照+名称映射
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


def _range_matches(actual: float | None, val: dict) -> bool:
    """Check a numeric value against min/max thresholds."""
    if actual is None:
        return False
    mn = val.get("min")
    mx = val.get("max")
    if mn is not None and actual < mn:
        return False
    if mx is not None and actual > mx:
        return False
    return True


def _make_detail(actual, threshold, passed: bool) -> dict:
    """Build a factor_details entry."""
    return {"actual": actual, "threshold": threshold, "pass": passed}


async def _fetch_dragon_tiger_codes(source) -> set[str]:
    """Fetch today's dragon-tiger list, return set of stock codes. Degrades to empty set."""
    try:
        items = await source.fetch_dragon_tiger()
        return {it.get("code", "") for it in items if it.get("code")}
    except Exception:
        return set()


async def _fetch_hot_rank_map(source) -> dict[str, int]:
    """Fetch hot stock ranking, return code->rank map. Degrades to empty dict."""
    try:
        items = await source.fetch_hot_stock()
        return {it.get("code", ""): it.get("rank") for it in items if it.get("code")}
    except Exception:
        return {}


async def _apply_pass2(source, stocks: list[dict], values: dict) -> list[dict]:
    """Pass2: 对幸存者逐个查 financial + technical + news factors.

    Each surviving stock gets a 'factor_details' dict with actual/threshold/pass per factor.
    News data source failures degrade gracefully - don't block other factors.
    """
    from app.engine.data_engine import engine
    from app.indicators import compute_all, compute_fibonacci_levels
    from app.signals import compute_signals

    # Determine which Pass2 factors are active
    fin_active = {f for f in FINANCIAL_FIELDS if isinstance(values.get(f), dict)}
    tech_bool_active = {f for f in TECH_BOOL_SIGNALS if values.get(f) is True}
    tech_num_active = {f for f in TECH_NUMERIC_FIELDS if isinstance(values.get(f), dict)}
    news_active = {f for f in NEWS_FIELDS if values.get(f) is True or isinstance(values.get(f), dict)}

    need_klines = bool(tech_bool_active or tech_num_active)

    end = str(date.today())
    start = str(date.today() - timedelta(days=400))  # ~1 year for 52-week high

    # Pre-fetch news data (batch) - degrade gracefully
    dt_codes: set[str] = set()
    hot_map: dict[str, int] = {}
    if "on_dragon_tiger" in news_active:
        dt_codes = await _fetch_dragon_tiger_codes(source)
    if "hot_rank" in news_active:
        hot_map = await _fetch_hot_rank_map(source)

    out = []
    for s in stocks:
        code = s["code"]
        factor_details: dict[str, dict] = {}

        # ── Financial factors (roe, debt_ratio) ──
        fin_data = None
        if fin_active:
            try:
                fin_data, _ = await engine.get_financial(code)
            except Exception:
                fin_data = None

        fin_failed = False
        for fname in fin_active:
            val = values[fname]
            actual = fin_data.get(fname) if fin_data else None
            passed = _range_matches(actual, val) if fin_data else False
            factor_details[fname] = _make_detail(actual, val, passed)
            s[fname] = actual
            if not passed:
                fin_failed = True
                break
        if fin_failed:
            continue

        # ── Technical factors (need K-lines) ──
        if need_klines:
            try:
                klines, _ = await engine.get_klines(code, "daily", start, end)
                if not klines:
                    for fname in tech_bool_active:
                        factor_details[fname] = _make_detail(False, True, False)
                    for fname in tech_num_active:
                        val = values[fname]
                        factor_details[fname] = _make_detail(None, val, False)
                    if tech_bool_active or tech_num_active:
                        continue
                else:
                    indicators = await compute_all(klines[-90:])
                    fibonacci = await compute_fibonacci_levels(klines)
                    payload = compute_signals(klines, indicators, fibonacci)
                    active_names = {sig["name"] for sig in payload["active_signal"]}

                    # Boolean tech signals
                    tech_bool_failed = False
                    for fname in tech_bool_active:
                        signal_name = TECH_BOOL_SIGNALS[fname]
                        actual = signal_name in active_names
                        factor_details[fname] = _make_detail(actual, True, actual)
                        if not actual:
                            tech_bool_failed = True
                            break
                    if tech_bool_failed:
                        continue

                    # Numeric tech signals from K-lines
                    last_close = klines[-1]["close"]
                    tech_num_failed = False
                    for fname in tech_num_active:
                        val = values[fname]
                        actual = _compute_tech_numeric(fname, klines, last_close)
                        passed = _range_matches(actual, val)
                        factor_details[fname] = _make_detail(actual, val, passed)
                        s[fname] = actual
                        if not passed:
                            tech_num_failed = True
                            break
                    if tech_num_failed:
                        continue

                    # Store signals for reference
                    s["signals"] = sorted(active_names)
                    s["score"] = payload["score"]["pct"]
            except Exception:
                for fname in tech_bool_active:
                    factor_details[fname] = _make_detail(False, True, False)
                for fname in tech_num_active:
                    val = values[fname]
                    factor_details[fname] = _make_detail(None, val, False)
                if tech_bool_active or tech_num_active:
                    continue

        # ── News factors ──
        news_failed = False
        for fname in news_active:
            val = values[fname]
            if fname == "on_dragon_tiger":
                actual = code in dt_codes
                passed = actual if val is True else _range_matches(1 if actual else 0, val)
                factor_details[fname] = _make_detail(actual, val, passed)
                if not passed:
                    news_failed = True
                    break
            elif fname == "hot_rank":
                actual = hot_map.get(code)
                if isinstance(val, dict):
                    passed = _range_matches(actual, val)
                else:
                    passed = actual is not None
                factor_details[fname] = _make_detail(actual, val, passed)
                s["hot_rank"] = actual
                if not passed:
                    news_failed = True
                    break
        if news_failed:
            continue

        # Stock passed all active Pass2 factors
        s["factor_details"] = factor_details
        out.append(s)

    return out


def _compute_tech_numeric(fname: str, klines: list[dict], last_close: float) -> float | None:
    """Compute numeric technical factors from K-line data."""
    if not klines or not last_close:
        return None
    try:
        if fname == "near_high_drop":
            highs = [k["high"] for k in klines if k.get("high") is not None]
            if not highs:
                return None
            high_52w = max(highs)
            if high_52w <= 0:
                return None
            return round((high_52w - last_close) / high_52w * 100, 2)
        elif fname == "change_5d":
            if len(klines) < 6:
                return None
            ref_close = klines[-6]["close"]
            if ref_close <= 0:
                return None
            return round((last_close - ref_close) / ref_close * 100, 2)
        elif fname == "change_20d":
            if len(klines) < 21:
                return None
            ref_close = klines[-21]["close"]
            if ref_close <= 0:
                return None
            return round((last_close - ref_close) / ref_close * 100, 2)
    except Exception:
        return None
    return None


async def run_screener(values: dict, sort: str = "change_pct", limit: int = 50) -> dict:
    source = get_source_for_market("a_share")
    if source is None:
        return {"results": [], "count": 0, "warning": "无 A 股数据源"}

    # 全市场快照+名称映射 (60s 缓存)
    snapshot, name_map = await _get_snapshot_cached(source)
    if not snapshot:
        return {"results": [], "count": 0, "warning": "同花顺行情快照暂不可用，请稍后重试"}

    # 补全 name
    for s in snapshot:
        if not s.get("name"):
            s["name"] = name_map.get(s["code"], s["code"].split(".")[-1])

    # Pass1: 快照过滤
    survivors = [s for s in snapshot if matches_snapshot(s, values)]

    # Determine which Pass2 factors are active
    has_pass2 = any(
        isinstance(values.get(f), dict) or values.get(f) is True
        for f in PASS2_FIELDS
    )

    # Pass2: financial + technical + news factors (幸存者上限100保延迟可控)
    if has_pass2:
        survivors = await _apply_pass2(source, survivors[:100], values)

    # Build factor_details for Pass1 (snapshot) factors on all results
    for s in survivors:
        if "factor_details" not in s:
            s["factor_details"] = {}
        for fname, val in values.items():
            if fname in s.get("factor_details", {}):
                continue
            if fname in SNAPSHOT_FIELDS:
                field = FIELD_BY_NAME.get(fname)
                if not field or not field.available:
                    continue
                raw = s.get(fname)
                if isinstance(val, dict):
                    passed = _range_matches(raw, val)
                    s["factor_details"][fname] = _make_detail(raw, val, passed)

    # 排序
    if sort in SORTABLE:
        survivors.sort(key=lambda s: (s.get(sort) if s.get(sort) is not None else -1e18), reverse=True)

    return {"results": survivors[:limit], "count": len(survivors)}
