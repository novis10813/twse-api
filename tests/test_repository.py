"""Repository unit tests using in-memory SQLite."""
import pytest
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from tests.conftest import SqliteStockInstitutional, SqliteTotalInstitutional, SqliteStockMargin, SqliteTotalMargin


async def test_upsert_stock_institutional_inserts(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 1000, "sell": 500},
    ]
    await repo.upsert_stock_institutional(rows)
    result = await test_session.execute(select(SqliteStockInstitutional))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].buy == 1000


async def test_upsert_stock_institutional_updates_on_conflict(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [{"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 1000, "sell": 500}]
    await repo.upsert_stock_institutional(rows)
    rows_updated = [{"date": date(2026, 3, 28), "stock_id": "2330", "name": "Foreign_Dealer", "buy": 2000, "sell": 800}]
    await repo.upsert_stock_institutional(rows_updated)
    result = await test_session.execute(select(SqliteStockInstitutional))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].buy == 2000


async def test_get_stock_institutional_returns_empty_when_missing(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    result = await repo.get_stock_institutional("20260328", "2330")
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
    result = await repo.get_stock_margin("20260328", "2330")
    assert result is not None
    assert result.MarginPurchaseTodayBalance == 12345


async def test_upsert_stock_margin_updates_on_conflict(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [{"date": date(2026, 3, 28), "stock_id": "2330", "MarginPurchaseTodayBalance": 100}]
    await repo.upsert_stock_margin(rows)
    rows_updated = [{"date": date(2026, 3, 28), "stock_id": "2330", "MarginPurchaseTodayBalance": 999}]
    await repo.upsert_stock_margin(rows_updated)
    result = await repo.get_stock_margin("20260328", "2330")
    assert result.MarginPurchaseTodayBalance == 999


async def test_get_stock_margin_returns_none_when_missing(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    result = await repo.get_stock_margin("20260328", "9999")
    assert result is None


async def test_upsert_total_margin_inserts(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 28), "name": "MarginPurchase", "buy": 100000, "sell": 80000, "TodayBalance": 915000, "YesBalance": 900000, "Return": 5000},
    ]
    await repo.upsert_total_margin(rows)
    rows_db = await repo.get_total_margin("20260328")
    assert len(rows_db) == 1
    assert rows_db[0].TodayBalance == 915000


async def test_get_stock_margin_history(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 27), "stock_id": "2330", "MarginPurchaseTodayBalance": 100},
        {"date": date(2026, 3, 28), "stock_id": "2330", "MarginPurchaseTodayBalance": 200},
        {"date": date(2026, 3, 29), "stock_id": "2330", "MarginPurchaseTodayBalance": 300},
    ]
    await repo.upsert_stock_margin(rows)
    history = await repo.get_stock_margin_history("2330", "20260327", "20260328")
    assert len(history) == 2
    assert history[0].MarginPurchaseTodayBalance == 100
    assert history[1].MarginPurchaseTodayBalance == 200
