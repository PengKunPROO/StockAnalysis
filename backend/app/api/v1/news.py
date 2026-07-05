from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio, json, subprocess, os, re
from datetime import date, datetime
from app.db.database import get_session_factory
from app.db.models import StockNews

router = APIRouter(prefix="/news", tags=["news"])


async def _fetch_news_akshare(code: str):
    """Fetch news via akshare for A-share stocks. Returns (result_dict, articles_list)."""
    today = date.today()

    if not code.startswith(("sh.", "sz.")):
        return {"code": code, "news": [], "cached": False, "error": "仅A股支持新闻获取"}, []

    raw_code = code.split(".", 1)[1]
    loop = asyncio.get_event_loop()

    def _fetch():
        import akshare as ak
        df = ak.stock_news_em(symbol=raw_code)
        # Column names: 关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接
        col_title = df.columns[1]
        col_content = df.columns[2]
        col_time = df.columns[3]
        col_source = df.columns[4]
        col_url = df.columns[5]

        articles = []
        for _, row in df.head(10).iterrows():
            title = str(row[col_title])
            content = str(row[col_content])[:200] if row[col_content] else ""
            pub_time = str(row[col_time])
            source = str(row[col_source])
            url = str(row[col_url])

            articles.append({
                "title": title,
                "source": source,
                "url": url,
                "summary": content,
            })
        return articles

    try:
        articles = await loop.run_in_executor(None, _fetch)
    except Exception as e:
        return {"code": code, "news": [], "cached": False, "error": f"新闻获取失败: {e}"}, []

    if not articles:
        return {"code": code, "news": [], "cached": False, "error": "暂未找到相关新闻"}, []

    factory = get_session_factory()
    async with factory() as session:
        for a in articles[:5]:
            session.add(StockNews(
                stock_code=code, title=a["title"],
                source=a["source"], url=a["url"],
                summary=a["summary"], fetched_at=today,
            ))
        await session.commit()

    return {"code": code, "news": [
        {"title": a["title"], "source": a["source"], "url": a["url"], "summary": a["summary"]}
        for a in articles[:5]
    ], "cached": False}, articles


@router.get("/stock/{code}")
async def get_news(code: str, refresh: bool = False):
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
        result, _ = await _fetch_news_akshare(code)
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
            return {"code": code, "news": [
                {"id": n.id, "title": n.title, "source": n.source, "url": n.url, "summary": n.summary}
                for n in cached
            ], "cached": True}

    result, _ = await _fetch_news_akshare(code)
    return result


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
