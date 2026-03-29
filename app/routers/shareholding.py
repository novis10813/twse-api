"""Shareholding Router — 外資持股比例 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.schemas.shareholding import (
    StockShareholdingResponse,
    AllStocksShareholdingResponse,
    ErrorResponse,
)
from app.services.shareholding import get_shareholding_service
from app.services.twse_client import TWSEAPIError

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get(
    "/stocks",
    response_model=AllStocksShareholdingResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_all_stocks_shareholding(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """全市場外資持股列表 (MI_QFIIS) — FinMind: TaiwanStockShareholding"""
    date = date or _default_date()
    try:
        return await get_shareholding_service(session).get_all_stocks_shareholding(date, force_refresh)
    except TWSEAPIError as e:
        if e.status_code == 404 or "沒有符合" in str(e.message):
            raise HTTPException(404, f"No data for date: {date}")
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}",
    response_model=StockShareholdingResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_stock_shareholding(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股外資持股 (MI_QFIIS) — FinMind: TaiwanStockShareholding"""
    date = date or _default_date()
    try:
        result = await get_shareholding_service(session).get_stock_shareholding(
            date, stock_id, force_refresh
        )
        if result is None:
            raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
        return result
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}/history",
    response_model=list[StockShareholdingResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_stock_shareholding_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股外資持股歷史（從 DB 查，不補爬）"""
    try:
        return await get_shareholding_service(session).get_stock_shareholding_history(
            stock_id, start_date, end_date
        )
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))
