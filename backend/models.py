from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Account = Literal["台股", "美股", "爸媽美股", "x"]


class Trade(BaseModel):
    id: str | None = None
    account: Account
    ticker: str
    date: Date | None = None
    buy_qty: float | None = None
    sell_qty: float | None = None
    price: float
    fee: float = 0
    total: float | None = None
    note: str = ""
    created_at: datetime | None = None


class TradeCreate(BaseModel):
    account: Account
    ticker: str = Field(min_length=1)
    date: Date
    buy_qty: float | None = None
    sell_qty: float | None = None
    price: float = Field(gt=0)
    fee: float = 0
    note: str = ""

    @model_validator(mode="after")
    def validate_side(self) -> "TradeCreate":
        buy = self.buy_qty or 0
        sell = self.sell_qty or 0
        if buy <= 0 and sell <= 0:
            raise ValueError("Either buy_qty or sell_qty must be greater than zero.")
        if buy > 0 and sell > 0:
            raise ValueError("buy_qty and sell_qty cannot both be set.")
        return self

    @model_validator(mode="after")
    def normalize_ticker(self) -> "TradeCreate":
        self.ticker = self.ticker.strip().upper()
        return self


class Holding(BaseModel):
    ticker: str
    qty: float
    avg_price: float
    current_price: float | None = None
    cost: float
    market_value: float | None = None
    realized_pnl: float = 0
    pnl: float | None = None
    pnl_pct: float | None = None
    weight: float | None = None


class ManualValueUpdate(BaseModel):
    key: str = Field(min_length=1)
    value: float = Field(ge=0)


class CashUpdate(BaseModel):
    amount: float
    currency: str | None = None


class CashCreate(BaseModel):
    name: str = Field(min_length=1)
    account: str = "台股"
    category: str = "現金"
    currency: str = "USD"
    amount: float = 0


class ManualInvestmentCreate(BaseModel):
    name: str = Field(min_length=1)
    asset_type: Literal["台股", "美股", "其他"] = "其他"
    cost: float = Field(ge=0)
    value: float = Field(ge=0)
    currency: str = "TWD"


class ManualInvestmentUpdate(BaseModel):
    name: str | None = None
    asset_type: Literal["台股", "美股", "其他"] | None = None
    cost: float | None = Field(default=None, ge=0)
    value: float | None = Field(default=None, ge=0)
    currency: str | None = None
