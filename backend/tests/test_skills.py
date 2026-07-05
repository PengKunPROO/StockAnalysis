def test_skills_list(client):
    r = client.get("/api/v1/skills")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert len(skills) >= 1
    names = [s["name"] for s in skills]
    assert "股票分析" in names


def test_skills_list_source_all(client):
    r = client.get("/api/v1/skills?source=all")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert len(skills) > 0
    for s in skills:
        assert "source" in s, f"Skill {s['name']} missing source field"


def test_skills_list_source_uploaded(client):
    r = client.get("/api/v1/skills?source=uploaded")
    assert r.status_code == 200
    for s in r.json()["skills"]:
        assert s["source"] == "uploaded", f"Expected uploaded, got {s.get('source')}"


def test_skills_list_source_hermes(client):
    r = client.get("/api/v1/skills?source=hermes")
    assert r.status_code == 200
    for s in r.json()["skills"]:
        assert s["source"] in ("hermes", "hermes-builtin"), f"Unexpected source: {s.get('source')}"


def test_skills_get_by_name(client):
    r = client.get("/api/v1/skills/股票分析")
    assert r.status_code == 200
    assert "content" in r.json()
    assert r.json().get("source") is not None


def test_skills_get_not_found(client):
    r = client.get("/api/v1/skills/nonexistent_skill_xyz")
    assert r.status_code == 404


def test_skills_upload_non_md_400(client):
    files = {"file": ("test.txt", b"hello", "text/plain")}
    r = client.post("/api/v1/skills/upload", files=files)
    assert r.status_code == 400


def test_skills_delete_nonexistent_404(client):
    r = client.delete("/api/v1/skills/nonexistent_xyz")
    assert r.status_code == 404


def test_skills_upload_and_delete(client):
    test_content = """---
name: test-skill
description: 测试用股票分析skill
mode: general
---
# 测试Skill
这是测试内容
"""
    files = {"file": ("test-skill.md", test_content.encode("utf-8"), "text/markdown")}
    r = client.post("/api/v1/skills/upload", files=files)
    assert r.status_code == 200

    r2 = client.get("/api/v1/skills")
    names = [s["name"] for s in r2.json()["skills"]]
    assert "test-skill" in names

    r3 = client.delete("/api/v1/skills/test-skill")
    assert r3.status_code == 200

    r4 = client.get("/api/v1/skills")
    names2 = [s["name"] for s in r4.json()["skills"]]
    assert "test-skill" not in names2
