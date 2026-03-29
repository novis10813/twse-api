"""
Data source Protocols (Ports) — 與實作無關的介面定義。
LendingSource / ShortSaleSource / DispositionSource 三個 Protocol，
TWSEPlaywrightClient 和 FinMindClient 都要實作這些介面。
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class LendingSource(Protocol):
    async def fetch_securities_lending(self, date_str: str) -> list[dict]:
        """回傳該日借券成交明細，list of dict。date_str 格式 YYYYMMDD。"""
        ...


@runtime_checkable
class ShortSaleSource(Protocol):
    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]:
        """回傳該日信用額度總量管制，list of dict。date_str 格式 YYYYMMDD。"""
        ...


@runtime_checkable
class DispositionSource(Protocol):
    async def fetch_disposition(self, date_str: str) -> list[dict]:
        """回傳該日處置有價證券公告，list of dict。date_str 格式 YYYYMMDD。"""
        ...
