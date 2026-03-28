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
