from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.diagnosis.skills_manager import list_skills, get_skill_content, save_skill, delete_skill
from app.diagnosis.hermes_skills import list_hermes_skills, get_hermes_skill_content

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def api_list_skills(source: str = Query(default="all", description="all | uploaded | hermes")):
    uploaded = list_skills()
    for s in uploaded:
        s["source"] = "uploaded"

    if source == "uploaded":
        return {"skills": uploaded}
    if source == "hermes":
        return {"skills": list_hermes_skills()}

    # all: merge, hermes skills first
    hermes = list_hermes_skills()
    seen = {s["name"] for s in uploaded}
    result = list(hermes)
    for s in uploaded:
        if s["name"] not in seen:
            result.append(s)
        else:
            s["source"] = "uploaded (override)"
            result.append(s)
    return {"skills": result}


@router.get("/{name}")
async def api_get_skill(name: str):
    content = get_skill_content(name)
    if content is not None:
        return {"name": name, "content": content, "source": "uploaded"}
    content = get_hermes_skill_content(name)
    if content is not None:
        return {"name": name, "content": content, "source": "hermes"}
    raise HTTPException(404, f"Skill '{name}' not found")


@router.post("/upload")
async def api_upload_skill(file: UploadFile = File(...)):
    if not file.filename.endswith(".md"):
        raise HTTPException(400, "Only .md files allowed")
    content = await file.read()
    result = save_skill(file.filename, content)
    return result


@router.delete("/{name}")
async def api_delete_skill(name: str):
    if not delete_skill(name):
        raise HTTPException(404, f"Skill '{name}' not found")
    return {"deleted": name}
