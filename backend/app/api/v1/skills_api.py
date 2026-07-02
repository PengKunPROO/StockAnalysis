from fastapi import APIRouter, UploadFile, File, HTTPException
from app.diagnosis.skills_manager import list_skills, get_skill_content, save_skill, delete_skill

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def api_list_skills():
    return {"skills": list_skills()}


@router.get("/{name}")
async def api_get_skill(name: str):
    content = get_skill_content(name)
    if content is None:
        raise HTTPException(404, f"Skill '{name}' not found")
    return {"name": name, "content": content}


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
