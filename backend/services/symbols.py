"""帳戶 + 代號 → 全域唯一 symbol。

price_cache / price_history / tickers / corporate_actions 都以 symbol 為主鍵，
台股加 'TW:' 前綴避免與美股代號撞號。
"""

from services.constants import TW_ACCOUNTS


def is_tw_account(account: str) -> bool:
    return account in TW_ACCOUNTS


def symbol_for(account: str, ticker: str) -> str:
    normalized = (ticker or "").strip().upper()
    return f"TW:{normalized}" if is_tw_account(account) else normalized


def ticker_from_symbol(symbol: str) -> str:
    return symbol.split(":", 1)[1] if symbol.startswith("TW:") else symbol
