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
