"""Money in the user's own currency, picked by the country of the departure city.

Every sum is kept in roubles (Aviasales prices, the budget levels) and converted only where it is shown, at the
Central Bank of Russia rates of 24 October 2026. Aviasales' own prices in these currencies match them within 1%.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

CurrencyCode = Literal["RUB", "KZT", "BYN", "UZS", "KGS", "USD", "EUR"]


@dataclass(frozen=True)
class Currency:
    code: CurrencyCode
    sign: str
    name: str  # for the model: «тенге»
    per_rub: float  # how much of it one rouble buys
    glyph: str  # repeated for a price level (₸₸₸); $ where the sign is a word

    def from_rub(self, rub: float) -> int:
        return round(rub * self.per_rub)

    def to_rub(self, amount: float) -> int:
        return round(amount / self.per_rub)

    def amount(self, value: int) -> str:
        """An amount already in this currency: 500000 → «500 000 ₸»."""
        return f"{value:,}\u00a0{self.sign}".replace(",", "\u00a0")

    def format(self, rub: int) -> str:
        return self.amount(self.from_rub(rub))

    def view(self) -> dict:
        return {"code": self.code, "sign": self.sign, "glyph": self.glyph, "per_rub": self.per_rub}


RUB = Currency("RUB", "₽", "рубли", 1.0, "₽")
CURRENCIES: dict[str, Currency] = {
    c.code: c
    for c in (
        RUB,
        Currency("KZT", "₸", "тенге", 5.561828, "₸"),
        Currency("BYN", "Br", "белорусские рубли", 0.036579, "$"),
        Currency("UZS", "сум", "сумы", 147.493713, "$"),
        Currency("KGS", "сом", "сомы", 1.085805, "$"),
        Currency("USD", "$", "доллары США", 0.012416, "$"),
        Currency("EUR", "€", "евро", 0.011081, "€"),
    )
}
BY_COUNTRY = {
    "Россия": "RUB",
    "Казахстан": "KZT",
    "Беларусь": "BYN",
    "Узбекистан": "UZS",
    "Кыргызстан": "KGS",
}

# The currency of the request being answered, set next to current_origin by the chat service.
current_currency: ContextVar[Currency] = ContextVar("current_currency", default=RUB)


def currency_of(country: str | None) -> Currency:
    """Roubles when the city is unknown, the local currency for ours, dollars for the rest of the world."""
    return CURRENCIES[BY_COUNTRY.get(country, "USD")] if country else RUB


def money(rub: int) -> str:
    return current_currency.get().format(rub)
