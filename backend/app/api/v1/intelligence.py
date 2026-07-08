"""市场情报 (intelligence) API: overview dashboard + 6 tabs.

All endpoints degrade gracefully - a failed data source yields an empty list
plus a `warning`, never a 500.
"""
from fastapi import APIRouter, Query
from app.engine.data_engine import engine
from app.datasources import eastmoney

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

INDEX_CODES = {
    "上证指数": "sh.000001",
    "深证成指": "sz.399001",
    "创业板指": "sz.399006",
    "科创50": "sh.000688",
    "沪深300": "sh.000300",
}


@router.get("/overview")
async def overview():
    """Market overview dashboard: indices + breadth + limit-up + sentiment."""
    warnings = []

    # 5 indices
    idx_data, idx_warn = await engine.get_index(list(INDEX_CODES.values()))
    if idx_warn:
        warnings.append(idx_warn)
    indices = []
    for name, code in INDEX_CODES.items():
        match = next((i for i in idx_data if i.get("code") == code), None)
        if match:
            indices.append({"name": name, "code": code, **match})

    # breadth + anomalies from snapshot
    snapshot = await eastmoney.fetch_market_snapshot(limit=5000)
    breadth = {"up": 0, "down": 0, "flat": 0, "limit_up": 0, "limit_down": 0}
    for s in snapshot:
        chg = s.get("change_pct")
        if chg is None:
            continue
        if chg > 0.01:
            breadth["up"] += 1
        elif chg < -0.01:
            breadth["down"] += 1
        else:
            breadth["flat"] += 1
        if chg >= 9.8:
            breadth["limit_up"] += 1
        elif chg <= -9.8:
            breadth["limit_down"] += 1
    if not snapshot:
        warnings.append("行情快照不可用")

    # limit-up pool for 涨停 detail + sentiment metrics
    pool = await eastmoney.fetch_limit_up_pool()
    board_buckets = {}
    seal_success = None
    promotion_rate = None
    if pool:
        sealed = sum(1 for p in pool if (p.get("broken_count") or 0) == 0)
        total = len(pool)
        seal_success = round(sealed / total * 100, 1) if total else 0
        multi = sum(1 for p in pool if (p.get("consecutive_days") or 1) >= 2)
        promotion_rate = round(multi / total * 100, 1) if total else 0
        for p in pool:
            d = p.get("consecutive_days") or 1
            bucket = "高位板" if d >= 5 else f"{d}板"
            board_buckets[bucket] = board_buckets.get(bucket, 0) + 1

    # sentiment: 恐惧贪婪 0-100 (greedy=high). derive from breadth + index direction
    total_stocks = breadth["up"] + breadth["down"]
    red_ratio = round(breadth["up"] / total_stocks * 100, 1) if total_stocks else 50
    avg_idx_chg = (
        sum(i.get("change_pct", 0) for i in indices) / len(indices) if indices else 0
    )
    fear_greed = max(0, min(100, round(50 + avg_idx_chg * 8 + (red_ratio - 50) * 0.4)))

    result = {
        "indices": indices,
        "breadth": breadth,
        "red_ratio": red_ratio,
        "limit_up_count": len(pool),
        "board_buckets": board_buckets,
        "sentiment": {
            "fear_greed": fear_greed,
            "fear_greed_label": "贪婪" if fear_greed >= 65 else ("恐惧" if fear_greed <= 35 else "中性"),
            "profit_effect": red_ratio,
            "seal_success_rate": seal_success,
            "promotion_rate": promotion_rate,
        },
    }
    if warnings:
        result["warning"] = "; ".join(warnings)
    return result


@router.get("/limit-up")
async def limit_up():
    pool = await eastmoney.fetch_limit_up_pool()
    if not pool:
        return {"stocks": [], "buckets": {}, "warning": "涨停股池数据暂不可用"}
    # sort by consecutive days desc
    pool.sort(key=lambda p: p.get("consecutive_days") or 1, reverse=True)
    buckets = {}
    for p in pool:
        d = p.get("consecutive_days") or 1
        bucket = "高位板" if d >= 5 else f"{d}板"
        buckets[bucket] = buckets.get(bucket, 0) + 1
    return {"stocks": pool, "buckets": buckets, "count": len(pool)}


@router.get("/fund-flow")
async def fund_flow(scope: str = Query("industry", pattern=r"^(industry|concept|north|stock)$")):
    if scope == "north":
        data = await eastmoney.fetch_north_bound(days=10)
        if not data:
            return {"north": [], "warning": "北向资金数据暂不可用"}
        return {"north": data}
    if scope in ("industry", "concept"):
        sectors = await eastmoney.fetch_sector_rank(board=scope, limit=30)
        if not sectors:
            return {"sectors": [], "warning": "板块资金数据暂不可用"}
        return {"sectors": sectors, "scope": scope}
    # stock scope: top by amount from snapshot
    snap = await eastmoney.fetch_market_snapshot(limit=500)
    if not snap:
        return {"stocks": [], "warning": "行情数据暂不可用"}
    snap.sort(key=lambda s: s.get("amount") or 0, reverse=True)
    top = [
        {"code": s["code"], "name": s["name"], "amount": round((s.get("amount") or 0) * 1e-8, 2),
         "change_pct": s.get("change_pct")}
        for s in snap[:30]
    ]
    return {"stocks": top, "scope": "stock"}


@router.get("/sectors")
async def sectors(type: str = Query("industry", pattern=r"^(industry|concept)$")):
    data = await eastmoney.fetch_sector_rank(board=type, limit=30)
    if not data:
        return {"sectors": [], "warning": "板块数据暂不可用"}
    return {"sectors": data, "type": type}


@router.get("/dragon-tiger")
async def dragon_tiger(date: str = Query("")):
    data = await eastmoney.fetch_dragon_tiger(date_str=date, limit=30)
    if not data:
        return {"stocks": [], "warning": "龙虎榜数据暂不可用（可能当日尚未更新）"}
    return {"stocks": data, "count": len(data)}


@router.get("/anomalies")
async def anomalies(limit: int = Query(30, ge=5, le=100)):
    snap = await eastmoney.fetch_market_snapshot(limit=5000)
    if not snap:
        return {"anomalies": [], "warning": "行情数据暂不可用"}
    out = []
    for s in snap:
        chg = s.get("change_pct")
        amp = s.get("amplitude")
        if chg is None:
            continue
        atype = None
        if chg >= 9.8:
            atype = "涨停"
        elif chg <= -9.8:
            atype = "跌停"
        elif (amp or 0) >= 8:
            atype = "振幅异动"
        elif chg >= 7:
            atype = "急涨"
        elif chg <= -7:
            atype = "急跌"
        if atype:
            out.append({
                "code": s["code"], "name": s["name"], "change_pct": chg,
                "amplitude": amp, "turnover": s.get("turnover"),
                "amount": round((s.get("amount") or 0) * 1e-8, 2), "type": atype,
            })
    out.sort(key=lambda x: abs(x["change_pct"] or 0), reverse=True)
    return {"anomalies": out[:limit], "count": len(out)}


@router.get("/announcements")
async def announcements(limit: int = Query(15, ge=5, le=50)):
    # announcements for top-market-cap stocks
    snap = await eastmoney.fetch_market_snapshot(limit=200)
    if not snap:
        return {"announcements": [], "warning": "行情数据暂不可用"}
    snap.sort(key=lambda s: s.get("total_market_cap") or 0, reverse=True)
    out = []
    for s in snap[:5]:
        anns = await eastmoney.fetch_announcements(s["code"], limit=3)
        for a in anns:
            out.append({"stock": s["name"], "code": s["code"], **a})
        if len(out) >= limit:
            break
    if not out:
        return {"announcements": [], "warning": "公告数据暂不可用"}
    return {"announcements": out[:limit], "count": len(out)}
