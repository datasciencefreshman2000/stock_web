from services.constants import ETF_LIST

BROKER_DISCOUNT = 0.6
MINIMUM_FEE = 1


def calc_tw_fee(price: float, qty: float) -> int:
    fee = price * qty * 0.001425 * BROKER_DISCOUNT
    return max(int(fee), MINIMUM_FEE)


def calc_tw_tax(price: float, qty: float, ticker: str) -> int:
    rate = 0.001 if ticker in ETF_LIST else 0.003
    return int(price * qty * rate)
