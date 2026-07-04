def test_skills_list(client):
    r = client.get("/api/v1/skills")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert len(skills) >= 1
    names = [s["name"] for s in skills]
    assert "股票分析" in names


def test_skills_get_by_name(client):
    r = client.get("/api/v1/skills/股票分析")
    assert r.status_code == 200
    assert "content" in r.json()


def test_skills_get_not_found(client):
    r = client.get("/api/v1/skills/nonexistent_skill_xyz")
    assert r.status_code == 404
