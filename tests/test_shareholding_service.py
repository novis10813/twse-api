"""Shareholding service DB cache tests."""
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shareholding import ShareholdingService


def _mock_client_with_data():
    client = MagicMock()
    client.fetch_shareholding_data = AsyncMock(return_value={
        "stat": "OK",
        "date": "20260328",
        "data": [
            ["2330", "台積電", "25,930,380,458", "14,900,000,000", "57.46", "15,000,000,000", "57.84"],
        ],
    })
    return client


async def test_get_stock_shareholding_calls_client_on_miss(test_session: AsyncSession):
    """DB miss → client should be called, data stored."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_stock_shareholding("20260328", "2330")

    client.fetch_shareholding_data.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["ForeignInvestmentSharesRatio"] == 57.84


async def test_get_stock_shareholding_returns_db_on_hit(test_session: AsyncSession):
    """DB hit → client should NOT be called."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    await service.get_stock_shareholding("20260328", "2330")
    client.fetch_shareholding_data.reset_mock()

    result = await service.get_stock_shareholding("20260328", "2330")
    client.fetch_shareholding_data.assert_not_called()
    assert result["ForeignInvestmentSharesRatio"] == 57.84


async def test_get_stock_shareholding_returns_none_for_unknown(test_session: AsyncSession):
    """Unknown stock_id → returns None."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_stock_shareholding("20260328", "9999")
    assert result is None


async def test_get_stock_shareholding_history_empty_before_ingest(test_session: AsyncSession):
    """History query on empty DB returns []."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_stock_shareholding_history("2330", "20260101", "20260328")
    assert result == []


async def test_get_all_stocks_shareholding_calls_client_on_miss(test_session: AsyncSession):
    """DB miss → client called, returns all stocks for that date."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_all_stocks_shareholding("20260328")

    client.fetch_shareholding_data.assert_called_once_with("20260328")
    assert result["date"] == "20260328"
    assert len(result["stocks"]) == 1
    assert result["stocks"][0]["stock_id"] == "2330"
    assert result["stocks"][0]["ForeignInvestmentSharesRatio"] == 57.84
