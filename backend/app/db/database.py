from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        connect_args = {}
        if "sqlite" in settings.database_url:
            connect_args = {"check_same_thread": False}
        _engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine():
    """Dispose the DB engine and close all connections. Called on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db():
    from app.db.models import Base, StockNews
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Ensure new tables/columns created (SQLite doesn't auto-migrate)
        await conn.run_sync(StockNews.__table__.create, checkfirst=True)
        # Add published_at column if missing (migration for existing DBs)
        from sqlalchemy import text as _text
        try:
            await conn.execute(_text("ALTER TABLE stock_news ADD COLUMN published_at VARCHAR(50)"))
        except Exception:
            pass  # Column already exists
        # Add group_name to stocks
        try:
            await conn.execute(_text("ALTER TABLE stocks ADD COLUMN group_name VARCHAR(50) DEFAULT '默认分组'"))
        except Exception:
            pass
