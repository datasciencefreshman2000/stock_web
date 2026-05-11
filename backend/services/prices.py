import asyncio
from datetime import datetime, timezone

import httpx
from fugle_marketdata import RestClient

from repositories.price_cache import list_price_cache, upsert_price_cache
from services.constants import TW_ACCOUNTS

PRICE_CACHE: dict[str, dict] = {}
RATE_CACHE: dict[str, float | str] = {}
PRICE_FETCH_STATE = {
    "in_progress": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_requested": 0,
    "last_fetched": 0,
    "last_cached": 0,
    "last_failed": 0,
    "last_missing": 0,
    "last_provider": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_price_status() -> None:
    PRICE_FETCH_STATE.update(
        {
            "in_progress": False,
            "last_started_at": None,
            "last_finished_at": None,
            "last_requested": 0,
            "last_fetched": 0,
            "last_cached": 0,
            "last_failed": 0,
            "last_missing": 0,
            "last_provider": None,
        }
    )


def is_tw_account(account: str) -> bool:
    return account in TW_ACCOUNTS


def get_price_symbol(ticker: str, account: str) -> str:
    normalized = ticker.strip().upper()
    if is_tw_account(account):
        return f"TW:{normalized}"
    return normalized


async def fetch_price(client: httpx.AsyncClient, ticker: str, symbol: str, api_key: str) -> tuple[str, float | None]:
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": api_key}
    try:
        response = await client.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get("c")
        return ticker, float(price) if price else None
    except Exception:
        return ticker, None


def fetch_fugle_price_sync(ticker: str, api_key: str) -> float | None:
    try:
        client = RestClient(api_key=api_key)
        stock = client.stock.intraday.quote(symbol=ticker)
        price = stock.get("lastPrice") or stock.get("closePrice") or stock.get("previousClose")
        return float(price) if price else None
    except Exception:
        return None


async def fetch_fugle_price(ticker: str, api_key: str) -> tuple[str, float | None]:
    price = await asyncio.to_thread(fetch_fugle_price_sync, ticker, api_key)
    return ticker, price


async def fetch_prices_batch(
    tickers: list[str],
    account: str,
    finnhub_key: str,
    refresh: bool = False,
    reset_state: bool = True,
    fugle_key: str = "",
    request_cache: dict[str, float | None] | None = None,
) -> dict[str, float | None]:
    if reset_state:
        reset_price_status()

    results: dict[str, float | None] = {}
    unique_tickers = sorted({ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()})
    to_fetch: list[tuple[str, str]] = []
    symbol_by_ticker = {ticker: get_price_symbol(ticker, account) for ticker in unique_tickers}
    db_cache = list_price_cache(list(symbol_by_ticker.values()))
    cached_count = 0
    request_cache = request_cache if request_cache is not None else {}

    for ticker in unique_tickers:
        symbol = symbol_by_ticker[ticker]
        cached = PRICE_CACHE.get(symbol)
        if symbol in request_cache:
            results[ticker] = request_cache[symbol]
            cached_count += 1
        elif cached and not refresh:
            results[ticker] = cached["price"]
            cached_count += 1
        elif db_cache.get(symbol) and not refresh:
            row = db_cache[symbol]
            price = float(row["price"]) if row.get("price") is not None else None
            results[ticker] = price
            cached_count += 1
            PRICE_CACHE[symbol] = {
                "ticker": ticker,
                "symbol": symbol,
                "account": row.get("account") or account,
                "price": price,
                "fetched_at": row.get("fetched_at"),
            }
        elif refresh:
            to_fetch.append((ticker, symbol))
        else:
            results[ticker] = None
            PRICE_FETCH_STATE["last_missing"] += 1

    PRICE_FETCH_STATE["in_progress"] = PRICE_FETCH_STATE["in_progress"] or bool(to_fetch)
    PRICE_FETCH_STATE["last_started_at"] = _now_iso() if to_fetch and not PRICE_FETCH_STATE["last_started_at"] else PRICE_FETCH_STATE["last_started_at"]
    PRICE_FETCH_STATE["last_requested"] += len(unique_tickers)
    PRICE_FETCH_STATE["last_cached"] += cached_count
    PRICE_FETCH_STATE["last_provider"] = "fugle" if is_tw_account(account) else "finnhub"

    if to_fetch:
        if is_tw_account(account):
            for ticker, symbol in to_fetch:
                _, price = await fetch_fugle_price(ticker, fugle_key)
                if price is None:
                    PRICE_FETCH_STATE["last_failed"] += 1
                    fallback = PRICE_CACHE.get(symbol) or db_cache.get(symbol)
                    results[ticker] = float(fallback["price"]) if fallback and fallback.get("price") is not None else None
                else:
                    results[ticker] = price
                    fetched_at = _now_iso()
                    PRICE_CACHE[symbol] = {
                        "ticker": ticker,
                        "symbol": symbol,
                        "account": account,
                        "price": price,
                        "currency": "TWD",
                        "fetched_at": fetched_at,
                    }
                    request_cache[symbol] = price
                    upsert_price_cache(
                        {
                            "symbol": symbol,
                            "ticker": ticker,
                            "account": account,
                            "price": price,
                            "currency": "TWD",
                            "fetched_at": fetched_at,
                            "source": "fugle",
                        }
                    )
                    PRICE_FETCH_STATE["last_fetched"] += 1
                await asyncio.sleep(0.1)
        else:
            async with httpx.AsyncClient() as client:
                for ticker, symbol in to_fetch:
                    _, price = await fetch_price(client, ticker, symbol, finnhub_key)
                    if price is None:
                        PRICE_FETCH_STATE["last_failed"] += 1
                        fallback = PRICE_CACHE.get(symbol) or db_cache.get(symbol)
                        results[ticker] = float(fallback["price"]) if fallback and fallback.get("price") is not None else None
                    else:
                        results[ticker] = price
                        fetched_at = _now_iso()
                        PRICE_CACHE[symbol] = {
                            "ticker": ticker,
                            "symbol": symbol,
                            "account": account,
                            "price": price,
                            "currency": "USD",
                            "fetched_at": fetched_at,
                        }
                        request_cache[symbol] = price
                        upsert_price_cache(
                            {
                                "symbol": symbol,
                                "ticker": ticker,
                                "account": account,
                                "price": price,
                                "currency": "USD",
                                "fetched_at": fetched_at,
                                "source": "finnhub",
                            }
                        )
                        PRICE_FETCH_STATE["last_fetched"] += 1
                    await asyncio.sleep(0.1)

        PRICE_FETCH_STATE["in_progress"] = False
        PRICE_FETCH_STATE["last_finished_at"] = _now_iso()

    return results


async def fetch_usd_rate(api_key: str, refresh: bool = False) -> float:
    if RATE_CACHE.get("usd_twd") and not refresh:
        return float(RATE_CACHE["usd_twd"])
    if not refresh:
        return 31.316

    url = "https://finnhub.io/api/v1/forex/rates"
    params = {"base": "USD", "token": api_key}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            rate = float(data["quote"].get("TWD", 31.316))
            RATE_CACHE["usd_twd"] = rate
            RATE_CACHE["fetched_at"] = _now_iso()
            return rate
        except Exception:
            return 31.316


def get_price_status() -> dict:
    return {
        **PRICE_FETCH_STATE,
        "cache_size": len(PRICE_CACHE),
        "cached_symbols": sorted(PRICE_CACHE.keys()),
        "usd_rate_cached": bool(RATE_CACHE.get("usd_twd")),
        "usd_rate_fetched_at": RATE_CACHE.get("fetched_at"),
    }
