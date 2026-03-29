"""Lending Router — 借券成交明細 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.lending import get_lending_service

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/stock/{stock_id}")
async def get_stock_lending(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股借券成交明細 — FinMind: TaiwanStockSecuritiesLending"""
    date = date or _default_date()
    result = await get_lending_service(session).get_stock_lending(date, stock_id, force_refresh)
    if result is None:
        raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
    return result


@router.get("/stock/{stock_id}/history")
async def get_stock_lending_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股借券歷史（從 DB 查，不補爬）"""
    return await get_lending_service(session).get_stock_lending_history(
        stock_id, start_date, end_date
    )
