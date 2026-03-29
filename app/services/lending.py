"""Lending Service — 借券成交明細 (DB-first cache)."""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import LendingSource
from app.adapters.twse_playwright import get_playwright_client
from app.db.repository import TWSERepository

logger = logging.getLogger(__name__)


class LendingService:
    def __init__(self, session: AsyncSession, adapter: Optional[LendingSource] = None):
        self.repo = TWSERepository(session)
        self.adapter = adapter or get_playwright_client()
        self.session = session

    async def get_stock_lending(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """個股借券。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            record = await self.repo.get_stock_lending(date_str, stock_id)
            if record:
                return self._format(record)

        await self._ingest(date_str)
        record = await self.repo.get_stock_lending(date_str, stock_id)
        return self._format(record) if record else None

    async def get_stock_lending_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """個股借券歷史（僅從 DB 查，不自動補爬）。"""
        records = await self.repo.get_stock_lending_history(stock_id, start_date, end_date)
        return [self._format(r) for r in records]

    async def _ingest(self, date_str: str) -> None:
        rows = await self.adapter.fetch_securities_lending(date_str)
        await self.repo.upsert_stock_lending(rows)
        await self.session.flush()

    def _format(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "LendingShares": record.LendingShares,
            "ReturningShares": record.ReturningShares,
            "LendingSharesBalance": record.LendingSharesBalance,
        }


def get_lending_service(session: AsyncSession) -> LendingService:
    return LendingService(session=session)
