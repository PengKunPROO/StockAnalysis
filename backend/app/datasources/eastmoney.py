"""East Money (东方财富) supplementary crawler.

Public push2 endpoints (no auth). Every method degrades gracefully:
on any network/parse error it returns None/[] and never raises.
Used for PE/PB valuation, fund flow, sector rotation, north-bound capital,
and announcements - data the tonghuashun datasource does not provide.
"""
import httpx

BASE = "http://push2.eastmoney.com"
KAMT = "https://push2.eastmoney.com"
ANNO = "http://np-anotice-stock.eastmoney.com"

# East Money field codes
# f57=code f58=name f162=pe_ttm f167=pb f116=total_mktcap f117=float_mktcap f173=roe
_VAL_FIELDS = "f57,f58,f162,f167,f116,f117,f173,f3"


def _secid(code: str) -> str | None:
    """stock code sh.600519 -> '1.600519'; sz.000001 -> '0.000001'."""
    parts = code.split(".", 1)
    if len(parts) != 2:
        return None
    market, raw = parts[0], parts[1]
    prefix = "1" if market == "sh" else "0"
    return f"{prefix}.{raw}"


def _num(val):
    try:
        f = float(val)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


async def _get_json(url: str, params: dict, timeout: float = 10.0) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def fetch_valuation(code: str) -> dict | None:
    """PE(TTM), PB, market caps, ROE, change_pct for one stock."""
    secid = _secid(code)
    if not secid:
        return None
    data = await _get_json(f"{BASE}/api/qt/stock/get", {
        "secid": secid, "fields": _VAL_FIELDS, "fltt": "2", "invt": "2",
    })
    if not data or data.get("rc") != 0:
        return None
    d = data.get("data") or {}
    return {
        "code": code,
        "name": d.get("f58") or "",
        "pe_ttm": _num(d.get("f162")),
        "pb": _num(d.get("f167")),
        "total_market_cap": _num(d.get("f116")),
        "float_market_cap": _num(d.get("f117")),
        "roe": _num(d.get("f173")),
        "change_pct": _num(d.get("f3")),
    }


async def fetch_fund_flow(code: str, days: int = 10) -> list[dict]:
    """Per-day main-force net inflow series."""
    secid = _secid(code)
    if not secid:
        return []
    data = await _get_json(f"{BASE}/api/qt/stock/fflow/daykline/get", {
        "secid": secid, "lmt": str(days),
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
    })
    if not data or data.get("rc") != 0:
        return []
    rows = (data.get("data") or {}).get("kls") or []
    out = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 5:
            continue
        out.append({
            "date": r[0],
            "main_net": _num(r[1]),
            "small_net": _num(r[2]),
            "medium_net": _num(r[3]),
            "large_net": _num(r[4]),
        })
    return out


async def fetch_sector_rank(board: str = "industry", limit: int = 30) -> list[dict]:
    """Sector/concept ranking by change_pct. board: 'industry' or 'concept'."""
    fs = "m:90+t:2" if board == "industry" else "m:90+t:3"
    data = await _get_json(f"{BASE}/api/qt/clist/get", {
        "pn": "1", "pz": str(limit), "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f3", "fs": fs,
        "fields": "f12,f14,f3,f104,f105,f62",
    })
    if not data or data.get("rc") != 0:
        return []
    diff = (data.get("data") or {}).get("diff") or []
    out = []
    for d in diff:
        out.append({
            "code": d.get("f12"),
            "name": d.get("f14"),
            "change_pct": _num(d.get("f3")),
            "up_count": _num(d.get("f104")),
            "down_count": _num(d.get("f105")),
            "main_net": _num(d.get("f62")),
        })
    return out


async def fetch_north_bound(days: int = 10) -> list[dict]:
    """North-bound (沪股通/深股通) net inflow history."""
    data = await _get_json(f"{KAMT}/api/qt/kamt.kline/get", {
        "fields1": "f1,f2,f3",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101", "lmt": str(days),
    })
    if not data or data.get("rc") != 0:
        return []
    rows = (data.get("data") or {}).get("s2n") or []
    out = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 4:
            continue
        out.append({
            "date": r[0],
            "sh_connect_net": _num(r[1]),
            "sz_connect_net": _num(r[2]),
            "total_net": _num(r[3]),
        })
    return out


async def fetch_announcements(code: str, limit: int = 10) -> list[dict]:
    """Recent announcements for one stock."""
    raw = code.split(".", 1)[-1]
    data = await _get_json(f"{ANNO}/api/security/ann", {
        "sr": "-1", "page_size": str(limit), "page_index": "1",
        "ann_type": "A", "client_source": "web", "stock_list": raw,
    })
    if not data:
        return []
    rows = (data.get("data") or {}).get("list") or []
    out = []
    for a in rows:
        out.append({
            "title": a.get("title") or "",
            "date": a.get("notice_date") or "",
            "ann_id": a.get("art_code") or "",
            "url": f"https://np-anotice-stock.eastmoney.com/api/security/ann?art_code={a.get('art_code') or ''}",
        })
    return out


async def fetch_market_stats() -> dict | None:
    """Market up/down/limit-up counts via the spot list aggregate."""
    # 涨跌家数 from SH+SZ spot lists
    async def _count(fs: str) -> dict | None:
        d = await _get_json(f"{BASE}/api/qt/clist/get", {
            "pn": "1", "pz": "1", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3", "fs": fs,
            "fields": "f2,f3,f12",
        })
        if not d or d.get("rc") != 0:
            return None
        return (d.get("data") or {}).get("total")
    sh_total = await _count("m:1+t:2")
    sz_total = await _count("m:0+t:6,m:0+t:80,m:0+t:81+s:2048")
    return {"sh_total": sh_total, "sz_total": sz_total}


async def fetch_market_snapshot(limit: int = 2000) -> list[dict]:
    """Full A-share snapshot with screener fields (one bulk call).

    Powers the screener: filtering ~5000 stocks by PE/PB/ROE/change/turnover
    without per-stock API calls. Degrades to [] on any error.
    """
    # All A-shares: SH main + STAR, SZ main + GEM
    fs = "m:1+t:2,m:0+t:6,m:0+t:80,m:0+t:81+s:2048,m:1+t:23"
    data = await _get_json(f"{BASE}/api/qt/clist/get", {
        "pn": "1", "pz": str(limit), "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f3", "fs": fs,
        "fields": "f12,f14,f2,f3,f5,f6,f7,f8,f15,f16,f17,f162,f167,f116,f117,f173",
    }, timeout=20.0)
    if not data or data.get("rc") != 0:
        return []
    diff = (data.get("data") or {}).get("diff") or []
    out = []
    for d in diff:
        raw_code = d.get("f12")
        if not raw_code:
            continue
        market = "sh" if str(raw_code).startswith("6") else "sz"
        out.append({
            "code": f"{market}.{raw_code}",
            "name": d.get("f14") or "",
            "price": _num(d.get("f2")),
            "change_pct": _num(d.get("f3")),
            "volume": _num(d.get("f5")),
            "amount": _num(d.get("f6")),
            "amplitude": _num(d.get("f7")),
            "turnover": _num(d.get("f8")),
            "high": _num(d.get("f15")),
            "low": _num(d.get("f16")),
            "open": _num(d.get("f17")),
            "pe_ttm": _num(d.get("f162")),
            "pb": _num(d.get("f167")),
            "total_market_cap": _num(d.get("f116")),
            "float_market_cap": _num(d.get("f117")),
            "roe": _num(d.get("f173")),
        })
    return out
