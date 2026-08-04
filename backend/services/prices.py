"""報價、匯率、公司名稱。

A2 修正：原本的 PRICE_CACHE / RATE_CACHE / COMPANY_NAME_CACHE 是 module-level dict，
在 Vercel serverless 上每個 instance 獨立且會被回收，實際命中率遠低於預期，
統計數字在多 instance 下也沒有意義。

現在的原則：
- 跨請求的真實來源一律是資料庫（price_cache / fx_rates / tickers）。
- 記憶體只做「同一次請求內」的 memo，用 PriceContext 明確傳遞。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from fugle_marketdata import RestClient

from repositories.fx_rates import get_fx_rate, upsert_fx_rate
from repositories.price_cache import list_price_cache, upsert_price_cache_rows
from repositories.tickers import list_tickers, upsert_tickers
from services.symbols import is_tw_account, symbol_for

PRICE_REFRESH_TTL_SECONDS = 10 * 60
RATE_REFRESH_TTL_SECONDS = 60 * 60
DEFAULT_USD_TWD = 31.316


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_fresh(fetched_at: object, ttl_seconds: int) -> bool:
    parsed = _parse_datetime(fetched_at)
    if not parsed:
        return False
    return (datetime.now(timezone.utc) - parsed).total_seconds() <= ttl_seconds


@dataclass
class PriceContext:
    """單一請求 / 單一排程執行的作用域。用完即丟，不跨請求存活。"""

    prices: dict[str, float | None] = field(default_factory=dict)
    db_cache: dict[str, dict] = field(default_factory=dict)
    stats: dict = field(
        default_factory=lambda: {
            "requested": 0,
            "fetched": 0,
            "cached": 0,
            "failed": 0,
            "missing": 0,
            "providers": [],
            "started_at": None,
            "finished_at": None,
        }
    )

    def preload(self, symbols: list[str]) -> None:
        missing = [s for s in symbols if s not in self.db_cache]
        if missing:
            self.db_cache.update(list_price_cache(missing))


# --------------------------------------------------------------------------
# 報價
# --------------------------------------------------------------------------


async def fetch_finnhub_price(client: httpx.AsyncClient, ticker: str, api_key: str) -> tuple[str, float | None]:
    try:
        response = await client.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": api_key},
            timeout=5,
        )
        response.raise_for_status()
        price = response.json().get("c")
        return ticker, float(price) if price else None
    except Exception:
        return ticker, None


def _fugle_price_sync(ticker: str, api_key: str) -> float | None:
    try:
        client = RestClient(api_key=api_key)
        quote = client.stock.intraday.quote(symbol=ticker)
        price = quote.get("lastPrice") or quote.get("closePrice") or quote.get("previousClose")
        return float(price) if price else None
    except Exception:
        return None


def _fugle_ticker_info_sync(ticker: str, api_key: str) -> dict | None:
    try:
        client = RestClient(api_key=api_key)
        return client.stock.intraday.ticker(symbol=ticker)
    except Exception:
        return None


async def _fugle_prices(tickers: list[str], api_key: str) -> dict[str, float | None]:
    semaphore = asyncio.Semaphore(5)

    async def one(ticker: str) -> tuple[str, float | None]:
        async with semaphore:
            return ticker, await asyncio.to_thread(_fugle_price_sync, ticker, api_key)

    return dict(await asyncio.gather(*(one(t) for t in tickers)))


async def _finnhub_prices(tickers: list[str], api_key: str) -> dict[str, float | None]:
    semaphore = asyncio.Semaphore(8)

    async def one(client: httpx.AsyncClient, ticker: str) -> tuple[str, float | None]:
        async with semaphore:
            return await fetch_finnhub_price(client, ticker, api_key)

    async with httpx.AsyncClient() as client:
        return dict(await asyncio.gather(*(one(client, t) for t in tickers)))


async def fetch_prices_batch(
    tickers: list[str],
    account: str,
    finnhub_key: str,
    refresh: bool = False,
    fugle_key: str = "",
    context: PriceContext | None = None,
) -> dict[str, float | None]:
    """回傳 {ticker: price}。refresh=False 時只讀資料庫快取，不打外部 API。"""
    context = context or PriceContext()
    unique = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not unique:
        return {}

    symbol_by_ticker = {t: symbol_for(account, t) for t in unique}
    context.preload(list(symbol_by_ticker.values()))
    context.stats["requested"] += len(unique)

    results: dict[str, float | None] = {}
    to_fetch: list[str] = []

    for ticker in unique:
        symbol = symbol_by_ticker[ticker]
        if symbol in context.prices:
            results[ticker] = context.prices[symbol]
            context.stats["cached"] += 1
            continue

        row = context.db_cache.get(symbol)
        row_price = float(row["price"]) if row and row.get("price") is not None else None

        if row and (not refresh or _is_fresh(row.get("fetched_at"), PRICE_REFRESH_TTL_SECONDS)):
            results[ticker] = row_price
            context.prices[symbol] = row_price
            context.stats["cached"] += 1
        elif refresh:
            to_fetch.append(ticker)
        else:
            results[ticker] = None
            context.stats["missing"] += 1

    if not to_fetch:
        return results

    context.stats["started_at"] = context.stats["started_at"] or _now_iso()
    tw = is_tw_account(account)
    provider = "fugle" if tw else "finnhub"
    if provider not in context.stats["providers"]:
        context.stats["providers"].append(provider)

    fetched = (
        await _fugle_prices(to_fetch, fugle_key)
        if tw
        else await _finnhub_prices(to_fetch, finnhub_key)
    )

    currency = "TWD" if tw else "USD"
    rows = []
    for ticker in to_fetch:
        symbol = symbol_by_ticker[ticker]
        price = fetched.get(ticker)
        if price is None:
            context.stats["failed"] += 1
            stale = context.db_cache.get(symbol)
            results[ticker] = float(stale["price"]) if stale and stale.get("price") is not None else None
            continue

        results[ticker] = price
        context.prices[symbol] = price
        context.stats["fetched"] += 1
        rows.append(
            {
                "symbol": symbol,
                "ticker": ticker,
                "account": account,
                "price": price,
                "currency": currency,
                "fetched_at": _now_iso(),
                "source": provider,
            }
        )

    upsert_price_cache_rows(rows)
    context.stats["finished_at"] = _now_iso()
    return results


# --------------------------------------------------------------------------
# 公司名稱（改存 tickers 主檔，不再用記憶體 dict）
# --------------------------------------------------------------------------


async def resolve_company_names(
    account: str,
    tickers: list[str],
    fugle_key: str = "",
) -> dict[str, str | None]:
    unique = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not unique:
        return {}

    symbol_by_ticker = {t: symbol_for(account, t) for t in unique}
    known = list_tickers(list(symbol_by_ticker.values()))
    names: dict[str, str | None] = {
        t: (known.get(s) or {}).get("name") for t, s in symbol_by_ticker.items()
    }

    missing = [t for t, name in names.items() if not name]
    if not missing or not is_tw_account(account) or not fugle_key:
        return names

    semaphore = asyncio.Semaphore(5)

    async def one(ticker: str) -> tuple[str, dict | None]:
        async with semaphore:
            return ticker, await asyncio.to_thread(_fugle_ticker_info_sync, ticker, fugle_key)

    fetched = dict(await asyncio.gather(*(one(t) for t in missing)))

    rows = []
    for ticker, info in fetched.items():
        if not info:
            continue
        name = info.get("name")
        if not name:
            continue
        names[ticker] = name
        market = str(info.get("market") or info.get("exchange") or "").upper()
        rows.append(
            {
                "symbol": symbol_by_ticker[ticker],
                "ticker": ticker,
                "name": name,
                "market": "TPEX" if market in {"OTC", "TPEX"} else "TWSE",
                "currency": "TWD",
                "updated_at": _now_iso(),
            }
        )

    upsert_tickers(rows)
    return names


# --------------------------------------------------------------------------
# 匯率（落地到 fx_rates 表）
# --------------------------------------------------------------------------


async def _exchangerate_api(client: httpx.AsyncClient) -> float:
    response = await client.get("https://open.er-api.com/v6/latest/USD", timeout=8)
    response.raise_for_status()
    data = response.json()
    rate = data.get("rates", {}).get("TWD")
    if data.get("result") != "success" or rate is None:
        raise ValueError("ExchangeRate-API did not return USD/TWD")
    return float(rate)


async def _currency_api(client: httpx.AsyncClient) -> float:
    response = await client.get(
        "https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/latest/currencies/usd/twd.json",
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()
    rate = data.get("twd") or data.get("usd", {}).get("twd")
    if rate is None:
        raise ValueError("Currency-api did not return USD/TWD")
    return float(rate)


async def fetch_usd_rate(api_key: str = "", refresh: bool = False) -> float:
    stored = get_fx_rate()
    stored_rate = float(stored["rate"]) if stored and stored.get("rate") is not None else None

    if stored_rate and (not refresh or _is_fresh(stored.get("fetched_at"), RATE_REFRESH_TTL_SECONDS)):
        return stored_rate

    if not refresh:
        return stored_rate or DEFAULT_USD_TWD

    async with httpx.AsyncClient() as client:
        for source, fetcher in (("exchangerate-api", _exchangerate_api), ("currency-api", _currency_api)):
            try:
                rate = await fetcher(client)
                upsert_fx_rate(rate, source)
                return rate
            except Exception:
                continue

    return stored_rate or DEFAULT_USD_TWD


def get_price_status(context: PriceContext | None = None) -> dict:
    """報價狀態改以資料庫為準；context 提供本次執行的統計。"""
    stored = get_fx_rate()
    status: dict = {
        "usd_rate": float(stored["rate"]) if stored and stored.get("rate") is not None else None,
        "usd_rate_fetched_at": stored.get("fetched_at") if stored else None,
        "usd_rate_source": stored.get("source") if stored else None,
    }
    if context:
        status.update(context.stats)
    return status
