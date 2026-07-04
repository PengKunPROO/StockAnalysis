TEST_CODE = "sh.600519"
TEST_NAME = "贵州茅台"


def test_watchlist_get(client):
    r = client.get("/api/v1/watchlist")
    assert r.status_code == 200
    assert "stocks" in r.json()


def test_watchlist_add(client):
    r = client.post("/api/v1/watchlist", json={"code": TEST_CODE, "name": TEST_NAME})
    assert r.status_code == 200
    assert r.json().get("added") == TEST_CODE


def test_watchlist_delete(client):
    r = client.delete(f"/api/v1/watchlist/{TEST_CODE}")
    assert r.status_code == 200
