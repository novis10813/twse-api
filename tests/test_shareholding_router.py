"""Shareholding router integration tests."""
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


async def test_shareholding_stock_returns_200():
    """GET /api/v1/shareholding/stock/2330 should return 200 with correct fields."""
    mock_service = MagicMock()
    mock_service.get_stock_shareholding = AsyncMock(return_value={
        "date": "2026-03-28",
        "stock_id": "2330",
        "NumberOfSharesIssued": 25930380458,
        "ForeignInvestmentShares": 15000000000,
        "ForeignInvestmentSharesRatio": 57.84,
        "ForeignInvestmentSharesWithoutDealers": 14900000000,
        "ForeignInvestmentSharesWithoutDealersRatio": 57.46,
    })

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/shareholding/stock/2330?date=20260328")

    assert response.status_code == 200
    data = response.json()
    assert data["stock_id"] == "2330"
    assert data["ForeignInvestmentSharesRatio"] == 57.84


async def test_shareholding_stock_returns_404_when_not_found():
    """GET /api/v1/shareholding/stock/9999 should return 404 when stock not in data."""
    mock_service = MagicMock()
    mock_service.get_stock_shareholding = AsyncMock(return_value=None)

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/shareholding/stock/9999?date=20260328")

    assert response.status_code == 404


async def test_shareholding_stocks_returns_200():
    """GET /api/v1/shareholding/stocks should return 200."""
    mock_service = MagicMock()
    mock_service.get_all_stocks_shareholding = AsyncMock(return_value={
        "date": "20260328",
        "stocks": [
            {
                "date": "2026-03-28",
                "stock_id": "2330",
                "NumberOfSharesIssued": 25930380458,
                "ForeignInvestmentShares": 15000000000,
                "ForeignInvestmentSharesRatio": 57.84,
                "ForeignInvestmentSharesWithoutDealers": 14900000000,
                "ForeignInvestmentSharesWithoutDealersRatio": 57.46,
            }
        ],
    })

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/shareholding/stocks?date=20260328")

    assert response.status_code == 200
    assert len(response.json()["stocks"]) == 1


async def test_shareholding_history_returns_200():
    """GET /api/v1/shareholding/stock/2330/history should return 200."""
    mock_service = MagicMock()
    mock_service.get_stock_shareholding_history = AsyncMock(return_value=[])

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/shareholding/stock/2330/history?start_date=20260101&end_date=20260328"
            )

    assert response.status_code == 200
    assert response.json() == []
