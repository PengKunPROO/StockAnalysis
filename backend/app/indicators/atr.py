def compute_atr(klines: list[dict], period=14) -> list[dict]:
    """Average True Range (Wilder's smoothing), aligned by index."""
    result = []
    trs = []
    for i, k in enumerate(klines):
        if i == 0:
            tr = k["high"] - k["low"]
        else:
            prev_close = klines[i - 1]["close"]
            tr = max(
                k["high"] - k["low"],
                abs(k["high"] - prev_close),
                abs(k["low"] - prev_close),
            )
        trs.append(tr)
        if i < period - 1:
            result.append({"atr14": None})
        elif i == period - 1:
            atr = sum(trs[:period]) / period
            result.append({"atr14": round(atr, 4)})
        else:
            prev_atr = result[i - 1]["atr14"]
            atr = (prev_atr * (period - 1) + trs[i]) / period
            result.append({"atr14": round(atr, 4)})
    return result
