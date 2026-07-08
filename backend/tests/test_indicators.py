def test_indicators_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) > 0


def test_indicators_has_all(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    last = r.json()["data"][-1]
    for key in ["macd", "rsi", "kdj", "boll", "atr"]:
        assert key in last, f"Missing: {key}"


def test_indicators_days_param(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=30")
    assert r.status_code == 200
    assert len(r.json()["data"]) <= 30


def test_indicators_days_boundary_20(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=20")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) <= 20
    assert len(data) > 0


def test_indicators_invalid_period_422(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?period=minute&days=60")
    assert r.status_code == 422


def test_indicators_invalid_days_422(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=10")
    assert r.status_code == 422


def test_indicators_response_structure(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/indicators?days=60")
    data = r.json()
    assert "code" in data
    assert "period" in data
    assert "data" in data
    assert "fibonacci" in data


# ---- ATR unit tests (pure compute, no network) ----
def _gen_klines(n=30, base=100.0):
    return [
        {"date": f"2026-01-{i+1:02d}", "open": base, "high": base + 2,
         "low": base - 2, "close": base + (1 if i % 2 == 0 else -1),
         "volume": 1000, "amount": 10000.0}
        for i in range(n)
    ]


def test_atr_warmup_none():
    from app.indicators.atr import compute_atr
    out = compute_atr(_gen_klines(30), period=14)
    assert len(out) == 30
    # first period-1 bars are None
    assert all(b["atr14"] is None for b in out[:13])
    # seed bar at index period-1 is a number
    assert out[13]["atr14"] is not None
    assert all(b["atr14"] is not None for b in out[13:])


def test_atr_positive_and_decreasing_volatility():
    from app.indicators.atr import compute_atr
    klines = _gen_klines(30)
    out = compute_atr(klines, period=14)
    # ATR must be positive (TR is always >= 0, and bars have range 4)
    assert out[-1]["atr14"] > 0


def test_atr_length_matches_input():
    from app.indicators.atr import compute_atr
    klines = _gen_klines(20)
    assert len(compute_atr(klines, period=14)) == 20
    assert len(compute_atr([], period=14)) == 0


# ---- Fibonacci unit tests ----
def test_fibonacci_returns_none_for_short_data():
    from app.indicators.fibonacci import compute_fibonacci
    assert compute_fibonacci(_gen_klines(3)) is None


def test_fibonacci_levels_between_high_and_low():
    from app.indicators.fibonacci import compute_fibonacci
    fib = compute_fibonacci(_gen_klines(60))
    assert fib is not None
    assert fib["direction"] in ("up", "down")
    levels = fib["levels"]
    # 0% and 78.6% bounds should be high/low (or low/high) depending on direction
    if fib["direction"] == "up":
        assert levels["0.0"] == fib["high"]
        assert levels["78.6"] < fib["high"]
        assert levels["78.6"] > fib["low"]
    else:
        assert levels["0.0"] == fib["low"]
        assert levels["78.6"] > fib["low"]
        assert levels["78.6"] < fib["high"]
    # all levels within [low, high]
    for v in levels.values():
        assert fib["low"] - 1e-6 <= v <= fib["high"] + 1e-6


def test_fibonacci_has_six_levels():
    from app.indicators.fibonacci import compute_fibonacci
    fib = compute_fibonacci(_gen_klines(60))
    assert set(fib["levels"].keys()) == {"0.0", "23.6", "38.2", "50.0", "61.8", "78.6"}
