def compute_kdj(klines: list[dict], n=9, m1=3, m2=3) -> list[dict]:
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    closes = [k["close"] for k in klines]
    result = []
    k_vals = [50.0] * len(klines)
    d_vals = [50.0] * len(klines)
    for i in range(n - 1, len(klines)):
        hn = max(highs[i - n + 1:i + 1])
        ln = min(lows[i - n + 1:i + 1])
        rsv = (closes[i] - ln) / (hn - ln) * 100 if hn != ln else 50
        k_vals[i] = rsv * (1 / m1) + k_vals[i - 1] * (1 - 1 / m1)
        d_vals[i] = k_vals[i] * (1 / m2) + d_vals[i - 1] * (1 - 1 / m2)
    for i in range(len(klines)):
        k = round(k_vals[i], 2)
        d = round(d_vals[i], 2)
        j = round(3 * k - 2 * d, 2)
        result.append({"k": k if i >= n - 1 else None, "d": d if i >= n - 1 else None, "j": j if i >= n - 1 else None})
    return result
