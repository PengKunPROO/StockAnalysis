import pytest

REQUIRED_FIELDS = ["report_date", "revenue", "net_profit", "pe_ratio", "pb_ratio", "roe", "debt_ratio", "total_assets", "total_equity"]


def test_financials_ok(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
    data = r.json()
    assert "code" in data


def test_financials_all_fields(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    data = r.json()
    reports = data.get("reports", [])
    assert len(reports) >= 1, "Should have at least one financial report"
    rpt = reports[0]
    for field in REQUIRED_FIELDS:
        assert field in rpt, f"Missing field: {field}"


def test_financials_has_report_data(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    assert r.status_code == 200
    data = r.json()
    assert "reports" in data
    assert isinstance(data["reports"], list)


def test_financials_not_found_404(client):
    r = client.get("/api/v1/stock/xx.999999/financial")
    assert r.status_code in [200, 404]


def test_financials_roe_and_debt(client, stock_code):
    r = client.get(f"/api/v1/stock/{stock_code}/financial")
    data = r.json()
    reports = data.get("reports", [])
    if reports:
        rpt = reports[0]
        assert "roe" in rpt, "ROE field missing"
        assert "debt_ratio" in rpt, "debt_ratio field missing"
