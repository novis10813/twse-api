"""Repository tests for shareholding upsert/get."""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from tests.conftest import SqliteStockShareholding


async def test_upsert_stock_shareholding_inserts(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "NumberOfSharesIssued": 25930380458,
            "ForeignInvestmentShares": 15000000000,
            "ForeignInvestmentSharesRatio": 57.84,
            "ForeignInvestmentSharesWithoutDealers": 14900000000,
            "ForeignInvestmentSharesWithoutDealersRatio": 57.46,
        }
    ]
    await repo.upsert_stock_shareholding(rows)
    result = await test_session.execute(select(SqliteStockShareholding))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].NumberOfSharesIssued == 25930380458


async def test_upsert_stock_shareholding_updates_on_conflict(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [{"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 100, "NumberOfSharesIssued": 99999}]
    await repo.upsert_stock_shareholding(rows)
    # Partial update: only ForeignInvestmentShares — NumberOfSharesIssued must be preserved
    rows_updated = [{"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 999}]
    await repo.upsert_stock_shareholding(rows_updated)
    result = await repo.get_stock_shareholding("20260328", "2330")
    assert result.ForeignInvestmentShares == 999
    assert result.NumberOfSharesIssued == 99999  # untouched field must be preserved


async def test_get_stock_shareholding_returns_none_when_missing(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    result = await repo.get_stock_shareholding("20260328", "9999")
    assert result is None


async def test_get_all_stocks_shareholding_returns_multiple(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 100},
        {"date": date(2026, 3, 28), "stock_id": "2317", "ForeignInvestmentShares": 200},
    ]
    await repo.upsert_stock_shareholding(rows)
    results = await repo.get_all_stocks_shareholding("20260328")
    assert len(results) == 2


async def test_get_stock_shareholding_history(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 27), "stock_id": "2330", "ForeignInvestmentShares": 100},
        {"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 200},
        {"date": date(2026, 3, 29), "stock_id": "2330", "ForeignInvestmentShares": 300},
    ]
    await repo.upsert_stock_shareholding(rows)
    history = await repo.get_stock_shareholding_history("2330", "20260327", "20260328")
    assert len(history) == 2
    assert history[0].ForeignInvestmentShares == 100
    assert history[1].ForeignInvestmentShares == 200
