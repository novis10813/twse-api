"""Unit tests for MI_MARGN JSON parsing logic."""
from unittest.mock import MagicMock
from app.services.margin import MarginService


def make_mock_margin_response():
    """
    MI_MARGN response structure:
    data0 = individual stocks
    data1 = market totals (3 rows: 融資/融券/融資金額)

    data0 column indices:
    [0] 股票代號
    [1] 股票名稱
    [2] 融資-買進(張)      → MarginPurchaseBuy
    [3] 融資-賣出(張)      → MarginPurchaseSell
    [4] 融資-現金償還(張)  → MarginPurchaseCashRepayment
    [5] 融資-前日餘額(張)  → MarginPurchaseYesterdayBalance
    [6] 融資-今日餘額(張)  → MarginPurchaseTodayBalance
    [7] 融資-限額(千張)    → MarginPurchaseLimit
    [8] 融券-賣出(張)      → ShortSaleSell
    [9] 融券-買進(張)      → ShortSaleBuy
    [10] 融券-現金償還(張) → ShortSaleCashRepayment
    [11] 融券-前日餘額(張) → ShortSaleYesterdayBalance
    [12] 融券-今日餘額(張) → ShortSaleTodayBalance
    [13] 融券-限額(千張)   → ShortSaleLimit
    [14] 資券互抵(張)      → OffsetLoanAndShort
    """
    return {
        "stat": "OK",
        "date": "20260328",
        "data0": [
            ["2330", "台積電", "1,200", "800", "50", "10,000", "10,350", "100",
             "300", "100", "20", "500", "680", "50", "30"],
            ["2317", "鴻海", "500", "300", "10", "3,000", "3,190", "50",
             "100", "50", "5", "200", "245", "20", "10"],
        ],
        "data1": [
            ["融資(借錢買)", "100,000", "80,000", "5,000", "900,000", "915,000", "1,000,000"],
            ["融券(借券賣)", "20,000", "10,000", "2,000", "80,000", "88,000", "200,000"],
            ["融資金額(仟元)", "500,000", "400,000", "25,000", "4,000,000", "4,075,000", "5,000,000"],
        ],
    }


async def test_parse_stock_margin_count():
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_stock_margin("20260328", make_mock_margin_response())
    assert len(rows) == 2


async def test_parse_stock_margin_fields():
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_stock_margin("20260328", make_mock_margin_response())
    tsmc = next(r for r in rows if r["stock_id"] == "2330")
    assert tsmc["MarginPurchaseBuy"] == 1200
    assert tsmc["MarginPurchaseSell"] == 800
    assert tsmc["MarginPurchaseTodayBalance"] == 10350
    assert tsmc["MarginPurchaseYesterdayBalance"] == 10000
    assert tsmc["ShortSaleSell"] == 300
    assert tsmc["ShortSaleBuy"] == 100
    assert tsmc["ShortSaleTodayBalance"] == 680
    assert tsmc["OffsetLoanAndShort"] == 30


async def test_parse_total_margin_count():
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_total_margin("20260328", make_mock_margin_response())
    assert len(rows) == 3
    names = {r["name"] for r in rows}
    assert names == {"MarginPurchase", "ShortSale", "MarginPurchaseMoney"}


async def test_parse_total_margin_balance():
    service = MarginService(session=MagicMock(), client=MagicMock())
    rows = service._parse_total_margin("20260328", make_mock_margin_response())
    margin = next(r for r in rows if r["name"] == "MarginPurchase")
    assert margin["TodayBalance"] == 915000
    assert margin["YesBalance"] == 900000
    assert margin["Return"] == 5000
