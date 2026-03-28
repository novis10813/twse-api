"""
Shared test fixtures.
Uses aiosqlite in-memory DB with SQLite-compatible models.
"""
import pytest
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class SqliteBase(DeclarativeBase):
    pass


class SqliteStockInstitutional(SqliteBase):
    __tablename__ = "twse_stock_institutional_investors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "stock_id", "name"),)


class SqliteTotalInstitutional(SqliteBase):
    __tablename__ = "twse_total_institutional_investors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "name"),)


class SqliteStockMargin(SqliteBase):
    __tablename__ = "twse_stock_margin"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    MarginPurchaseBuy = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseSell = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseCashRepayment = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseTodayBalance = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseYesterdayBalance = Column(BigInteger, nullable=False, default=0)
    MarginPurchaseLimit = Column(BigInteger, nullable=False, default=0)
    ShortSaleBuy = Column(BigInteger, nullable=False, default=0)
    ShortSaleSell = Column(BigInteger, nullable=False, default=0)
    ShortSaleCashRepayment = Column(BigInteger, nullable=False, default=0)
    ShortSaleTodayBalance = Column(BigInteger, nullable=False, default=0)
    ShortSaleYesterdayBalance = Column(BigInteger, nullable=False, default=0)
    ShortSaleLimit = Column(BigInteger, nullable=False, default=0)
    OffsetLoanAndShort = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class SqliteTotalMargin(SqliteBase):
    __tablename__ = "twse_total_margin"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(30), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    TodayBalance = Column(BigInteger, nullable=False, default=0)
    YesBalance = Column(BigInteger, nullable=False, default=0)
    Return = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "name"),)


@pytest.fixture
async def test_session():
    """In-memory SQLite session for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SqliteBase.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()
