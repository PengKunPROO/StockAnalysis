def test_search_by_code(client):
    r = client.get("/api/v1/search?q=600519")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) > 0
    assert any("茅台" in s["name"] for s in results)


def test_search_by_name(client):
    r = client.get("/api/v1/search?q=贵州茅台")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) > 0


def test_search_empty(client):
    r = client.get("/api/v1/search?q=zzz_nonexistent_xyz")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 0


def test_search_result_structure(client):
    r = client.get("/api/v1/search?q=600519")
    assert r.status_code == 200
    for s in r.json()["results"]:
        for field in ["code", "name", "market"]:
            assert field in s, f"Missing field: {field}"


def test_search_count_field(client):
    r = client.get("/api/v1/search?q=600519")
    data = r.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= len(data["results"])


def test_search_with_market_filter(client):
    r = client.get("/api/v1/search?q=600519&market=a_share")
    assert r.status_code == 200
    for s in r.json()["results"]:
        assert s["market"] == "a_share", f"Expected a_share, got {s['market']}"


def test_search_invalid_market_422(client):
    r = client.get("/api/v1/search?q=test&market=invalid")
    assert r.status_code == 422
