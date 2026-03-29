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
