"""
models.py
=========
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DecryptedCredential:
    """Solo existe en memoria, nunca se guarda así — ver store.py."""
    user_id: str
    exchange: str           # "binance" | "bybit" | "weex"
    label: str
    api_key: str
    api_secret: str
    testnet: bool
    permissions_verified: bool
    permissions_verified_at: datetime | None
    created_at: datetime
