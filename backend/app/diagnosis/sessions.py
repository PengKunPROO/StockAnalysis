"""Session storage for AI diagnosis conversations."""
import uuid
from datetime import datetime
from app.db.database import get_session_factory
from app.db.models import DiagnosisSession, SessionStock, DiagnosisMessage


async def create_session(skill_name: str, model: str, stock_codes: list[dict]) -> str:
    sid = str(uuid.uuid4())
    factory = get_session_factory()
    async with factory() as session:
        session.add(DiagnosisSession(id=sid, skill_name=skill_name, model=model))
        for s in stock_codes:
            session.add(SessionStock(session_id=sid, stock_code=s["code"], stock_name=s["name"]))
        await session.commit()
    return sid


async def add_stock_to_session(session_id: str, code: str, name: str):
    factory = get_session_factory()
    async with factory() as session:
        session.add(SessionStock(session_id=session_id, stock_code=code, stock_name=name))
        await session.commit()


async def get_session_stocks(session_id: str) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(SessionStock).where(SessionStock.session_id == session_id)
        )
        return [{"code": s.stock_code, "name": s.stock_name} for s in result.scalars().all()]


async def get_messages(session_id: str) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DiagnosisMessage)
            .where(DiagnosisMessage.session_id == session_id)
            .order_by(DiagnosisMessage.id.asc())
        )
        return [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_call_id": m.tool_call_id,
                "created_at": str(m.created_at),
            }
            for m in result.scalars().all()
        ]


async def save_message(session_id: str, role: str, content: str = None,
                       tool_calls: str = None, tool_call_id: str = None):
    factory = get_session_factory()
    async with factory() as session:
        msg = DiagnosisMessage(
            session_id=session_id, role=role,
            content=content, tool_calls=tool_calls, tool_call_id=tool_call_id,
        )
        session.add(msg)
        from sqlalchemy import update
        await session.execute(
            update(DiagnosisSession).where(DiagnosisSession.id == session_id)
            .values(updated_at=datetime.now())
        )
        await session.commit()


async def list_sessions() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DiagnosisSession).order_by(DiagnosisSession.updated_at.desc()).limit(50)
        )
        return [
            {"id": s.id, "skill_name": s.skill_name, "model": s.model,
             "created_at": str(s.created_at), "updated_at": str(s.updated_at)}
            for s in result.scalars().all()
        ]
