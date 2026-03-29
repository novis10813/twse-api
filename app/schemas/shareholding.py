"""Pydantic schemas for shareholding (外資持股) data — aligned with FinMind field names."""
from typing import List
from pydantic import BaseModel


class StockShareholdingResponse(BaseModel):
    """個股外資持股 — FinMind: TaiwanStockShareholding"""
    date: str
    stock_id: str
    NumberOfSharesIssued: int = 0
    ForeignInvestmentShares: int = 0
    ForeignInvestmentSharesRatio: float = 0.0
    ForeignInvestmentSharesWithoutDealers: int = 0
    ForeignInvestmentSharesWithoutDealersRatio: float = 0.0


class AllStocksShareholdingResponse(BaseModel):
    """全市場外資持股列表"""
    date: str
    stocks: List[StockShareholdingResponse]


class ErrorResponse(BaseModel):
    detail: str
