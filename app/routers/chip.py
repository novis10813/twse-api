"""Chip Data Router — 三大法人 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.chip import get_chip_service
from app.services.twse_client import TWSEAPIError

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/summary")
async def get_chip_summary(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """三大法人買賣金額統計 (BFI82U)"""
    date = date or _default_date()
    try:
        return await get_chip_service(session).get_chip_summary(date, force_refresh)
    except TWSEAPIError as e:
        if e.status_code == 404 or "沒有符合" in str(e.message):
            raise HTTPException(404, f"No data for date: {date}")
        raise HTTPException(500, str(e.message))


@router.get("/stocks")
async def get_stock_chip_list(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股三大法人買賣超列表 (T86)"""
    date = date or _default_date()
    try:
        return await get_chip_service(session).get_all_stocks_chip(date, force_refresh)
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))


@router.get("/stock/{stock_id}")
async def get_stock_chip_detail(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股三大法人詳情"""
    date = date or _default_date()
    try:
        result = await get_chip_service(session).get_stock_chip(date, stock_id, force_refresh)
        if result is None:
            raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
        return result
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))
