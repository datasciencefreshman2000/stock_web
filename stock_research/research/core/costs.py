"""台股交易成本模型。

這是你相對於通用回測套件的優勢——多數開源框架的台股成本是錯的。
數字與 backend/services/fees.py 保持一致。
"""

from dataclasses import dataclass

BROKER_FEE_RATE = 0.001425
BROKER_DISCOUNT = 0.6          # 券商折讓，6 折
MINIMUM_FEE = 1                # 最低手續費 1 元
TAX_RATE_STOCK = 0.003         # 一般股票證交稅 0.3%
TAX_RATE_ETF = 0.001           # ETF 證交稅 0.1%


def buy_fee(price: float, qty: float) -> int:
    return max(int(price * qty * BROKER_FEE_RATE * BROKER_DISCOUNT), MINIMUM_FEE)


def sell_fee(price: float, qty: float) -> int:
    return max(int(price * qty * BROKER_FEE_RATE * BROKER_DISCOUNT), MINIMUM_FEE)


def sell_tax(price: float, qty: float, is_etf: bool = False) -> int:
    rate = TAX_RATE_ETF if is_etf else TAX_RATE_STOCK
    return int(price * qty * rate)


@dataclass(frozen=True)
class RoundTripCost:
    """一趟來回（買進 + 賣出）的成本，以「佔本金的比例」表示。

    忽略最低手續費 1 元的影響（只在極小額交易才有差別），
    因此可以直接用比例做向量化計算。
    """

    buy_rate: float
    sell_rate: float

    @property
    def total(self) -> float:
        return self.buy_rate + self.sell_rate

    def net_return(self, gross_return: float) -> float:
        """把毛報酬換成扣掉來回成本後的淨報酬。"""
        return gross_return - self.total


def round_trip_cost(is_etf: bool = False, discount: float = BROKER_DISCOUNT) -> RoundTripCost:
    fee = BROKER_FEE_RATE * discount
    tax = TAX_RATE_ETF if is_etf else TAX_RATE_STOCK
    return RoundTripCost(buy_rate=fee, sell_rate=fee + tax)


# 常用常數：一般股票來回約 0.471%
STOCK_ROUND_TRIP = round_trip_cost(is_etf=False).total
ETF_ROUND_TRIP = round_trip_cost(is_etf=True).total


def annual_cost_drag(trades_per_year: float, is_etf: bool = False) -> float:
    """一年進出 N 趟的年化成本拖累。

    這個數字通常比人們想像的大很多——每週換股就要先賺 24.5% 才回本。
    """
    return round_trip_cost(is_etf).total * trades_per_year
