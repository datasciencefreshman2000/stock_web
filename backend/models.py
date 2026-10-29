from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Currency = Literal["TWD", "USD"]
Account = Literal["台股", "美股", "爸媽美股"]


class WriteRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, str_strip_whitespace=True)
    operation_id: UUID = Field(default_factory=uuid4)
    expected_updated_at: str | None = None


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


class TradeCreate(WriteRequest):
    account: Account
    ticker: str = Field(min_length=1)
    date: Date
    buy_qty: float | None = Field(default=None, ge=0)
    sell_qty: float | None = Field(default=None, ge=0)
    price: float = Field(gt=0)
    fee: float | None = Field(default=None, ge=0)
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


class ManualValueUpdate(WriteRequest):
    key: str = Field(min_length=1)
    value: float
    reason: str = "校正投入金額"


class CashUpdate(WriteRequest):
    amount: float
    currency: Currency | None = None
    reason: str = "餘額校正"


class CashCreate(WriteRequest):
    name: str = Field(min_length=1)
    account: str = ""
    category: str = "現金"
    currency: Currency = "TWD"
    amount: float = 0


class ManualInvestmentCreate(WriteRequest):
    name: str = Field(min_length=1)
    asset_type: str = "其他"
    cost: float = Field(ge=0)
    cash_amount: float = Field(default=0, ge=0)
    value: float = Field(ge=0)
    currency: Currency = "TWD"


class ManualInvestmentUpdate(WriteRequest):
    name: str | None = None
    asset_type: str | None = None
    cost: float | None = Field(default=None, ge=0)
    cash_amount: float | None = Field(default=None, ge=0)
    value: float | None = Field(default=None, ge=0)
    currency: Currency | None = None


class ManualInvestmentBulkItem(ManualInvestmentCreate):
    # The containing bulk operation owns idempotency; don't generate a fresh ID
    # for each item during request validation on every retry.
    operation_id: UUID | None = None
    id: str = Field(min_length=1)


class ManualInvestmentBulkUpdate(WriteRequest):
    investments: list[ManualInvestmentBulkItem] = Field(min_length=1)


class CapitalMovementCreate(WriteRequest):
    movement_date: Date
    from_bucket: str | None = None
    to_bucket: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: Currency = "TWD"
    to_amount: float | None = Field(default=None, gt=0)
    to_currency: Currency | None = None
    note: str = ""
    affects_balance: bool = True

    @model_validator(mode="after")
    def check_transfer(self):
        from services.accounts import ACCOUNT_CURRENCY, BUCKET_ALIASES
        self.from_bucket = BUCKET_ALIASES.get(self.from_bucket, self.from_bucket)
        self.to_bucket = BUCKET_ALIASES.get(self.to_bucket, self.to_bucket)
        source = ACCOUNT_CURRENCY.get(self.from_bucket)
        target = ACCOUNT_CURRENCY.get(self.to_bucket)
        if source and self.currency != source:
            raise ValueError(f"{self.from_bucket} 換出幣別必須為 {source}")
        destination_currency = self.to_currency or self.currency
        if self.to_bucket == "支出" and not self.from_bucket:
            raise ValueError("支出必須選擇付款帳戶")
        if target and destination_currency != target:
            raise ValueError(f"{self.to_bucket} 入帳幣別必須為 {target}，請填實際換入金額")
        if destination_currency != self.currency and self.to_amount is None:
            raise ValueError("跨幣別調動必須填寫實際換入金額")
        if self.from_bucket == self.to_bucket and self.currency == destination_currency:
            raise ValueError("來源與目的地不能是同一帳戶及幣別")
        if destination_currency == self.currency and self.to_amount is not None and self.to_amount != self.amount:
            raise ValueError("同幣別調動兩邊金額必須一致")
        return self


class CapitalMovementUpdate(CapitalMovementCreate):
    pass


class CreditCardPaymentCreate(WriteRequest):
    source_id: UUID
    source_name: str = Field(min_length=1)
    debt_id: UUID
    currency: Currency = 'TWD'
    amount: float = Field(gt=0)
    repayment_mode: Literal['all', 'partial'] = 'partial'
    movement_date: Date
    note: str = Field(default='', max_length=200)

    @model_validator(mode='after')
    def validate_payment(self):
        from services.dates import today
        from services.money import decimal
        if self.movement_date.isoformat() > today():
            raise ValueError('請填寫今天或之前的實際繳款日期。')
        amount = decimal(self.amount)
        if self.repayment_mode == 'partial' and amount != amount.quantize(decimal('0.01')):
            raise ValueError('繳款金額最多兩位小數。')
        return self


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
