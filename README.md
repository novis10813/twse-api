# twse-api

REST API service for fetching TWSE (Taiwan Stock Exchange) chip data.

## Features

- 三大法人買賣金額統計 (Institutional Investors Summary)
- 個股三大法人買賣超 (Stock Chip Data)
- 個股籌碼詳情查詢
- 個股籌碼趨勢分析

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/chip/summary` | 三大法人買賣金額統計 |
| GET | `/api/v1/chip/stocks` | 個股三大法人買賣超列表 |
| GET | `/api/v1/chip/stock/{code}` | 個股籌碼詳情 |

### Query Parameters

- `date`: 日期 (YYYYMMDD format, default: today)

## Development

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker

```bash
# Build
docker build -t twse-api .

# Run
docker run -p 8000:8000 twse-api
```

## GHCR Image

```bash
docker pull ghcr.io/novis10813/twse-api:latest
```
