"""models.py"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class PriceQuote:
    asset: str
    venue: str
    price: float
    symbol_used: str
    fetched_at: datetime

    @classmethod
    def now(cls, asset: str, venue: str, price: float, symbol_used: str) -> "PriceQuote":
        return cls(asset=asset, venue=venue, price=price, symbol_used=symbol_used,
                   fetched_at=datetime.now(timezone.utc))
