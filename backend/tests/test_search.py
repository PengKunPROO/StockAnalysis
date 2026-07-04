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
