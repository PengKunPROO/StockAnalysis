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


def test_watchlist_full_crud(client):
    code = "sh.601318"
    name = "中国平安"
    # Add
    r = client.post("/api/v1/watchlist", json={"code": code, "name": name})
    assert r.status_code == 200
    assert r.json()["added"] == code

    # Verify in list
    r = client.get("/api/v1/watchlist")
    stocks = r.json()["stocks"]
    assert any(s["code"] == code for s in stocks), "Added stock not found in watchlist"

    # Delete
    r = client.delete(f"/api/v1/watchlist/{code}")
    assert r.status_code == 200

    # Verify removed
    r = client.get("/api/v1/watchlist")
    stocks = r.json()["stocks"]
    assert not any(s["code"] == code for s in stocks), "Deleted stock still in watchlist"


def test_watchlist_delete(client):
    r = client.delete(f"/api/v1/watchlist/{TEST_CODE}")
    assert r.status_code == 200


def test_watchlist_delete_nonexistent_resilient(client):
    r = client.delete("/api/v1/watchlist/xx.nonexist")
    # Should not crash; may return 200 with error or 404
    assert r.status_code in (200, 404)
