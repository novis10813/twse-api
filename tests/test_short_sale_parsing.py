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
