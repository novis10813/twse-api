"""Margin router integration tests."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


async def test_margin_stock_returns_200():
    """GET /api/v1/margin/stock/2330 should return 200 with correct fields."""
    mock_service = MagicMock()
    mock_service.get_stock_margin = AsyncMock(return_value={
        "date": "2026-03-28",
        "stock_id": "2330",
        "MarginPurchaseTodayBalance": 10350,
        "MarginPurchaseLimit": 100000,
        "ShortSaleTodayBalance": 680,
        "ShortSaleLimit": 50000,
        "OffsetLoanAndShort": 30,
        "MarginPurchaseBuy": 1200,
        "MarginPurchaseSell": 800,
        "MarginPurchaseCashRepayment": 50,
        "MarginPurchaseYesterdayBalance": 10000,
        "ShortSaleBuy": 100,
        "ShortSaleSell": 300,
        "ShortSaleCashRepayment": 20,
        "ShortSaleYesterdayBalance": 500,
    })

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/margin/stock/2330?date=20260328")

    assert response.status_code == 200
    data = response.json()
    assert data["stock_id"] == "2330"
    assert data["MarginPurchaseTodayBalance"] == 10350


async def test_margin_stock_returns_404_when_not_found():
    """GET /api/v1/margin/stock/9999 should return 404 when stock not in data."""
    mock_service = MagicMock()
    mock_service.get_stock_margin = AsyncMock(return_value=None)

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/margin/stock/9999?date=20260328")

    assert response.status_code == 404


async def test_margin_summary_returns_200():
    """GET /api/v1/margin/summary should return 200."""
    mock_service = MagicMock()
    mock_service.get_total_margin = AsyncMock(return_value={
        "date": "20260328",
        "items": [
            {"name": "MarginPurchase", "buy": 100000, "sell": 80000, "TodayBalance": 915000, "YesBalance": 900000, "Return": 5000},
        ]
    })

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/margin/summary?date=20260328")

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "MarginPurchase"


async def test_margin_history_returns_200():
    """GET /api/v1/margin/stock/2330/history should return 200."""
    mock_service = MagicMock()
    mock_service.get_stock_margin_history = AsyncMock(return_value=[])

    with patch("app.routers.margin.get_margin_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/margin/stock/2330/history?start_date=20260101&end_date=20260328"
            )

    assert response.status_code == 200
    assert response.json() == []
