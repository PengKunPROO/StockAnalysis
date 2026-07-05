"""Skill file management."""
import re
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def _parse_frontmatter(content: str) -> dict:
    match = re.match(r'^---\s*\r?\n(.*?)\r?\n---\s*\r?\n', content, re.DOTALL)
    if not match:
        return {}
    try:
        import yaml
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def list_skills() -> list[dict]:
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for f in sorted(SKILLS_DIR.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        skills.append({
            "name": meta.get("name", f.stem),
            "description": meta.get("description", ""),
            "mode": meta.get("mode", "general"),
            "filename": f.name,
        })
    return skills


def get_skill_content(name: str) -> str | None:
    for f in SKILLS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        if meta.get("name") == name or f.stem == name:
            return content
    return None


def save_skill(filename: str, content: bytes) -> dict:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = SKILLS_DIR / filename
    path.write_bytes(content)
    text = path.read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    return {
        "name": meta.get("name", path.stem),
        "description": meta.get("description", ""),
        "mode": meta.get("mode", "general"),
        "filename": filename,
    }


def delete_skill(name: str) -> bool:
    for f in SKILLS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        if meta.get("name") == name or f.stem == name:
            f.unlink()
            return True
    return False
