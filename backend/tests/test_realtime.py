def test_realtime_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    assert r.status_code == 200
    data = r.json()
    assert data["price"] is not None and data["price"] > 0


def test_realtime_fields(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    for field in ["price", "change_pct", "volume", "high", "low"]:
        assert field in data, f"Missing field: {field}"


def test_realtime_change_pct_is_number(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    assert isinstance(data["change_pct"], (int, float))


def test_realtime_not_found_404(client):
    r = client.get("/api/v1/stock/xx.999999/realtime")
    assert r.status_code == 404
    assert "error" in r.json()


def test_realtime_with_warning_key(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/realtime")
    data = r.json()
    assert "warning" in data
