"""信用額度 router 整合測試。"""
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app

_RECORD = {
    "date": "2026-03-28",
    "stock_id": "2330",
    "ShortSaleShares": 5000,
    "ShortSaleLimit": 100000,
}


async def test_get_stock_short_sale_200():
    mock_service = MagicMock()
    mock_service.get_stock_short_sale = AsyncMock(return_value=_RECORD)

    with patch("app.routers.short_sale.get_short_sale_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/short-sale/stock/2330?date=20260328")

    assert resp.status_code == 200
    assert resp.json()["ShortSaleShares"] == 5000


async def test_get_stock_short_sale_404():
    mock_service = MagicMock()
    mock_service.get_stock_short_sale = AsyncMock(return_value=None)

    with patch("app.routers.short_sale.get_short_sale_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/short-sale/stock/9999?date=20260328")

    assert resp.status_code == 404
