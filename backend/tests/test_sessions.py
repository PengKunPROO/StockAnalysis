import json

def test_session_list_returns_200(client):
    r = client.get("/api/v1/diagnosis/sessions")
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data or isinstance(data, list)


def test_session_crud(client):
    # Create a session via chat
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析", "message": "测试",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    assert r.status_code == 200
    sid = None
    for line in r.text.split("\n"):
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("session_id"):
                sid = d["session_id"]
    assert sid is not None, f"No session_id in SSE: {r.text[:200]}"

    # List sessions
    r2 = client.get("/api/v1/diagnosis/sessions")
    sessions = r2.json().get("sessions", [])
    assert any(s.get("id") == sid for s in sessions), f"Session {sid} not in list"


def test_session_detail(client):
    # Create session first
    r = client.post("/api/v1/diagnosis/chat", json={
        "skill": "股票分析", "message": "测试",
        "stock_codes": [{"code": "sh.600519", "name": "贵州茅台"}],
    })
    sid = None
    for line in r.text.split("\n"):
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("session_id"):
                sid = d["session_id"]
    if sid:
        r3 = client.get(f"/api/v1/diagnosis/sessions/{sid}")
        assert r3.status_code == 200
