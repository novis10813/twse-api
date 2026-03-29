"""Disposition Service — 處置有價證券 (DB-first cache)."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import DispositionSource
from app.adapters.twse_playwright import get_playwright_client
from app.db.repository import TWSERepository

logger = logging.getLogger(__name__)

_TW_TZ = timezone(timedelta(hours=8))


class DispositionService:
    def __init__(self, session: AsyncSession, adapter: Optional[DispositionSource] = None):
        self.repo = TWSERepository(session)
        self.adapter = adapter or get_playwright_client()
        self.session = session

    async def get_by_stock(
        self, stock_id: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """取得某 stock 所有處置記錄。force_refresh 時重新爬取今日公告。"""
        if not force_refresh:
            records = await self.repo.get_disposition_by_stock(stock_id)
            if records:
                return [self._format(r) for r in records]

        today = datetime.now(_TW_TZ).strftime("%Y%m%d")
        await self._ingest(today)
        records = await self.repo.get_disposition_by_stock(stock_id)
        return [self._format(r) for r in records]

    async def get_by_date(
        self, date_str: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """取得某日有效的所有處置。"""
        if not force_refresh:
            records = await self.repo.get_disposition_by_date(date_str)
            if records:
                return [self._format(r) for r in records]

        await self._ingest(date_str)
        records = await self.repo.get_disposition_by_date(date_str)
        return [self._format(r) for r in records]

    async def _ingest(self, date_str: str) -> None:
        rows = await self.adapter.fetch_disposition(date_str)
        await self.repo.upsert_disposition(rows)
        await self.session.flush()

    def _format(self, record) -> dict[str, Any]:
        return {
            "start_date": record.start_date.strftime("%Y-%m-%d"),
            "end_date": record.end_date.strftime("%Y-%m-%d") if record.end_date else None,
            "stock_id": record.stock_id,
            "reason": record.reason,
        }


def get_disposition_service(session: AsyncSession) -> DispositionService:
    return DispositionService(session=session)
