"""
Margin Service — 融資融券資料 (DB-first cache).

MI_MARGN response structure:
  data0: individual stock rows
  data1: market total rows (3 rows: 融資/融券/融資金額)

data0 column indices:
  [0] 股票代號
  [1] 股票名稱
  [2] 融資-買進(張)      → MarginPurchaseBuy
  [3] 融資-賣出(張)      → MarginPurchaseSell
  [4] 融資-現金償還(張)  → MarginPurchaseCashRepayment
  [5] 融資-前日餘額(張)  → MarginPurchaseYesterdayBalance
  [6] 融資-今日餘額(張)  → MarginPurchaseTodayBalance
  [7] 融資-限額(千張)    → MarginPurchaseLimit
  [8] 融券-賣出(張)      → ShortSaleSell
  [9] 融券-買進(張)      → ShortSaleBuy
  [10] 融券-現金償還(張) → ShortSaleCashRepayment
  [11] 融券-前日餘額(張) → ShortSaleYesterdayBalance
  [12] 融券-今日餘額(張) → ShortSaleTodayBalance
  [13] 融券-限額(千張)   → ShortSaleLimit
  [14] 資券互抵(張)      → OffsetLoanAndShort

data1 column indices:
  [0] 項目別 (融資/融券/融資金額)
  [1] 買進(張)   → buy
  [2] 賣出(張)   → sell
  [3] 現金償還   → Return
  [4] 前日餘額   → YesBalance
  [5] 今日餘額   → TodayBalance
  [6] 限額       → (ignored)

NOTE: Verify actual TWSE response format before deploying. Run:
  curl "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date=20260101&selectType=ALL"
"""
import logging
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from app.services.twse_client import TWSEClient, get_twse_client

logger = logging.getLogger(__name__)

_TOTAL_NAME_MAP = {
    "融資": "MarginPurchase",
    "融資(借錢買)": "MarginPurchase",
    "融券": "ShortSale",
    "融券(借券賣)": "ShortSale",
    "融資金額": "MarginPurchaseMoney",
    "融資金額(仟元)": "MarginPurchaseMoney",
}


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _parse_date(date_str: str) -> date_type:
    return date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))


class MarginService:
    def __init__(self, session: AsyncSession, client: Optional[TWSEClient] = None):
        self.repo = TWSERepository(session)
        self.client = client or get_twse_client()
        self.session = session

    async def get_stock_margin(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """個股融資融券。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            record = await self.repo.get_stock_margin(date_str, stock_id)
            if record:
                return self._format_stock_margin(record)

        await self._ingest_margin(date_str)
        record = await self.repo.get_stock_margin(date_str, stock_id)
        return self._format_stock_margin(record) if record else None

    async def get_total_margin(self, date_str: str, force_refresh: bool = False) -> dict[str, Any]:
        """整體市場融資融券。"""
        if not force_refresh:
            rows = await self.repo.get_total_margin(date_str)
            if rows:
                return self._format_total_margin(date_str, rows)

        await self._ingest_margin(date_str)
        rows = await self.repo.get_total_margin(date_str)
        return self._format_total_margin(date_str, rows)

    async def get_stock_margin_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """個股融資融券歷史（僅從 DB 查，不自動補爬）。"""
        records = await self.repo.get_stock_margin_history(stock_id, start_date, end_date)
        return [self._format_stock_margin(r) for r in records]

    # ── Ingest ───────────────────────────────────────────────────

    async def _ingest_margin(self, date_str: str) -> None:
        raw = await self.client.fetch_margin_data(date_str)
        stock_rows = self._parse_stock_margin(date_str, raw)
        total_rows = self._parse_total_margin(date_str, raw)
        await self.repo.upsert_stock_margin(stock_rows)
        await self.repo.upsert_total_margin(total_rows)
        await self.session.flush()
        # Eager compute placeholder — indicators_pipeline.compute() goes here (batch 3)

    # ── Parsers ──────────────────────────────────────────────────

    def _parse_stock_margin(self, date_str: str, data: dict) -> list[dict]:
        """MI_MARGN data0 → rows for twse_stock_margin."""
        d = _parse_date(date_str)
        rows = []
        for row in data.get("data0", []):
            if len(row) < 15:
                continue
            try:
                rows.append({
                    "date": d,
                    "stock_id": row[0].strip(),
                    "MarginPurchaseBuy": _int(row[2]),
                    "MarginPurchaseSell": _int(row[3]),
                    "MarginPurchaseCashRepayment": _int(row[4]),
                    "MarginPurchaseYesterdayBalance": _int(row[5]),
                    "MarginPurchaseTodayBalance": _int(row[6]),
                    "MarginPurchaseLimit": _int(row[7]),
                    "ShortSaleSell": _int(row[8]),
                    "ShortSaleBuy": _int(row[9]),
                    "ShortSaleCashRepayment": _int(row[10]),
                    "ShortSaleYesterdayBalance": _int(row[11]),
                    "ShortSaleTodayBalance": _int(row[12]),
                    "ShortSaleLimit": _int(row[13]),
                    "OffsetLoanAndShort": _int(row[14]),
                })
            except (ValueError, IndexError):
                continue
        return rows

    def _parse_total_margin(self, date_str: str, data: dict) -> list[dict]:
        """MI_MARGN data1 → rows for twse_total_margin."""
        d = _parse_date(date_str)
        rows = []
        for row in data.get("data1", []):
            if len(row) < 6:
                continue
            raw_name = row[0].strip()
            finmind_name = _TOTAL_NAME_MAP.get(raw_name)
            if not finmind_name:
                continue
            try:
                rows.append({
                    "date": d,
                    "name": finmind_name,
                    "buy": _int(row[1]),
                    "sell": _int(row[2]),
                    "Return": _int(row[3]),
                    "YesBalance": _int(row[4]),
                    "TodayBalance": _int(row[5]),
                })
            except (ValueError, IndexError):
                continue
        return rows

    # ── Formatters ───────────────────────────────────────────────

    def _format_stock_margin(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "MarginPurchaseBuy": record.MarginPurchaseBuy,
            "MarginPurchaseSell": record.MarginPurchaseSell,
            "MarginPurchaseCashRepayment": record.MarginPurchaseCashRepayment,
            "MarginPurchaseTodayBalance": record.MarginPurchaseTodayBalance,
            "MarginPurchaseYesterdayBalance": record.MarginPurchaseYesterdayBalance,
            "MarginPurchaseLimit": record.MarginPurchaseLimit,
            "ShortSaleBuy": record.ShortSaleBuy,
            "ShortSaleSell": record.ShortSaleSell,
            "ShortSaleCashRepayment": record.ShortSaleCashRepayment,
            "ShortSaleTodayBalance": record.ShortSaleTodayBalance,
            "ShortSaleYesterdayBalance": record.ShortSaleYesterdayBalance,
            "ShortSaleLimit": record.ShortSaleLimit,
            "OffsetLoanAndShort": record.OffsetLoanAndShort,
        }

    def _format_total_margin(self, date_str: str, rows) -> dict[str, Any]:
        return {
            "date": date_str,
            "items": [
                {
                    "name": r.name,
                    "buy": r.buy,
                    "sell": r.sell,
                    "TodayBalance": r.TodayBalance,
                    "YesBalance": r.YesBalance,
                    "Return": r.Return,
                }
                for r in rows
            ],
        }


def get_margin_service(session: AsyncSession) -> MarginService:
    return MarginService(session=session)
