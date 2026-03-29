"""Short Sale Service — 信用額度總量管制 (DB-first cache)."""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import ShortSaleSource
from app.adapters.twse_playwright import get_playwright_client
from app.db.repository import TWSERepository

logger = logging.getLogger(__name__)


class ShortSaleService:
    def __init__(self, session: AsyncSession, adapter: Optional[ShortSaleSource] = None):
        self.repo = TWSERepository(session)
        self.adapter = adapter or get_playwright_client()
        self.session = session

    async def get_stock_short_sale(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        if not force_refresh:
            record = await self.repo.get_short_sale_balances(date_str, stock_id)
            if record:
                return self._format(record)

        await self._ingest(date_str)
        record = await self.repo.get_short_sale_balances(date_str, stock_id)
        return self._format(record) if record else None

    async def get_stock_short_sale_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        records = await self.repo.get_short_sale_balances_history(stock_id, start_date, end_date)
        return [self._format(r) for r in records]

    async def _ingest(self, date_str: str) -> None:
        rows = await self.adapter.fetch_short_sale_balances(date_str)
        await self.repo.upsert_short_sale_balances(rows)
        await self.session.flush()

    def _format(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "ShortSaleShares": record.ShortSaleShares,
            "ShortSaleLimit": record.ShortSaleLimit,
        }


def get_short_sale_service(session: AsyncSession) -> ShortSaleService:
    return ShortSaleService(session=session)
