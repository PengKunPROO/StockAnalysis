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

    # Verify it appears in list
    r2 = client.get("/api/v1/skills")
    names = [s["name"] for s in r2.json()["skills"]]
    assert "test-skill" in names

    # Delete it
    r3 = client.delete("/api/v1/skills/test-skill")
    assert r3.status_code == 200

    # Verify removed
    r4 = client.get("/api/v1/skills")
    names2 = [s["name"] for s in r4.json()["skills"]]
    assert "test-skill" not in names2
