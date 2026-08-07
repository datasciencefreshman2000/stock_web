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

from config import get_settings
from repositories.fx_rates import get_fx_rate, upsert_fx_rate
from repositories.price_cache import list_price_cache, upsert_price_cache_rows
from repositories.tickers import list_tickers, upsert_tickers
from services.symbols import is_tw_account, symbol_for

def _price_ttl() -> int:
    """價格快取的存活秒數。可用環境變數 PRICE_REFRESH_TTL_SECONDS 調整。

    這個值決定「實際」更新頻率的下限 —— 排程再密集，
    只要快取還在有效期內就不會去打外部 API。
    """
    return get_settings().price_refresh_ttl_seconds


def _rate_ttl() -> int:
    return get_settings().rate_refresh_ttl_seconds
DEFAULT_USD_TWD = 31.316


def _fugle_client(api_key: str):
    from fugle_marketdata import RestClient

    return RestClient(api_key=api_key)


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
    fx_row: dict | None = None          # 這次請求已讀過的匯率，避免重複查
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
        client = _fugle_client(api_key)
        quote = client.stock.intraday.quote(symbol=ticker)
        price = quote.get("lastPrice") or quote.get("closePrice") or quote.get("previousClose")
        return float(price) if price else None
    except Exception:
        return None


def _fugle_ticker_info_sync(ticker: str, api_key: str) -> dict | None:
    try:
        client = _fugle_client(api_key)
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
    fetch_missing: bool = False,
) -> dict[str, float | None]:
    """回傳 {ticker: price}。refresh=False 時只讀資料庫快取，不打外部 API。

    fetch_missing=True 時有一個例外：**完全沒有快取列的標的仍然會去抓。**

    為什麼要有這個例外：
      「快取有點舊」和「根本沒有價格」是兩件事。
      前者只是數字晚幾分鐘，後者會讓市值被當成 0 ——
      新買一檔沒持有過的股票之後，持倉頁顯示不出現價，
      帳戶總額直接少掉那筆的市值，首頁現金條的比例也跟著錯。
      要等下一次排程才會對。

      這是有界的：一個標的只會發生一次，抓過就進 price_cache 了。
    """
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

        has_price = row is not None and row.get("price") is not None
        # 上次補抓失敗會留下一列 price=null，用它的時間做退避，
        # 免得抓不到的標的（下市、代號打錯）每次重建都再打一次外部 API
        recently_tried = row is not None and _is_fresh(row.get("fetched_at"), _price_ttl())

        if has_price and (not refresh or _is_fresh(row.get("fetched_at"), _price_ttl())):
            results[ticker] = row_price
            context.prices[symbol] = row_price
            context.stats["cached"] += 1
        elif refresh or (fetch_missing and not has_price and not recently_tried):
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
            if stale is None:
                # 留一筆「試過了、抓不到」的紀錄當退避標記
                rows.append({
                    "symbol": symbol, "ticker": ticker, "account": account,
                    "price": None, "currency": currency,
                    "fetched_at": _now_iso(), "source": provider,
                })
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
    return (await resolve_company_names_batch({account: tickers}, fugle_key)).get(account, {})


async def resolve_company_names_batch(
    tickers_by_account: dict[str, list[str]], fugle_key: str = ""
) -> dict[str, dict[str, str | None]]:
    """一次查詢所有帳戶的公司名稱；缺少的台股名稱再批次向 Fugle 補齊。"""
    normalized = {
        account: sorted({t.strip().upper() for t in tickers if t and t.strip()})
        for account, tickers in tickers_by_account.items()
    }
    symbol_maps = {
        account: {ticker: symbol_for(account, ticker) for ticker in tickers}
        for account, tickers in normalized.items()
    }
    symbols = sorted({symbol for mapping in symbol_maps.values() for symbol in mapping.values()})
    known = list_tickers(symbols) if symbols else {}
    names = {
        account: {
            ticker: (known.get(symbol) or {}).get("name")
            for ticker, symbol in symbol_maps[account].items()
        }
        for account in normalized
    }

    missing_symbols: dict[str, str] = {}
    for account, account_names in names.items():
        if not is_tw_account(account):
            continue
        for ticker, name in account_names.items():
            if not name:
                missing_symbols[symbol_maps[account][ticker]] = ticker
    if not missing_symbols or not fugle_key:
        return names
    missing_symbol_by_ticker = {ticker: symbol for symbol, ticker in missing_symbols.items()}

    semaphore = asyncio.Semaphore(5)

    async def one(ticker: str) -> tuple[str, dict | None]:
        async with semaphore:
            return ticker, await asyncio.to_thread(_fugle_ticker_info_sync, ticker, fugle_key)

    fetched = dict(await asyncio.gather(*(one(t) for t in sorted(set(missing_symbols.values())))))

    rows = []
    for ticker, info in fetched.items():
        if not info:
            continue
        name = info.get("name")
        if not name:
            continue
        market = str(info.get("market") or info.get("exchange") or "").upper()
        rows.append(
            {
                "symbol": missing_symbol_by_ticker[ticker],
                "ticker": ticker,
                "name": name,
                "market": "TPEX" if market in {"OTC", "TPEX"} else "TWSE",
                "currency": "TWD",
                "updated_at": _now_iso(),
            }
        )

    upsert_tickers(rows)
    for account, mapping in symbol_maps.items():
        for ticker, symbol in mapping.items():
            if not names[account].get(ticker):
                names[account][ticker] = next(
                    (row.get("name") for row in rows if row.get("symbol") == symbol),
                    None,
                )
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


async def fetch_usd_rate(api_key: str = "", refresh: bool = False,
                         context: PriceContext | None = None) -> float:
    """取得 USD/TWD。傳入 context 時，同一次請求內只會查一次資料庫。"""
    stored = context.fx_row if context and context.fx_row is not None else get_fx_rate()
    if context is not None:
        context.fx_row = stored or {}
    stored_rate = float(stored["rate"]) if stored and stored.get("rate") is not None else None

    if stored_rate and (not refresh or _is_fresh(stored.get("fetched_at"), _rate_ttl())):
        return stored_rate

    if not refresh:
        return stored_rate or DEFAULT_USD_TWD

    async with httpx.AsyncClient() as client:
        for source, fetcher in (("exchangerate-api", _exchangerate_api), ("currency-api", _currency_api)):
            try:
                rate = await fetcher(client)
                row = upsert_fx_rate(rate, source)
                if context is not None:
                    context.fx_row = row
                return rate
            except Exception:
                continue

    return stored_rate or DEFAULT_USD_TWD


def get_price_status(context: PriceContext | None = None) -> dict:
    """報價狀態改以資料庫為準；context 提供本次執行的統計。

    context 已經讀過匯率時直接沿用，不再多查一次。
    """
    stored = context.fx_row if context and context.fx_row is not None else get_fx_rate()
    status: dict = {
        "usd_rate": float(stored["rate"]) if stored and stored.get("rate") is not None else None,
        "usd_rate_fetched_at": stored.get("fetched_at") if stored else None,
        "usd_rate_source": stored.get("source") if stored else None,
    }
    if context:
        status.update(context.stats)
    return status
