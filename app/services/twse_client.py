"""
TWSE HTTP Client — pure HTTP layer, no business logic.
Handles retries and error normalisation only.
"""
import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
BASE_URL = "https://www.twse.com.tw"


class TWSEAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TWSEClient:
    """Low-level TWSE API HTTP client with retry logic."""

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(verify=False, timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    if "stat" in data and data["stat"] != "OK":
                        raise TWSEAPIError(f"TWSE stat: {data['stat']}")
                    return data
            except TWSEAPIError:
                raise
            except httpx.TimeoutException:
                last_exc = TWSEAPIError(f"Timeout: {url}")
            except httpx.HTTPStatusError as e:
                last_exc = TWSEAPIError(f"HTTP {e.response.status_code}", e.response.status_code)
            except Exception as e:
                last_exc = TWSEAPIError(str(e))
            if attempt < DEFAULT_MAX_RETRIES - 1:
                await asyncio.sleep(min(1.0 * (2 ** attempt), 10.0))
        raise last_exc or TWSEAPIError("Request failed")

    async def fetch_chip_summary(self, date_str: str) -> dict[str, Any]:
        """BFI82U — 三大法人買賣金額統計表"""
        url = f"{BASE_URL}/rwd/zh/fund/BFI82U?response=json&date={date_str}"
        return await self._fetch_json(url)

    async def fetch_stock_chip_data(self, date_str: str) -> dict[str, Any]:
        """T86 — 個股三大法人買賣超"""
        url = f"{BASE_URL}/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
        return await self._fetch_json(url)

    async def fetch_margin_data(self, date_str: str) -> dict[str, Any]:
        """MI_MARGN — 融資融券（個股 + 整體市場）"""
        url = f"{BASE_URL}/rwd/zh/marginTrading/MI_MARGN?response=json&date={date_str}&selectType=ALL"
        return await self._fetch_json(url)

    async def fetch_shareholding_data(self, date_str: str) -> dict[str, Any]:
        """MI_QFIIS — 外資持股比例 (selectType=ALLBUT0999 excludes ETF/fund codes)"""
        url = f"{BASE_URL}/rwd/zh/fund/MI_QFIIS?response=json&date={date_str}&selectType=ALLBUT0999"
        return await self._fetch_json(url)


_client: Optional[TWSEClient] = None


def get_twse_client() -> TWSEClient:
    global _client
    if _client is None:
        _client = TWSEClient()
    return _client
