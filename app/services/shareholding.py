"""
Shareholding Service — 外資持股比例 (DB-first cache).

MI_QFIIS response structure:
  data: list of stock rows (7 columns each)

data column indices:
  [0] 證券代號                               → stock_id
  [1] 證券名稱                               → (ignored)
  [2] 發行股數                               → NumberOfSharesIssued
  [3] 外資及陸資(不含外資自營商)-持有股數      → ForeignInvestmentSharesWithoutDealers
  [4] 外資及陸資(不含外資自營商)-持股比例(%)   → ForeignInvestmentSharesWithoutDealersRatio
  [5] 外資及陸資-持有股數                     → ForeignInvestmentShares
  [6] 外資及陸資-持股比例(%)                  → ForeignInvestmentSharesRatio

NOTE: Verify actual TWSE response format before deploying. Run:
  curl "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?response=json&date=20260101&selectType=ALLBUT0999"
"""
import logging
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from app.services.twse_client import TWSEClient, get_twse_client

logger = logging.getLogger(__name__)


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _float(value: str) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _parse_date(date_str: str) -> date_type:
    return date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))


class ShareholdingService:
    def __init__(self, session: AsyncSession, client: Optional[TWSEClient] = None):
        self.repo = TWSERepository(session)
        self.client = client or get_twse_client()
        self.session = session

    async def get_stock_shareholding(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """個股外資持股。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            record = await self.repo.get_stock_shareholding(date_str, stock_id)
            if record:
                return self._format_shareholding(record)

        await self._ingest_shareholding(date_str)
        record = await self.repo.get_stock_shareholding(date_str, stock_id)
        return self._format_shareholding(record) if record else None

    async def get_all_stocks_shareholding(
        self, date_str: str, force_refresh: bool = False
    ) -> dict[str, Any]:
        """全市場外資持股列表。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            rows = await self.repo.get_all_stocks_shareholding(date_str)
            if rows:
                return self._format_all_stocks(date_str, rows)

        await self._ingest_shareholding(date_str)
        rows = await self.repo.get_all_stocks_shareholding(date_str)
        return self._format_all_stocks(date_str, rows)

    async def get_stock_shareholding_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """個股外資持股歷史（僅從 DB 查，不自動補爬）。"""
        records = await self.repo.get_stock_shareholding_history(stock_id, start_date, end_date)
        return [self._format_shareholding(r) for r in records]

    # ── Ingest ───────────────────────────────────────────────────

    async def _ingest_shareholding(self, date_str: str) -> None:
        raw = await self.client.fetch_shareholding_data(date_str)
        rows = self._parse_shareholding(date_str, raw)
        await self.repo.upsert_stock_shareholding(rows)
        await self.session.flush()

    # ── Parser ───────────────────────────────────────────────────

    def _parse_shareholding(self, date_str: str, data: dict) -> list[dict]:
        """MI_QFIIS data → rows for twse_stock_shareholding."""
        d = _parse_date(date_str)
        rows = []
        for row in data.get("data", []):
            if len(row) < 7:
                continue
            try:
                rows.append({
                    "date": d,
                    "stock_id": row[0].strip(),
                    "NumberOfSharesIssued": _int(row[2]),
                    "ForeignInvestmentSharesWithoutDealers": _int(row[3]),
                    "ForeignInvestmentSharesWithoutDealersRatio": _float(row[4]),
                    "ForeignInvestmentShares": _int(row[5]),
                    "ForeignInvestmentSharesRatio": _float(row[6]),
                })
            except (ValueError, IndexError):
                continue
        return rows

    # ── Formatter ────────────────────────────────────────────────

    def _format_shareholding(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "NumberOfSharesIssued": record.NumberOfSharesIssued,
            "ForeignInvestmentShares": record.ForeignInvestmentShares,
            "ForeignInvestmentSharesRatio": float(record.ForeignInvestmentSharesRatio),
            "ForeignInvestmentSharesWithoutDealers": record.ForeignInvestmentSharesWithoutDealers,
            "ForeignInvestmentSharesWithoutDealersRatio": float(record.ForeignInvestmentSharesWithoutDealersRatio),
        }

    def _format_all_stocks(self, date_str: str, rows) -> dict[str, Any]:
        return {
            "date": date_str,
            "stocks": [self._format_shareholding(r) for r in rows],
        }


def get_shareholding_service(session: AsyncSession) -> ShareholdingService:
    return ShareholdingService(session=session)
