from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class Trade(BaseModel):
    id: str | None = None
    account: str
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
    account: str
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


class TradeUpdate(TradeCreate):
    pass


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
    account: str = ""
    category: str = "現金"
    currency: str = "USD"
    amount: float = 0


class ManualInvestmentCreate(BaseModel):
    name: str = Field(min_length=1)
    asset_type: str = "其他"
    cost: float = Field(ge=0)
    cash_amount: float = Field(default=0, ge=0)
    value: float = Field(ge=0)
    currency: str = "TWD"


class ManualInvestmentUpdate(BaseModel):
    name: str | None = None
    asset_type: str | None = None
    cost: float | None = Field(default=None, ge=0)
    cash_amount: float | None = Field(default=None, ge=0)
    value: float | None = Field(default=None, ge=0)
    currency: str | None = None


class ManualInvestmentBulkItem(ManualInvestmentCreate):
    id: str = Field(min_length=1)


class ManualInvestmentBulkUpdate(BaseModel):
    investments: list[ManualInvestmentBulkItem] = Field(min_length=1)


class CapitalMovementCreate(BaseModel):
    movement_date: Date
    from_bucket: str | None = None
    to_bucket: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = "TWD"
    to_amount: float | None = Field(default=None, gt=0)
    to_currency: str | None = None
    note: str = ""


class CapitalMovementUpdate(CapitalMovementCreate):
    pass


class CapitalMovementOptionCreate(BaseModel):
    category: str = Field(min_length=1)
    label: str = Field(min_length=1)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class CorporateActionCreate(BaseModel):
    account: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    action_type: str = Field(pattern="^(split|reverse_split|cash_dividend|stock_dividend)$")
    ex_date: Date
    ratio: float | None = Field(default=None, gt=0)
    amount: float | None = None
    currency: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def validate_payload(self) -> "CorporateActionCreate":
        self.ticker = self.ticker.strip().upper()
        if self.action_type in {"split", "reverse_split", "stock_dividend"} and not self.ratio:
            raise ValueError("分割類事件必須提供 ratio（1 股變成幾股）")
        if self.action_type == "cash_dividend" and self.amount is None:
            raise ValueError("現金股利必須提供 amount（每股金額）")
        return self
