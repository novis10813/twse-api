# twse-api Chip DB & Margin 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 twse-api 加入 PostgreSQL 持久化層，將現有三大法人資料入庫，並新增融資融券（MI_MARGN）資料的爬取、儲存與查詢端點。

**Architecture:** FastAPI + SQLAlchemy async + asyncpg（Production）/ aiosqlite（Tests）。資料流為 DB-first cache：Router → Service → Repository（DB hit 直接回傳，DB miss 才呼叫 TWSEClient 爬取）。services 分為純 HTTP client（twse_client.py）與 business logic（chip.py、margin.py），對應 mops-financial-api 的分層模式。

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 async, asyncpg, aiosqlite（test）, pytest-asyncio, pytest-httpx, pydantic-settings

---

## File Map

| 動作 | 檔案 | 說明 |
|------|------|------|
| 修改 | `pyproject.toml` | 新增 DB + test 依賴 |
| 新增 | `app/config.py` | Pydantic Settings，TWSE_ prefix |
| 新增 | `.env.dev.example` | 環境變數範本 |
| 新增 | `docker-compose.dev.yml` | 本地 Postgres container |
| 新增 | `app/db/__init__.py` | 空 init |
| 新增 | `app/db/models.py` | SQLAlchemy ORM：4 個表 |
| 新增 | `app/db/connection.py` | async engine + session factory |
| 新增 | `app/db/repository.py` | CRUD：upsert 各表 |
| 新增 | `app/services/twse_client.py` | 純 HTTP layer（從 twse.py 拆出） |
| 修改 | `app/services/twse.py` | 刪除，邏輯移至 chip.py + twse_client.py |
| 新增 | `app/services/chip.py` | 三大法人 service（DB cache） |
| 修改 | `app/routers/chip.py` | 改用新 chip service |
| 新增 | `app/services/margin.py` | 融資融券 service（DB cache） |
| 新增 | `app/schemas/margin.py` | 融資融券 Pydantic schemas |
| 新增 | `app/routers/margin.py` | 融資融券 endpoints |
| 修改 | `app/main.py` | lifespan（init_db）+ 掛上 margin router |
| 新增 | `tests/__init__.py` | 空 init |
| 新增 | `tests/conftest.py` | aiosqlite test DB fixture |
| 新增 | `tests/test_repository.py` | Repository upsert 測試 |
| 新增 | `tests/test_chip_service.py` | chip service DB cache 測試 |
| 新增 | `tests/test_margin_parsing.py` | MI_MARGN JSON 解析測試 |
| 新增 | `tests/test_margin_service.py` | margin service DB cache 測試 |
| 新增 | `tests/test_margin_router.py` | margin router 整合測試 |
| 新增 | `pytest.ini` | asyncio_mode = auto |

---

## Task 1：依賴套件 + Config + Docker Compose

**Files:**
- Modify: `pyproject.toml`
- Create: `app/config.py`
- Create: `.env.dev.example`
- Create: `docker-compose.dev.yml`
- Create: `pytest.ini`

- [ ] **Step 1：更新 pyproject.toml**

```toml
[project]
name = "twse-api"
version = "0.1.0"
description = "REST API service for fetching TWSE (Taiwan Stock Exchange) chip data"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.28.1",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "pydantic-settings>=2.0",
]

[dependency-groups]
dev = [
    "aiosqlite>=0.20",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.35",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2：建立 app/config.py**

```python
"""TWSE API Configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TWSE_")

    # TWSE request settings
    request_timeout: float = 30.0
    max_retries: int = 3

    # Database settings
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "core-postgres"
    postgres_port: int = 5432
    postgres_db: str = "twse_db"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
```

- [ ] **Step 3：建立 .env.dev.example**

```
TWSE_POSTGRES_USER=postgres
TWSE_POSTGRES_PASSWORD=postgres
TWSE_POSTGRES_HOST=twse-postgres
TWSE_POSTGRES_PORT=5432
TWSE_POSTGRES_DB=twse_db
```

複製成 `.env.dev`（實際開發用，git-ignored）。

- [ ] **Step 4：建立 docker-compose.dev.yml**

```yaml
# Development Docker Compose for twse-api
# Uses local postgres (core-postgres 暫時關閉，待網路規劃完成後再遷移)
#
# Usage:
#   docker compose -f docker-compose.dev.yml up --build

services:
  twse-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: twse-api-dev
    restart: unless-stopped
    env_file:
      - .env.dev
    ports:
      - "8020:8000"
    volumes:
      - ./app:/app/app:ro
    depends_on:
      twse-postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  twse-postgres:
    image: postgres:15-alpine
    container_name: twse-postgres-dev
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: twse_db
    ports:
      - "5433:5432"
    volumes:
      - twse_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  twse_postgres_data:
```

- [ ] **Step 5：安裝依賴**

```bash
cd /mnt/raid1/novis/home-stack/twse-api
uv sync --dev
```

Expected: 成功安裝所有依賴，無錯誤。

- [ ] **Step 6：Commit**

```bash
git add pyproject.toml app/config.py .env.dev.example docker-compose.dev.yml uv.lock
git commit -m "chore: add DB deps, config, and dev docker-compose"
```

---

## Task 2：DB Models + Connection

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/models.py`
- Create: `app/db/connection.py`

- [ ] **Step 1：建立 app/db/__init__.py**

```python
```

（空檔案）

- [ ] **Step 2：建立 app/db/models.py**

```python
"""
SQLAlchemy ORM models for TWSE chip data.
Column naming follows FinMind dataset conventions for easy cross-reference.
"""
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class StockInstitutionalInvestors(Base):
    """
    個股三大法人買賣 — FinMind: TaiwanStockInstitutionalInvestorsBuySell
    TWSE source: T86
    name values: Foreign_Dealer / Foreign_Dealer_Self / Investment_Trust / Dealer_self / Dealer_Hedging
    """
    __tablename__ = "twse_stock_institutional_investors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id", "name"),)


class TotalInstitutionalInvestors(Base):
    """
    整體市場三大法人買賣 — FinMind: TaiwanStockTotalInstitutionalInvestors
    TWSE source: BFI82U
    name values: 自營商(自行買賣) / 自營商(避險) / 投信 / 外資及陸資(不含外資自營商) / 外資自營商 / 合計
    """
    __tablename__ = "twse_total_institutional_investors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("date", "name"),)


class StockMargin(Base):
    """
    個股融資融券 — FinMind: TaiwanStockMarginPurchaseShortSale
    TWSE source: MI_MARGN (data0)
    """
    __tablename__ = "twse_stock_margin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    MarginPurchaseBuy = Column(BigInteger, default=0)
    MarginPurchaseSell = Column(BigInteger, default=0)
    MarginPurchaseCashRepayment = Column(BigInteger, default=0)
    MarginPurchaseTodayBalance = Column(BigInteger, default=0)
    MarginPurchaseYesterdayBalance = Column(BigInteger, default=0)
    MarginPurchaseLimit = Column(BigInteger, default=0)
    ShortSaleBuy = Column(BigInteger, default=0)
    ShortSaleSell = Column(BigInteger, default=0)
    ShortSaleCashRepayment = Column(BigInteger, default=0)
    ShortSaleTodayBalance = Column(BigInteger, default=0)
    ShortSaleYesterdayBalance = Column(BigInteger, default=0)
    ShortSaleLimit = Column(BigInteger, default=0)
    OffsetLoanAndShort = Column(BigInteger, default=0)

    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class TotalMargin(Base):
    """
    整體市場融資融券 — FinMind: TaiwanStockTotalMarginPurchaseShortSale
    TWSE source: MI_MARGN (data1)
    name values: MarginPurchase / ShortSale / MarginPurchaseMoney
    """
    __tablename__ = "twse_total_margin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(30), nullable=False)
    buy = Column(BigInteger, default=0)
    sell = Column(BigInteger, default=0)
    TodayBalance = Column(BigInteger, default=0)
    YesBalance = Column(BigInteger, default=0)
    Return = Column(BigInteger, default=0)  # 現金(現券)償還；Return 是 FinMind 欄位名，非 Python keyword

    __table_args__ = (UniqueConstraint("date", "name"),)
```

- [ ] **Step 3：建立 app/db/connection.py**

```python
"""Database Connection — async SQLAlchemy session factory"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db.models import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables. Call at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine. Call at application shutdown."""
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 4：Commit**

```bash
git add app/db/
git commit -m "feat: add DB models and connection (institutional investors + margin)"
```

---

## Task 3：Repository

**Files:**
- Create: `app/db/repository.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1：建立 tests/conftest.py**

```python
"""
Shared test fixtures.
Uses aiosqlite in-memory DB with SQLite-compatible models.
"""
import pytest
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class TestBase(DeclarativeBase):
    pass


class TestStockInstitutional(TestBase):
    __tablename__ = "twse_stock_institutional_investors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "stock_id", "name"),)


class TestTotalInstitutional(TestBase):
    __tablename__ = "twse_total_institutional_investors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(50), nullable=False)
    buy = Column(BigInteger, nullable=False, default=0)
    sell = Column(BigInteger, nullable=False, default=0)
    __table_args__ = (UniqueConstraint("date", "name"),)


class TestStockMargin(TestBase):
    __tablename__ = "twse_stock_margin"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    MarginPurchaseBuy = Column(BigInteger, default=0)
    MarginPurchaseSell = Column(BigInteger, default=0)
    MarginPurchaseCashRepayment = Column(BigInteger, default=0)
    MarginPurchaseTodayBalance = Column(BigInteger, default=0)
    MarginPurchaseYesterdayBalance = Column(BigInteger, default=0)
    MarginPurchaseLimit = Column(BigInteger, default=0)
    ShortSaleBuy = Column(BigInteger, default=0)
    ShortSaleSell = Column(BigInteger, default=0)
    ShortSaleCashRepayment = Column(BigInteger, default=0)
    ShortSaleTodayBalance = Column(BigInteger, default=0)
    ShortSaleYesterdayBalance = Column(BigInteger, default=0)
    ShortSaleLimit = Column(BigInteger, default=0)
    OffsetLoanAndShort = Column(BigInteger, default=0)
    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class TestTotalMargin(TestBase):
    __tablename__ = "twse_total_margin"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    name = Column(String(30), nullable=False)
    buy = Column(BigInteger, default=0)
    sell = Column(BigInteger, default=0)
    TodayBalance = Column(BigInteger, default=0)
    YesBalance = Column(BigInteger, default=0)
    Return = Column(BigInteger, default=0)
    __table_args__ = (UniqueConstraint("date", "name"),)


@pytest.fixture
async def test_session():
    """In-memory SQLite session for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()
```

- [ ] **Step 2：建立 tests/test_repository.py（先寫測試）**

```python
"""Repository unit tests using in-memory SQLite."""
import pytest
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from tests.conftest import TestStockInstitutional, TestTotalInstitutional, TestStockMargin, TestTotalMargin


async def test_upsert_stock_institutional_inserts(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 1000, "sell": 500},
    ]
    await repo.upsert_stock_institutional(rows)
    result = await test_session.execute(select(TestStockInstitutional))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].buy == 1000


async def test_upsert_stock_institutional_updates_on_conflict(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [{"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 1000, "sell": 500}]
    await repo.upsert_stock_institutional(rows)
    rows_updated = [{"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 2000, "sell": 800}]
    await repo.upsert_stock_institutional(rows_updated)
    result = await test_session.execute(select(TestStockInstitutional))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].buy == 2000


async def test_get_stock_institutional_returns_none_when_missing(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    result = await repo.get_stock_institutional("2026-03-28", "2330")
    assert result == []


async def test_upsert_stock_margin_inserts(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "MarginPurchaseTodayBalance": 12345,
            "MarginPurchaseLimit": 50000,
            "ShortSaleTodayBalance": 678,
            "ShortSaleLimit": 10000,
            "OffsetLoanAndShort": 100,
        }
    ]
    await repo.upsert_stock_margin(rows)
    result = await repo.get_stock_margin("2026-03-28", "2330")
    assert result is not None
    assert result.MarginPurchaseTodayBalance == 12345
```

- [ ] **Step 3：執行測試確認失敗**

```bash
cd /mnt/raid1/novis/home-stack/twse-api
uv run pytest tests/test_repository.py -v
```

Expected: `ImportError: cannot import name 'TWSERepository'`

- [ ] **Step 4：建立 app/db/repository.py**

```python
"""TWSE Repository — CRUD operations for chip and margin data."""
import logging
from datetime import date as date_type
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    StockInstitutionalInvestors,
    TotalInstitutionalInvestors,
    StockMargin,
    TotalMargin,
)

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date_type:
    """Parse YYYYMMDD or YYYY-MM-DD to date."""
    date_str = date_str.strip()
    if len(date_str) == 8:
        return date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    return date_type.fromisoformat(date_str)


class TWSERepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 個股三大法人 ──────────────────────────────────────────────

    async def upsert_stock_institutional(self, rows: list[dict]) -> None:
        """Upsert rows into twse_stock_institutional_investors."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(StockInstitutionalInvestors).where(
                    StockInstitutionalInvestors.date == d,
                    StockInstitutionalInvestors.stock_id == row["stock_id"],
                    StockInstitutionalInvestors.name == row["name"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                record.buy = row.get("buy", 0)
                record.sell = row.get("sell", 0)
            else:
                self.session.add(StockInstitutionalInvestors(
                    date=d,
                    stock_id=row["stock_id"],
                    name=row["name"],
                    buy=row.get("buy", 0),
                    sell=row.get("sell", 0),
                ))
        await self.session.flush()

    async def get_stock_institutional(self, date_str: str, stock_id: str) -> list[StockInstitutionalInvestors]:
        """Get all name rows for a stock on a date. Returns [] if not found."""
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockInstitutionalInvestors).where(
                StockInstitutionalInvestors.date == d,
                StockInstitutionalInvestors.stock_id == stock_id,
            )
        )
        return list(result.scalars().all())

    async def get_all_stocks_institutional(self, date_str: str) -> list[StockInstitutionalInvestors]:
        """Get all stocks for a date."""
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockInstitutionalInvestors).where(StockInstitutionalInvestors.date == d)
        )
        return list(result.scalars().all())

    # ── 整體市場三大法人 ──────────────────────────────────────────

    async def upsert_total_institutional(self, rows: list[dict]) -> None:
        """Upsert rows into twse_total_institutional_investors."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(TotalInstitutionalInvestors).where(
                    TotalInstitutionalInvestors.date == d,
                    TotalInstitutionalInvestors.name == row["name"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                record.buy = row.get("buy", 0)
                record.sell = row.get("sell", 0)
            else:
                self.session.add(TotalInstitutionalInvestors(
                    date=d,
                    name=row["name"],
                    buy=row.get("buy", 0),
                    sell=row.get("sell", 0),
                ))
        await self.session.flush()

    async def get_total_institutional(self, date_str: str) -> list[TotalInstitutionalInvestors]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(TotalInstitutionalInvestors).where(TotalInstitutionalInvestors.date == d)
        )
        return list(result.scalars().all())

    # ── 個股融資融券 ──────────────────────────────────────────────

    async def upsert_stock_margin(self, rows: list[dict]) -> None:
        """Upsert rows into twse_stock_margin."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(StockMargin).where(
                    StockMargin.date == d,
                    StockMargin.stock_id == row["stock_id"],
                )
            )
            record = existing.scalar_one_or_none()
            fields = [
                "MarginPurchaseBuy", "MarginPurchaseSell", "MarginPurchaseCashRepayment",
                "MarginPurchaseTodayBalance", "MarginPurchaseYesterdayBalance", "MarginPurchaseLimit",
                "ShortSaleBuy", "ShortSaleSell", "ShortSaleCashRepayment",
                "ShortSaleTodayBalance", "ShortSaleYesterdayBalance", "ShortSaleLimit",
                "OffsetLoanAndShort",
            ]
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "stock_id": row["stock_id"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(StockMargin(**kwargs))
        await self.session.flush()

    async def get_stock_margin(self, date_str: str, stock_id: str) -> Optional[StockMargin]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockMargin).where(StockMargin.date == d, StockMargin.stock_id == stock_id)
        )
        return result.scalar_one_or_none()

    async def get_stock_margin_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[StockMargin]:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        result = await self.session.execute(
            select(StockMargin).where(
                StockMargin.stock_id == stock_id,
                StockMargin.date >= start,
                StockMargin.date <= end,
            ).order_by(StockMargin.date)
        )
        return list(result.scalars().all())

    # ── 整體市場融資融券 ──────────────────────────────────────────

    async def upsert_total_margin(self, rows: list[dict]) -> None:
        """Upsert rows into twse_total_margin."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(TotalMargin).where(TotalMargin.date == d, TotalMargin.name == row["name"])
            )
            record = existing.scalar_one_or_none()
            fields = ["buy", "sell", "TodayBalance", "YesBalance", "Return"]
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "name": row["name"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(TotalMargin(**kwargs))
        await self.session.flush()

    async def get_total_margin(self, date_str: str) -> list[TotalMargin]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(TotalMargin).where(TotalMargin.date == d)
        )
        return list(result.scalars().all())
```

- [ ] **Step 5：執行測試確認通過**

```bash
uv run pytest tests/test_repository.py -v
```

Expected: 全部 PASS

- [ ] **Step 6：Commit**

```bash
git add app/db/repository.py tests/
git commit -m "feat: add TWSERepository with upsert/get for institutional and margin data"
```

---

## Task 4：TWSEClient 重構 + Chip Service

**Files:**
- Create: `app/services/twse_client.py`
- Create: `app/services/chip.py`
- Delete: `app/services/twse.py`（邏輯移走後刪除）
- Modify: `app/routers/chip.py`
- Create: `tests/test_chip_service.py`

- [ ] **Step 1：建立 tests/test_chip_service.py（先寫測試）**

```python
"""Chip service unit tests."""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chip import ChipService


async def test_get_chip_summary_returns_db_data_on_hit(test_session: AsyncSession):
    """DB hit: should not call TWSE client."""
    mock_client = MagicMock()
    mock_client.fetch_chip_summary = AsyncMock()

    # Pre-insert total institutional data
    from app.db.repository import TWSERepository
    repo = TWSERepository(test_session)
    await repo.upsert_total_institutional([
        {"date": date(2026, 3, 28), "name": "合計", "buy": 10000, "sell": 5000},
    ])
    await test_session.commit()

    service = ChipService(session=test_session, client=mock_client)
    result = await service.get_chip_summary("20260328")

    mock_client.fetch_chip_summary.assert_not_called()
    assert result["total_diff"] == 5000


async def test_get_chip_summary_calls_client_on_miss(test_session: AsyncSession):
    """DB miss: should call TWSE client and store result."""
    mock_client = MagicMock()
    mock_client.fetch_chip_summary = AsyncMock(return_value={
        "stat": "OK",
        "data": [
            ["自營商(自行買賣)", "1,000", "500", "500"],
            ["投信", "2,000", "800", "1,200"],
            ["外資及陸資(不含外資自營商)", "5,000", "3,000", "2,000"],
            ["合計", "8,000", "4,300", "3,700"],
        ]
    })

    service = ChipService(session=test_session, client=mock_client)
    result = await service.get_chip_summary("20260328")

    mock_client.fetch_chip_summary.assert_called_once_with("20260328")
    assert result["total_diff"] == 3700


async def test_get_stock_chip_returns_db_on_hit(test_session: AsyncSession):
    """DB hit for stock chip: should not call client."""
    mock_client = MagicMock()
    mock_client.fetch_stock_chip_data = AsyncMock()

    from app.db.repository import TWSERepository
    repo = TWSERepository(test_session)
    await repo.upsert_stock_institutional([
        {"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 1000, "sell": 300},
        {"date": date(2026, 3, 28), "stock_id": "2330", "name": "Investment_Trust", "buy": 200, "sell": 100},
    ])
    await test_session.commit()

    service = ChipService(session=test_session, client=mock_client)
    result = await service.get_stock_chip("20260328", "2330")

    mock_client.fetch_stock_chip_data.assert_not_called()
    assert result["stock_id"] == "2330"
    assert result["foreign_buy"] == 1000
```

- [ ] **Step 2：執行測試確認失敗**

```bash
uv run pytest tests/test_chip_service.py -v
```

Expected: `ImportError: cannot import name 'ChipService'`

- [ ] **Step 3：建立 app/services/twse_client.py（純 HTTP layer）**

```python
"""
TWSE HTTP Client — pure HTTP layer, no business logic.
Handles retries and error normalisation only.
"""
import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
BASE_URL = "https://www.twse.com.tw"


class TWSEAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TWSEClient:
    """Low-level TWSE API HTTP client with retry logic."""

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(verify=False, timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    if "stat" in data and data["stat"] != "OK":
                        raise TWSEAPIError(f"TWSE stat: {data['stat']}")
                    return data
            except TWSEAPIError:
                raise
            except httpx.TimeoutException:
                last_exc = TWSEAPIError(f"Timeout: {url}")
            except httpx.HTTPStatusError as e:
                last_exc = TWSEAPIError(f"HTTP {e.response.status_code}", e.response.status_code)
            except Exception as e:
                last_exc = TWSEAPIError(str(e))
            if attempt < DEFAULT_MAX_RETRIES - 1:
                await asyncio.sleep(min(1.0 * (2 ** attempt), 10.0))
        raise last_exc or TWSEAPIError("Request failed")

    async def fetch_chip_summary(self, date_str: str) -> dict[str, Any]:
        """BFI82U — 三大法人買賣金額統計表"""
        url = f"{BASE_URL}/rwd/zh/fund/BFI82U?response=json&date={date_str}"
        return await self._fetch_json(url)

    async def fetch_stock_chip_data(self, date_str: str) -> dict[str, Any]:
        """T86 — 個股三大法人買賣超"""
        url = f"{BASE_URL}/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
        return await self._fetch_json(url)

    async def fetch_margin_data(self, date_str: str) -> dict[str, Any]:
        """MI_MARGN — 融資融券（個股 + 整體市場）"""
        url = f"{BASE_URL}/rwd/zh/marginTrading/MI_MARGN?response=json&date={date_str}&selectType=ALL"
        return await self._fetch_json(url)


_client: Optional[TWSEClient] = None


def get_twse_client() -> TWSEClient:
    global _client
    if _client is None:
        _client = TWSEClient()
    return _client
```

- [ ] **Step 4：建立 app/services/chip.py**

```python
"""
Chip Service — 三大法人資料 (DB-first cache).
Parses TWSE T86 / BFI82U responses and maps to FinMind-compatible names.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from app.services.twse_client import TWSEClient, get_twse_client

logger = logging.getLogger(__name__)
TW_TZ = timezone(timedelta(hours=8))

# T86 column → FinMind name mapping
# Each tuple: (buy_col_idx, sell_col_idx, finmind_name)
T86_NAME_MAP = [
    (2,  3,  "Foreign_Dealer"),       # 外陸資
    (5,  6,  "Foreign_Dealer_Self"),  # 外資自營商
    (8,  9,  "Investment_Trust"),     # 投信
    (12, 13, "Dealer_self"),          # 自營商(自行買賣)
    (15, 16, "Dealer_Hedging"),       # 自營商(避險)
]


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


class ChipService:
    def __init__(self, session: AsyncSession, client: Optional[TWSEClient] = None):
        self.repo = TWSERepository(session)
        self.client = client or get_twse_client()
        self.session = session

    async def get_chip_summary(self, date_str: str, force_refresh: bool = False) -> dict[str, Any]:
        """整體市場三大法人。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            rows = await self.repo.get_total_institutional(date_str)
            if rows:
                return self._format_chip_summary(date_str, rows)

        raw = await self.client.fetch_chip_summary(date_str)
        db_rows = self._parse_bfi82u(date_str, raw)
        await self.repo.upsert_total_institutional(db_rows)
        await self.session.commit()
        rows = await self.repo.get_total_institutional(date_str)
        return self._format_chip_summary(date_str, rows)

    async def get_all_stocks_chip(self, date_str: str, force_refresh: bool = False) -> dict[str, Any]:
        """個股三大法人列表。"""
        if not force_refresh:
            rows = await self.repo.get_all_stocks_institutional(date_str)
            if rows:
                return self._format_stocks_chip(date_str, rows)

        raw = await self.client.fetch_stock_chip_data(date_str)
        db_rows = self._parse_t86(date_str, raw)
        await self.repo.upsert_stock_institutional(db_rows)
        await self.session.commit()
        rows = await self.repo.get_all_stocks_institutional(date_str)
        return self._format_stocks_chip(date_str, rows)

    async def get_stock_chip(self, date_str: str, stock_id: str, force_refresh: bool = False) -> Optional[dict[str, Any]]:
        """個股三大法人。若不存在回傳 None。"""
        if not force_refresh:
            rows = await self.repo.get_stock_institutional(date_str, stock_id)
            if rows:
                return self._format_single_stock(date_str, stock_id, rows)

        raw = await self.client.fetch_stock_chip_data(date_str)
        db_rows = self._parse_t86(date_str, raw)
        await self.repo.upsert_stock_institutional(db_rows)
        await self.session.commit()
        rows = await self.repo.get_stock_institutional(date_str, stock_id)
        if not rows:
            return None
        return self._format_single_stock(date_str, stock_id, rows)

    # ── Parsers ──────────────────────────────────────────────────

    def _parse_bfi82u(self, date_str: str, data: dict) -> list[dict]:
        """BFI82U → rows for twse_total_institutional_investors."""
        from datetime import date as date_type
        d = date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        rows = []
        for row in data.get("data", []):
            if len(row) >= 4:
                try:
                    rows.append({
                        "date": d,
                        "name": row[0].strip(),
                        "buy": _int(row[1]),
                        "sell": _int(row[2]),
                    })
                except (ValueError, IndexError):
                    continue
        return rows

    def _parse_t86(self, date_str: str, data: dict) -> list[dict]:
        """T86 → rows for twse_stock_institutional_investors."""
        from datetime import date as date_type
        d = date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        rows = []
        for row in data.get("data", []):
            if len(row) < 17:
                continue
            stock_id = row[0].strip()
            for buy_idx, sell_idx, name in T86_NAME_MAP:
                try:
                    rows.append({
                        "date": d,
                        "stock_id": stock_id,
                        "name": name,
                        "buy": _int(row[buy_idx]),
                        "sell": _int(row[sell_idx]),
                    })
                except (ValueError, IndexError):
                    continue
        return rows

    # ── Formatters ───────────────────────────────────────────────

    def _format_chip_summary(self, date_str: str, rows) -> dict[str, Any]:
        investors = [{"name": r.name, "buy": r.buy, "sell": r.sell, "diff": r.buy - r.sell} for r in rows]
        total_diff = next((r.buy - r.sell for r in rows if "合計" in r.name), 0)
        return {"date": date_str, "investors": investors, "total_diff": total_diff}

    def _format_stocks_chip(self, date_str: str, rows) -> dict[str, Any]:
        stocks_map: dict[str, dict] = {}
        for r in rows:
            if r.stock_id not in stocks_map:
                stocks_map[r.stock_id] = {
                    "stock_id": r.stock_id, "date": date_str,
                    "foreign_buy": 0, "foreign_sell": 0, "foreign_diff": 0,
                    "trust_buy": 0, "trust_sell": 0, "trust_diff": 0,
                    "dealer_diff": 0, "total_diff": 0,
                }
            s = stocks_map[r.stock_id]
            if r.name == "Foreign_Dealer":
                s["foreign_buy"] = r.buy
                s["foreign_sell"] = r.sell
                s["foreign_diff"] = r.buy - r.sell
            elif r.name == "Investment_Trust":
                s["trust_buy"] = r.buy
                s["trust_sell"] = r.sell
                s["trust_diff"] = r.buy - r.sell
            elif r.name in ("Dealer_self", "Dealer_Hedging"):
                s["dealer_diff"] += r.buy - r.sell
        stocks = list(stocks_map.values())
        for s in stocks:
            s["total_diff"] = s["foreign_diff"] + s["trust_diff"] + s["dealer_diff"]
        return {
            "date": date_str,
            "stocks": stocks,
            "top_foreign_buy": sorted(stocks, key=lambda x: x["foreign_diff"], reverse=True)[:10],
            "top_foreign_sell": sorted(stocks, key=lambda x: x["foreign_diff"])[:10],
            "top_trust_buy": sorted(stocks, key=lambda x: x["trust_diff"], reverse=True)[:10],
            "top_trust_sell": sorted(stocks, key=lambda x: x["trust_diff"])[:10],
        }

    def _format_single_stock(self, date_str: str, stock_id: str, rows) -> dict[str, Any]:
        result = {
            "stock_id": stock_id, "date": date_str,
            "foreign_buy": 0, "foreign_sell": 0, "foreign_diff": 0,
            "trust_buy": 0, "trust_sell": 0, "trust_diff": 0,
            "dealer_self_diff": 0, "dealer_hedge_diff": 0, "dealer_diff": 0,
            "total_diff": 0,
        }
        for r in rows:
            if r.name == "Foreign_Dealer":
                result["foreign_buy"] = r.buy
                result["foreign_sell"] = r.sell
                result["foreign_diff"] = r.buy - r.sell
            elif r.name == "Investment_Trust":
                result["trust_buy"] = r.buy
                result["trust_sell"] = r.sell
                result["trust_diff"] = r.buy - r.sell
            elif r.name == "Dealer_self":
                result["dealer_self_diff"] = r.buy - r.sell
            elif r.name == "Dealer_Hedging":
                result["dealer_hedge_diff"] = r.buy - r.sell
        result["dealer_diff"] = result["dealer_self_diff"] + result["dealer_hedge_diff"]
        result["total_diff"] = result["foreign_diff"] + result["trust_diff"] + result["dealer_diff"]
        return result


_chip_service: Optional[ChipService] = None


def get_chip_service(session: AsyncSession) -> ChipService:
    return ChipService(session=session)
```

- [ ] **Step 5：執行 chip service 測試**

```bash
uv run pytest tests/test_chip_service.py -v
```

Expected: 全部 PASS

- [ ] **Step 6：更新 app/routers/chip.py（改用新 service + DB）**

```python
"""Chip Data Router — 三大法人 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.chip import get_chip_service
from app.services.twse_client import TWSEAPIError

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/summary")
async def get_chip_summary(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """三大法人買賣金額統計 (BFI82U)"""
    date = date or _default_date()
    try:
        return await get_chip_service(session).get_chip_summary(date, force_refresh)
    except TWSEAPIError as e:
        if e.status_code == 404 or "沒有符合" in str(e.message):
            raise HTTPException(404, f"No data for date: {date}")
        raise HTTPException(500, str(e.message))


@router.get("/stocks")
async def get_stock_chip_list(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股三大法人買賣超列表 (T86)"""
    date = date or _default_date()
    try:
        return await get_chip_service(session).get_all_stocks_chip(date, force_refresh)
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))


@router.get("/stock/{stock_id}")
async def get_stock_chip_detail(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股三大法人詳情"""
    date = date or _default_date()
    try:
        result = await get_chip_service(session).get_stock_chip(date, stock_id, force_refresh)
        if result is None:
            raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
        return result
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))
```

- [ ] **Step 7：刪除 app/services/twse.py**

```bash
rm app/services/twse.py
```

- [ ] **Step 8：Commit**

```bash
git add app/services/twse_client.py app/services/chip.py app/routers/chip.py tests/test_chip_service.py
git rm app/services/twse.py
git commit -m "refactor: extract TWSEClient, implement ChipService with DB caching"
```

---

## Task 5：Margin Parsing（MI_MARGN）

**Files:**
- Modify: `app/services/twse_client.py`（`fetch_margin_data` 已加，這 task 專注 parser）
- Create: `tests/test_margin_parsing.py`

> **注意**：MI_MARGN 實際 response 在實作前請先手動驗證：
> ```bash
> curl "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date=20260328&selectType=ALL" | python3 -m json.tool | head -50
> ```
> 確認 `data0`（個股）與 `data1`（市場合計）的 key 名稱與欄位順序。

- [ ] **Step 1：建立 tests/test_margin_parsing.py（先寫測試）**

```python
"""Unit tests for MI_MARGN JSON parsing logic."""
import pytest
from datetime import date
from app.services.margin import MarginService, _int


def make_mock_margin_response():
    """
    MI_MARGN response structure:
    data0 = individual stocks (欄位順序見 fields0)
    data1 = market totals (3 rows: 融資/融券/融資金額)

    fields0 indices:
    [0] 股票代號
    [1] 股票名稱
    [2] 融資-買進(張)     → MarginPurchaseBuy
    [3] 融資-賣出(張)     → MarginPurchaseSell
    [4] 融資-現金償還(張) → MarginPurchaseCashRepayment
    [5] 融資-前日餘額(張) → MarginPurchaseYesterdayBalance
    [6] 融資-今日餘額(張) → MarginPurchaseTodayBalance
    [7] 融資-限額(千張)   → MarginPurchaseLimit
    [8] 融券-賣出(張)     → ShortSaleSell
    [9] 融券-買進(張)     → ShortSaleBuy
    [10] 融券-現金償還(張) → ShortSaleCashRepayment
    [11] 融券-前日餘額(張) → ShortSaleYesterdayBalance
    [12] 融券-今日餘額(張) → ShortSaleTodayBalance
    [13] 融券-限額(千張)  → ShortSaleLimit
    [14] 資券互抵(張)     → OffsetLoanAndShort
    """
    return {
        "stat": "OK",
        "date": "20260328",
        "data0": [
            ["2330", "台積電", "1,200", "800", "50", "10,000", "10,350", "100", "300", "100", "20", "500", "680", "50", "30"],
            ["2317", "鴻海", "500", "300", "10", "3,000", "3,190", "50", "100", "50", "5", "200", "245", "20", "10"],
        ],
        "data1": [
            ["融資(借錢買)", "100,000", "80,000", "5,000", "900,000", "915,000", "1,000,000"],
            ["融券(借券賣)", "20,000", "10,000", "2,000", "80,000", "88,000", "200,000"],
            ["融資金額(仟元)", "500,000", "400,000", "25,000", "4,000,000", "4,075,000", "5,000,000"],
        ],
    }


async def test_parse_stock_margin_count():
    """Should parse 2 stocks from data0."""
    from app.services.margin import MarginService
    from unittest.mock import MagicMock
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_stock_margin("20260328", make_mock_margin_response())
    assert len(rows) == 2


async def test_parse_stock_margin_fields():
    """Should map data0 columns to FinMind field names correctly."""
    from app.services.margin import MarginService
    from unittest.mock import MagicMock
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_stock_margin("20260328", make_mock_margin_response())
    tsmc = next(r for r in rows if r["stock_id"] == "2330")
    assert tsmc["MarginPurchaseBuy"] == 1200
    assert tsmc["MarginPurchaseSell"] == 800
    assert tsmc["MarginPurchaseTodayBalance"] == 10350
    assert tsmc["MarginPurchaseYesterdayBalance"] == 10000
    assert tsmc["ShortSaleSell"] == 300
    assert tsmc["ShortSaleBuy"] == 100
    assert tsmc["ShortSaleTodayBalance"] == 680
    assert tsmc["OffsetLoanAndShort"] == 30


async def test_parse_total_margin_count():
    """Should parse 3 rows from data1 (融資/融券/融資金額)."""
    from app.services.margin import MarginService
    from unittest.mock import MagicMock
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_total_margin("20260328", make_mock_margin_response())
    assert len(rows) == 3
    names = {r["name"] for r in rows}
    assert names == {"MarginPurchase", "ShortSale", "MarginPurchaseMoney"}


async def test_parse_total_margin_balance():
    """Should map TodayBalance and YesBalance correctly."""
    from app.services.margin import MarginService
    from unittest.mock import MagicMock
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_total_margin("20260328", make_mock_margin_response())
    margin = next(r for r in rows if r["name"] == "MarginPurchase")
    assert margin["TodayBalance"] == 915000
    assert margin["YesBalance"] == 900000
    assert margin["Return"] == 5000
```

- [ ] **Step 2：執行確認失敗**

```bash
uv run pytest tests/test_margin_parsing.py -v
```

Expected: `ImportError: cannot import name 'MarginService'`

- [ ] **Step 3：建立 app/services/margin.py（只實作 parser 部分，先讓 parsing tests 通過）**

```python
"""
Margin Service — 融資融券資料 (DB-first cache).

MI_MARGN response structure:
  data0: individual stock rows
  data1: market total rows (3 rows: 融資/融券/融資金額)

data0 column indices (0-indexed, after 股票代號 and 股票名稱):
  [0] 股票代號
  [1] 股票名稱
  [2] 融資-買進(張)      → MarginPurchaseBuy
  [3] 融資-賣出(張)      → MarginPurchaseSell
  [4] 融資-現金償還(張)  → MarginPurchaseCashRepayment
  [5] 融資-前日餘額(張)  → MarginPurchaseYesterdayBalance
  [6] 融資-今日餘額(張)  → MarginPurchaseTodayBalance
  [7] 融資-限額(千張)    → MarginPurchaseLimit
  [8] 融券-賣出(張)      → ShortSaleSell
  [9] 融券-買進(張)      → ShortSaleBuy
  [10] 融券-現金償還(張) → ShortSaleCashRepayment
  [11] 融券-前日餘額(張) → ShortSaleYesterdayBalance
  [12] 融券-今日餘額(張) → ShortSaleTodayBalance
  [13] 融券-限額(千張)   → ShortSaleLimit
  [14] 資券互抵(張)      → OffsetLoanAndShort

data1 column indices:
  [0] 項目別 (融資/融券/融資金額)
  [1] 買進(張)   → buy
  [2] 賣出(張)   → sell
  [3] 現金償還   → Return
  [4] 前日餘額   → YesBalance
  [5] 今日餘額   → TodayBalance
  [6] 限額       → (ignored, not in FinMind schema)

NOTE: Verify actual TWSE response format before deploying. Run:
  curl "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date=20260101&selectType=ALL"
"""
import logging
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from app.services.twse_client import TWSEClient, get_twse_client

logger = logging.getLogger(__name__)

# data1 row[0] → FinMind name mapping
_TOTAL_NAME_MAP = {
    "融資": "MarginPurchase",
    "融資(借錢買)": "MarginPurchase",
    "融券": "ShortSale",
    "融券(借券賣)": "ShortSale",
    "融資金額": "MarginPurchaseMoney",
    "融資金額(仟元)": "MarginPurchaseMoney",
}


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _parse_date(date_str: str) -> date_type:
    return date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))


class MarginService:
    def __init__(self, session: AsyncSession, client: Optional[TWSEClient] = None):
        self.repo = TWSERepository(session)
        self.client = client or get_twse_client()
        self.session = session

    async def get_stock_margin(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """個股融資融券。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            record = await self.repo.get_stock_margin(date_str, stock_id)
            if record:
                return self._format_stock_margin(date_str, record)

        await self._ingest_margin(date_str)
        record = await self.repo.get_stock_margin(date_str, stock_id)
        return self._format_stock_margin(date_str, record) if record else None

    async def get_total_margin(self, date_str: str, force_refresh: bool = False) -> dict[str, Any]:
        """整體市場融資融券。"""
        if not force_refresh:
            rows = await self.repo.get_total_margin(date_str)
            if rows:
                return self._format_total_margin(date_str, rows)

        await self._ingest_margin(date_str)
        rows = await self.repo.get_total_margin(date_str)
        return self._format_total_margin(date_str, rows)

    async def get_stock_margin_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """個股融資融券歷史（僅從 DB 查，不自動補爬）。"""
        records = await self.repo.get_stock_margin_history(stock_id, start_date, end_date)
        return [self._format_stock_margin(r.date.strftime("%Y%m%d"), r) for r in records]

    # ── Ingest ───────────────────────────────────────────────────

    async def _ingest_margin(self, date_str: str) -> None:
        raw = await self.client.fetch_margin_data(date_str)
        stock_rows = self._parse_stock_margin(date_str, raw)
        total_rows = self._parse_total_margin(date_str, raw)
        await self.repo.upsert_stock_margin(stock_rows)
        await self.repo.upsert_total_margin(total_rows)
        await self.session.commit()
        # Eager compute placeholder — indicators_pipeline.compute() goes here (Task 3 batch)

    # ── Parsers ──────────────────────────────────────────────────

    def _parse_stock_margin(self, date_str: str, data: dict) -> list[dict]:
        """MI_MARGN data0 → rows for twse_stock_margin."""
        d = _parse_date(date_str)
        rows = []
        for row in data.get("data0", []):
            if len(row) < 15:
                continue
            try:
                rows.append({
                    "date": d,
                    "stock_id": row[0].strip(),
                    "MarginPurchaseBuy": _int(row[2]),
                    "MarginPurchaseSell": _int(row[3]),
                    "MarginPurchaseCashRepayment": _int(row[4]),
                    "MarginPurchaseYesterdayBalance": _int(row[5]),
                    "MarginPurchaseTodayBalance": _int(row[6]),
                    "MarginPurchaseLimit": _int(row[7]),
                    "ShortSaleSell": _int(row[8]),
                    "ShortSaleBuy": _int(row[9]),
                    "ShortSaleCashRepayment": _int(row[10]),
                    "ShortSaleYesterdayBalance": _int(row[11]),
                    "ShortSaleTodayBalance": _int(row[12]),
                    "ShortSaleLimit": _int(row[13]),
                    "OffsetLoanAndShort": _int(row[14]),
                })
            except (ValueError, IndexError):
                continue
        return rows

    def _parse_total_margin(self, date_str: str, data: dict) -> list[dict]:
        """MI_MARGN data1 → rows for twse_total_margin."""
        d = _parse_date(date_str)
        rows = []
        for row in data.get("data1", []):
            if len(row) < 6:
                continue
            raw_name = row[0].strip()
            finmind_name = _TOTAL_NAME_MAP.get(raw_name)
            if not finmind_name:
                continue
            try:
                rows.append({
                    "date": d,
                    "name": finmind_name,
                    "buy": _int(row[1]),
                    "sell": _int(row[2]),
                    "Return": _int(row[3]),
                    "YesBalance": _int(row[4]),
                    "TodayBalance": _int(row[5]),
                })
            except (ValueError, IndexError):
                continue
        return rows

    # ── Formatters ───────────────────────────────────────────────

    def _format_stock_margin(self, date_str: str, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d") if hasattr(record.date, "strftime") else date_str,
            "stock_id": record.stock_id,
            "MarginPurchaseBuy": record.MarginPurchaseBuy,
            "MarginPurchaseSell": record.MarginPurchaseSell,
            "MarginPurchaseCashRepayment": record.MarginPurchaseCashRepayment,
            "MarginPurchaseTodayBalance": record.MarginPurchaseTodayBalance,
            "MarginPurchaseYesterdayBalance": record.MarginPurchaseYesterdayBalance,
            "MarginPurchaseLimit": record.MarginPurchaseLimit,
            "ShortSaleBuy": record.ShortSaleBuy,
            "ShortSaleSell": record.ShortSaleSell,
            "ShortSaleCashRepayment": record.ShortSaleCashRepayment,
            "ShortSaleTodayBalance": record.ShortSaleTodayBalance,
            "ShortSaleYesterdayBalance": record.ShortSaleYesterdayBalance,
            "ShortSaleLimit": record.ShortSaleLimit,
            "OffsetLoanAndShort": record.OffsetLoanAndShort,
        }

    def _format_total_margin(self, date_str: str, rows) -> dict[str, Any]:
        result: dict[str, Any] = {"date": date_str, "items": []}
        for r in rows:
            result["items"].append({
                "name": r.name,
                "buy": r.buy,
                "sell": r.sell,
                "TodayBalance": r.TodayBalance,
                "YesBalance": r.YesBalance,
                "Return": r.Return,
            })
        return result


def get_margin_service(session: AsyncSession) -> MarginService:
    return MarginService(session=session)
```

- [ ] **Step 4：執行 parsing tests**

```bash
uv run pytest tests/test_margin_parsing.py -v
```

Expected: 全部 PASS

- [ ] **Step 5：Commit**

```bash
git add app/services/margin.py tests/test_margin_parsing.py
git commit -m "feat: add MarginService with MI_MARGN parsing (data0/data1)"
```

---

## Task 6：Margin Service DB Cache Tests

**Files:**
- Create: `tests/test_margin_service.py`

- [ ] **Step 1：建立 tests/test_margin_service.py**

```python
"""Margin service DB cache tests."""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.margin import MarginService
from app.db.repository import TWSERepository


def _mock_client_with_data():
    client = MagicMock()
    client.fetch_margin_data = AsyncMock(return_value={
        "stat": "OK",
        "date": "20260328",
        "data0": [
            ["2330", "台積電", "1,200", "800", "50", "10,000", "10,350", "100",
             "300", "100", "20", "500", "680", "50", "30"],
        ],
        "data1": [
            ["融資(借錢買)", "100,000", "80,000", "5,000", "900,000", "915,000", "1,000,000"],
            ["融券(借券賣)", "20,000", "10,000", "2,000", "80,000", "88,000", "200,000"],
            ["融資金額(仟元)", "500,000", "400,000", "25,000", "4,000,000", "4,075,000", "5,000,000"],
        ],
    })
    return client


async def test_get_stock_margin_calls_client_on_miss(test_session: AsyncSession):
    """DB miss → client should be called, data stored."""
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_stock_margin("20260328", "2330")

    client.fetch_margin_data.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["MarginPurchaseTodayBalance"] == 10350


async def test_get_stock_margin_returns_db_on_hit(test_session: AsyncSession):
    """DB hit → client should NOT be called."""
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    # First call populates DB
    await service.get_stock_margin("20260328", "2330")
    client.fetch_margin_data.reset_mock()

    # Second call should hit DB
    result = await service.get_stock_margin("20260328", "2330")
    client.fetch_margin_data.assert_not_called()
    assert result["MarginPurchaseTodayBalance"] == 10350


async def test_get_stock_margin_returns_none_for_unknown_stock(test_session: AsyncSession):
    """Unknown stock_id → returns None."""
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_stock_margin("20260328", "9999")
    assert result is None


async def test_get_total_margin_returns_three_rows(test_session: AsyncSession):
    """Total margin should return 3 rows (MarginPurchase/ShortSale/MarginPurchaseMoney)."""
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_total_margin("20260328")
    assert len(result["items"]) == 3
    names = {item["name"] for item in result["items"]}
    assert names == {"MarginPurchase", "ShortSale", "MarginPurchaseMoney"}


async def test_get_stock_margin_history_empty_before_ingest(test_session: AsyncSession):
    """History query on empty DB returns []."""
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_stock_margin_history("2330", "20260101", "20260328")
    assert result == []
```

- [ ] **Step 2：執行測試**

```bash
uv run pytest tests/test_margin_service.py -v
```

Expected: 全部 PASS

- [ ] **Step 3：Commit**

```bash
git add tests/test_margin_service.py
git commit -m "test: add margin service DB cache tests"
```

---

## Task 7：Margin Schemas + Router + main.py

**Files:**
- Create: `app/schemas/margin.py`
- Create: `app/routers/margin.py`
- Modify: `app/main.py`
- Create: `tests/test_margin_router.py`

- [ ] **Step 1：建立 tests/test_margin_router.py（先寫測試）**

```python
"""Margin router integration tests."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


async def test_margin_stock_returns_200():
    """GET /api/v1/margin/stock/2330 should return 200 with correct fields."""
    mock_service = MagicMock()
    mock_service.get_stock_margin = AsyncMock(return_value={
        "date": "2026-03-28",
        "stock_id": "2330",
        "MarginPurchaseTodayBalance": 10350,
        "MarginPurchaseLimit": 100000,
        "ShortSaleTodayBalance": 680,
        "ShortSaleLimit": 50000,
        "OffsetLoanAndShort": 30,
        "MarginPurchaseBuy": 1200,
        "MarginPurchaseSell": 800,
        "MarginPurchaseCashRepayment": 50,
        "MarginPurchaseYesterdayBalance": 10000,
        "ShortSaleBuy": 100,
        "ShortSaleSell": 300,
        "ShortSaleCashRepayment": 20,
        "ShortSaleYesterdayBalance": 500,
    })

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/margin/stock/2330?date=20260328")

    assert response.status_code == 200
    data = response.json()
    assert data["stock_id"] == "2330"
    assert data["MarginPurchaseTodayBalance"] == 10350


async def test_margin_stock_returns_404_when_not_found():
    """GET /api/v1/margin/stock/9999 should return 404 when stock not in data."""
    mock_service = MagicMock()
    mock_service.get_stock_margin = AsyncMock(return_value=None)

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/margin/stock/9999?date=20260328")

    assert response.status_code == 404


async def test_margin_summary_returns_200():
    """GET /api/v1/margin/summary should return 200."""
    mock_service = MagicMock()
    mock_service.get_total_margin = AsyncMock(return_value={
        "date": "20260328",
        "items": [
            {"name": "MarginPurchase", "buy": 100000, "sell": 80000, "TodayBalance": 915000, "YesBalance": 900000, "Return": 5000},
        ]
    })

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/margin/summary?date=20260328")

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "MarginPurchase"


async def test_margin_history_returns_200():
    """GET /api/v1/margin/stock/2330/history should return 200."""
    mock_service = MagicMock()
    mock_service.get_stock_margin_history = AsyncMock(return_value=[])

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/margin/stock/2330/history?start_date=20260101&end_date=20260328"
            )

    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2：執行確認失敗**

```bash
uv run pytest tests/test_margin_router.py -v
```

Expected: `ImportError` 或 `404 Not Found`（margin router 尚未掛上）

- [ ] **Step 3：建立 app/schemas/margin.py**

```python
"""Pydantic schemas for margin (融資融券) data — aligned with FinMind field names."""
from typing import List, Optional
from pydantic import BaseModel


class StockMarginResponse(BaseModel):
    """個股融資融券 — FinMind: TaiwanStockMarginPurchaseShortSale"""
    date: str
    stock_id: str
    MarginPurchaseBuy: int = 0
    MarginPurchaseSell: int = 0
    MarginPurchaseCashRepayment: int = 0
    MarginPurchaseTodayBalance: int = 0
    MarginPurchaseYesterdayBalance: int = 0
    MarginPurchaseLimit: int = 0
    ShortSaleBuy: int = 0
    ShortSaleSell: int = 0
    ShortSaleCashRepayment: int = 0
    ShortSaleTodayBalance: int = 0
    ShortSaleYesterdayBalance: int = 0
    ShortSaleLimit: int = 0
    OffsetLoanAndShort: int = 0


class TotalMarginItem(BaseModel):
    """單一項目（融資/融券/融資金額）"""
    name: str
    buy: int = 0
    sell: int = 0
    TodayBalance: int = 0
    YesBalance: int = 0
    Return: int = 0


class TotalMarginResponse(BaseModel):
    """整體市場融資融券 — FinMind: TaiwanStockTotalMarginPurchaseShortSale"""
    date: str
    items: List[TotalMarginItem]


class ErrorResponse(BaseModel):
    detail: str
```

- [ ] **Step 4：建立 app/routers/margin.py**

```python
"""Margin Router — 融資融券 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.schemas.margin import StockMarginResponse, TotalMarginResponse, ErrorResponse
from app.services.margin import get_margin_service
from app.services.twse_client import TWSEAPIError

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get(
    "/summary",
    response_model=TotalMarginResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_margin_summary(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """整體市場融資融券統計 (MI_MARGN data1) — FinMind: TaiwanStockTotalMarginPurchaseShortSale"""
    date = date or _default_date()
    try:
        return await get_margin_service(session).get_total_margin(date, force_refresh)
    except TWSEAPIError as e:
        if e.status_code == 404 or "沒有符合" in str(e.message):
            raise HTTPException(404, f"No data for date: {date}")
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}",
    response_model=StockMarginResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_stock_margin(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股融資融券 (MI_MARGN data0) — FinMind: TaiwanStockMarginPurchaseShortSale"""
    date = date or _default_date()
    try:
        result = await get_margin_service(session).get_stock_margin(date, stock_id, force_refresh)
        if result is None:
            raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
        return result
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}/history",
    response_model=list[StockMarginResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_stock_margin_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股融資融券歷史（從 DB 查，不補爬）"""
    try:
        return await get_margin_service(session).get_stock_margin_history(stock_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(500, str(e))
```

- [ ] **Step 5：更新 app/main.py（加 lifespan + margin router）**

```python
"""TWSE API — FastAPI Application"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import close_db, init_db
from app.routers import chip
from app.routers import margin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="TWSE API",
    description="REST API service for TWSE chip data with PostgreSQL caching",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chip.router, prefix="/api/v1/chip", tags=["chip"])
app.include_router(margin.router, prefix="/api/v1/margin", tags=["margin"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "twse-api"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
```

- [ ] **Step 6：執行全部測試**

```bash
uv run pytest tests/ -v
```

Expected: 全部 PASS

- [ ] **Step 7：Final Commit**

```bash
git add app/schemas/margin.py app/routers/margin.py app/main.py tests/test_margin_router.py
git commit -m "feat: add margin router and schemas, wire up lifespan DB init"
```

---

## 完成後驗證

```bash
# 確認所有測試通過
uv run pytest tests/ -v --tb=short

# 確認 import 正確（不需 DB）
uv run python -c "from app.main import app; print('OK')"

# (可選) 啟動 dev server（需要 Docker Postgres）
docker compose -f docker-compose.dev.yml up -d twse-postgres
uv run uvicorn app.main:app --reload --port 8020
# 然後訪問 http://localhost:8020/docs
```

---

## Self-Review Checklist

- [x] Task 1 覆蓋 config + deps + docker-compose
- [x] Task 2 覆蓋所有 4 個 ORM models
- [x] Task 3 覆蓋 repository 的 upsert/get，含 conftest.py
- [x] Task 4 覆蓋 TWSEClient 拆分 + chip service + chip router 重構
- [x] Task 5 覆蓋 MI_MARGN parsing（data0/data1）及其單元測試
- [x] Task 6 覆蓋 margin service 的 DB cache hit/miss 測試
- [x] Task 7 覆蓋 margin schemas + router + main.py lifespan
- [x] 所有測試步驟有完整程式碼，無 TBD
- [x] `get_chip_service` / `get_margin_service` 命名一致
- [x] `_int()` helper 在 chip.py 和 margin.py 各自定義（兩個模組獨立）
- [x] force_refresh 參數所有 endpoint 均支援
- [x] Eager compute placeholder 在 `_ingest_margin()` 中已留好位置
