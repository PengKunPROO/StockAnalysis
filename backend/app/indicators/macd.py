def compute_macd(klines: list[dict], fast=12, slow=26, signal=9) -> list[dict]:
    closes = [k["close"] for k in klines]
    def _ema(data, period):
        result = []
        multiplier = 2 / (period + 1)
        for i, val in enumerate(data):
            if i == 0:
                result.append(val)
            else:
                result.append((val - result[-1]) * multiplier + result[-1])
        return result
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    macd = [(d - e) * 2 for d, e in zip(dif, dea)]
    return [
        {"dif": round(dif[i], 4), "dea": round(dea[i], 4), "macd": round(macd[i], 4)}
        for i in range(len(klines))
    ]
