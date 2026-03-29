"""
FinMind Adapter — stub，未來實作。
切換 DATA_SOURCE_ADAPTER=finmind 時使用。
"""
from typing import Optional


class FinMindClient:
    """
    FinMind API adapter，實作 LendingSource / ShortSaleSource / DispositionSource。
    目前為 stub，所有方法回傳空 list。
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token

    async def fetch_securities_lending(self, date_str: str) -> list[dict]:
        raise NotImplementedError(f"FinMind adapter not yet implemented (date={date_str})")

    async def fetch_short_sale_balances(self, date_str: str) -> list[dict]:
        raise NotImplementedError(f"FinMind adapter not yet implemented (date={date_str})")

    async def fetch_disposition(self, date_str: str) -> list[dict]:
        raise NotImplementedError(f"FinMind adapter not yet implemented (date={date_str})")


_finmind_client: Optional[FinMindClient] = None


def get_finmind_client() -> FinMindClient:
    global _finmind_client
    if _finmind_client is None:
        _finmind_client = FinMindClient()
    return _finmind_client
