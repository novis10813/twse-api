"""信用額度 service DB cache 測試。"""
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.short_sale import ShortSaleService


def _mock_adapter():
    adapter = MagicMock()
    adapter.fetch_short_sale_balances = AsyncMock(return_value=[
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "ShortSaleShares": 5000,
            "ShortSaleLimit": 100000,
        }
    ])
    return adapter


async def test_get_stock_short_sale_calls_adapter_on_miss(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = ShortSaleService(session=test_session, adapter=adapter)

    result = await service.get_stock_short_sale("20260328", "2330")

    adapter.fetch_short_sale_balances.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["ShortSaleShares"] == 5000


async def test_get_stock_short_sale_returns_db_on_hit(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = ShortSaleService(session=test_session, adapter=adapter)

    await service.get_stock_short_sale("20260328", "2330")
    adapter.fetch_short_sale_balances.reset_mock()

    result = await service.get_stock_short_sale("20260328", "2330")
    adapter.fetch_short_sale_balances.assert_not_called()
    assert result is not None
    assert result["ShortSaleLimit"] == 100000


async def test_get_stock_short_sale_returns_none_for_unknown(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = ShortSaleService(session=test_session, adapter=adapter)

    result = await service.get_stock_short_sale("20260328", "9999")
    assert result is None
