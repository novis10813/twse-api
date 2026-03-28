"""Margin Router — 融資融券 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.schemas.margin import StockMarginResponse, TotalMarginResponse, ErrorResponse
from app.services.margin import get_margin_service
from app.services.twse_client import TWSEAPIError

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get(
    "/summary",
    response_model=TotalMarginResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_margin_summary(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """整體市場融資融券統計 (MI_MARGN data1) — FinMind: TaiwanStockTotalMarginPurchaseShortSale"""
    date = date or _default_date()
    try:
        return await get_margin_service(session).get_total_margin(date, force_refresh)
    except TWSEAPIError as e:
        if e.status_code == 404 or "沒有符合" in str(e.message):
            raise HTTPException(404, f"No data for date: {date}")
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}",
    response_model=StockMarginResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_stock_margin(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股融資融券 (MI_MARGN data0) — FinMind: TaiwanStockMarginPurchaseShortSale"""
    date = date or _default_date()
    try:
        result = await get_margin_service(session).get_stock_margin(date, stock_id, force_refresh)
        if result is None:
            raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
        return result
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}/history",
    response_model=list[StockMarginResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_stock_margin_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股融資融券歷史（從 DB 查，不補爬）"""
    try:
        return await get_margin_service(session).get_stock_margin_history(stock_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(500, str(e))
