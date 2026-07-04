def test_health_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_has_datasources(client):
    r = client.get("/api/v1/health")
    sources = r.json()["datasources"]
    assert "tonghuashun" in sources


def test_health_db_connected(client):
    r = client.get("/api/v1/health")
    assert r.json()["database"] == "connected"
