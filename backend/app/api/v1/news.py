from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, subprocess, os, re
from datetime import date
from app.db.database import get_session_factory
from app.db.models import StockNews

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/stock/{code}")
async def get_news(code: str):
    today = date.today()
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(StockNews).where(
                StockNews.stock_code == code,
                StockNews.fetched_at == today,
            ).order_by(StockNews.id.desc())
        )
        cached = result.scalars().all()
        if cached:
            return {"code": code, "news": [
                {"id": n.id, "title": n.title, "source": n.source, "url": n.url, "summary": n.summary}
                for n in cached
            ], "cached": True}

    prompt = f'搜索 "{code}" 最近3天的重要财经新闻，返回JSON数组，格式: [{{"title":"...","source":"东方财富/雪球/新浪等","url":"...","summary":"一句话摘要"}}]。只返回JSON，不要其他文字。最多5条。'

    env = {**os.environ, "NO_COLOR": "1"}
    proc = subprocess.Popen(
        ["hermes", "chat", "-q", prompt],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True, encoding="utf-8", errors="replace",
    )

    output = proc.stdout.read()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"code": code, "news": [], "cached": False, "error": "News fetch timeout"}

    json_match = re.search(r'\[[\s\S]*\]', output)
    if not json_match:
        return {"code": code, "news": [], "cached": False}

    try:
        articles = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {"code": code, "news": [], "cached": False}

    async with factory() as session:
        for a in articles[:5]:
            session.add(StockNews(
                stock_code=code, title=a.get("title", ""),
                source=a.get("source", ""), url=a.get("url", ""),
                summary=a.get("summary", ""), fetched_at=today,
            ))
        await session.commit()

    return {"code": code, "news": [
        {"title": a.get("title", ""), "source": a.get("source", ""), "url": a.get("url", ""), "summary": a.get("summary", "")}
        for a in articles[:5]
    ], "cached": False}


class AnalyzeRequest(BaseModel):
    title: str
    source: str = ""
    summary: str = ""


@router.post("/stock/{code}/analyze")
async def analyze_news(code: str, req: AnalyzeRequest):
    prompt = f'分析这条新闻对股票 {code} 的影响。结合技术面和基本面，判断是利好/利空/中性，短期和中期影响。\n\n新闻: {req.title}\n来源: {req.source}\n摘要: {req.summary}\n\n请用中文简要分析，给出影响评级（强利好/利好/中性/利空/强利空）。'

    async def event_stream():
        env = {**os.environ, "NO_COLOR": "1"}
        proc = subprocess.Popen(
            ["hermes", "chat", "-q", prompt],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, encoding="utf-8", errors="replace",
        )
        in_analysis = False
        for line in proc.stdout:
            if '╭─' in line: in_analysis = True; continue
            if '╰─' in line: continue
            if not in_analysis: continue
            clean = line.strip()
            if clean:
                yield f"data: {json.dumps({'content': clean + chr(10)}, ensure_ascii=False)}\n\n"
        proc.wait()
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
