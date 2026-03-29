# twse-api 第二批：外資持股比例（MI_QFIIS）設計文件

**日期**：2026-03-29
**範圍**：第二批實作 — TaiwanStockShareholding（MI_QFIIS）

---

## 背景

第一批完成了三大法人（T86/BFI82U）與融資融券（MI_MARGN）的 DB caching 架構。第二批原規劃包含：

| Dataset | 狀態 |
|---|---|
| TaiwanStockShareholding（MI_QFIIS） | **本次實作** |
| TaiwanStockSecuritiesLending（TWT49U） | TODO — TWSE 無公開 API，疑似需填表單或反爬蟲處理，待研究 |
| TaiwanDailyShortSaleBalances（TWTAUU） | 跳過 — 融券限額（ShortSaleLimit）已涵蓋於第一批 StockMargin |
| TaiwanStockDispositionSecuritiesPeriod（TWTBNU） | 跳過 — API 僅返回當前清單，無歷史查詢，待 Phase 4/5 排程機制後再做 |

本次只實作 **MI_QFIIS**。

---

## TWSE 資料來源

**Endpoint：**
```
GET https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?response=json&date={YYYYMMDD}&selectType=ALLBUT0999
```

- `selectType=ALLBUT0999`：排除基金/ETF 代碼（0999 前綴），只取個股
- 需傳入有效交易日（非假日、非週末）
- 每日約 948 筆

**Response 結構：**
```json
{
  "stat": "OK",
  "date": "20260328",
  "fields": ["證券代號", "證券名稱", "發行股數", "..."],
  "data": [["1101", "台泥", "5,575,682,340", "1,027,932,760", "18.44", "..."], ...],
  "total": 948
}
```

**欄位對應（7 欄）：**

| index | TWSE 欄位 | DB 欄位 | 型別 |
|---|---|---|---|
| 0 | 證券代號 | stock_id | VARCHAR(10) |
| 1 | 證券名稱 | （略） | — |
| 2 | 發行股數 | NumberOfSharesIssued | BIGINT |
| 3 | 外資及陸資(不含外資自營商)-持有股數 | ForeignInvestmentSharesWithoutDealers | BIGINT |
| 4 | 外資及陸資(不含外資自營商)-持股比例(%) | ForeignInvestmentSharesWithoutDealersRatio | NUMERIC(10,4) |
| 5 | 外資及陸資-持有股數 | ForeignInvestmentShares | BIGINT |
| 6 | 外資及陸資-持股比例(%) | ForeignInvestmentSharesRatio | NUMERIC(10,4) |

---

## DB Schema

```sql
CREATE TABLE twse_stock_shareholding (
    id                                          SERIAL PRIMARY KEY,
    date                                        DATE NOT NULL,
    stock_id                                    VARCHAR(10) NOT NULL,
    NumberOfSharesIssued                        BIGINT NOT NULL DEFAULT 0,
    ForeignInvestmentShares                     BIGINT NOT NULL DEFAULT 0,
    ForeignInvestmentSharesRatio                NUMERIC(10,4) NOT NULL DEFAULT 0,
    ForeignInvestmentSharesWithoutDealers       BIGINT NOT NULL DEFAULT 0,
    ForeignInvestmentSharesWithoutDealersRatio  NUMERIC(10,4) NOT NULL DEFAULT 0,
    created_at                                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (date, stock_id)
);
```

**設計決策：** 比例欄位使用 `NUMERIC(10,4)` 儲存（如 `18.4400`），對齊 FinMind 格式，支援數值查詢（> 30%、排序等）。SQLite 測試環境用 `Float` 替代。

---

## 架構

與第一批相同的分層模式：

```
app/
├── db/
│   ├── models.py          # 新增 StockShareholding ORM model
│   └── repository.py      # 新增 4 個 shareholding 方法
├── services/
│   ├── twse_client.py     # 新增 fetch_shareholding_data()
│   └── shareholding.py    # 新增 ShareholdingService
├── schemas/
│   └── shareholding.py    # 新增 Pydantic schemas
└── routers/
    └── shareholding.py    # 新增 3 個 endpoints
```

---

## Services

### twse_client.py 新增

```python
async def fetch_shareholding_data(self, date_str: str) -> dict:
    """MI_QFIIS — 外資持股比例"""
    # GET /rwd/zh/fund/MI_QFIIS?response=json&date={date}&selectType=ALLBUT0999
```

### app/services/shareholding.py

**DB-first cache 模式（與 chip/margin 一致）：**

```
get_stock_shareholding(date_str, stock_id, force_refresh)
  → DB hit: 直接回傳
  → DB miss: _ingest_shareholding(date_str) → 回傳

get_all_stocks_shareholding(date_str, force_refresh)
  → DB hit: 直接回傳
  → DB miss: _ingest_shareholding(date_str) → 回傳

get_stock_shareholding_history(stock_id, start_date, end_date)
  → DB only，不自動補爬
```

**Parser：**
- `_parse_shareholding(date_str, data)` — 解析 7 欄 row
- `_float()` helper — `"18.44"` → `18.44`（處理千分位逗號 + strip）
- 短 row（< 7 欄）略過
- `_ingest_shareholding(date_str)` — fetch → parse → upsert → `session.flush()`

---

## Repository 新增方法

```python
async def upsert_stock_shareholding(rows: list[dict]) -> None
async def get_stock_shareholding(date_str: str, stock_id: str) -> Optional[StockShareholding]
async def get_all_stocks_shareholding(date_str: str) -> list[StockShareholding]
async def get_stock_shareholding_history(stock_id: str, start_date: str, end_date: str) -> list[StockShareholding]
```

upsert 沿用第一批的 select+update 模式（SQLite/PostgreSQL 相容）。

---

## Schemas

```python
class StockShareholdingResponse(BaseModel):
    date: str
    stock_id: str
    NumberOfSharesIssued: int = 0
    ForeignInvestmentShares: int = 0
    ForeignInvestmentSharesRatio: float = 0.0
    ForeignInvestmentSharesWithoutDealers: int = 0
    ForeignInvestmentSharesWithoutDealersRatio: float = 0.0
```

---

## Router Endpoints

**Prefix：`/api/v1/shareholding`**

| Method | Path | 說明 |
|---|---|---|
| GET | `/stocks` | 全市場外資持股列表（某日） |
| GET | `/stock/{stock_id}` | 個股外資持股 |
| GET | `/stock/{stock_id}/history` | 個股歷史（DB only） |

全部支援：
- `?date=YYYYMMDD`（預設當日）
- `?force_refresh=true`（強制重爬）
- `history` endpoint 用 `?start_date=` + `?end_date=`

---

## Tests

| 測試檔案 | 測試內容 |
|---|---|
| `tests/test_shareholding_parsing.py` | 欄位對應正確、比例為 float、短 row 略過（3 tests） |
| `tests/test_shareholding_service.py` | DB hit/miss、unknown stock → None、history empty（4 tests） |
| `tests/test_shareholding_router.py` | 3 endpoints 的 200/404 case（4 tests） |

`conftest.py` 新增 `SqliteStockShareholding`（NUMERIC 欄位改用 SQLite `Float`）。

---

## File Map

| 動作 | 檔案 |
|---|---|
| 修改 | `app/db/models.py` |
| 修改 | `app/db/repository.py` |
| 修改 | `app/services/twse_client.py` |
| 新增 | `app/services/shareholding.py` |
| 新增 | `app/schemas/shareholding.py` |
| 新增 | `app/routers/shareholding.py` |
| 修改 | `app/main.py` |
| 修改 | `tests/conftest.py` |
| 新增 | `tests/test_shareholding_parsing.py` |
| 新增 | `tests/test_shareholding_service.py` |
| 新增 | `tests/test_shareholding_router.py` |
