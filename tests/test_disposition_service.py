"""處置有價證券 service 測試。"""
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.disposition import DispositionService

_ROW = {
    "start_date": date(2026, 3, 1),
    "end_date": date(2026, 3, 31),
    "stock_id": "1234",
    "reason": "異常交易",
}


def _mock_adapter():
    adapter = MagicMock()
    adapter.fetch_disposition = AsyncMock(return_value=[_ROW])
    return adapter


async def test_get_by_stock_calls_adapter_on_miss(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = DispositionService(session=test_session, adapter=adapter)

    with patch("app.services.disposition.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "20260328"
        result = await service.get_by_stock("1234")

    adapter.fetch_disposition.assert_called_once()
    assert len(result) == 1
    assert result[0]["stock_id"] == "1234"


async def test_get_by_date_calls_adapter_on_miss(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = DispositionService(session=test_session, adapter=adapter)

    result = await service.get_by_date("20260315")

    adapter.fetch_disposition.assert_called_once_with("20260315")
    assert len(result) == 1
    assert result[0]["reason"] == "異常交易"


async def test_get_by_stock_returns_db_on_hit(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = DispositionService(session=test_session, adapter=adapter)

    with patch("app.services.disposition.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "20260328"
        await service.get_by_stock("1234")
        adapter.fetch_disposition.reset_mock()
        result = await service.get_by_stock("1234")

    adapter.fetch_disposition.assert_not_called()
    assert len(result) == 1
