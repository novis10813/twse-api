"""處置 router 整合測試。"""
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app

_RECORD = {
    "start_date": "2026-03-01",
    "end_date": "2026-03-31",
    "stock_id": "1234",
    "reason": "異常交易",
}


async def test_get_disposition_by_stock_200():
    mock_service = MagicMock()
    mock_service.get_by_stock = AsyncMock(return_value=[_RECORD])

    with patch("app.routers.disposition.get_disposition_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/disposition/stock/1234")

    assert resp.status_code == 200
    assert resp.json()[0]["reason"] == "異常交易"


async def test_get_disposition_by_date_200():
    mock_service = MagicMock()
    mock_service.get_by_date = AsyncMock(return_value=[_RECORD])

    with patch("app.routers.disposition.get_disposition_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/disposition?date=20260315")

    assert resp.status_code == 200
    assert resp.json()[0]["stock_id"] == "1234"
