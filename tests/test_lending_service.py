"""借券 service DB cache 測試。"""
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lending import LendingService


def _mock_adapter_with_data():
    adapter = MagicMock()
    adapter.fetch_securities_lending = AsyncMock(return_value=[
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "LendingShares": 1000,
            "ReturningShares": 500,
            "LendingSharesBalance": 50000,
        }
    ])
    return adapter


async def test_get_stock_lending_calls_adapter_on_miss(test_session: AsyncSession):
    """DB miss → adapter 被呼叫，資料存入 DB。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    result = await service.get_stock_lending("20260328", "2330")

    adapter.fetch_securities_lending.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["LendingShares"] == 1000


async def test_get_stock_lending_returns_db_on_hit(test_session: AsyncSession):
    """DB hit → adapter 不被呼叫。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    await service.get_stock_lending("20260328", "2330")
    adapter.fetch_securities_lending.reset_mock()

    result = await service.get_stock_lending("20260328", "2330")
    adapter.fetch_securities_lending.assert_not_called()
    assert result["LendingSharesBalance"] == 50000


async def test_get_stock_lending_returns_none_for_unknown(test_session: AsyncSession):
    """未知 stock_id → 回傳 None。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    result = await service.get_stock_lending("20260328", "9999")
    assert result is None


async def test_get_stock_lending_history_empty_before_ingest(test_session: AsyncSession):
    """空 DB history 查詢回傳 []。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    result = await service.get_stock_lending_history("2330", "20260101", "20260328")
    assert result == []
