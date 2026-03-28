"""Pydantic schemas for margin (融資融券) data — aligned with FinMind field names."""
from typing import List
from pydantic import BaseModel


class StockMarginResponse(BaseModel):
    """個股融資融券 — FinMind: TaiwanStockMarginPurchaseShortSale"""
    date: str
    stock_id: str
    MarginPurchaseBuy: int = 0
    MarginPurchaseSell: int = 0
    MarginPurchaseCashRepayment: int = 0
    MarginPurchaseTodayBalance: int = 0
    MarginPurchaseYesterdayBalance: int = 0
    MarginPurchaseLimit: int = 0
    ShortSaleBuy: int = 0
    ShortSaleSell: int = 0
    ShortSaleCashRepayment: int = 0
    ShortSaleTodayBalance: int = 0
    ShortSaleYesterdayBalance: int = 0
    ShortSaleLimit: int = 0
    OffsetLoanAndShort: int = 0


class TotalMarginItem(BaseModel):
    """單一項目（融資/融券/融資金額）"""
    name: str
    buy: int = 0
    sell: int = 0
    TodayBalance: int = 0
    YesBalance: int = 0
    Return: int = 0


class TotalMarginResponse(BaseModel):
    """整體市場融資融券 — FinMind: TaiwanStockTotalMarginPurchaseShortSale"""
    date: str
    items: List[TotalMarginItem]


class ErrorResponse(BaseModel):
    detail: str
