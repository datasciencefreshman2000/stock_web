from services.constants import ETF_LIST

BROKER_DISCOUNT = 0.6
MINIMUM_FEE = 1


def calc_tw_fee(price: float, qty: float) -> int:
    fee = price * qty * 0.001425 * BROKER_DISCOUNT
    return max(int(fee), MINIMUM_FEE)


def calc_tw_tax(price: float, qty: float, ticker: str, is_etf: bool | None = None) -> int:
    """證交稅。ETF 0.1%，一般股票 0.3%。

    is_etf 由呼叫端傳入（來自 tickers 主檔），未傳時退回硬編清單。
    """
    etf = (ticker in ETF_LIST) if is_etf is None else is_etf
    rate = 0.001 if etf else 0.003
    return int(price * qty * rate)
