from fastapi import APIRouter
from app.engine.data_engine import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return await engine.health()
