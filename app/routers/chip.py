"""
Chip Data Router
API endpoints for TWSE chip (institutional investors) data
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query

from app.services.twse import get_twse_service, TWSEAPIError
from app.schemas.chip import (
    ChipSummary,
    StockChipList,
    StockChipDetail,
    ErrorResponse
)

router = APIRouter()

# Taiwan timezone
TW_TZ = timezone(timedelta(hours=8))


def get_default_date() -> str:
    """Get default date (today in Taiwan timezone)"""
    return datetime.now(TW_TZ).strftime("%Y%m%d")


@router.get(
    "/summary",
    response_model=ChipSummary,
    responses={
        404: {"model": ErrorResponse, "description": "Data not found for the specified date"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_chip_summary(
    date: Optional[str] = Query(
        None,
        description="Date in YYYYMMDD format (default: today)",
        pattern=r"^\d{8}$"
    )
):
    """
    取得三大法人買賣金額統計 (BFI82U)
    
    Get institutional investors buy/sell summary for a specific date.
    
    - **date**: Date in YYYYMMDD format (default: today)
    """
    if date is None:
        date = get_default_date()
    
    service = get_twse_service()
    
    try:
        raw_data = await service.fetch_chip_summary(date)
        result = service.parse_chip_summary(raw_data, date)
        return result
    except TWSEAPIError as e:
        if "沒有符合條件的資料" in str(e.message) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"No data available for date: {date}")
        raise HTTPException(status_code=500, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stocks",
    response_model=StockChipList,
    responses={
        404: {"model": ErrorResponse, "description": "Data not found for the specified date"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_stock_chip_list(
    date: Optional[str] = Query(
        None,
        description="Date in YYYYMMDD format (default: today)",
        pattern=r"^\d{8}$"
    )
):
    """
    取得個股三大法人買賣超列表 (T86)
    
    Get stock-level institutional investors data with top buy/sell rankings.
    
    - **date**: Date in YYYYMMDD format (default: today)
    """
    if date is None:
        date = get_default_date()
    
    service = get_twse_service()
    
    try:
        raw_data = await service.fetch_stock_chip_data(date)
        result = service.parse_stock_chip_data(raw_data, date)
        return result
    except TWSEAPIError as e:
        if "沒有符合條件的資料" in str(e.message) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"No data available for date: {date}")
        raise HTTPException(status_code=500, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stock/{code}",
    response_model=StockChipDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Stock not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_stock_chip_detail(
    code: str,
    date: Optional[str] = Query(
        None,
        description="Date in YYYYMMDD format (default: today)",
        pattern=r"^\d{8}$"
    )
):
    """
    取得個股籌碼詳情
    
    Get detailed chip data for a specific stock.
    
    - **code**: Stock code (e.g., 2330)
    - **date**: Date in YYYYMMDD format (default: today)
    """
    if date is None:
        date = get_default_date()
    
    service = get_twse_service()
    
    try:
        raw_data = await service.fetch_stock_chip_data(date)
        parsed_data = service.parse_stock_chip_data(raw_data, date)
        stock_detail = service.get_stock_detail(parsed_data, code)
        
        if stock_detail is None:
            raise HTTPException(status_code=404, detail=f"Stock {code} not found for date: {date}")
        
        return {
            **stock_detail,
            "date": date
        }
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(status_code=500, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
