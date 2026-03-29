# twse-api MI_QFIIS 外資持股 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增外資持股比例（MI_QFIIS）的爬取、DB 儲存與 HTTP 查詢端點，對齊 FinMind TaiwanStockShareholding 資料集。

**Architecture:** FastAPI + SQLAlchemy async + asyncpg (prod) / aiosqlite (tests)。資料流為 DB-first cache：Router → ShareholdingService → TWSERepository（DB hit 直接回傳，DB miss 才呼叫 TWSEClient 爬取 MI_QFIIS）。與現有 chip/margin service 完全相同分層模式。

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pytest-asyncio (asyncio_mode="auto"), aiosqlite (test)

---

## File Map

| 動作 | 檔案 | 說明 |
|------|------|------|
| 修改 | `app/db/models.py` | 新增 `StockShareholding` ORM model |
| 修改 | `app/db/repository.py` | 新增 4 個 shareholding 方法 |
| 修改 | `app/services/twse_client.py` | 新增 `fetch_shareholding_data()` |
| 新增 | `app/services/shareholding.py` | `ShareholdingService`（DB-first cache） |
| 新增 | `app/schemas/shareholding.py` | Pydantic response schemas |
| 新增 | `app/routers/shareholding.py` | 3 個 HTTP endpoints |
| 修改 | `app/main.py` | include shareholding router |
| 修改 | `tests/conftest.py` | 新增 `SqliteStockShareholding` test model |
| 新增 | `tests/test_shareholding_parsing.py` | parser 單元測試 |
| 新增 | `tests/test_shareholding_service.py` | DB cache hit/miss 測試 |
| 新增 | `tests/test_shareholding_router.py` | router 整合測試 |

---

## Task 1：DB Model + conftest

**Files:**
- Modify: `app/db/models.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1：新增 `StockShareholding` 到 `app/db/models.py`**

在 `TotalMargin` class 之後加入以下 import 修改和新 class。先在檔案頂部的 import 行加上 `Numeric`：

```python
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint
```

然後在 `TotalMargin` class 之後加入：

```python
class StockShareholding(Base):
    """
    個股外資持股比例 — FinMind: TaiwanStockShareholding
    TWSE source: MI_QFIIS (selectType=ALLBUT0999)
    """
    __tablename__ = "twse_stock_shareholding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    NumberOfSharesIssued = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentShares = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentSharesRatio = Column(Numeric(10, 4), nullable=False, default=0)
    ForeignInvestmentSharesWithoutDealers = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentSharesWithoutDealersRatio = Column(Numeric(10, 4), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("date", "stock_id"),)
```

- [ ] **Step 2：新增 `SqliteStockShareholding` 到 `tests/conftest.py`**

在 `SqliteBase` class 定義之後加入以下 import 修改（在原有 import 行加入 `Float`）：

```python
from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Integer, String, UniqueConstraint
```

然後在 `SqliteTotalMargin` class 之後加入：

```python
class SqliteStockShareholding(SqliteBase):
    __tablename__ = "twse_stock_shareholding"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    stock_id = Column(String(10), nullable=False)
    NumberOfSharesIssued = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentShares = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentSharesRatio = Column(Float, nullable=False, default=0.0)
    ForeignInvestmentSharesWithoutDealers = Column(BigInteger, nullable=False, default=0)
    ForeignInvestmentSharesWithoutDealersRatio = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime)
    __table_args__ = (UniqueConstraint("date", "stock_id"),)
```

- [ ] **Step 3：執行現有測試確認沒有 regression**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/ -v --tb=short
```

Expected: 全部 24 tests PASS（新的 model 不影響現有測試）

- [ ] **Step 4：Commit**

```bash
git add app/db/models.py tests/conftest.py
git commit -m "feat: add StockShareholding ORM model and SQLite test model"
```

---

## Task 2：Repository + Repository Tests

**Files:**
- Modify: `app/db/repository.py`
- Create: `tests/test_shareholding_repository.py`

- [ ] **Step 1：先建立 `tests/test_shareholding_repository.py`（先寫測試）**

```python
"""Repository tests for shareholding upsert/get."""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from tests.conftest import SqliteStockShareholding


async def test_upsert_stock_shareholding_inserts(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {
            "date": date(2026, 3, 28),
            "stock_id": "2330",
            "NumberOfSharesIssued": 25930380458,
            "ForeignInvestmentShares": 15000000000,
            "ForeignInvestmentSharesRatio": 57.84,
            "ForeignInvestmentSharesWithoutDealers": 14900000000,
            "ForeignInvestmentSharesWithoutDealersRatio": 57.46,
        }
    ]
    await repo.upsert_stock_shareholding(rows)
    result = await test_session.execute(select(SqliteStockShareholding))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].NumberOfSharesIssued == 25930380458


async def test_upsert_stock_shareholding_updates_on_conflict(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [{"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 100}]
    await repo.upsert_stock_shareholding(rows)
    rows_updated = [{"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 999}]
    await repo.upsert_stock_shareholding(rows_updated)
    result = await repo.get_stock_shareholding("20260328", "2330")
    assert result.ForeignInvestmentShares == 999


async def test_get_stock_shareholding_returns_none_when_missing(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    result = await repo.get_stock_shareholding("20260328", "9999")
    assert result is None


async def test_get_all_stocks_shareholding_returns_multiple(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 100},
        {"date": date(2026, 3, 28), "stock_id": "2317", "ForeignInvestmentShares": 200},
    ]
    await repo.upsert_stock_shareholding(rows)
    results = await repo.get_all_stocks_shareholding("20260328")
    assert len(results) == 2


async def test_get_stock_shareholding_history(test_session: AsyncSession):
    repo = TWSERepository(test_session)
    rows = [
        {"date": date(2026, 3, 27), "stock_id": "2330", "ForeignInvestmentShares": 100},
        {"date": date(2026, 3, 28), "stock_id": "2330", "ForeignInvestmentShares": 200},
        {"date": date(2026, 3, 29), "stock_id": "2330", "ForeignInvestmentShares": 300},
    ]
    await repo.upsert_stock_shareholding(rows)
    history = await repo.get_stock_shareholding_history("2330", "20260327", "20260328")
    assert len(history) == 2
    assert history[0].ForeignInvestmentShares == 100
    assert history[1].ForeignInvestmentShares == 200
```

- [ ] **Step 2：執行確認失敗**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/test_shareholding_repository.py -v
```

Expected: `AttributeError: 'TWSERepository' object has no attribute 'upsert_stock_shareholding'`

- [ ] **Step 3：在 `app/db/repository.py` 新增 shareholding import 和 4 個方法**

在 `repository.py` 頂部的 import 中加入 `StockShareholding`：

```python
from app.db.models import (
    StockInstitutionalInvestors,
    TotalInstitutionalInvestors,
    StockMargin,
    TotalMargin,
    StockShareholding,
)
```

在 `TWSERepository` class 的最後（`get_total_margin` 方法之後）加入：

```python
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
```

- [ ] **Step 4：執行 repository 測試確認通過**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/test_shareholding_repository.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5：執行全部測試確認無 regression**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/ -v --tb=short
```

Expected: 全部 PASS（24 + 5 = 29 tests）

- [ ] **Step 6：Commit**

```bash
git add app/db/repository.py tests/test_shareholding_repository.py
git commit -m "feat: add shareholding repository methods and tests"
```

---

## Task 3：TWSEClient + ShareholdingService + Parsing Tests

**Files:**
- Modify: `app/services/twse_client.py`
- Create: `app/services/shareholding.py`
- Create: `tests/test_shareholding_parsing.py`

- [ ] **Step 1：先建立 `tests/test_shareholding_parsing.py`（先寫測試）**

```python
"""Unit tests for MI_QFIIS JSON parsing logic."""
from unittest.mock import MagicMock
from app.services.shareholding import ShareholdingService


def make_mock_shareholding_response():
    """
    MI_QFIIS response structure:
    data[i] = [證券代號, 證券名稱, 發行股數, 外資(不含自營)-持有股數, 外資(不含自營)-持股比例, 外資-持有股數, 外資-持股比例]

    index mapping:
    [0] 證券代號                               → stock_id
    [1] 證券名稱                               → (skip)
    [2] 發行股數                               → NumberOfSharesIssued
    [3] 外資及陸資(不含外資自營商)-持有股數      → ForeignInvestmentSharesWithoutDealers
    [4] 外資及陸資(不含外資自營商)-持股比例(%)   → ForeignInvestmentSharesWithoutDealersRatio
    [5] 外資及陸資-持有股數                     → ForeignInvestmentShares
    [6] 外資及陸資-持股比例(%)                  → ForeignInvestmentSharesRatio
    """
    return {
        "stat": "OK",
        "date": "20260328",
        "data": [
            ["2330", "台積電", "25,930,380,458", "14,900,000,000", "57.46", "15,000,000,000", "57.84"],
            ["2317", "鴻海",   "13,872,977,380",  "4,200,000,000", "30.27",  "4,300,000,000", "30.99"],
        ],
    }


async def test_parse_shareholding_count():
    """Should parse 2 stocks from data."""
    service = ShareholdingService(session=MagicMock(), client=MagicMock())
    rows = service._parse_shareholding("20260328", make_mock_shareholding_response())
    assert len(rows) == 2


async def test_parse_shareholding_fields():
    """Should map data columns to FinMind field names correctly."""
    service = ShareholdingService(session=MagicMock(), client=MagicMock())
    rows = service._parse_shareholding("20260328", make_mock_shareholding_response())
    tsmc = next(r for r in rows if r["stock_id"] == "2330")
    assert tsmc["NumberOfSharesIssued"] == 25930380458
    assert tsmc["ForeignInvestmentShares"] == 15000000000
    assert tsmc["ForeignInvestmentSharesRatio"] == 57.84
    assert tsmc["ForeignInvestmentSharesWithoutDealers"] == 14900000000
    assert tsmc["ForeignInvestmentSharesWithoutDealersRatio"] == 57.46


async def test_parse_shareholding_skips_short_rows():
    """Rows with fewer than 7 columns should be silently skipped."""
    service = ShareholdingService(session=MagicMock(), client=MagicMock())
    bad_response = {
        "stat": "OK",
        "data": [
            ["2330", "台積電", "too", "few"],       # only 4 columns — skip
            ["2317", "鴻海", "13,872,977,380", "4,200,000,000", "30.27", "4,300,000,000", "30.99"],
        ],
    }
    rows = service._parse_shareholding("20260328", bad_response)
    assert len(rows) == 1
    assert rows[0]["stock_id"] == "2317"
```

- [ ] **Step 2：執行確認失敗**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/test_shareholding_parsing.py -v
```

Expected: `ImportError: cannot import name 'ShareholdingService'`

- [ ] **Step 3：在 `app/services/twse_client.py` 新增 `fetch_shareholding_data`**

在 `fetch_margin_data` 方法之後加入：

```python
    async def fetch_shareholding_data(self, date_str: str) -> dict[str, Any]:
        """MI_QFIIS — 外資持股比例"""
        url = f"{BASE_URL}/rwd/zh/fund/MI_QFIIS?response=json&date={date_str}&selectType=ALLBUT0999"
        return await self._fetch_json(url)
```

- [ ] **Step 4：建立 `app/services/shareholding.py`**

```python
"""
Shareholding Service — 外資持股比例 (DB-first cache).

MI_QFIIS response structure:
  data: list of stock rows (7 columns each)

data column indices:
  [0] 證券代號                               → stock_id
  [1] 證券名稱                               → (ignored)
  [2] 發行股數                               → NumberOfSharesIssued
  [3] 外資及陸資(不含外資自營商)-持有股數      → ForeignInvestmentSharesWithoutDealers
  [4] 外資及陸資(不含外資自營商)-持股比例(%)   → ForeignInvestmentSharesWithoutDealersRatio
  [5] 外資及陸資-持有股數                     → ForeignInvestmentShares
  [6] 外資及陸資-持股比例(%)                  → ForeignInvestmentSharesRatio

NOTE: Verify actual TWSE response format before deploying. Run:
  curl "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?response=json&date=20260101&selectType=ALLBUT0999"
"""
import logging
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import TWSERepository
from app.services.twse_client import TWSEClient, get_twse_client

logger = logging.getLogger(__name__)


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _float(value: str) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _parse_date(date_str: str) -> date_type:
    return date_type(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))


class ShareholdingService:
    def __init__(self, session: AsyncSession, client: Optional[TWSEClient] = None):
        self.repo = TWSERepository(session)
        self.client = client or get_twse_client()
        self.session = session

    async def get_stock_shareholding(
        self, date_str: str, stock_id: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """個股外資持股。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            record = await self.repo.get_stock_shareholding(date_str, stock_id)
            if record:
                return self._format_shareholding(record)

        await self._ingest_shareholding(date_str)
        record = await self.repo.get_stock_shareholding(date_str, stock_id)
        return self._format_shareholding(record) if record else None

    async def get_all_stocks_shareholding(
        self, date_str: str, force_refresh: bool = False
    ) -> dict[str, Any]:
        """全市場外資持股列表。DB hit → 直接回傳；miss → 爬取並存 DB。"""
        if not force_refresh:
            rows = await self.repo.get_all_stocks_shareholding(date_str)
            if rows:
                return self._format_all_stocks(date_str, rows)

        await self._ingest_shareholding(date_str)
        rows = await self.repo.get_all_stocks_shareholding(date_str)
        return self._format_all_stocks(date_str, rows)

    async def get_stock_shareholding_history(
        self, stock_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """個股外資持股歷史（僅從 DB 查，不自動補爬）。"""
        records = await self.repo.get_stock_shareholding_history(stock_id, start_date, end_date)
        return [self._format_shareholding(r) for r in records]

    # ── Ingest ───────────────────────────────────────────────────

    async def _ingest_shareholding(self, date_str: str) -> None:
        raw = await self.client.fetch_shareholding_data(date_str)
        rows = self._parse_shareholding(date_str, raw)
        await self.repo.upsert_stock_shareholding(rows)
        await self.session.flush()

    # ── Parser ───────────────────────────────────────────────────

    def _parse_shareholding(self, date_str: str, data: dict) -> list[dict]:
        """MI_QFIIS data → rows for twse_stock_shareholding."""
        d = _parse_date(date_str)
        rows = []
        for row in data.get("data", []):
            if len(row) < 7:
                continue
            try:
                rows.append({
                    "date": d,
                    "stock_id": row[0].strip(),
                    "NumberOfSharesIssued": _int(row[2]),
                    "ForeignInvestmentSharesWithoutDealers": _int(row[3]),
                    "ForeignInvestmentSharesWithoutDealersRatio": _float(row[4]),
                    "ForeignInvestmentShares": _int(row[5]),
                    "ForeignInvestmentSharesRatio": _float(row[6]),
                })
            except (ValueError, IndexError):
                continue
        return rows

    # ── Formatter ────────────────────────────────────────────────

    def _format_shareholding(self, record) -> dict[str, Any]:
        return {
            "date": record.date.strftime("%Y-%m-%d"),
            "stock_id": record.stock_id,
            "NumberOfSharesIssued": record.NumberOfSharesIssued,
            "ForeignInvestmentShares": record.ForeignInvestmentShares,
            "ForeignInvestmentSharesRatio": float(record.ForeignInvestmentSharesRatio),
            "ForeignInvestmentSharesWithoutDealers": record.ForeignInvestmentSharesWithoutDealers,
            "ForeignInvestmentSharesWithoutDealersRatio": float(record.ForeignInvestmentSharesWithoutDealersRatio),
        }

    def _format_all_stocks(self, date_str: str, rows) -> dict[str, Any]:
        return {
            "date": date_str,
            "stocks": [self._format_shareholding(r) for r in rows],
        }


def get_shareholding_service(session: AsyncSession) -> ShareholdingService:
    return ShareholdingService(session=session)
```

- [ ] **Step 5：執行 parsing tests 確認通過**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/test_shareholding_parsing.py -v
```

Expected: 3 tests PASS

- [ ] **Step 6：Commit**

```bash
git add app/services/twse_client.py app/services/shareholding.py tests/test_shareholding_parsing.py
git commit -m "feat: add ShareholdingService with MI_QFIIS parsing"
```

---

## Task 4：ShareholdingService DB Cache Tests

**Files:**
- Create: `tests/test_shareholding_service.py`

- [ ] **Step 1：建立 `tests/test_shareholding_service.py`**

```python
"""Shareholding service DB cache tests."""
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shareholding import ShareholdingService


def _mock_client_with_data():
    client = MagicMock()
    client.fetch_shareholding_data = AsyncMock(return_value={
        "stat": "OK",
        "date": "20260328",
        "data": [
            ["2330", "台積電", "25,930,380,458", "14,900,000,000", "57.46", "15,000,000,000", "57.84"],
        ],
    })
    return client


async def test_get_stock_shareholding_calls_client_on_miss(test_session: AsyncSession):
    """DB miss → client should be called, data stored."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_stock_shareholding("20260328", "2330")

    client.fetch_shareholding_data.assert_called_once_with("20260328")
    assert result is not None
    assert result["stock_id"] == "2330"
    assert result["ForeignInvestmentSharesRatio"] == 57.84


async def test_get_stock_shareholding_returns_db_on_hit(test_session: AsyncSession):
    """DB hit → client should NOT be called."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    await service.get_stock_shareholding("20260328", "2330")
    client.fetch_shareholding_data.reset_mock()

    result = await service.get_stock_shareholding("20260328", "2330")
    client.fetch_shareholding_data.assert_not_called()
    assert result["ForeignInvestmentSharesRatio"] == 57.84


async def test_get_stock_shareholding_returns_none_for_unknown(test_session: AsyncSession):
    """Unknown stock_id → returns None."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_stock_shareholding("20260328", "9999")
    assert result is None


async def test_get_stock_shareholding_history_empty_before_ingest(test_session: AsyncSession):
    """History query on empty DB returns []."""
    client = _mock_client_with_data()
    service = ShareholdingService(session=test_session, client=client)

    result = await service.get_stock_shareholding_history("2330", "20260101", "20260328")
    assert result == []
```

- [ ] **Step 2：執行測試確認通過**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/test_shareholding_service.py -v
```

Expected: 4 tests PASS

- [ ] **Step 3：執行全部測試確認無 regression**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/ -v --tb=short
```

Expected: 全部 PASS（29 + 3 + 4 = 36 tests）

- [ ] **Step 4：Commit**

```bash
git add tests/test_shareholding_service.py
git commit -m "test: add shareholding service DB cache tests"
```

---

## Task 5：Schemas + Router + main.py

**Files:**
- Create: `app/schemas/shareholding.py`
- Create: `app/routers/shareholding.py`
- Modify: `app/main.py`
- Create: `tests/test_shareholding_router.py`

- [ ] **Step 1：先建立 `tests/test_shareholding_router.py`（先寫測試）**

```python
"""Shareholding router integration tests."""
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


async def test_shareholding_stock_returns_200():
    """GET /api/v1/shareholding/stock/2330 should return 200 with correct fields."""
    mock_service = MagicMock()
    mock_service.get_stock_shareholding = AsyncMock(return_value={
        "date": "2026-03-28",
        "stock_id": "2330",
        "NumberOfSharesIssued": 25930380458,
        "ForeignInvestmentShares": 15000000000,
        "ForeignInvestmentSharesRatio": 57.84,
        "ForeignInvestmentSharesWithoutDealers": 14900000000,
        "ForeignInvestmentSharesWithoutDealersRatio": 57.46,
    })

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/shareholding/stock/2330?date=20260328")

    assert response.status_code == 200
    data = response.json()
    assert data["stock_id"] == "2330"
    assert data["ForeignInvestmentSharesRatio"] == 57.84


async def test_shareholding_stock_returns_404_when_not_found():
    """GET /api/v1/shareholding/stock/9999 should return 404 when stock not in data."""
    mock_service = MagicMock()
    mock_service.get_stock_shareholding = AsyncMock(return_value=None)

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/shareholding/stock/9999?date=20260328")

    assert response.status_code == 404


async def test_shareholding_stocks_returns_200():
    """GET /api/v1/shareholding/stocks should return 200."""
    mock_service = MagicMock()
    mock_service.get_all_stocks_shareholding = AsyncMock(return_value={
        "date": "20260328",
        "stocks": [
            {
                "date": "2026-03-28",
                "stock_id": "2330",
                "NumberOfSharesIssued": 25930380458,
                "ForeignInvestmentShares": 15000000000,
                "ForeignInvestmentSharesRatio": 57.84,
                "ForeignInvestmentSharesWithoutDealers": 14900000000,
                "ForeignInvestmentSharesWithoutDealersRatio": 57.46,
            }
        ],
    })

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/shareholding/stocks?date=20260328")

    assert response.status_code == 200
    assert len(response.json()["stocks"]) == 1


async def test_shareholding_history_returns_200():
    """GET /api/v1/shareholding/stock/2330/history should return 200."""
    mock_service = MagicMock()
    mock_service.get_stock_shareholding_history = AsyncMock(return_value=[])

    with patch("app.routers.shareholding.get_shareholding_service", return_value=mock_service):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/shareholding/stock/2330/history?start_date=20260101&end_date=20260328"
            )

    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2：執行確認失敗**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/test_shareholding_router.py -v
```

Expected: `ImportError` 或 404（router 未掛上）

- [ ] **Step 3：建立 `app/schemas/shareholding.py`**

```python
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
```

- [ ] **Step 4：建立 `app/routers/shareholding.py`**

```python
"""Shareholding Router — 外資持股比例 endpoints"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.schemas.shareholding import (
    StockShareholdingResponse,
    AllStocksShareholdingResponse,
    ErrorResponse,
)
from app.services.shareholding import get_shareholding_service
from app.services.twse_client import TWSEAPIError

router = APIRouter()
TW_TZ = timezone(timedelta(hours=8))


def _default_date() -> str:
    return datetime.now(TW_TZ).strftime("%Y%m%d")


async def _get_session():
    async with get_session() as session:
        yield session


@router.get(
    "/stocks",
    response_model=AllStocksShareholdingResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_all_stocks_shareholding(
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """全市場外資持股列表 (MI_QFIIS) — FinMind: TaiwanStockShareholding"""
    date = date or _default_date()
    try:
        return await get_shareholding_service(session).get_all_stocks_shareholding(date, force_refresh)
    except TWSEAPIError as e:
        if e.status_code == 404 or "沒有符合" in str(e.message):
            raise HTTPException(404, f"No data for date: {date}")
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}",
    response_model=StockShareholdingResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_stock_shareholding(
    stock_id: str,
    date: Optional[str] = Query(None, pattern=r"^\d{8}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(_get_session),
):
    """個股外資持股 (MI_QFIIS) — FinMind: TaiwanStockShareholding"""
    date = date or _default_date()
    try:
        result = await get_shareholding_service(session).get_stock_shareholding(
            date, stock_id, force_refresh
        )
        if result is None:
            raise HTTPException(404, f"Stock {stock_id} not found for date: {date}")
        return result
    except HTTPException:
        raise
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))


@router.get(
    "/stock/{stock_id}/history",
    response_model=list[StockShareholdingResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_stock_shareholding_history(
    stock_id: str,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
    session: AsyncSession = Depends(_get_session),
):
    """個股外資持股歷史（從 DB 查，不補爬）"""
    try:
        return await get_shareholding_service(session).get_stock_shareholding_history(
            stock_id, start_date, end_date
        )
    except TWSEAPIError as e:
        raise HTTPException(500, str(e.message))
```

- [ ] **Step 5：修改 `app/main.py`，加入 shareholding router**

將 `app/main.py` 的 import 區段改為：

```python
"""TWSE API — FastAPI Application"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import close_db, init_db
from app.routers import chip
from app.routers import margin
from app.routers import shareholding
```

將 router 掛載區段改為：

```python
app.include_router(chip.router, prefix="/api/v1/chip", tags=["chip"])
app.include_router(margin.router, prefix="/api/v1/margin", tags=["margin"])
app.include_router(shareholding.router, prefix="/api/v1/shareholding", tags=["shareholding"])
```

（版本號從 `"0.2.0"` 改為 `"0.3.0"`）

- [ ] **Step 6：執行全部測試確認通過**

```bash
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/ -v --tb=short
```

Expected: 全部 PASS（36 + 4 = 40 tests）

- [ ] **Step 7：Commit**

```bash
git add app/schemas/shareholding.py app/routers/shareholding.py app/main.py tests/test_shareholding_router.py
git commit -m "feat: add shareholding router and schemas, wire up to main.py"
```

---

## 完成後驗證

```bash
# 確認所有測試通過
cd /mnt/raid1/novis/home-stack/twse-api && uv run pytest tests/ -v --tb=short

# 確認 import 正確
uv run python -c "from app.main import app; print('OK')"
```

---

## Self-Review Checklist

- [x] Task 1 — ORM model (Numeric) + SQLite test model (Float)
- [x] Task 2 — Repository 4 個方法 + 5 個 repository tests
- [x] Task 3 — TWSEClient.fetch_shareholding_data + ShareholdingService + 3 個 parsing tests
- [x] Task 4 — 4 個 service DB cache tests (hit/miss/unknown/history)
- [x] Task 5 — Schemas + Router (3 endpoints) + main.py + 4 個 router tests
- [x] 所有測試步驟有完整程式碼，無 TBD
- [x] `get_shareholding_service(session)` factory 一致
- [x] `_int()` / `_float()` helpers 在 shareholding.py 各自定義
- [x] `force_refresh` 所有非 history endpoint 均支援
- [x] `session.flush()` 在 `_ingest_shareholding()` 中使用（非 commit）
- [x] `_format_shareholding` 對 `Numeric` 欄位加 `float()` 轉換（Decimal → float）
