"""借券 router 整合測試。"""
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app

_LENDING_RECORD = {
    "date": "2026-03-28",
    "stock_id": "2330",
    "LendingShares": 1000,
    "ReturningShares": 500,
    "LendingSharesBalance": 50000,
}


async def test_get_stock_lending_200():
    mock_service = MagicMock()
    mock_service.get_stock_lending = AsyncMock(return_value=_LENDING_RECORD)

    with patch("app.routers.lending.get_lending_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/lending/stock/2330?date=20260328")

    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_id"] == "2330"
    assert data["LendingShares"] == 1000


async def test_get_stock_lending_404():
    mock_service = MagicMock()
    mock_service.get_stock_lending = AsyncMock(return_value=None)

    with patch("app.routers.lending.get_lending_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/lending/stock/9999?date=20260328")

    assert resp.status_code == 404


async def test_get_stock_lending_history_200():
    mock_service = MagicMock()
    mock_service.get_stock_lending_history = AsyncMock(return_value=[_LENDING_RECORD])

    with patch("app.routers.lending.get_lending_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/lending/stock/2330/history?start_date=20260101&end_date=20260328")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["stock_id"] == "2330"
