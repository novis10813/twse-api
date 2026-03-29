"""TWSE Repository — CRUD operations for chip and margin data."""
import logging
from datetime import date as date_type
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    StockInstitutionalInvestors,
    TotalInstitutionalInvestors,
    StockMargin,
    TotalMargin,
    StockShareholding,
    StockLending,
    ShortSaleBalances,
    Disposition,
)

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date_type:
    """Parse YYYYMMDD or YYYY-MM-DD to date."""
    date_str = date_str.strip()
    if len(date_str) == 8:
        return date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    return date_type.fromisoformat(date_str)


class TWSERepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 個股三大法人 ──────────────────────────────────────────────

    async def upsert_stock_institutional(self, rows: list[dict]) -> None:
        """Upsert rows into twse_stock_institutional_investors."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(StockInstitutionalInvestors).where(
                    StockInstitutionalInvestors.date == d,
                    StockInstitutionalInvestors.stock_id == row["stock_id"],
                    StockInstitutionalInvestors.name == row["name"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                if "buy" in row:
                    record.buy = row["buy"]
                if "sell" in row:
                    record.sell = row["sell"]
            else:
                self.session.add(StockInstitutionalInvestors(
                    date=d,
                    stock_id=row["stock_id"],
                    name=row["name"],
                    buy=row.get("buy", 0),
                    sell=row.get("sell", 0),
                ))
        await self.session.flush()

    async def get_stock_institutional(self, date_str: str, stock_id: str) -> list[StockInstitutionalInvestors]:
        """Get all name rows for a stock on a date. Returns [] if not found."""
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockInstitutionalInvestors).where(
                StockInstitutionalInvestors.date == d,
                StockInstitutionalInvestors.stock_id == stock_id,
            )
        )
        return list(result.scalars().all())

    async def get_all_stocks_institutional(self, date_str: str) -> list[StockInstitutionalInvestors]:
        """Get all stocks for a date."""
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockInstitutionalInvestors).where(StockInstitutionalInvestors.date == d)
        )
        return list(result.scalars().all())

    # ── 整體市場三大法人 ──────────────────────────────────────────

    async def upsert_total_institutional(self, rows: list[dict]) -> None:
        """Upsert rows into twse_total_institutional_investors."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(TotalInstitutionalInvestors).where(
                    TotalInstitutionalInvestors.date == d,
                    TotalInstitutionalInvestors.name == row["name"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                if "buy" in row:
                    record.buy = row["buy"]
                if "sell" in row:
                    record.sell = row["sell"]
            else:
                self.session.add(TotalInstitutionalInvestors(
                    date=d,
                    name=row["name"],
                    buy=row.get("buy", 0),
                    sell=row.get("sell", 0),
                ))
        await self.session.flush()

    async def get_total_institutional(self, date_str: str) -> list[TotalInstitutionalInvestors]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(TotalInstitutionalInvestors).where(TotalInstitutionalInvestors.date == d)
        )
        return list(result.scalars().all())

    # ── 個股融資融券 ──────────────────────────────────────────────

    async def upsert_stock_margin(self, rows: list[dict]) -> None:
        """Upsert rows into twse_stock_margin."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(StockMargin).where(
                    StockMargin.date == d,
                    StockMargin.stock_id == row["stock_id"],
                )
            )
            record = existing.scalar_one_or_none()
            fields = [
                "MarginPurchaseBuy", "MarginPurchaseSell", "MarginPurchaseCashRepayment",
                "MarginPurchaseTodayBalance", "MarginPurchaseYesterdayBalance", "MarginPurchaseLimit",
                "ShortSaleBuy", "ShortSaleSell", "ShortSaleCashRepayment",
                "ShortSaleTodayBalance", "ShortSaleYesterdayBalance", "ShortSaleLimit",
                "OffsetLoanAndShort",
            ]
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "stock_id": row["stock_id"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(StockMargin(**kwargs))
        await self.session.flush()

    async def get_stock_margin(self, date_str: str, stock_id: str) -> Optional[StockMargin]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockMargin).where(StockMargin.date == d, StockMargin.stock_id == stock_id)
        )
        return result.scalar_one_or_none()

    async def get_stock_margin_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[StockMargin]:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        result = await self.session.execute(
            select(StockMargin).where(
                StockMargin.stock_id == stock_id,
                StockMargin.date >= start,
                StockMargin.date <= end,
            ).order_by(StockMargin.date)
        )
        return list(result.scalars().all())

    # ── 整體市場融資融券 ──────────────────────────────────────────

    async def upsert_total_margin(self, rows: list[dict]) -> None:
        """Upsert rows into twse_total_margin."""
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(TotalMargin).where(TotalMargin.date == d, TotalMargin.name == row["name"])
            )
            record = existing.scalar_one_or_none()
            fields = ["buy", "sell", "TodayBalance", "YesBalance", "Return"]
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "name": row["name"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(TotalMargin(**kwargs))
        await self.session.flush()

    async def get_total_margin(self, date_str: str) -> list[TotalMargin]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(TotalMargin).where(TotalMargin.date == d)
        )
        return list(result.scalars().all())

    # ── 個股外資持股 ──────────────────────────────────────────────

    async def upsert_stock_shareholding(self, rows: list[dict]) -> None:
        """Upsert rows into twse_stock_shareholding."""
        fields = [
            "NumberOfSharesIssued",
            "ForeignInvestmentShares",
            "ForeignInvestmentSharesRatio",
            "ForeignInvestmentSharesWithoutDealers",
            "ForeignInvestmentSharesWithoutDealersRatio",
        ]
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(StockShareholding).where(
                    StockShareholding.date == d,
                    StockShareholding.stock_id == row["stock_id"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "stock_id": row["stock_id"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(StockShareholding(**kwargs))
        await self.session.flush()

    async def get_stock_shareholding(
        self, date_str: str, stock_id: str
    ) -> Optional[StockShareholding]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockShareholding).where(
                StockShareholding.date == d,
                StockShareholding.stock_id == stock_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_stocks_shareholding(self, date_str: str) -> list[StockShareholding]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockShareholding).where(StockShareholding.date == d)
        )
        return list(result.scalars().all())

    async def get_stock_shareholding_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[StockShareholding]:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        result = await self.session.execute(
            select(StockShareholding).where(
                StockShareholding.stock_id == stock_id,
                StockShareholding.date >= start,
                StockShareholding.date <= end,
            ).order_by(StockShareholding.date)
        )
        return list(result.scalars().all())

    # ── 借券成交明細 ──────────────────────────────────────────────

    async def upsert_stock_lending(self, rows: list[dict]) -> None:
        """Upsert rows into twse_stock_lending."""
        fields = ["LendingShares", "ReturningShares", "LendingSharesBalance"]
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(StockLending).where(
                    StockLending.date == d,
                    StockLending.stock_id == row["stock_id"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "stock_id": row["stock_id"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(StockLending(**kwargs))
        await self.session.flush()

    async def get_stock_lending(
        self, date_str: str, stock_id: str
    ) -> Optional[StockLending]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(StockLending).where(
                StockLending.date == d,
                StockLending.stock_id == stock_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_stock_lending_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[StockLending]:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        result = await self.session.execute(
            select(StockLending).where(
                StockLending.stock_id == stock_id,
                StockLending.date >= start,
                StockLending.date <= end,
            ).order_by(StockLending.date)
        )
        return list(result.scalars().all())

    # ── 信用額度總量管制 ──────────────────────────────────────────

    async def upsert_short_sale_balances(self, rows: list[dict]) -> None:
        """Upsert rows into twse_short_sale_balances."""
        fields = ["ShortSaleShares", "ShortSaleLimit"]
        for row in rows:
            d = row["date"] if isinstance(row["date"], date_type) else _parse_date(str(row["date"]))
            existing = await self.session.execute(
                select(ShortSaleBalances).where(
                    ShortSaleBalances.date == d,
                    ShortSaleBalances.stock_id == row["stock_id"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                for f in fields:
                    if f in row:
                        setattr(record, f, row[f])
            else:
                kwargs = {"date": d, "stock_id": row["stock_id"]}
                for f in fields:
                    kwargs[f] = row.get(f, 0)
                self.session.add(ShortSaleBalances(**kwargs))
        await self.session.flush()

    async def get_short_sale_balances(
        self, date_str: str, stock_id: str
    ) -> Optional[ShortSaleBalances]:
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(ShortSaleBalances).where(
                ShortSaleBalances.date == d,
                ShortSaleBalances.stock_id == stock_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_short_sale_balances_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[ShortSaleBalances]:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        result = await self.session.execute(
            select(ShortSaleBalances).where(
                ShortSaleBalances.stock_id == stock_id,
                ShortSaleBalances.date >= start,
                ShortSaleBalances.date <= end,
            ).order_by(ShortSaleBalances.date)
        )
        return list(result.scalars().all())

    # ── 處置有價證券 ──────────────────────────────────────────────

    async def upsert_disposition(self, rows: list[dict]) -> None:
        """Upsert rows into twse_disposition."""
        for row in rows:
            start = row["start_date"] if isinstance(row["start_date"], date_type) else _parse_date(str(row["start_date"]))
            existing = await self.session.execute(
                select(Disposition).where(
                    Disposition.start_date == start,
                    Disposition.stock_id == row["stock_id"],
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                if "end_date" in row:
                    record.end_date = row["end_date"]
                if "reason" in row:
                    record.reason = row["reason"]
            else:
                self.session.add(Disposition(
                    start_date=start,
                    end_date=row.get("end_date"),
                    stock_id=row["stock_id"],
                    reason=row.get("reason"),
                ))
        await self.session.flush()

    async def get_disposition_by_stock(self, stock_id: str) -> list[Disposition]:
        """取得某 stock 目前或歷史所有處置記錄。"""
        result = await self.session.execute(
            select(Disposition).where(
                Disposition.stock_id == stock_id,
            ).order_by(Disposition.start_date.desc())
        )
        return list(result.scalars().all())

    async def get_disposition_by_date(self, date_str: str) -> list[Disposition]:
        """取得某日有效的所有處置（start_date <= date <= end_date，或 end_date is null）。"""
        from sqlalchemy import or_, null
        d = _parse_date(date_str)
        result = await self.session.execute(
            select(Disposition).where(
                Disposition.start_date <= d,
                or_(Disposition.end_date >= d, Disposition.end_date == null()),
            ).order_by(Disposition.start_date)
        )
        return list(result.scalars().all())
