"""Margin service DB cache tests."""
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.margin import MarginService


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
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_stock_margin("20260328", "2330")

    client.fetch_margin_data.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["MarginPurchaseTodayBalance"] == 10350


async def test_get_stock_margin_returns_db_on_hit(test_session: AsyncSession):
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    await service.get_stock_margin("20260328", "2330")
    client.fetch_margin_data.reset_mock()

    result = await service.get_stock_margin("20260328", "2330")
    client.fetch_margin_data.assert_not_called()
    assert result["MarginPurchaseTodayBalance"] == 10350


async def test_get_stock_margin_returns_none_for_unknown_stock(test_session: AsyncSession):
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_stock_margin("20260328", "9999")
    assert result is None


async def test_get_total_margin_returns_three_rows(test_session: AsyncSession):
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_total_margin("20260328")
    assert len(result["items"]) == 3
    names = {item["name"] for item in result["items"]}
    assert names == {"MarginPurchase", "ShortSale", "MarginPurchaseMoney"}


async def test_get_stock_margin_history_empty_before_ingest(test_session: AsyncSession):
    client = _mock_client_with_data()
    service = MarginService(session=test_session, client=client)

    result = await service.get_stock_margin_history("2330", "20260101", "20260328")
    assert result == []
