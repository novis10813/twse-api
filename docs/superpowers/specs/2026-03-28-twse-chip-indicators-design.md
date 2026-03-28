# twse-api 籌碼指標擴充設計文件

**日期**：2026-03-28
**範圍**：第一批實作（DB 基礎建設 + 三大法人入庫 + 融資融券）

---

## 背景

twse-api 目前是純 HTTP proxy，沒有持久化層。所有資料每次請求都直接爬 TWSE，無法支援歷史查詢與計算型指標。本次擴充目標是對齊 FinMind 籌碼面資料集，建立 DB caching 架構，並為第三批的 eager compute indicators 層預留介面。

整體架構遵循 home-stack ROADMAP：現階段維持 FastAPI HTTP，Phase 4 再轉 NATS listener，Phase 5 加事件化排程。

---

## 設計前提

| 決策 | 說明 |
|------|------|
| 資料庫 | core-postgres（開發階段用本地 Docker Postgres，上線換 env 即可） |
| 市場範圍 | 只爬 TWSE 上市，不含上櫃 |
| 模組分離 | 原始資料爬蟲與計算指標分離（同 mops `indicators/` 模式） |
| 計算方式 | Eager compute：資料入庫後批次計算，結果存 DB |
| 跳過範圍 | 分點資訊（TaiwanStockTradingDailyReport 等）技術複雜度過高，暫不實作 |

---

## FinMind 對齊範圍

### 第一批（本次實作）

| FinMind Dataset | 中文 | TWSE 來源 | 狀態 |
|---|---|---|---|
| `TaiwanStockInstitutionalInvestorsBuySell` | 個股三大法人 | T86 | 已有，補入 DB |
| `TaiwanStockTotalInstitutionalInvestors` | 整體市場三大法人 | BFI82U | 已有，補入 DB |
| `TaiwanStockMarginPurchaseShortSale` | 個股融資融券 | MI_MARGN | 新增 |
| `TaiwanStockTotalMarginPurchaseShortSale` | 整體市場融資融券 | MI_MARGN | 新增 |

### 第二批（待後續）

| FinMind Dataset | 中文 | TWSE 來源 |
|---|---|---|
| `TaiwanStockShareholding` | 外資持股比例 | MI_QFIIS |
| `TaiwanStockSecuritiesLending` | 借券成交明細 | TWT49U |
| `TaiwanDailyShortSaleBalances` | 信用額度總量管制 | TWSE |
| `TaiwanStockDispositionSecuritiesPeriod` | 處置有價證券 | 交易所公告 |

### 第三批（待後續）

- `indicators/` 計算層：券資比、連續買超天數、N 日累計買超等
- Eager compute pipeline

---

## 架構

```
twse-api/
├── app/
│   ├── main.py
│   ├── config.py                # Pydantic Settings (TWSE_ prefix)
│   ├── db/
│   │   ├── connection.py        # async session factory
│   │   ├── models.py            # SQLAlchemy ORM tables
│   │   └── repository.py       # CRUD
│   ├── routers/
│   │   ├── chip.py              # 三大法人（重構，加 DB）
│   │   └── margin.py            # 融資融券（新增）
│   ├── services/
│   │   ├── twse_client.py       # 純 HTTP layer（從 twse.py 拆出）
│   │   ├── chip.py              # 三大法人 service（從 twse.py 移出）
│   │   └── margin.py            # 融資融券 service（新增）
│   └── schemas/
│       ├── chip.py              # 現有
│       └── margin.py            # 新增
```

**`services/twse_client.py`**：純 HTTP layer，只負責 `_fetch_json()` 與各 `fetch_*()` 方法，含 retry 邏輯。現有 `twse.py` 的 business logic 移至各自 service。

---

## DB Schema

欄位命名對齊 FinMind PascalCase，方便資料比對。

### 三大法人

```sql
-- TaiwanStockInstitutionalInvestorsBuySell
CREATE TABLE twse_stock_institutional_investors (
    id         SERIAL PRIMARY KEY,
    date       DATE NOT NULL,
    stock_id   VARCHAR(10) NOT NULL,
    name       VARCHAR(50) NOT NULL,
    -- name 值：Foreign_Dealer_Self / Foreign_Dealer / Investment_Trust / Dealer_self / Dealer_Hedging
    buy        BIGINT NOT NULL DEFAULT 0,
    sell       BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (date, stock_id, name)
);

-- TaiwanStockTotalInstitutionalInvestors
CREATE TABLE twse_total_institutional_investors (
    id   SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    name VARCHAR(50) NOT NULL,
    buy  BIGINT NOT NULL DEFAULT 0,
    sell BIGINT NOT NULL DEFAULT 0,
    UNIQUE (date, name)
);
```

### 融資融券

```sql
-- TaiwanStockMarginPurchaseShortSale
CREATE TABLE twse_stock_margin (
    id                              SERIAL PRIMARY KEY,
    date                            DATE NOT NULL,
    stock_id                        VARCHAR(10) NOT NULL,
    MarginPurchaseBuy               BIGINT DEFAULT 0,
    MarginPurchaseSell              BIGINT DEFAULT 0,
    MarginPurchaseCashRepayment     BIGINT DEFAULT 0,
    MarginPurchaseTodayBalance      BIGINT DEFAULT 0,
    MarginPurchaseYesterdayBalance  BIGINT DEFAULT 0,
    MarginPurchaseLimit             BIGINT DEFAULT 0,
    ShortSaleBuy                    BIGINT DEFAULT 0,
    ShortSaleSell                   BIGINT DEFAULT 0,
    ShortSaleCashRepayment          BIGINT DEFAULT 0,
    ShortSaleTodayBalance           BIGINT DEFAULT 0,
    ShortSaleYesterdayBalance       BIGINT DEFAULT 0,
    ShortSaleLimit                  BIGINT DEFAULT 0,
    OffsetLoanAndShort              BIGINT DEFAULT 0,
    UNIQUE (date, stock_id)
);

-- TaiwanStockTotalMarginPurchaseShortSale
CREATE TABLE twse_total_margin (
    id           SERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    name         VARCHAR(30) NOT NULL,
    -- name 值：MarginPurchase / ShortSale / MarginPurchaseMoney
    buy          BIGINT DEFAULT 0,
    sell         BIGINT DEFAULT 0,
    TodayBalance BIGINT DEFAULT 0,
    YesBalance   BIGINT DEFAULT 0,
    Return       BIGINT DEFAULT 0,
    UNIQUE (date, name)
);
```

---

## 資料流

```
Router 收到請求 (date, stock_id?)
  → Service 查 DB
  → DB hit  → 直接回傳
  → DB miss → TWSEClient.fetch_*()
            → 解析 JSON
            → repository.save()
            → 回傳資料
```

所有 endpoint 支援 `?force_refresh=true` 繞過 DB cache。

**Eager compute 預留介面**：

```python
async def ingest_daily(date: str):
    raw = await client.fetch_*(date)
    await repo.save(raw)
    await indicators_pipeline.compute(date)  # 第三批實作，現在是 no-op
```

---

## API Endpoints

```
# 三大法人（現有，重構加 DB）
GET /api/v1/chip/summary?date=YYYYMMDD
GET /api/v1/chip/stocks?date=YYYYMMDD
GET /api/v1/chip/stock/{stock_id}?date=YYYYMMDD

# 融資融券（新增）
GET /api/v1/margin/summary?date=YYYYMMDD
GET /api/v1/margin/stock/{stock_id}?date=YYYYMMDD
GET /api/v1/margin/stock/{stock_id}/history?start_date=YYYYMMDD&end_date=YYYYMMDD
```

Response 欄位對齊 FinMind schema，例如個股融資融券：

```json
{
  "date": "2026-03-28",
  "stock_id": "2330",
  "MarginPurchaseTodayBalance": 12345,
  "MarginPurchaseLimit": 50000,
  "ShortSaleTodayBalance": 678,
  "ShortSaleLimit": 10000,
  "OffsetLoanAndShort": 100
}
```

---

## 測試策略

| 層級 | 內容 |
|------|------|
| Parsing | JSON → schema 正確轉換（MI_MARGN 原始格式 → `TwseStockMargin`） |
| Service | DB cache hit/miss 邏輯；miss 時呼叫 client，hit 時不呼叫 |
| Router | HTTP endpoint 整合；200 + 正確欄位；404 無資料日期 |

- **pytest + pytest-asyncio**（asyncio_mode = "auto"）
- **Test DB**：aiosqlite in-memory
- **HTTP mock**：pytest-httpx

---

## 新增依賴

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.28.1",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "aiosqlite>=0.20",
    "pydantic-settings>=2.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.35",
]
```

---

## 未納入範圍（明確排除）

- 分點資訊（TaiwanStockTradingDailyReport 等）：爬蟲難度過高
- 上櫃（TPEx）資料
- 股東持股分級表（集保結算所，週更，另外規劃）
- 大盤融資維持率（FinMind 付費資料，可直接爬 TWSE，待第二批評估）
