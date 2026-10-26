"""Exchange rates for any currency a price is found in: a taxi in baht, a visa in pounds.

The app keeps every sum in roubles (app.money). The Central Bank of Russia's daily rates cover 54 currencies;
they are read from the cbr-xml-daily.ru mirror of its official XML (cbr.ru itself refuses scripts) and kept
for 12 hours. When the source is down, the app's own fixed rates (app.money) still convert its 7 currencies.
"""

import asyncio
import logging
import time

import httpx

from app.money import CURRENCIES

log = logging.getLogger(__name__)

CBR_DAILY = "https://www.cbr-xml-daily.ru/daily_json.js"
TTL_S = 12 * 3600
RETRY_S = 600  # after a failed refresh, the old table serves this long before the next try


def _fixed(currency: str) -> float | None:
    """Roubles per unit from app.money: the fallback for its own currencies."""
    known = CURRENCIES.get(currency)
    return 1 / known.per_rub if known else None


class Rates:
    """Roubles per unit of each currency, refreshed lazily."""

    def __init__(self, client: httpx.AsyncClient | None = None, url: str = CBR_DAILY):
        self._client = client
        self._url = url
        self._table: dict[str, float] = {}
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def ensure(self) -> None:
        """The table fresh enough: fetched at most every 12 hours, and not hammered when the source is down."""
        if time.monotonic() < self._next:
            return
        async with self._lock:
            if time.monotonic() < self._next:
                return
            try:
                self._client = self._client or httpx.AsyncClient(timeout=10.0)
                response = await self._client.get(self._url)
                response.raise_for_status()
                valutes = response.json()["Valute"]
                self._table = {
                    code: float(v["Value"]) / float(v["Nominal"])
                    for code, v in valutes.items()
                    if v.get("Nominal")
                }
                self._table["RUB"] = 1.0
                self._next = time.monotonic() + TTL_S
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as problem:
                log.warning(
                    "Exchange rates unavailable (%s): the app's fixed rates serve", type(problem).__name__
                )
                self._next = time.monotonic() + RETRY_S

    def rub(self, amount: float, currency: str) -> int | None:
        """The amount in roubles from the last table, or the fixed rates; None for a currency neither knows."""
        rate = self._table.get(currency.upper()) or _fixed(currency.upper())
        return round(amount * rate) if rate else None

    async def to_rub(self, amount: float, currency: str) -> int | None:
        await self.ensure()
        return self.rub(amount, currency)


class FixedRates(Rates):
    """No network: the app's own 7 currencies only. Tests and a disabled setting use it."""

    def __init__(self):
        super().__init__(client=None, url="")
        self._next = float("inf")

    async def ensure(self) -> None:
        return None


_rates: Rates = FixedRates()


def configure(rates: Rates) -> None:
    global _rates
    _rates = rates


def rates() -> Rates:
    return _rates
