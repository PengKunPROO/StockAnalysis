def compute_macd(klines: list[dict], fast=12, slow=26, signal=9) -> list[dict]:
    closes = [k["close"] for k in klines]

    def _ema(data, period):
        result = []
        multiplier = 2 / (period + 1)
        for i, val in enumerate(data):
            if i < period:
                result.append(None)
            elif i == period:
                result.append(sum(data[:period]) / period)
            else:
                result.append((val - result[-1]) * multiplier + result[-1])
        return result

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    dif = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif[i] = ema_fast[i] - ema_slow[i]

    # DEA = EMA of DIF values
    dif_valid = [d for d in dif if d is not None]
    dea_raw = _ema(dif_valid, signal)
    dea = [None] * len(closes)
    start = slow  # first valid DIF index
    for j, dv in enumerate(dea_raw):
        idx = start + j
        if dv is not None:
            dea[idx] = dv

    result = []
    for i in range(len(closes)):
        d, e = dif[i], dea[i]
        if d is not None and e is not None:
            result.append({"dif": round(d, 4), "dea": round(e, 4), "macd": round((d - e) * 2, 4)})
        else:
            result.append({"dif": None, "dea": None, "macd": None})
    return result
