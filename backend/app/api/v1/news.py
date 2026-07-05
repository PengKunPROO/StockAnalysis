from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio, json, subprocess, os
from datetime import date, datetime, timedelta
from app.db.database import get_session_factory
from app.db.models import StockNews
from app.engine.data_engine import engine as data_engine

router = APIRouter(prefix="/news", tags=["news"])

NEWS_DAYS_DEFAULT = 7


def _filter_recent(articles: list[dict], days: int) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    result = []
    for a in articles:
        pub_str = a.get("published_at", "")[:10]
        try:
            if date.fromisoformat(pub_str) >= cutoff:
                result.append(a)
        except (ValueError, TypeError):
            result.append(a)
    return result


async def _fetch_and_cache_news(code: str, limit: int = 10):
    today = date.today()
    articles, error = await data_engine.get_news(code, limit=max(limit * 3, 20))

    if not articles:
        return {"code": code, "news": [], "cached": False, "error": error or "暂未找到相关新闻"}, []

    factory = get_session_factory()
    async with factory() as session:
        for a in articles[:limit]:
            session.add(StockNews(
                stock_code=code, title=a["title"],
                source=a["source"], url=a["url"],
                summary=a["summary"], fetched_at=today,
                published_at=a.get("published_at", ""),
            ))
        await session.commit()

    return {"code": code, "news": [
        {**a, "fetched_at": today.isoformat()}
        for a in articles[:limit]
    ], "cached": False}, articles


@router.get("/stock/{code}")
async def get_news(
    code: str,
    refresh: bool = False,
    limit: int = 10,
    days: int = Query(default=NEWS_DAYS_DEFAULT, ge=1, le=30, description="Show news from last N days"),
):
    from sqlalchemy import select, delete
    today = date.today()
    factory = get_session_factory()

    if refresh:
        async with factory() as session:
            await session.execute(
                delete(StockNews).where(
                    StockNews.stock_code == code,
                    StockNews.fetched_at == today,
                )
            )
            await session.commit()
        result, _ = await _fetch_and_cache_news(code, limit)
        # Filter by days
        result["news"] = _filter_recent(result["news"], days)
        return result

    async with factory() as session:
        result = await session.execute(
            select(StockNews).where(
                StockNews.stock_code == code,
                StockNews.fetched_at == today,
            ).order_by(StockNews.id.desc())
        )
        cached = result.scalars().all()
        if cached:
            news_list = [
                {
                    "id": n.id, "title": n.title, "source": n.source,
                    "url": n.url, "summary": n.summary,
                    "published_at": getattr(n, "published_at", ""),
                }
                for n in cached
            ]
            news_list = _filter_recent(news_list, days)
            return {"code": code, "news": news_list, "cached": True}

    result, _ = await _fetch_and_cache_news(code, limit)
    result["news"] = _filter_recent(result["news"], days)
    return result


class AnalyzeRequest(BaseModel):
    title: str
    source: str = ""
    summary: str = ""


@router.post("/stock/{code}/analyze")
async def analyze_news(code: str, req: AnalyzeRequest):
    prompt = (
        f'分析这条新闻对股票 {code} 的影响。结合技术面和基本面，判断是利好/利空/中性，短期和中期影响。'
        f'\n\n新闻: {req.title}\n来源: {req.source}\n摘要: {req.summary}'
        f'\n\n请用中文简要分析，给出影响评级（强利好/利好/中性/利空/强利空）。'
    )

    async def event_stream():
        env = {**os.environ, "NO_COLOR": "1"}
        proc = subprocess.Popen(
            ["hermes", "chat", "-Q", "-q", prompt, "--max-turns", "1"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            clean = line.strip()
            if clean and not clean.startswith("session_id:"):
                yield f"data: {json.dumps({'content': clean + chr(10)}, ensure_ascii=False)}\n\n"
        proc.wait()
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
