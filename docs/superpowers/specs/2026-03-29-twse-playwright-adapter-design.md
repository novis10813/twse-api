# twse-api Playwright Adapter 設計文件

**日期**：2026-03-29
**範圍**：第二批剩餘資料集（借券、信用額度管制、處置有價證券）+ Port/Adapter 架構

---

## 背景

第二批實作中，`TaiwanStockShareholding`（MI_QFIIS）已透過直接 GET JSON 完成。剩餘三個資料集：

| FinMind Dataset | 中文 | TWSE 來源 | 問題 |
|---|---|---|---|
| `TaiwanStockSecuritiesLending` | 借券成交明細 | TWT49U | 需表單 POST / 僅 HTML |
| `TaiwanDailyShortSaleBalances` | 信用額度總量管制 | TWSE | 需表單 / 反爬蟲 |
| `TaiwanStockDispositionSecuritiesPeriod` | 處置有價證券 | 交易所公告 | HTML 公告頁面 |

TWSE 對這些資料集有複合式反爬蟲防護（session cookie、表單 POST、無 JSON API、動態載入），需用 Playwright 瀏覽器自動化處理。

---

## 設計目標

1. **快速接通資料**：Playwright 作為第一個實作 adapter
2. **可切換架構**：未來可不改 service 直接換成 FinMind adapter
3. **可複用模式**：`FormScraperBase` 與 TWSE 無關，可搬到其他專案

---

## 架構

```
app/
├── adapters/
│   ├── protocols.py            # Python Protocol 定義（Port）
│   ├── twse_playwright.py      # Playwright 實作
│   └── finmind.py              # FinMind 實作（stub，未來擴充）
├── services/
│   ├── twse_client.py          # 現有 GET JSON（不動）
│   ├── lending.py              # 借券 service（新）
│   ├── short_sale.py           # 信用額度管制 service（新）
│   └── disposition.py          # 處置有價證券 service（新）
├── routers/
│   ├── lending.py              # 新
│   ├── short_sale.py           # 新
│   └── disposition.py          # 新
└── db/
    ├── models.py               # 擴充三個新 table
    └── repository.py           # 擴充對應 CRUD
```

---

## Port 定義（adapters/protocols.py）

用 Python `Protocol` 定義每個資料集的 data source 介面：

```python
class LendingSource(Protocol):
    async def fetch_securities_lending(self, date_str: str) -> list[dict]: ...

class ShortSaleSource(Protocol):
    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]: ...

class DispositionSource(Protocol):
    async def fetch_disposition(self, date_str: str) -> list[dict]: ...
```

Service 只依賴 Protocol，adapter 透過 config 注入，不硬綁定實作。

---

## Playwright Adapter（adapters/twse_playwright.py）

### Browser 生命週期

Playwright browser 為 singleton，由 FastAPI `lifespan` 管理：

```python
@asynccontextmanager
async def lifespan(app):
    await playwright_client.startup()   # launch chromium
    yield
    await playwright_client.shutdown()  # close browser
```

每次爬取開新 `page`，用完關閉。Browser context 共用以保留 session / cookie。

### FormScraperBase（可複用）

```python
class FormScraperBase:
    """與 TWSE 無關的瀏覽器表單操作 base class，可搬到其他專案。"""

    async def _submit_form(self, page, selectors: dict, values: dict) -> None:
        """填入表單欄位並送出。"""

    async def _parse_table(self, page, table_selector: str) -> list[list[str]]:
        """解析 HTML table，回傳 list of row strings。"""

    async def _wait_and_retry(self, coro, retries: int = 3, delay: float = 2.0):
        """重試邏輯，失敗時等待後重試。"""
```

### 反爬蟲防護

- 隨機 User-Agent（模擬真實瀏覽器）
- 請求間 `asyncio.sleep(random 1–3s)`
- `page.wait_for_load_state("networkidle")` 等待動態載入
- retry 策略與現有 `TWSEClient` 一致（最多 3 次，exponential backoff）

### TWSEPlaywrightClient

繼承 `FormScraperBase`，實作三個 Protocol：

```python
class TWSEPlaywrightClient(FormScraperBase):
    async def fetch_securities_lending(self, date_str: str) -> list[dict]: ...
    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]: ...
    async def fetch_disposition(self, date_str: str) -> list[dict]: ...
```

每個方法封裝：導航 → 填表單 → 等待 → 解析 HTML table → 回傳 list[dict]。

---

## Adapter 切換

`config.py` 新增：

```python
DATA_SOURCE_ADAPTER: Literal["playwright", "finmind"] = "playwright"
```

`main.py` 依 config 決定注入哪個 adapter，service 完全不知道底層實作。

---

## DB Schema

欄位命名對齊 FinMind PascalCase。

```sql
-- TaiwanStockSecuritiesLending（借券成交明細）
CREATE TABLE twse_stock_lending (
    id                   SERIAL PRIMARY KEY,
    date                 DATE NOT NULL,
    stock_id             VARCHAR(10) NOT NULL,
    LendingShares        BIGINT DEFAULT 0,
    ReturningShares      BIGINT DEFAULT 0,
    LendingSharesBalance BIGINT DEFAULT 0,
    UNIQUE (date, stock_id)
);

-- TaiwanDailyShortSaleBalances（信用額度總量管制）
CREATE TABLE twse_short_sale_balances (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    stock_id        VARCHAR(10) NOT NULL,
    ShortSaleShares BIGINT DEFAULT 0,
    ShortSaleLimit  BIGINT DEFAULT 0,
    UNIQUE (date, stock_id)
);

-- TaiwanStockDispositionSecuritiesPeriod（處置有價證券）
CREATE TABLE twse_disposition (
    id         SERIAL PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date   DATE,
    stock_id   VARCHAR(10) NOT NULL,
    reason     TEXT,
    UNIQUE (start_date, stock_id)
);
```

> 實際欄位待爬到資料後對齊 FinMind schema 確認，可能需微調。

---

## 資料流

```
Router 收到請求 (date, stock_id?)
  → Service 查 DB
  → DB hit  → 直接回傳
  → DB miss → Adapter.fetch_*()       ← 此處可切換 playwright / finmind
            → 解析 → repository.save()
            → 回傳資料
```

---

## API Endpoints

```
# 借券成交明細
GET /api/v1/lending/stock/{stock_id}?date=YYYYMMDD
GET /api/v1/lending/stock/{stock_id}/history?start_date=YYYYMMDD&end_date=YYYYMMDD

# 信用額度總量管制
GET /api/v1/short-sale/stock/{stock_id}?date=YYYYMMDD
GET /api/v1/short-sale/stock/{stock_id}/history?start_date=YYYYMMDD&end_date=YYYYMMDD

# 處置有價證券
GET /api/v1/disposition/stock/{stock_id}
GET /api/v1/disposition?date=YYYYMMDD
```

所有 endpoint 支援 `?force_refresh=true`。

---

## 新增依賴

```toml
dependencies = [
    # 現有...
    "playwright>=1.44",
]
```

需在部署時執行 `playwright install chromium`。

---

## 測試策略

| 層級 | 內容 |
|------|------|
| FormScraperBase | 用 Playwright mock page 測試 `_submit_form`、`_parse_table` |
| Adapter | 用錄製的 HTML fixture 測試解析邏輯（不真正打開瀏覽器） |
| Service | DB cache hit/miss 邏輯（aiosqlite in-memory，mock adapter） |
| Router | HTTP 整合測試（200 + 欄位正確；404 無資料日期） |

---

## 未納入範圍

- FinMind adapter 實作（預留 stub）
- 上櫃（TPEx）資料
- 第三批 indicators 計算層
