"""Disposition Router — 處置有價證券 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.disposition import get_disposition_service

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/stock/{stock_id}")
async def get_disposition_by_stock(
    stock_id: str,
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股處置記錄 — FinMind: TaiwanStockDispositionSecuritiesPeriod"""
    return await get_disposition_service(session).get_by_stock(stock_id, force_refresh)


@router.get("")
async def get_disposition_by_date(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """某日有效的全市場處置清單"""
    date = date or _default_date()
    return await get_disposition_service(session).get_by_date(date, force_refresh)
