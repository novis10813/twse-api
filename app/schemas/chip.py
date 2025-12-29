"""
Pydantic schemas for chip data
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import date


class InvestorData(BaseModel):
    """單一法人買賣資料"""
    name: str = Field(..., description="法人名稱")
    buy: int = Field(..., description="買進金額 (元)")
    sell: int = Field(..., description="賣出金額 (元)")
    diff: int = Field(..., description="買賣差額 (元)")


class ChipSummary(BaseModel):
    """三大法人買賣金額統計"""
    date: str = Field(..., description="資料日期 (YYYYMMDD)")
    title: str = Field(..., description="標題")
    investors: List[InvestorData] = Field(default_factory=list, description="法人資料")
    total_diff: int = Field(0, description="三大法人合計買賣差額")


class StockChipData(BaseModel):
    """個股籌碼資料"""
    code: str = Field(..., description="股票代碼")
    name: str = Field(..., description="股票名稱")
    foreign_buy: int = Field(0, description="外資買超 (股)")
    foreign_sell: int = Field(0, description="外資賣超 (股)")
    foreign_diff: int = Field(0, description="外資買賣超 (股)")
    trust_buy: int = Field(0, description="投信買超 (股)")
    trust_sell: int = Field(0, description="投信賣超 (股)")
    trust_diff: int = Field(0, description="投信買賣超 (股)")
    dealer_diff: int = Field(0, description="自營商買賣超 (股)")
    total_diff: int = Field(0, description="三大法人合計 (股)")


class StockChipList(BaseModel):
    """個股籌碼列表"""
    date: str = Field(..., description="資料日期")
    stocks: List[StockChipData] = Field(default_factory=list, description="個股資料")
    top_foreign_buy: List[StockChipData] = Field(default_factory=list, description="外資買超前10")
    top_foreign_sell: List[StockChipData] = Field(default_factory=list, description="外資賣超前10")
    top_trust_buy: List[StockChipData] = Field(default_factory=list, description="投信買超前10")
    top_trust_sell: List[StockChipData] = Field(default_factory=list, description="投信賣超前10")


class StockChipDetail(BaseModel):
    """個股籌碼詳情"""
    code: str
    name: str
    date: str
    foreign_buy: int = 0
    foreign_sell: int = 0
    foreign_diff: int = 0
    trust_buy: int = 0
    trust_sell: int = 0
    trust_diff: int = 0
    dealer_self_diff: int = 0
    dealer_hedge_diff: int = 0
    dealer_diff: int = 0
    total_diff: int = 0


class ChipTrendData(BaseModel):
    """籌碼趨勢資料"""
    date: str
    foreign_diff: int = 0
    trust_diff: int = 0
    dealer_diff: int = 0
    total_diff: int = 0


class StockChipTrend(BaseModel):
    """個股籌碼趨勢"""
    code: str
    name: str
    investor_type: str = "全部"
    days: int = 5
    trend: List[ChipTrendData] = Field(default_factory=list)
    cumulative_diff: int = 0


class ErrorResponse(BaseModel):
    """錯誤回應"""
    detail: str
    error_code: Optional[str] = None
