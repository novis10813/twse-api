"""
Chip Service — 三大法人資料 (DB-first cache).
Parses TWSE T86 / BFI82U responses and maps to FinMind-compatible names.
"""
import logging
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from app.services.twse_client import TWSEClient, get_twse_client

logger = logging.getLogger(__name__)

# T86 column → FinMind name mapping
# Each tuple: (buy_col_idx, sell_col_idx, finmind_name)
T86_NAME_MAP = [
    (2,  3,  "Foreign_Dealer"),       # 外陸資
    (5,  6,  "Foreign_Dealer_Self"),  # 外資自營商
    (8,  9,  "Investment_Trust"),     # 投信
    (12, 13, "Dealer_self"),          # 自營商(自行買賣)
    (15, 16, "Dealer_Hedging"),       # 自營商(避險)
]


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


class ChipService:
    def __init__(self, session: AsyncSession, client: Optional[TWSEClient] = None):
        self.repo = TWSERepository(session)
        self.client = client or get_twse_client()
        self.session = session

    async def get_chip_summary(self, date_str: str, force_refresh: bool = False) -> dict[str, Any]:
        """整體市場三大法人。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            rows = await self.repo.get_total_institutional(date_str)
            if rows:
                return self._format_chip_summary(date_str, rows)

        raw = await self.client.fetch_chip_summary(date_str)
        db_rows = self._parse_bfi82u(date_str, raw)
        await self.repo.upsert_total_institutional(db_rows)
        await self.session.flush()
        rows = await self.repo.get_total_institutional(date_str)
        return self._format_chip_summary(date_str, rows)

    async def get_all_stocks_chip(self, date_str: str, force_refresh: bool = False) -> dict[str, Any]:
        """個股三大法人列表。"""
        if not force_refresh:
            rows = await self.repo.get_all_stocks_institutional(date_str)
            if rows:
                return self._format_stocks_chip(date_str, rows)

        raw = await self.client.fetch_stock_chip_data(date_str)
        db_rows = self._parse_t86(date_str, raw)
        await self.repo.upsert_stock_institutional(db_rows)
        await self.session.flush()
        rows = await self.repo.get_all_stocks_institutional(date_str)
        return self._format_stocks_chip(date_str, rows)

    async def get_stock_chip(self, date_str: str, stock_id: str, force_refresh: bool = False) -> Optional[dict[str, Any]]:
        """個股三大法人。若不存在回傳 None。"""
        if not force_refresh:
            rows = await self.repo.get_stock_institutional(date_str, stock_id)
            if rows:
                return self._format_single_stock(date_str, stock_id, rows)

        raw = await self.client.fetch_stock_chip_data(date_str)
        db_rows = self._parse_t86(date_str, raw)
        await self.repo.upsert_stock_institutional(db_rows)
        await self.session.flush()
        rows = await self.repo.get_stock_institutional(date_str, stock_id)
        if not rows:
            return None
        return self._format_single_stock(date_str, stock_id, rows)

    # ── Parsers ──────────────────────────────────────────────────

    def _parse_bfi82u(self, date_str: str, data: dict) -> list[dict]:
        """BFI82U → rows for twse_total_institutional_investors."""
        d = date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        rows = []
        for row in data.get("data", []):
            if len(row) >= 4:
                try:
                    rows.append({
                        "date": d,
                        "name": row[0].strip(),
                        "buy": _int(row[1]),
                        "sell": _int(row[2]),
                    })
                except (ValueError, IndexError):
                    continue
        return rows

    def _parse_t86(self, date_str: str, data: dict) -> list[dict]:
        """T86 → rows for twse_stock_institutional_investors."""
        d = date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        rows = []
        for row in data.get("data", []):
            if len(row) < 17:
                continue
            stock_id = row[0].strip()
            for buy_idx, sell_idx, name in T86_NAME_MAP:
                try:
                    rows.append({
                        "date": d,
                        "stock_id": stock_id,
                        "name": name,
                        "buy": _int(row[buy_idx]),
                        "sell": _int(row[sell_idx]),
                    })
                except (ValueError, IndexError):
                    continue
        return rows

    # ── Formatters ───────────────────────────────────────────────

    def _format_chip_summary(self, date_str: str, rows) -> dict[str, Any]:
        investors = [{"name": r.name, "buy": r.buy, "sell": r.sell, "diff": r.buy - r.sell} for r in rows]
        total_diff = next((r.buy - r.sell for r in rows if "合計" in r.name), 0)
        return {"date": date_str, "investors": investors, "total_diff": total_diff}

    def _format_stocks_chip(self, date_str: str, rows) -> dict[str, Any]:
        stocks_map: dict[str, dict] = {}
        for r in rows:
            if r.stock_id not in stocks_map:
                stocks_map[r.stock_id] = {
                    "stock_id": r.stock_id, "date": date_str,
                    "foreign_buy": 0, "foreign_sell": 0, "foreign_diff": 0,
                    "trust_buy": 0, "trust_sell": 0, "trust_diff": 0,
                    "dealer_diff": 0, "total_diff": 0,
                }
            s = stocks_map[r.stock_id]
            if r.name == "Foreign_Dealer":
                s["foreign_buy"] = r.buy
                s["foreign_sell"] = r.sell
                s["foreign_diff"] = r.buy - r.sell
            elif r.name == "Investment_Trust":
                s["trust_buy"] = r.buy
                s["trust_sell"] = r.sell
                s["trust_diff"] = r.buy - r.sell
            elif r.name in ("Dealer_self", "Dealer_Hedging"):
                s["dealer_diff"] += r.buy - r.sell
        stocks = list(stocks_map.values())
        for s in stocks:
            s["total_diff"] = s["foreign_diff"] + s["trust_diff"] + s["dealer_diff"]
        return {
            "date": date_str,
            "stocks": stocks,
            "top_foreign_buy": sorted(stocks, key=lambda x: x["foreign_diff"], reverse=True)[:10],
            "top_foreign_sell": sorted(stocks, key=lambda x: x["foreign_diff"])[:10],
            "top_trust_buy": sorted(stocks, key=lambda x: x["trust_diff"], reverse=True)[:10],
            "top_trust_sell": sorted(stocks, key=lambda x: x["trust_diff"])[:10],
        }

    def _format_single_stock(self, date_str: str, stock_id: str, rows) -> dict[str, Any]:
        result = {
            "stock_id": stock_id, "date": date_str,
            "foreign_buy": 0, "foreign_sell": 0, "foreign_diff": 0,
            "trust_buy": 0, "trust_sell": 0, "trust_diff": 0,
            "dealer_self_diff": 0, "dealer_hedge_diff": 0, "dealer_diff": 0,
            "total_diff": 0,
        }
        for r in rows:
            if r.name == "Foreign_Dealer":
                result["foreign_buy"] = r.buy
                result["foreign_sell"] = r.sell
                result["foreign_diff"] = r.buy - r.sell
            elif r.name == "Investment_Trust":
                result["trust_buy"] = r.buy
                result["trust_sell"] = r.sell
                result["trust_diff"] = r.buy - r.sell
            elif r.name == "Dealer_self":
                result["dealer_self_diff"] = r.buy - r.sell
            elif r.name == "Dealer_Hedging":
                result["dealer_hedge_diff"] = r.buy - r.sell
        result["dealer_diff"] = result["dealer_self_diff"] + result["dealer_hedge_diff"]
        result["total_diff"] = result["foreign_diff"] + result["trust_diff"] + result["dealer_diff"]
        return result


def get_chip_service(session: AsyncSession) -> ChipService:
    return ChipService(session=session)
