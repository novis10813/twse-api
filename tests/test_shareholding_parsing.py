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
