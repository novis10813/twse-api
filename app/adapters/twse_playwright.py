"""
TWSE Playwright Adapter — 瀏覽器自動化爬蟲。

FormScraperBase: 通用瀏覽器操作，與 TWSE 無關，可搬至其他專案。
TWSEPlaywrightClient: 實作 LendingSource / ShortSaleSource / DispositionSource。

⚠️  TWSE 頁面選擇器（URL、CSS selector）需在實際開啟頁面後確認。
    每個 fetch_* 方法都標有 # TODO: verify selector 的行。
"""
import asyncio
import logging
import random
from datetime import date as date_type
from typing import Any, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_MAX_RETRIES = 3


class FormScraperBase:
    """
    通用瀏覽器表單操作 base class。
    與任何網站無關，可複用至其他專案。
    """

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def startup(self) -> None:
        """啟動 Playwright + Chromium。由 FastAPI lifespan 呼叫。"""
        self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(headless=True)
        self._browser = browser
        self._context = await browser.new_context(
            user_agent=_DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        logger.info("Playwright browser started")

    async def shutdown(self) -> None:
        """關閉 Playwright。由 FastAPI lifespan 呼叫。"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Playwright browser stopped")

    async def _new_page(self) -> Page:
        """開新 page，由 caller 負責 close。"""
        if self._context is None:
            raise RuntimeError("FormScraperBase.startup() not called")
        return await self._context.new_page()

    async def _extract_table_rows(
        self, page: Page, table_selector: str = "table"
    ) -> list[list[str]]:
        """
        用 JS 從頁面擷取 table 的所有 td 文字，回傳 list of row (list of cell strings)。
        selector 作為參數傳入 evaluate，避免 JS injection。
        """
        rows: list[list[str]] = await page.evaluate(
            """(selector) => {
            const table = document.querySelector(selector);
            if (!table) return [];
            return Array.from(table.querySelectorAll('tbody tr')).map(tr =>
                Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
            );
        }""",
            table_selector,
        )
        return rows

    async def _retry(self, coro_fn: Any, retries: int = _MAX_RETRIES, delay: float = 2.0) -> Any:
        """重試 async callable，失敗時 exponential backoff。"""
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return await coro_fn()
            except Exception as e:
                last_exc = e
                if attempt < retries - 1:
                    wait = delay * (2 ** attempt)
                    logger.warning("Retry %d/%d after %.1fs: %s", attempt + 1, retries, wait, e)
                    await asyncio.sleep(wait)
        raise last_exc or RuntimeError("All retries failed")


class TWSEPlaywrightClient(FormScraperBase):
    """實作 LendingSource / ShortSaleSource / DispositionSource 三個 Protocol。"""

    # ── 借券成交明細（TWT49U）──────────────────────────────────────

    async def fetch_securities_lending(self, date_str: str) -> list[dict]:
        """TWT49U — 借券成交明細。"""
        async def _fetch():
            page = await self._new_page()
            try:
                # TODO: verify actual URL
                await page.goto(
                    "https://www.twse.com.tw/rwd/zh/SBL/TWT49U",
                    wait_until="networkidle",
                )
                await asyncio.sleep(random.uniform(1.0, 2.0))
                # TODO: verify date input selector
                await page.fill('input[name="date"]', date_str)
                # TODO: verify submit button selector
                await page.click('button[type="submit"]')
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(random.uniform(1.0, 3.0))
                rows = await self._extract_table_rows(page)
                return self._parse_lending_rows(rows, date_str)
            finally:
                await page.close()
        return await self._retry(_fetch)

    @staticmethod
    def _parse_lending_rows(rows: list[list[str]], date_str: str) -> list[dict]:
        """
        TWT49U HTML table rows → list[dict].

        ⚠️  欄位 index 須在實際頁面確認後更新。
        預設欄位順序（待確認）：
          [0] 證券代號  [1] 證券名稱  [2] 借券成交量  [3] 還券成交量  [4] 借券餘額
        """
        d = date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        result = []
        for row in rows:
            if len(row) < 5:
                continue
            try:
                result.append({
                    "date": d,
                    "stock_id": row[0].strip(),
                    "LendingShares": int(row[2].replace(",", "") or 0),       # TODO: verify index
                    "ReturningShares": int(row[3].replace(",", "") or 0),     # TODO: verify index
                    "LendingSharesBalance": int(row[4].replace(",", "") or 0), # TODO: verify index
                })
            except (ValueError, IndexError):
                continue
        return result

    # ── 信用額度總量管制 ──────────────────────────────────────────

    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]:
        """信用額度總量管制。"""
        async def _fetch():
            page = await self._new_page()
            try:
                # TODO: verify actual URL
                await page.goto(
                    "https://www.twse.com.tw/rwd/zh/marginTrading/shortSaleBalances",
                    wait_until="networkidle",
                )
                await asyncio.sleep(random.uniform(1.0, 2.0))
                # TODO: verify date input selector
                await page.fill('input[name="date"]', date_str)
                # TODO: verify submit button selector
                await page.click('button[type="submit"]')
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(random.uniform(1.0, 3.0))
                rows = await self._extract_table_rows(page)
                return self._parse_short_sale_rows(rows, date_str)
            finally:
                await page.close()
        return await self._retry(_fetch)

    @staticmethod
    def _parse_short_sale_rows(rows: list[list[str]], date_str: str) -> list[dict]:
        """
        信用額度 HTML table rows → list[dict].

        ⚠️  欄位 index 須在實際頁面確認後更新。
        預設欄位順序（待確認）：
          [0] 證券代號  [1] 證券名稱  [2] 融券賣出  [3] 可融券上限
        """
        d = date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        result = []
        for row in rows:
            if len(row) < 4:
                continue
            try:
                result.append({
                    "date": d,
                    "stock_id": row[0].strip(),
                    "ShortSaleShares": int(row[2].replace(",", "") or 0),  # TODO: verify index
                    "ShortSaleLimit": int(row[3].replace(",", "") or 0),   # TODO: verify index
                })
            except (ValueError, IndexError):
                continue
        return result

    # ── 處置有價證券 ──────────────────────────────────────────────

    async def fetch_disposition(self, date_str: str) -> list[dict]:
        """處置有價證券公告。date_str 用於日誌記錄；TWSE 公告頁面不接受日期篩選。"""
        logger.debug("Fetching disposition for date: %s", date_str)
        async def _fetch():
            page = await self._new_page()
            try:
                # TODO: verify actual URL
                await page.goto(
                    "https://www.twse.com.tw/rwd/zh/announcement/punish",
                    wait_until="networkidle",
                )
                await asyncio.sleep(random.uniform(1.0, 2.0))
                rows = await self._extract_table_rows(page)
                return self._parse_disposition_rows(rows)
            finally:
                await page.close()
        return await self._retry(_fetch)

    @staticmethod
    def _parse_disposition_rows(rows: list[list[str]]) -> list[dict]:
        """
        處置有價證券 HTML table rows → list[dict].

        ⚠️  欄位 index 須在實際頁面確認後更新。
        預設欄位順序（待確認）：
          [0] 處置起始日  [1] 處置終止日  [2] 證券代號  [3] 原因
        """

        def _parse_date(s: str) -> date_type | None:
            s = s.strip().replace("/", "-")
            try:
                return date_type.fromisoformat(s)
            except ValueError:
                return None

        result = []
        for row in rows:
            if len(row) < 4:
                continue
            start = _parse_date(row[0])
            if start is None:
                continue
            result.append({
                "start_date": start,
                "end_date": _parse_date(row[1]),
                "stock_id": row[2].strip(),   # TODO: verify index
                "reason": row[3].strip(),      # TODO: verify index
            })
        return result


_playwright_client: Optional[TWSEPlaywrightClient] = None


def get_playwright_client() -> TWSEPlaywrightClient:
    """Return the singleton TWSEPlaywrightClient. startup() must be called before use (done by FastAPI lifespan)."""
    global _playwright_client
    if _playwright_client is None:
        _playwright_client = TWSEPlaywrightClient()
    return _playwright_client
