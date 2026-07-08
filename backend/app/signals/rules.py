"""Rule-based signal engine — pure compute, no network.

Consumes klines + per-bar indicators (output of app.indicators.compute_all) and
an optional fibonacci dict, producing the structured payload for the 操作建议 panel.
"""
from typing import Any


def _last(indicators: list[dict], key: str) -> dict | None:
    """Last non-None entry for an indicator sub-dict (macd/rsi/kdj/boll/atr)."""
    for bar in reversed(indicators):
        val = bar.get(key)
        if val:
            return val
    return None


def _prev(indicators: list[dict], key: str) -> dict | None:
    """Second-to-last non-None entry for an indicator sub-dict."""
    found = 0
    for bar in reversed(indicators):
        val = bar.get(key)
        if val:
            found += 1
            if found == 2:
                return val
    return None


def _strength_from_mag(mag: float, scale: float) -> str:
    """Map a magnitude (0..1+) to 强/中/弱."""
    ratio = abs(mag) / scale if scale else 0
    if ratio >= 0.66:
        return "强"
    if ratio >= 0.33:
        return "中"
    return "弱"


def _detect_signals(indicators: list[dict]) -> list[dict]:
    signals: list[dict] = []
    if len(indicators) < 2:
        return signals

    macd_now = _last(indicators, "macd")
    macd_prev = _prev(indicators, "macd")
    rsi_now = _last(indicators, "rsi")
    kdj_now = _last(indicators, "kdj")
    kdj_prev = _prev(indicators, "kdj")
    boll_now = _last(indicators, "boll")

    last_bar = indicators[-1]
    date = last_bar.get("date", "")
    close = last_bar.get("_close")  # set by caller via _augment; fallback below

    # MACD cross
    if macd_now and macd_prev:
        dif_n, dea_n = macd_now.get("dif"), macd_now.get("dea")
        dif_p, dea_p = macd_prev.get("dif"), macd_prev.get("dea")
        if None not in (dif_n, dea_n, dif_p, dea_p):
            hist = abs(macd_now.get("macd") or 0)
            if dif_p <= dea_p and dif_n > dea_n:
                signals.append({
                    "name": "MACD金叉", "direction": "bull",
                    "strength": _strength_from_mag(hist, 0.5),
                    "detail": f"DIF上穿DEA · {date}", "date": date,
                })
            elif dif_p >= dea_p and dif_n < dea_n:
                signals.append({
                    "name": "MACD死叉", "direction": "bear",
                    "strength": _strength_from_mag(hist, 0.5),
                    "detail": f"DIF下穿DEA · {date}", "date": date,
                })

    # RSI overbought/oversold
    if rsi_now:
        rsi = rsi_now.get("rsi14")
        if rsi is not None:
            if rsi < 30:
                signals.append({
                    "name": "RSI超卖", "direction": "bull",
                    "strength": "强" if rsi < 20 else "中",
                    "detail": f"RSI={round(rsi, 1)} · {date}", "date": date,
                })
            elif rsi > 70:
                signals.append({
                    "name": "RSI超买", "direction": "bear",
                    "strength": "强" if rsi > 80 else "中",
                    "detail": f"RSI={round(rsi, 1)} · {date}", "date": date,
                })

    # KDJ cross
    if kdj_now and kdj_prev:
        k_n, d_n = kdj_now.get("k"), kdj_now.get("d")
        k_p, d_p = kdj_prev.get("k"), kdj_prev.get("d")
        if None not in (k_n, d_n, k_p, d_p):
            if k_p <= d_p and k_n > d_n:
                signals.append({
                    "name": "KDJ金叉", "direction": "bull",
                    "strength": _strength_from_mag(k_n - d_n, 5),
                    "detail": f"K上穿D · {date}", "date": date,
                })
            elif k_p >= d_p and k_n < d_n:
                signals.append({
                    "name": "KDJ死叉", "direction": "bear",
                    "strength": _strength_from_mag(k_n - d_n, 5),
                    "detail": f"K下穿D · {date}", "date": date,
                })

    # BOLL breakout
    if boll_now:
        upper = boll_now.get("upper")
        lower = boll_now.get("lower")
        mid = boll_now.get("mid")
        c = close
        if c is not None and upper is not None and lower is not None and mid is not None:
            if c > upper:
                signals.append({
                    "name": "BOLL突破上轨", "direction": "bull", "strength": "中",
                    "detail": f"收盘{c}破上轨{upper} · {date}", "date": date,
                })
            elif c < lower:
                signals.append({
                    "name": "BOLL跌破下轨", "direction": "bear", "strength": "中",
                    "detail": f"收盘{c}破下轨{lower} · {date}", "date": date,
                })
            elif lower is not None and mid is not None and c <= lower + (mid - lower) * 0.1:
                signals.append({
                    "name": "BOLL触下轨", "direction": "bull", "strength": "弱",
                    "detail": f"收盘贴近下轨{lower} · {date}", "date": date,
                })

    return signals


def _compute_score(signals: list[dict]) -> dict:
    """Aggregate active signals into a -100..100 score and 0..100 pct."""
    weight = {"强": 30, "中": 18, "弱": 8}
    score = 0
    for s in signals:
        w = weight.get(s.get("strength", "中"), 18)
        score += w if s["direction"] == "bull" else -w
    score = max(-100, min(100, score))
    pct = round(50 + score / 2)  # 0..100, 50 = neutral
    if pct >= 65:
        label = "偏多"
    elif pct <= 35:
        label = "偏空"
    else:
        label = "中性"
    return {"value": score, "pct": pct, "label": label}


def _key_levels(boll: dict | None, fibonacci: dict | None, close: float | None) -> list[dict]:
    levels: list[dict] = []
    if boll:
        upper, lower = boll.get("upper"), boll.get("lower")
        if upper is not None:
            levels.append({"price": round(upper, 2), "type": "阻力", "source": "布林上轨", "note": "BOLL upper"})
        if lower is not None:
            levels.append({"price": round(lower, 2), "type": "支撑", "source": "布林下轨", "note": "BOLL lower"})
    if fibonacci and fibonacci.get("levels"):
        for pct_str in ["38.2", "50.0", "61.8"]:
            price = fibonacci["levels"].get(pct_str)
            if price is not None and close is not None and abs(price - close) / (close or 1) < 0.15:
                levels.append({
                    "price": round(price, 2), "type": "斐波",
                    "source": f"斐波{pct_str}%", "note": f"Fibonacci {pct_str}%",
                })
    # sort by price desc
    levels.sort(key=lambda x: x["price"], reverse=True)
    return levels


def _compute_risk(atr: float | None, close: float, boll_upper: float | None) -> dict:
    atr_val = atr if atr and atr > 0 else close * 0.02  # fallback 2% if no ATR
    stop_loss = close - atr_val
    take_profit = boll_upper if (boll_upper and boll_upper > close) else close + 1.7 * atr_val
    stop_pct = -atr_val / close * 100 if close else 0
    tp_pct = (take_profit - close) / close * 100 if close else 0
    rr = (take_profit - close) / atr_val if atr_val else 0

    # Kelly: derive win prob p from a notional edge; cap position at 50%
    # p mapped from risk-reward; conservative: p = 0.55 baseline, +edge from rr
    p = min(0.70, 0.55 + min(rr, 2.0) * 0.05)
    kelly_raw = p - (1 - p) / max(rr, 0.1)
    kelly_pct = max(0, min(0.5, kelly_raw)) * 100

    return {
        "atr": round(atr_val, 4),
        "stop_loss": round(stop_loss, 2),
        "stop_loss_pct": round(stop_pct, 2),
        "take_profit": round(take_profit, 2),
        "take_profit_pct": round(tp_pct, 2),
        "kelly_pct": round(kelly_pct, 0),
        "risk_reward_ratio": round(rr, 2),
    }


def _build_summary(signals: list[dict], score: dict, risk: dict, close: float | None) -> str:
    if not signals:
        return f"当前无活跃信号，整体{score['label']}（{score['pct']}%）。建议观望，等待信号明确。"
    bull = [s["name"] for s in signals if s["direction"] == "bull"]
    bear = [s["name"] for s in signals if s["direction"] == "bear"]
    parts = []
    if bull:
        parts.append("+".join(bull))
    if bear:
        parts.append("+".join(bear))
    combo = "组合".join(["，".join([",".join(bull), ",".join(bear)]) if bull or bear else ""])
    sig_text = "+".join(bull + bear) if (bull or bear) else "无"
    trend = "反弹/上涨" if score["pct"] >= 50 else "调整/下跌"
    buy_lo = round(risk["stop_loss"], 2) if close else 0
    buy_hi = round(close, 2) if close else 0
    return (
        f"{sig_text}信号触发，整体{score['label']}（{score['pct']}%），短线{trend}倾向。"
        f"建议{buy_lo}-{buy_hi}区间分批关注，止损{risk['stop_loss']}（{risk['stop_loss_pct']}%），"
        f"目标{risk['take_profit']}（{risk['take_profit_pct']}%），仓位约{risk['kelly_pct']}%。"
    )


def compute_signals(
    klines: list[dict],
    indicators: list[dict],
    fibonacci: dict | None = None,
) -> dict[str, Any]:
    """Compute the full 操作建议 payload. Pure function — no side effects."""
    if not klines or not indicators:
        return {
            "active_signals": [], "score": {"value": 0, "pct": 50, "label": "中性"},
            "key_levels": [], "risk": None, "summary": "数据不足，无法生成操作建议。",
        }

    # Augment indicators with close for signal detection (avoid coupling to kline index)
    last_close = klines[-1]["close"]
    indicators = [dict(b, _close=k["close"]) for b, k in zip(indicators, klines[-len(indicators):])]

    close = last_close
    atr_val = (_last(indicators, "atr") or {}).get("atr14")
    boll_now = _last(indicators, "boll")
    boll_upper = (boll_now or {}).get("upper")

    active = _detect_signals(indicators)
    score = _compute_score(active)
    levels = _key_levels(boll_now, fibonacci, close)
    risk = _compute_risk(atr_val, close, boll_upper)
    summary = _build_summary(active, score, risk, close)

    return {
        "active_signals": active,
        "score": score,
        "key_levels": levels,
        "risk": risk,
        "summary": summary,
    }
