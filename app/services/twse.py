"""
TWSE API Service
Handles all requests to Taiwan Stock Exchange API
"""
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Taiwan timezone
TW_TZ = timezone(timedelta(hours=8))

# Default settings
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 10.0


class TWSEAPIError(Exception):
    """TWSE API Error"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TWSEService:
    """TWSE API Service"""
    
    def __init__(self):
        self.base_url = "https://www.twse.com.tw"
    
    def _get_today_date(self) -> str:
        """Get today's date in YYYYMMDD format (Taiwan timezone)"""
        return datetime.now(TW_TZ).strftime("%Y%m%d")
    
    async def _fetch_json(
        self,
        url: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ) -> Dict[str, Any]:
        """
        Fetch JSON with exponential backoff retry
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Validate TWSE API response
                    if "stat" in data and data.get("stat") != "OK":
                        raise TWSEAPIError(
                            f"API returned error status: {data.get('stat')}",
                            status_code=None
                        )
                    
                    return data
                    
            except httpx.TimeoutException:
                last_exception = TWSEAPIError(f"Request timeout: {url}")
                logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries}): {url}")
                
            except httpx.HTTPStatusError as e:
                last_exception = TWSEAPIError(
                    f"HTTP error: {e.response.status_code}",
                    status_code=e.response.status_code
                )
                logger.warning(f"HTTP error {e.response.status_code} (attempt {attempt + 1}/{max_retries})")
                
            except httpx.RequestError as e:
                last_exception = TWSEAPIError(f"Request error: {str(e)}")
                logger.warning(f"Request error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
            except Exception as e:
                if isinstance(e, TWSEAPIError):
                    raise e
                last_exception = TWSEAPIError(f"Unknown error: {str(e)}")
                logger.warning(f"Unknown error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            # Exponential backoff
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                await asyncio.sleep(delay)
        
        raise last_exception or TWSEAPIError("Request failed")
    
    async def fetch_chip_summary(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch institutional investors summary (BFI82U)
        三大法人買賣金額統計表
        """
        if date_str is None:
            date_str = self._get_today_date()
        
        url = f"{self.base_url}/rwd/zh/fund/BFI82U?response=json&date={date_str}"
        return await self._fetch_json(url)
    
    async def fetch_stock_chip_data(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch stock chip data (T86)
        個股三大法人買賣超
        """
        if date_str is None:
            date_str = self._get_today_date()
        
        url = f"{self.base_url}/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
        return await self._fetch_json(url)
    
    def parse_chip_summary(self, data: Dict[str, Any], date_str: str) -> Dict[str, Any]:
        """Parse chip summary response into structured format"""
        result = {
            "date": date_str,
            "title": data.get("title", "三大法人買賣金額統計表"),
            "investors": [],
            "total_diff": 0
        }
        
        raw_data = data.get("data", [])
        
        for row in raw_data:
            if len(row) >= 4:
                name = row[0].strip()
                # Remove commas and convert to int
                try:
                    buy = int(row[1].replace(",", ""))
                    sell = int(row[2].replace(",", ""))
                    diff = int(row[3].replace(",", ""))
                except (ValueError, AttributeError):
                    continue
                
                result["investors"].append({
                    "name": name,
                    "buy": buy,
                    "sell": sell,
                    "diff": diff
                })
                
                # Calculate total
                if "合計" in name:
                    result["total_diff"] = diff
        
        return result
    
    def parse_stock_chip_data(self, data: Dict[str, Any], date_str: str) -> Dict[str, Any]:
        """Parse stock chip data response"""
        result = {
            "date": date_str,
            "stocks": [],
            "top_foreign_buy": [],
            "top_foreign_sell": [],
            "top_trust_buy": [],
            "top_trust_sell": []
        }
        
        raw_data = data.get("data", [])
        stocks = []
        
        for row in raw_data:
            if len(row) >= 17:
                try:
                    code = row[0].strip()
                    name = row[1].strip()
                    foreign_diff = int(row[4].replace(",", ""))
                    trust_diff = int(row[10].replace(",", ""))
                    dealer_diff = int(row[11].replace(",", "")) + int(row[14].replace(",", ""))
                    total_diff = int(row[17].replace(",", "")) if len(row) > 17 else foreign_diff + trust_diff + dealer_diff
                    
                    stock = {
                        "code": code,
                        "name": name,
                        "foreign_buy": int(row[2].replace(",", "")) if row[2] else 0,
                        "foreign_sell": int(row[3].replace(",", "")) if row[3] else 0,
                        "foreign_diff": foreign_diff,
                        "trust_buy": int(row[8].replace(",", "")) if row[8] else 0,
                        "trust_sell": int(row[9].replace(",", "")) if row[9] else 0,
                        "trust_diff": trust_diff,
                        "dealer_diff": dealer_diff,
                        "total_diff": total_diff
                    }
                    stocks.append(stock)
                except (ValueError, IndexError, AttributeError):
                    continue
        
        result["stocks"] = stocks
        
        # Sort and get top 10
        result["top_foreign_buy"] = sorted(stocks, key=lambda x: x["foreign_diff"], reverse=True)[:10]
        result["top_foreign_sell"] = sorted(stocks, key=lambda x: x["foreign_diff"])[:10]
        result["top_trust_buy"] = sorted(stocks, key=lambda x: x["trust_diff"], reverse=True)[:10]
        result["top_trust_sell"] = sorted(stocks, key=lambda x: x["trust_diff"])[:10]
        
        return result
    
    def get_stock_detail(self, stocks_data: Dict[str, Any], stock_code: str) -> Optional[Dict[str, Any]]:
        """Get specific stock detail from parsed data"""
        for stock in stocks_data.get("stocks", []):
            if stock["code"] == stock_code:
                return stock
        return None


# Singleton instance
_twse_service: Optional[TWSEService] = None


def get_twse_service() -> TWSEService:
    """Get TWSE service instance (singleton)"""
    global _twse_service
    if _twse_service is None:
        _twse_service = TWSEService()
    return _twse_service
