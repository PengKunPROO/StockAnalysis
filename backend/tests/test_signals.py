"""Tests for 操作建议 signal engine + API."""
import pytest


def _bar(date, close, macd, rsi, kdj, boll, atr=None):
    """Build one indicator dict (matching compute_all output shape)."""
    return {
        "date": date, "_close": close,
        "macd": macd, "rsi": rsi, "kdj": kdj, "boll": boll, "atr": atr,
    }


def _kline(date, close):
    return {"date": date, "open": close, "high": close + 1, "low": close - 1,
            "close": close, "volume": 1000, "amount": 10000.0}


def _macd(dif, dea):
    return {"dif": dif, "dea": dea, "macd": round((dif - dea) * 2, 4)}


def _rsi(v):
    return {"rsi14": v}


def _kdj(k, d):
    return {"k": k, "d": d, "j": round(3 * k - 2 * d, 2)}


def _boll(upper, mid, lower):
    return {"upper": upper, "mid": mid, "lower": lower}


def _atr(v):
    return {"atr14": v}


# ---------- pure compute ----------
def test_empty_returns_safe_default():
    from app.signals import compute_signals
    out = compute_signals([], [])
    assert out["active_signals"] == []
    assert out["risk"] is None
    assert "数据不足" in out["summary"]


def test_macd_golden_cross_detected():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 101)]
    indicators = [
        _bar("2026-01-01", 100, _macd(1, 2), _rsi(50), _kdj(40, 50), _boll(102, 100, 98)),
        _bar("2026-01-02", 101, _macd(3, 2), _rsi(50), _kdj(40, 50), _boll(102, 100, 98)),
    ]
    out = compute_signals(klines, indicators)
    names = [s["name"] for s in out["active_signals"]]
    assert "MACD金叉" in names
    bull = [s for s in out["active_signals"] if s["name"] == "MACD金叉"][0]
    assert bull["direction"] == "bull"


def test_macd_death_cross_detected():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 101), _kline("2026-01-02", 100)]
    indicators = [
        _bar("2026-01-01", 101, _macd(3, 2), _rsi(50), _kdj(60, 50), _boll(102, 100, 98)),
        _bar("2026-01-02", 100, _macd(1, 2), _rsi(50), _kdj(60, 50), _boll(102, 100, 98)),
    ]
    out = compute_signals(klines, indicators)
    assert "MACD死叉" in [s["name"] for s in out["active_signals"]]


def test_rsi_oversold_and_overbought():
    from app.signals import compute_signals
    # oversold
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 99)]
    indicators = [
        _bar("2026-01-01", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(102, 100, 98)),
        _bar("2026-01-02", 99, _macd(2, 2), _rsi(25), _kdj(50, 50), _boll(102, 100, 98)),
    ]
    out = compute_signals(klines, indicators)
    assert any(s["name"] == "RSI超卖" and s["direction"] == "bull" for s in out["active_signals"])

    # overbought
    indicators[1] = _bar("2026-01-02", 99, _macd(2, 2), _rsi(75), _kdj(50, 50), _boll(102, 100, 98))
    out = compute_signals(klines, indicators)
    assert any(s["name"] == "RSI超买" and s["direction"] == "bear" for s in out["active_signals"])


def test_kdj_cross():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 101)]
    indicators = [
        _bar("2026-01-01", 100, _macd(2, 2), _rsi(50), _kdj(40, 50), _boll(102, 100, 98)),
        _bar("2026-01-02", 101, _macd(2, 2), _rsi(50), _kdj(60, 50), _boll(102, 100, 98)),
    ]
    out = compute_signals(klines, indicators)
    assert "KDJ金叉" in [s["name"] for s in out["active_signals"]]


def test_boll_breakout_up():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 105)]
    indicators = [
        _bar("2026-01-01", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(102, 100, 98)),
        _bar("2026-01-02", 105, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(102, 100, 98)),
    ]
    out = compute_signals(klines, indicators)
    assert any(s["name"] == "BOLL突破上轨" and s["direction"] == "bull" for s in out["active_signals"])


def test_score_bullish_when_bull_signals():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 101)]
    indicators = [
        _bar("2026-01-01", 100, _macd(1, 2), _rsi(50), _kdj(40, 50), _boll(102, 100, 98), _atr(1.0)),
        _bar("2026-01-02", 101, _macd(3, 2), _rsi(25), _kdj(60, 50), _boll(102, 100, 98), _atr(1.0)),
    ]
    out = compute_signals(klines, indicators)
    assert out["score"]["pct"] > 50
    assert out["score"]["label"] == "偏多"


def test_score_bearish_when_bear_signals():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 101), _kline("2026-01-02", 100)]
    indicators = [
        _bar("2026-01-01", 101, _macd(3, 2), _rsi(75), _kdj(60, 50), _boll(102, 100, 98), _atr(1.0)),
        _bar("2026-01-02", 100, _macd(1, 2), _rsi(75), _kdj(40, 50), _boll(102, 100, 98), _atr(1.0)),
    ]
    out = compute_signals(klines, indicators)
    assert out["score"]["pct"] < 50
    assert out["score"]["label"] == "偏空"


def test_risk_computation():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 100)]
    indicators = [
        _bar("2026-01-01", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(104, 100, 96), _atr(2.0)),
        _bar("2026-01-02", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(104, 100, 96), _atr(2.0)),
    ]
    out = compute_signals(klines, indicators)
    risk = out["risk"]
    assert risk is not None
    assert risk["atr"] == 2.0
    # stop = 100 - 2 = 98; take = boll upper 104 (>close); rr = (104-100)/2 = 2.0
    assert risk["stop_loss"] == 98.0
    assert risk["take_profit"] == 104.0
    assert risk["risk_reward_ratio"] == 2.0
    assert 0 <= risk["kelly_pct"] <= 50


def test_kelly_capped_at_50():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 100)]
    # huge rr -> take_profit = close + 1.7*atr; atr small so rr large
    indicators = [
        _bar("2026-01-01", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), None, _atr(0.5)),
        _bar("2026-01-02", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), None, _atr(0.5)),
    ]
    out = compute_signals(klines, indicators)
    assert out["risk"]["kelly_pct"] <= 50


def test_summary_built_and_mentions_levels():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 101)]
    indicators = [
        _bar("2026-01-01", 100, _macd(1, 2), _rsi(50), _kdj(40, 50), _boll(104, 100, 96), _atr(1.0)),
        _bar("2026-01-02", 101, _macd(3, 2), _rsi(50), _kdj(40, 50), _boll(104, 100, 96), _atr(1.0)),
    ]
    out = compute_signals(klines, indicators)
    assert out["summary"]
    assert "止损" in out["summary"]
    assert "仓位" in out["summary"]


def test_key_levels_include_boll():
    from app.signals import compute_signals
    klines = [_kline("2026-01-01", 100), _kline("2026-01-02", 100)]
    indicators = [
        _bar("2026-01-01", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(104, 100, 96), _atr(1.0)),
        _bar("2026-01-02", 100, _macd(2, 2), _rsi(50), _kdj(50, 50), _boll(104, 100, 96), _atr(1.0)),
    ]
    out = compute_signals(klines, indicators)
    sources = [lvl["source"] for lvl in out["key_levels"]]
    assert "布林上轨" in sources
    assert "布林下轨" in sources


# ---------- API ----------
def test_signals_api_get_structure(client, stock_code):
    r = client.get(f"/api/v1/signals/{stock_code}?days=90")
    # 200 when data loads, 503 when datasource unavailable - both acceptable, never 500
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        for key in ("active_signals", "score", "key_levels", "risk", "summary", "code"):
            assert key in data, f"Missing: {key}"
        assert data["score"]["pct"] in range(0, 101)


def test_signals_api_ai_stream_no_llm_key(client, stock_code, monkeypatch):
    """Without an LLM key, /ai still streams signals + error + done (no 500)."""
    from app.config import settings
    monkeypatch.setattr(settings, "diagnosis_llm_api_key", "")
    r = client.post(f"/api/v1/signals/{stock_code}/ai?days=90")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        body = r.text
        assert "data:" in body
        # always emits a done event (or error path)
        assert "done" in body or "error" in body


def _has_llm_key():
    from app.config import settings
    return bool(settings.diagnosis_llm_api_key)


@pytest.mark.skipif(not _has_llm_key(), reason="no llm key")
def test_signals_ai_streams_reasoning_or_content(client, stock_code):
    """bug2 修复: v4-pro 推理模型把答案放 reasoning_content, SSE 应能收到 reasoning 或 content。"""
    r = client.post(f"/api/v1/signals/{stock_code}/ai?days=90")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        body = r.text
        assert "signals" in body
        # 修复后应捕获 reasoning_content 或 content
        assert "reasoning" in body or "content" in body or "error" in body
