from sqlalchemy import Column, String, Date, Integer, BigInteger, Numeric, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    code = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    market = Column(String(10), nullable=False)
    industry = Column(String(50))
    list_date = Column(Date)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DailyKline(Base):
    __tablename__ = "stock_daily"

    code = Column(String(20), primary_key=True)
    trade_date = Column(Date, primary_key=True)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    volume = Column(BigInteger)
    amount = Column(Numeric(20, 2))


class Financial(Base):
    __tablename__ = "stock_financial"

    code = Column(String(20), primary_key=True)
    report_date = Column(Date, primary_key=True)
    revenue = Column(Numeric(20, 2))
    net_profit = Column(Numeric(20, 2))
    pe_ratio = Column(Numeric(12, 4))
    pb_ratio = Column(Numeric(12, 4))
    roe = Column(Numeric(8, 4))
    debt_ratio = Column(Numeric(8, 4))
    total_assets = Column(Numeric(20, 2))
    total_equity = Column(Numeric(20, 2))


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False)
    data_type = Column(String(20), nullable=False)
    code = Column(String(20))
    status = Column(String(10), nullable=False)
    rows_count = Column(Integer, default=0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_msg = Column(Text)


from sqlalchemy import ForeignKey


class DiagnosisSession(Base):
    __tablename__ = "diagnosis_sessions"
    id = Column(String(36), primary_key=True)
    skill_name = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SessionStock(Base):
    __tablename__ = "session_stocks"
    session_id = Column(String(36), ForeignKey("diagnosis_sessions.id"), primary_key=True)
    stock_code = Column(String(20), primary_key=True)
    stock_name = Column(String(100), nullable=False)


class DiagnosisMessage(Base):
    __tablename__ = "diagnosis_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("diagnosis_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text)
    tool_calls = Column(Text)
    tool_call_id = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())


class StockNews(Base):
    __tablename__ = "stock_news"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    title = Column(Text, nullable=False)
    source = Column(String(100))
    url = Column(Text)
    summary = Column(Text)
    published_at = Column(String(50))
    fetched_at = Column(Date, nullable=False)
    __table_args__ = (UniqueConstraint('stock_code', 'title', 'fetched_at'),)
