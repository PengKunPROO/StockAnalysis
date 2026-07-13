"""Discover and load skills from local hermes installation."""
import re
import os
from pathlib import Path

HERMES_SKILLS_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes\skills"))

FINANCE_KEYWORDS = ['股票', '金融', '投资', 'A股', '财报', '估值', 'ESG', '红利', '分红',
    '市场', '交易', '技术分析', '基本面', '量化', '基金', '证券', '股息', '因子',
    'stock', 'finance', 'invest', 'market', 'trade', 'portfolio']


def _is_finance_skill(name: str, description: str) -> bool:
    text = (name + " " + description).lower()
    return any(kw.lower() in text for kw in FINANCE_KEYWORDS)


def _parse_frontmatter(content: str) -> dict:
    match = re.match(r'^---\s*\r?\n(.*?)\r?\n---\s*\r?\n', content, re.DOTALL)
    if not match:
        return {}
    try:
        import yaml
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def _find_skill_dirs(root: Path) -> list[Path]:
    """Find all skill directories containing SKILL.md"""
    result = []
    if not root.exists():
        return result
    for md_file in root.rglob("SKILL.md"):
        result.append(md_file.parent)
    return result


def list_hermes_skills() -> list[dict]:
    """List all installed hermes skills with metadata (filtered to finance-relevant only)."""
    skills = []
    for skill_dir in _find_skill_dirs(HERMES_SKILLS_DIR):
        md_path = skill_dir / "SKILL.md"
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = _parse_frontmatter(content)
        name = meta.get("name", skill_dir.name)
        desc = meta.get("description", "")
        if not _is_finance_skill(name, desc):
            continue
        source = "hermes"
        if (skill_dir / ".builtin").exists() or skill_dir.name in ("claude-code", "codex", "hermes-agent", "opencode"):
            source = "hermes-builtin"
        skills.append({
            "name": name,
            "description": desc,
            "mode": meta.get("mode", "general"),
            "source": source,
            "path": str(skill_dir.relative_to(HERMES_SKILLS_DIR)),
        })
    return skills


def get_hermes_skill_content(name: str) -> str | None:
    """Get SKILL.md content for a hermes skill by name."""
    for skill_dir in _find_skill_dirs(HERMES_SKILLS_DIR):
        md_path = skill_dir / "SKILL.md"
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = _parse_frontmatter(content)
        if meta.get("name") == name or skill_dir.name == name:
            return content
    return None
