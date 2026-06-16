# TWSE Playwright Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 透過 Playwright 瀏覽器自動化爬取 TWSE 三個需填表單的資料集（借券、信用額度管制、處置有價證券），並建立可切換 FinMind 的 Port/Adapter 架構。

**Architecture:** `adapters/protocols.py` 定義 Python Protocol（Port），`adapters/twse_playwright.py` 實作 Playwright adapter，Service 只依賴 Protocol，透過 config 的 `DATA_SOURCE_ADAPTER` env var 決定注入哪個 adapter。`FormScraperBase` 封裝通用瀏覽器操作，可複用至其他專案。

**Tech Stack:** Python 3.13, FastAPI, Playwright (`playwright>=1.44`), SQLAlchemy async, aiosqlite (test), pytest-asyncio

---

## File Map

| 操作 | 路徑 | 說明 |
|------|------|------|
| 新增 | `app/adapters/__init__.py` | 空 |
| 新增 | `app/adapters/protocols.py` | Port Protocol 定義 |
| 新增 | `app/adapters/twse_playwright.py` | Playwright adapter |
| 新增 | `app/adapters/finmind.py` | FinMind stub |
| 修改 | `app/config.py` | 新增 `DATA_SOURCE_ADAPTER` |
| 修改 | `app/db/models.py` | 新增三個 table model |
| 修改 | `app/db/repository.py` | 新增三個 table 的 CRUD |
| 修改 | `tests/conftest.py` | 新增三個 SQLite model |
| 修改 | `pyproject.toml` | 新增 `playwright>=1.44` |
| 新增 | `app/services/lending.py` | 借券 service |
| 新增 | `app/services/short_sale.py` | 信用額度 service |
| 新增 | `app/services/disposition.py` | 處置有價證券 service |
| 新增 | `app/routers/lending.py` | 借券 router |
| 新增 | `app/routers/short_sale.py` | 信用額度 router |
| 新增 | `app/routers/disposition.py` | 處置有價證券 router |
| 修改 | `app/main.py` | lifespan + 三個 router 掛載 |
| 新增 | `tests/test_lending_parsing.py` | 借券解析測試 |
| 新增 | `tests/test_lending_service.py` | 借券 service 測試 |
| 新增 | `tests/test_lending_router.py` | 借券 router 測試 |
| 新增 | `tests/test_short_sale_parsing.py` | 信用額度解析測試 |
| 新增 | `tests/test_short_sale_service.py` | 信用額度 service 測試 |
| 新增 | `tests/test_short_sale_router.py` | 信用額度 router 測試 |
| 新增 | `tests/test_disposition_parsing.py` | 處置解析測試 |
| 新增 | `tests/test_disposition_service.py` | 處置 service 測試 |
| 新增 | `tests/test_disposition_router.py` | 處置 router 測試 |

---

## Task 1: Protocol 定義

**Files:**
- Create: `app/adapters/__init__.py`
- Create: `app/adapters/protocols.py`

- [ ] **Step 1: 新增 `app/adapters/__init__.py`（空檔案）**

```python
```

- [ ] **Step 2: 新增 `app/adapters/protocols.py`**

```python
"""
Data source Protocols (Ports) — 與實作無關的介面定義。
LendingSource / ShortSaleSource / DispositionSource 三個 Protocol，
TWSEPlaywrightClient 和 FinMindClient 都要實作這些介面。
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class LendingSource(Protocol):
    async def fetch_securities_lending(self, date_str: str) -> list[dict]:
        """回傳該日借券成交明細，list of dict。date_str 格式 YYYYMMDD。"""
        ...


@runtime_checkable
class ShortSaleSource(Protocol):
    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]:
        """回傳該日信用額度總量管制，list of dict。date_str 格式 YYYYMMDD。"""
        ...


@runtime_checkable
class DispositionSource(Protocol):
    async def fetch_disposition(self, date_str: str) -> list[dict]:
        """回傳該日處置有價證券公告，list of dict。date_str 格式 YYYYMMDD。"""
        ...
```

- [ ] **Step 3: Commit**

```bash
git add app/adapters/
git commit -m "feat: add data source Protocols (Port definitions)"
```

---

## Task 2: FormScraperBase + TWSEPlaywrightClient stub

**Files:**
- Create: `app/adapters/twse_playwright.py`

- [ ] **Step 1: 新增 `app/adapters/twse_playwright.py`**

```python
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
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def startup(self) -> None:
        """啟動 Playwright + Chromium。由 FastAPI lifespan 呼叫。"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
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
        """
        rows: list[list[str]] = await page.evaluate(
            f"""
            () => {{
                const table = document.querySelector('{table_selector}');
                if (!table) return [];
                return Array.from(table.querySelectorAll('tbody tr')).map(tr =>
                    Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                );
            }}
            """
        )
        return rows

    async def _retry(self, coro_fn, retries: int = _MAX_RETRIES, delay: float = 2.0) -> Any:
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
        from datetime import date as date_type
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
        from datetime import date as date_type
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
        """處置有價證券公告。"""
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
        from datetime import date as date_type

        def _parse_date(s: str) -> Optional[date_type]:
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
    global _playwright_client
    if _playwright_client is None:
        _playwright_client = TWSEPlaywrightClient()
    return _playwright_client
```

- [ ] **Step 2: Run（確認 import 無誤，playwright 尚未安裝所以先跳過）**

```bash
cd twse-api && python -c "from app.adapters.twse_playwright import TWSEPlaywrightClient; print('ok')"
```
Expected: `ModuleNotFoundError: No module named 'playwright'`（正常，Task 8 才安裝）

- [ ] **Step 3: Commit**

```bash
git add app/adapters/twse_playwright.py
git commit -m "feat: add FormScraperBase and TWSEPlaywrightClient stub"
```

---

## Task 3: FinMind stub

**Files:**
- Create: `app/adapters/finmind.py`

- [ ] **Step 1: 新增 `app/adapters/finmind.py`**

```python
"""
FinMind Adapter — stub，未來實作。
切換 DATA_SOURCE_ADAPTER=finmind 時使用。
"""
from typing import Optional


class FinMindClient:
    """
    FinMind API adapter，實作 LendingSource / ShortSaleSource / DispositionSource。
    目前為 stub，所有方法回傳空 list。
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token

    async def fetch_securities_lending(self, date_str: str) -> list[dict]:
        raise NotImplementedError("FinMind adapter not yet implemented")

    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]:
        raise NotImplementedError("FinMind adapter not yet implemented")

    async def fetch_disposition(self, date_str: str) -> list[dict]:
        raise NotImplementedError("FinMind adapter not yet implemented")


_finmind_client: Optional[FinMindClient] = None


def get_finmind_client() -> FinMindClient:
    global _finmind_client
    if _finmind_client is None:
        _finmind_client = FinMindClient()
    return _finmind_client
```

- [ ] **Step 2: Commit**

```bash
git add app/adapters/finmind.py
git commit -m "feat: add FinMind adapter stub"
```

---

## Task 4: Config 更新

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: 在 `Settings` class 新增 `data_source_adapter` 欄位**

在 `app/config.py` 的 `postgres_db` 行後加入：

```python
    # Data source adapter
    data_source_adapter: str = "playwright"  # "playwright" | "finmind"
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat: add DATA_SOURCE_ADAPTER config setting"
```

---

## Task 5: DB Models 擴充

**Files:**
- Modify: `app/db/models.py`

- [ ] **Step 1: 在 `models.py` 末尾新增三個 model**

在 `StockShareholding` class 後新增：

```python

class StockLending(Base):
    """
    個股借券成交明細 — FinMind: TaiwanStockSecuritiesLending
    TWSE source: TWT49U
    """
    __tablename__ = "twse_stock_lending"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    LendingShares = Column(BigInteger, nullable=False, default=0)
    ReturningShares = Column(BigInteger, nullable=False, default=0)
    LendingSharesBalance = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class ShortSaleBalances(Base):
    """
    個股信用額度總量管制 — FinMind: TaiwanDailyShortSaleBalances
    TWSE source: 信用額度總量管制頁面
    """
    __tablename__ = "twse_short_sale_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    ShortSaleShares = Column(BigInteger, nullable=False, default=0)
    ShortSaleLimit = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class Disposition(Base):
    """
    處置有價證券 — FinMind: TaiwanStockDispositionSecuritiesPeriod
    TWSE source: 交易所公告頁面
    """
    __tablename__ = "twse_disposition"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    stock_id = Column(String(10), nullable=False)
    reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("start_date", "stock_id"),)
```

也要把新 model 加入 `models.py` 頂端 import 的 `String` 已存在，`Text` 不需要（用 `String(500)`）。

- [ ] **Step 2: Commit**

```bash
git add app/db/models.py
git commit -m "feat: add StockLending, ShortSaleBalances, Disposition DB models"
```

---

## Task 6: conftest.py 擴充

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: 在 `conftest.py` 的 `SqliteStockShareholding` 後新增三個 SQLite model**

注意：SQLite 不支援 `Numeric` precision，使用 `Float`。`BigInteger` 在 SQLite 降為 `Integer`，沒問題。

```python
class SqliteStockLending(SqliteBase):
    __tablename__ = "twse_stock_lending"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    LendingShares = Column(BigInteger, nullable=False, default=0)
    ReturningShares = Column(BigInteger, nullable=False, default=0)
    LendingSharesBalance = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class SqliteShortSaleBalances(SqliteBase):
    __tablename__ = "twse_short_sale_balances"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    ShortSaleShares = Column(BigInteger, nullable=False, default=0)
    ShortSaleLimit = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "stock_id"),)


class SqliteDisposition(SqliteBase):
    __tablename__ = "twse_disposition"
    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    stock_id = Column(String(10), nullable=False)
    reason = Column(String(500), nullable=True)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("start_date", "stock_id"),)
```

- [ ] **Step 2: Run test_session fixture 確認新 table 可建立**

```bash
cd twse-api && python -m pytest tests/conftest.py -v --co
```
Expected: 沒有 error（conftest 本身不是測試，只確認語法正確）

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add SQLite models for lending, short_sale_balances, disposition"
```

---

## Task 7: Repository 擴充

**Files:**
- Modify: `app/db/repository.py`

- [ ] **Step 1: 在 `repository.py` 的 import 區塊新增三個新 model**

找到：
```python
from app.db.models import (
    StockInstitutionalInvestors,
    TotalInstitutionalInvestors,
    StockMargin,
    TotalMargin,
    StockShareholding,
)
```
改為：
```python
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
```

- [ ] **Step 2: 在 `TWSERepository` 末尾新增三個 section**

```python
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
        d = _parse_date(date_str)
        from sqlalchemy import or_, null
        result = await self.session.execute(
            select(Disposition).where(
                Disposition.start_date <= d,
                or_(Disposition.end_date >= d, Disposition.end_date == null()),
            ).order_by(Disposition.start_date)
        )
        return list(result.scalars().all())
```

- [ ] **Step 3: Run 確認 import 正確**

```bash
cd twse-api && python -c "from app.db.repository import TWSERepository; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/db/repository.py
git commit -m "feat: add lending, short_sale_balances, disposition repository methods"
```

---

## Task 8: 新增 Playwright 依賴

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 在 `pyproject.toml` 的 `dependencies` 新增 playwright**

找到 `"pydantic-settings>=2.0",` 這行，在後面加入：

```toml
    "playwright>=1.44",
```

- [ ] **Step 2: 安裝依賴 + chromium**

```bash
cd twse-api && uv sync && uv run playwright install chromium
```
Expected: chromium 下載並安裝成功

- [ ] **Step 3: 確認 import 正常**

```bash
cd twse-api && python -c "from app.adapters.twse_playwright import TWSEPlaywrightClient; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add playwright dependency"
```

---

## Task 9: 借券解析器測試 + 借券 Service

**Files:**
- Create: `tests/test_lending_parsing.py`
- Create: `app/services/lending.py`
- Create: `tests/test_lending_service.py`

- [ ] **Step 1: 撰寫解析測試（先跑，確認 FAIL）**

新增 `tests/test_lending_parsing.py`：

```python
"""借券解析器單元測試 — 測試 _parse_lending_rows 靜態方法。"""
from app.adapters.twse_playwright import TWSEPlaywrightClient


def test_parse_lending_rows_basic():
    """正常資料：兩筆 row → 兩筆 dict。"""
    rows = [
        ["2330", "台積電", "1,000", "500", "50,000"],
        ["2317", "鴻海",   "200",   "100", "10,000"],
    ]
    result = TWSEPlaywrightClient._parse_lending_rows(rows, "20260328")
    assert len(result) == 2
    assert result[0]["stock_id"] == "2330"
    assert result[0]["LendingShares"] == 1000
    assert result[0]["ReturningShares"] == 500
    assert result[0]["LendingSharesBalance"] == 50000
    assert str(result[0]["date"]) == "2026-03-28"


def test_parse_lending_rows_skips_short_rows():
    """欄位不足的 row 應被忽略。"""
    rows = [
        ["2330", "台積電"],  # 只有 2 欄
        ["2317", "鴻海", "200", "100", "10,000"],
    ]
    result = TWSEPlaywrightClient._parse_lending_rows(rows, "20260328")
    assert len(result) == 1
    assert result[0]["stock_id"] == "2317"


def test_parse_lending_rows_handles_empty_cells():
    """空字串應轉為 0。"""
    rows = [
        ["2330", "台積電", "", "", ""],
    ]
    result = TWSEPlaywrightClient._parse_lending_rows(rows, "20260328")
    assert len(result) == 1
    assert result[0]["LendingShares"] == 0
    assert result[0]["LendingSharesBalance"] == 0


def test_parse_lending_rows_empty_input():
    """空 input → 空 list。"""
    assert TWSEPlaywrightClient._parse_lending_rows([], "20260328") == []
```

- [ ] **Step 2: 跑測試，確認 PASS（解析器已在 Task 2 實作）**

```bash
cd twse-api && uv run pytest tests/test_lending_parsing.py -v
```
Expected: 4 passed

- [ ] **Step 3: 撰寫 LendingService 測試（先跑，確認 FAIL）**

新增 `tests/test_lending_service.py`：

```python
"""借券 service DB cache 測試。"""
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lending import LendingService


def _mock_adapter_with_data():
    adapter = MagicMock()
    adapter.fetch_securities_lending = AsyncMock(return_value=[
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "LendingShares": 1000,
            "ReturningShares": 500,
            "LendingSharesBalance": 50000,
        }
    ])
    return adapter


async def test_get_stock_lending_calls_adapter_on_miss(test_session: AsyncSession):
    """DB miss → adapter 被呼叫，資料存入 DB。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    result = await service.get_stock_lending("20260328", "2330")

    adapter.fetch_securities_lending.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["LendingShares"] == 1000


async def test_get_stock_lending_returns_db_on_hit(test_session: AsyncSession):
    """DB hit → adapter 不被呼叫。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    await service.get_stock_lending("20260328", "2330")
    adapter.fetch_securities_lending.reset_mock()

    result = await service.get_stock_lending("20260328", "2330")
    adapter.fetch_securities_lending.assert_not_called()
    assert result["LendingSharesBalance"] == 50000


async def test_get_stock_lending_returns_none_for_unknown(test_session: AsyncSession):
    """未知 stock_id → 回傳 None。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    result = await service.get_stock_lending("20260328", "9999")
    assert result is None


async def test_get_stock_lending_history_empty_before_ingest(test_session: AsyncSession):
    """空 DB history 查詢回傳 []。"""
    adapter = _mock_adapter_with_data()
    service = LendingService(session=test_session, adapter=adapter)

    result = await service.get_stock_lending_history("2330", "20260101", "20260328")
    assert result == []
```

- [ ] **Step 4: 跑測試，確認 FAIL（ImportError: app.services.lending）**

```bash
cd twse-api && uv run pytest tests/test_lending_service.py -v
```
Expected: `ImportError` 或 `ModuleNotFoundError`

- [ ] **Step 5: 新增 `app/services/lending.py`**

```python
"""Lending Service — 借券成交明細 (DB-first cache)."""
import logging
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import LendingSource
from app.adapters.twse_playwright import get_playwright_client
from app.db.repository import TWSERepository

logger = logging.getLogger(__name__)


class LendingService:
    def __init__(self, session: AsyncSession, adapter: Optional[LendingSource] = None):
        self.repo = TWSERepository(session)
        self.adapter = adapter or get_playwright_client()
        self.session = session

    async def get_stock_lending(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """個股借券。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            record = await self.repo.get_stock_lending(date_str, stock_id)
            if record:
                return self._format(record)

        await self._ingest(date_str)
        record = await self.repo.get_stock_lending(date_str, stock_id)
        return self._format(record) if record else None

    async def get_stock_lending_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """個股借券歷史（僅從 DB 查，不自動補爬）。"""
        records = await self.repo.get_stock_lending_history(stock_id, start_date, end_date)
        return [self._format(r) for r in records]

    async def _ingest(self, date_str: str) -> None:
        rows = await self.adapter.fetch_securities_lending(date_str)
        await self.repo.upsert_stock_lending(rows)
        await self.session.flush()

    def _format(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "LendingShares": record.LendingShares,
            "ReturningShares": record.ReturningShares,
            "LendingSharesBalance": record.LendingSharesBalance,
        }


def get_lending_service(session: AsyncSession) -> LendingService:
    return LendingService(session=session)
```

- [ ] **Step 6: 跑測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_lending_service.py tests/test_lending_parsing.py -v
```
Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add app/services/lending.py tests/test_lending_parsing.py tests/test_lending_service.py
git commit -m "feat: add LendingService with DB-first cache and parsing tests"
```

---

## Task 10: 借券 Router

**Files:**
- Create: `app/routers/lending.py`
- Create: `tests/test_lending_router.py`

- [ ] **Step 1: 撰寫 router 測試（先跑，確認 FAIL）**

新增 `tests/test_lending_router.py`：

```python
"""借券 router 整合測試。"""
from unittest.mock import AsyncMock, patch
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

_LENDING_RECORD = {
    "date": "2026-03-28",
    "stock_id": "2330",
    "LendingShares": 1000,
    "ReturningShares": 500,
    "LendingSharesBalance": 50000,
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_stock_lending_200(client):
    with patch("app.routers.lending.get_lending_service") as mock_svc_factory:
        svc = AsyncMock()
        svc.get_stock_lending = AsyncMock(return_value=_LENDING_RECORD)
        mock_svc_factory.return_value = svc

        resp = client.get("/api/v1/lending/stock/2330?date=20260328")

    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_id"] == "2330"
    assert data["LendingShares"] == 1000


def test_get_stock_lending_404(client):
    with patch("app.routers.lending.get_lending_service") as mock_svc_factory:
        svc = AsyncMock()
        svc.get_stock_lending = AsyncMock(return_value=None)
        mock_svc_factory.return_value = svc

        resp = client.get("/api/v1/lending/stock/9999?date=20260328")

    assert resp.status_code == 404


def test_get_stock_lending_history_200(client):
    with patch("app.routers.lending.get_lending_service") as mock_svc_factory:
        svc = AsyncMock()
        svc.get_stock_lending_history = AsyncMock(return_value=[_LENDING_RECORD])
        mock_svc_factory.return_value = svc

        resp = client.get("/api/v1/lending/stock/2330/history?start_date=20260101&end_date=20260328")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["stock_id"] == "2330"
```

- [ ] **Step 2: 跑測試，確認 FAIL**

```bash
cd twse-api && uv run pytest tests/test_lending_router.py -v
```
Expected: `ImportError` 或 404

- [ ] **Step 3: 新增 `app/routers/lending.py`**

```python
"""Lending Router — 借券成交明細 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.lending import get_lending_service

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/stock/{stock_id}")
async def get_stock_lending(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股借券成交明細 — FinMind: TaiwanStockSecuritiesLending"""
    date = date or _default_date()
    result = await get_lending_service(session).get_stock_lending(date, stock_id, force_refresh)
    if result is None:
        raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
    return result


@router.get("/stock/{stock_id}/history")
async def get_stock_lending_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股借券歷史（從 DB 查，不補爬）"""
    return await get_lending_service(session).get_stock_lending_history(
        stock_id, start_date, end_date
    )
```

- [ ] **Step 4: 跑測試，確認 PASS（main.py 尚未掛 router，但 TestClient 用 `app` object 直接測）**

先在 `app/main.py` 加入 lending router（預覽 Task 16 的一部分）：

```python
from app.routers import lending
app.include_router(lending.router, prefix="/api/v1/lending", tags=["lending"])
```

```bash
cd twse-api && uv run pytest tests/test_lending_router.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/lending.py tests/test_lending_router.py
git commit -m "feat: add LendingRouter with stock and history endpoints"
```

---

## Task 11: 信用額度管制解析器 + Service + Router

**Files:**
- Create: `tests/test_short_sale_parsing.py`
- Create: `app/services/short_sale.py`
- Create: `tests/test_short_sale_service.py`
- Create: `app/routers/short_sale.py`
- Create: `tests/test_short_sale_router.py`

- [ ] **Step 1: 新增解析測試 `tests/test_short_sale_parsing.py`**

```python
"""信用額度管制解析器單元測試。"""
from app.adapters.twse_playwright import TWSEPlaywrightClient


def test_parse_short_sale_rows_basic():
    rows = [
        ["2330", "台積電", "5,000", "100,000"],
        ["2317", "鴻海",   "1,000",  "50,000"],
    ]
    result = TWSEPlaywrightClient._parse_short_sale_rows(rows, "20260328")
    assert len(result) == 2
    assert result[0]["stock_id"] == "2330"
    assert result[0]["ShortSaleShares"] == 5000
    assert result[0]["ShortSaleLimit"] == 100000
    assert str(result[0]["date"]) == "2026-03-28"


def test_parse_short_sale_rows_skips_short_rows():
    rows = [
        ["2330"],
        ["2317", "鴻海", "1,000", "50,000"],
    ]
    result = TWSEPlaywrightClient._parse_short_sale_rows(rows, "20260328")
    assert len(result) == 1
    assert result[0]["stock_id"] == "2317"


def test_parse_short_sale_rows_handles_empty_cells():
    rows = [["2330", "台積電", "", ""]]
    result = TWSEPlaywrightClient._parse_short_sale_rows(rows, "20260328")
    assert result[0]["ShortSaleShares"] == 0
    assert result[0]["ShortSaleLimit"] == 0


def test_parse_short_sale_rows_empty_input():
    assert TWSEPlaywrightClient._parse_short_sale_rows([], "20260328") == []
```

- [ ] **Step 2: 跑解析測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_short_sale_parsing.py -v
```
Expected: 4 passed

- [ ] **Step 3: 新增 `app/services/short_sale.py`**

```python
"""Short Sale Service — 信用額度總量管制 (DB-first cache)."""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import ShortSaleSource
from app.adapters.twse_playwright import get_playwright_client
from app.db.repository import TWSERepository

logger = logging.getLogger(__name__)


class ShortSaleService:
    def __init__(self, session: AsyncSession, adapter: Optional[ShortSaleSource] = None):
        self.repo = TWSERepository(session)
        self.adapter = adapter or get_playwright_client()
        self.session = session

    async def get_stock_short_sale(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        if not force_refresh:
            record = await self.repo.get_short_sale_balances(date_str, stock_id)
            if record:
                return self._format(record)

        await self._ingest(date_str)
        record = await self.repo.get_short_sale_balances(date_str, stock_id)
        return self._format(record) if record else None

    async def get_stock_short_sale_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        records = await self.repo.get_short_sale_balances_history(stock_id, start_date, end_date)
        return [self._format(r) for r in records]

    async def _ingest(self, date_str: str) -> None:
        rows = await self.adapter.fetch_short_sale_balances(date_str)
        await self.repo.upsert_short_sale_balances(rows)
        await self.session.flush()

    def _format(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "ShortSaleShares": record.ShortSaleShares,
            "ShortSaleLimit": record.ShortSaleLimit,
        }


def get_short_sale_service(session: AsyncSession) -> ShortSaleService:
    return ShortSaleService(session=session)
```

- [ ] **Step 4: 新增 `tests/test_short_sale_service.py`**

```python
"""信用額度 service DB cache 測試。"""
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.short_sale import ShortSaleService


def _mock_adapter():
    adapter = MagicMock()
    adapter.fetch_short_sale_balances = AsyncMock(return_value=[
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "ShortSaleShares": 5000,
            "ShortSaleLimit": 100000,
        }
    ])
    return adapter


async def test_get_stock_short_sale_calls_adapter_on_miss(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = ShortSaleService(session=test_session, adapter=adapter)

    result = await service.get_stock_short_sale("20260328", "2330")

    adapter.fetch_short_sale_balances.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["ShortSaleShares"] == 5000


async def test_get_stock_short_sale_returns_db_on_hit(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = ShortSaleService(session=test_session, adapter=adapter)

    await service.get_stock_short_sale("20260328", "2330")
    adapter.fetch_short_sale_balances.reset_mock()

    result = await service.get_stock_short_sale("20260328", "2330")
    adapter.fetch_short_sale_balances.assert_not_called()
    assert result["ShortSaleLimit"] == 100000


async def test_get_stock_short_sale_returns_none_for_unknown(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = ShortSaleService(session=test_session, adapter=adapter)

    result = await service.get_stock_short_sale("20260328", "9999")
    assert result is None
```

- [ ] **Step 5: 跑 service 測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_short_sale_service.py -v
```
Expected: 3 passed

- [ ] **Step 6: 新增 `app/routers/short_sale.py`**

```python
"""Short Sale Router — 信用額度總量管制 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.short_sale import get_short_sale_service

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/stock/{stock_id}")
async def get_stock_short_sale(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股信用額度管制 — FinMind: TaiwanDailyShortSaleBalances"""
    date = date or _default_date()
    result = await get_short_sale_service(session).get_stock_short_sale(date, stock_id, force_refresh)
    if result is None:
        raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
    return result


@router.get("/stock/{stock_id}/history")
async def get_stock_short_sale_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股信用額度歷史（從 DB 查，不補爬）"""
    return await get_short_sale_service(session).get_stock_short_sale_history(
        stock_id, start_date, end_date
    )
```

- [ ] **Step 7: 新增 `tests/test_short_sale_router.py`**

```python
"""信用額度 router 整合測試。"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_RECORD = {
    "date": "2026-03-28",
    "stock_id": "2330",
    "ShortSaleShares": 5000,
    "ShortSaleLimit": 100000,
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_stock_short_sale_200(client):
    with patch("app.routers.short_sale.get_short_sale_service") as mock_svc_factory:
        svc = AsyncMock()
        svc.get_stock_short_sale = AsyncMock(return_value=_RECORD)
        mock_svc_factory.return_value = svc

        resp = client.get("/api/v1/short-sale/stock/2330?date=20260328")

    assert resp.status_code == 200
    assert resp.json()["ShortSaleShares"] == 5000


def test_get_stock_short_sale_404(client):
    with patch("app.routers.short_sale.get_short_sale_service") as mock_svc_factory:
        svc = AsyncMock()
        svc.get_stock_short_sale = AsyncMock(return_value=None)
        mock_svc_factory.return_value = svc

        resp = client.get("/api/v1/short-sale/stock/9999?date=20260328")

    assert resp.status_code == 404
```

- [ ] **Step 8: 暫時在 main.py 加入 short_sale router（供 router test 用）**

```python
from app.routers import short_sale
app.include_router(short_sale.router, prefix="/api/v1/short-sale", tags=["short-sale"])
```

- [ ] **Step 9: 跑所有測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_short_sale_parsing.py tests/test_short_sale_service.py tests/test_short_sale_router.py -v
```
Expected: 9 passed

- [ ] **Step 10: Commit**

```bash
git add app/services/short_sale.py app/routers/short_sale.py \
        tests/test_short_sale_parsing.py tests/test_short_sale_service.py tests/test_short_sale_router.py
git commit -m "feat: add ShortSaleService and router with DB-first cache"
```

---

## Task 12: 處置有價證券解析器 + Service + Router

**Files:**
- Create: `tests/test_disposition_parsing.py`
- Create: `app/services/disposition.py`
- Create: `tests/test_disposition_service.py`
- Create: `app/routers/disposition.py`
- Create: `tests/test_disposition_router.py`

- [ ] **Step 1: 新增解析測試 `tests/test_disposition_parsing.py`**

```python
"""處置有價證券解析器單元測試。"""
from app.adapters.twse_playwright import TWSEPlaywrightClient


def test_parse_disposition_rows_basic():
    rows = [
        ["2026-03-01", "2026-03-31", "1234", "異常交易"],
        ["2026-02-01", "2026-02-28", "5678", "連續漲停"],
    ]
    result = TWSEPlaywrightClient._parse_disposition_rows(rows)
    assert len(result) == 2
    assert result[0]["stock_id"] == "1234"
    assert str(result[0]["start_date"]) == "2026-03-01"
    assert str(result[0]["end_date"]) == "2026-03-31"
    assert result[0]["reason"] == "異常交易"


def test_parse_disposition_rows_null_end_date():
    """end_date 無法解析 → None。"""
    rows = [["2026-03-01", "N/A", "1234", "異常交易"]]
    result = TWSEPlaywrightClient._parse_disposition_rows(rows)
    assert result[0]["end_date"] is None


def test_parse_disposition_rows_skips_unparseable_start():
    """start_date 無法解析 → 整筆略過。"""
    rows = [
        ["invalid", "2026-03-31", "1234", "異常交易"],
        ["2026-03-01", "2026-03-31", "5678", "正常"],
    ]
    result = TWSEPlaywrightClient._parse_disposition_rows(rows)
    assert len(result) == 1
    assert result[0]["stock_id"] == "5678"


def test_parse_disposition_rows_slash_date_format():
    """TWSE 有時用 2026/03/01 格式。"""
    rows = [["2026/03/01", "2026/03/31", "2330", "測試"]]
    result = TWSEPlaywrightClient._parse_disposition_rows(rows)
    assert str(result[0]["start_date"]) == "2026-03-01"


def test_parse_disposition_rows_empty_input():
    assert TWSEPlaywrightClient._parse_disposition_rows([]) == []
```

- [ ] **Step 2: 跑解析測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_disposition_parsing.py -v
```
Expected: 5 passed

- [ ] **Step 3: 新增 `app/services/disposition.py`**

```python
"""Disposition Service — 處置有價證券 (DB-first cache)."""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import DispositionSource
from app.adapters.twse_playwright import get_playwright_client
from app.db.repository import TWSERepository

logger = logging.getLogger(__name__)


class DispositionService:
    def __init__(self, session: AsyncSession, adapter: Optional[DispositionSource] = None):
        self.repo = TWSERepository(session)
        self.adapter = adapter or get_playwright_client()
        self.session = session

    async def get_by_stock(
        self, stock_id: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """取得某 stock 所有處置記錄。force_refresh 時重新爬取今日公告。"""
        if not force_refresh:
            records = await self.repo.get_disposition_by_stock(stock_id)
            if records:
                return [self._format(r) for r in records]

        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
        await self._ingest(today)
        records = await self.repo.get_disposition_by_stock(stock_id)
        return [self._format(r) for r in records]

    async def get_by_date(
        self, date_str: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """取得某日有效的所有處置。"""
        if not force_refresh:
            records = await self.repo.get_disposition_by_date(date_str)
            if records:
                return [self._format(r) for r in records]

        await self._ingest(date_str)
        records = await self.repo.get_disposition_by_date(date_str)
        return [self._format(r) for r in records]

    async def _ingest(self, date_str: str) -> None:
        rows = await self.adapter.fetch_disposition(date_str)
        await self.repo.upsert_disposition(rows)
        await self.session.flush()

    def _format(self, record) -> dict[str, Any]:
        return {
            "start_date": record.start_date.strftime("%Y-%m-%d"),
            "end_date": record.end_date.strftime("%Y-%m-%d") if record.end_date else None,
            "stock_id": record.stock_id,
            "reason": record.reason,
        }


def get_disposition_service(session: AsyncSession) -> DispositionService:
    return DispositionService(session=session)
```

- [ ] **Step 4: 新增 `tests/test_disposition_service.py`**

```python
"""處置有價證券 service 測試。"""
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.disposition import DispositionService

_ROW = {
    "start_date": date(2026, 3, 1),
    "end_date": date(2026, 3, 31),
    "stock_id": "1234",
    "reason": "異常交易",
}


def _mock_adapter():
    adapter = MagicMock()
    adapter.fetch_disposition = AsyncMock(return_value=[_ROW])
    return adapter


async def test_get_by_stock_calls_adapter_on_miss(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = DispositionService(session=test_session, adapter=adapter)

    with patch("app.services.disposition.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "20260328"
        result = await service.get_by_stock("1234")

    adapter.fetch_disposition.assert_called_once()
    assert len(result) == 1
    assert result[0]["stock_id"] == "1234"


async def test_get_by_date_calls_adapter_on_miss(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = DispositionService(session=test_session, adapter=adapter)

    result = await service.get_by_date("20260315")

    adapter.fetch_disposition.assert_called_once_with("20260315")
    assert len(result) == 1
    assert result[0]["reason"] == "異常交易"


async def test_get_by_stock_returns_db_on_hit(test_session: AsyncSession):
    adapter = _mock_adapter()
    service = DispositionService(session=test_session, adapter=adapter)

    with patch("app.services.disposition.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "20260328"
        await service.get_by_stock("1234")
        adapter.fetch_disposition.reset_mock()
        result = await service.get_by_stock("1234")

    adapter.fetch_disposition.assert_not_called()
    assert len(result) == 1
```

- [ ] **Step 5: 跑 service 測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_disposition_service.py -v
```
Expected: 3 passed

- [ ] **Step 6: 新增 `app/routers/disposition.py`**

```python
"""Disposition Router — 處置有價證券 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.services.disposition import get_disposition_service

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get("/stock/{stock_id}")
async def get_disposition_by_stock(
    stock_id: str,
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股處置記錄 — FinMind: TaiwanStockDispositionSecuritiesPeriod"""
    return await get_disposition_service(session).get_by_stock(stock_id, force_refresh)


@router.get("")
async def get_disposition_by_date(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """某日有效的全市場處置清單"""
    date = date or _default_date()
    return await get_disposition_service(session).get_by_date(date, force_refresh)
```

- [ ] **Step 7: 新增 `tests/test_disposition_router.py`**

```python
"""處置 router 整合測試。"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_RECORD = {
    "start_date": "2026-03-01",
    "end_date": "2026-03-31",
    "stock_id": "1234",
    "reason": "異常交易",
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_disposition_by_stock_200(client):
    with patch("app.routers.disposition.get_disposition_service") as mock_factory:
        svc = AsyncMock()
        svc.get_by_stock = AsyncMock(return_value=[_RECORD])
        mock_factory.return_value = svc

        resp = client.get("/api/v1/disposition/stock/1234")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["reason"] == "異常交易"


def test_get_disposition_by_date_200(client):
    with patch("app.routers.disposition.get_disposition_service") as mock_factory:
        svc = AsyncMock()
        svc.get_by_date = AsyncMock(return_value=[_RECORD])
        mock_factory.return_value = svc

        resp = client.get("/api/v1/disposition?date=20260315")

    assert resp.status_code == 200
    assert resp.json()[0]["stock_id"] == "1234"
```

- [ ] **Step 8: 暫時在 main.py 加入 disposition router**

```python
from app.routers import disposition
app.include_router(disposition.router, prefix="/api/v1/disposition", tags=["disposition"])
```

- [ ] **Step 9: 跑所有測試，確認 PASS**

```bash
cd twse-api && uv run pytest tests/test_disposition_parsing.py tests/test_disposition_service.py tests/test_disposition_router.py -v
```
Expected: 11 passed

- [ ] **Step 10: Commit**

```bash
git add app/services/disposition.py app/routers/disposition.py \
        tests/test_disposition_parsing.py tests/test_disposition_service.py tests/test_disposition_router.py
git commit -m "feat: add DispositionService and router with DB-first cache"
```

---

## Task 13: main.py 整合 + Playwright lifespan

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 更新 `app/main.py`**

用以下內容完整替換（整合 Task 10/11/12 中暫時加入的 router，並加入 lifespan 的 Playwright 管理）：

```python
"""TWSE API — FastAPI Application"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import close_db, init_db
from app.adapters.twse_playwright import get_playwright_client
from app.routers import chip, margin, shareholding, lending, short_sale, disposition


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await get_playwright_client().startup()
    yield
    await get_playwright_client().shutdown()
    await close_db()


app = FastAPI(
    title="TWSE API",
    description="REST API service for TWSE chip data with PostgreSQL caching",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chip.router, prefix="/api/v1/chip", tags=["chip"])
app.include_router(margin.router, prefix="/api/v1/margin", tags=["margin"])
app.include_router(shareholding.router, prefix="/api/v1/shareholding", tags=["shareholding"])
app.include_router(lending.router, prefix="/api/v1/lending", tags=["lending"])
app.include_router(short_sale.router, prefix="/api/v1/short-sale", tags=["short-sale"])
app.include_router(disposition.router, prefix="/api/v1/disposition", tags=["disposition"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "twse-api"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
```

- [ ] **Step 2: 跑全部測試，確認全部 PASS**

```bash
cd twse-api && uv run pytest tests/ -v
```
Expected: 全部 PASS（router tests 因為 TestClient 啟動 lifespan 可能觸發 Playwright startup；若 chromium 已安裝應正常）

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: integrate Playwright lifespan and all new routers into main.py"
```

---

## Task 14: 手動驗證 TWSE 頁面選擇器

⚠️ **這個 Task 需要人工執行**，確認實際 TWSE 頁面的 URL 和 CSS selector，然後更新 `twse_playwright.py`。

- [ ] **Step 1: 寫一個臨時 script 確認借券頁面（TWT49U）**

新增 `scripts/inspect_twtxxx.py`（執行完刪除）：

```python
"""臨時 script：打開 TWSE 借券頁面，印出所有 input/button 的 selector。執行完刪除。"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False 可以看到畫面
        page = await browser.new_page()
        await page.goto("https://www.twse.com.tw/rwd/zh/SBL/TWT49U")
        await page.wait_for_load_state("networkidle")
        # 印出所有 input 的 name/id/type
        inputs = await page.evaluate("""
            () => Array.from(document.querySelectorAll('input,select,button')).map(el => ({
                tag: el.tagName, name: el.name, id: el.id, type: el.type, class: el.className
            }))
        """)
        for inp in inputs:
            print(inp)
        await browser.close()

asyncio.run(main())
```

```bash
cd twse-api && uv run python scripts/inspect_twtxxx.py
```

- [ ] **Step 2: 根據輸出更新 `twse_playwright.py` 中的 `# TODO: verify selector` 行**

以實際 selector 替換以下三個方法中的 TODO 行：
- `fetch_securities_lending`：URL、date input selector、submit button selector、table selector
- `fetch_short_sale_balances`：同上
- `fetch_disposition`：URL、table selector（此頁可能無需填表單）

- [ ] **Step 3: 用真實日期跑一次端對端確認**

```bash
cd twse-api && uv run uvicorn app.main:app --reload &
sleep 3
curl "http://localhost:8000/api/v1/lending/stock/2330?date=20260328" | python -m json.tool
curl "http://localhost:8000/api/v1/short-sale/stock/2330?date=20260328" | python -m json.tool
curl "http://localhost:8000/api/v1/disposition?date=20260328" | python -m json.tool
```
Expected: 各 endpoint 回傳含有資料的 JSON（或 404 若該日無資料）

- [ ] **Step 4: Commit selector 更新**

```bash
git add app/adapters/twse_playwright.py
git commit -m "fix: update TWSE page selectors after manual inspection"
```
