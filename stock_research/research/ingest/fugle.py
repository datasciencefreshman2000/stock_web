"""Fugle 歷史行情 client。

免費方案（基本用戶）的歷史行情額度是 **60 次/分鐘**，這個 client 會自動節流。

重要限制（來自官方文件）：
- 日 K 可指定 from/to，個股最遠回溯 2010 年
- **分 K 無法指定日期，一律回傳近 30 日** → 分 K 做不了回測，要用 Shioaji
"""

import os
import time
from collections import deque
from dataclasses import dataclass, field

import requests

BASE_URL = "https://api.fugle.tw/marketdata/v1.0/stock"
RATE_LIMIT_PER_MIN = 60
FIELDS = "open,high,low,close,volume,turnover,change"


class FugleError(RuntimeError):
    pass


@dataclass
class RateLimiter:
    """滑動視窗節流。免費方案 60 次/分，這裡預設留一點餘裕。"""

    max_calls: int = RATE_LIMIT_PER_MIN - 2
    window_seconds: float = 60.0
    _calls: deque = field(default_factory=deque)

    def acquire(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > self.window_seconds:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            sleep_for = self.window_seconds - (now - self._calls[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
            return self.acquire()
        self._calls.append(now)


class FugleClient:
    def __init__(self, api_key: str | None = None, max_retries: int = 4):
        self.api_key = api_key or os.getenv("FUGLE_API_KEY", "")
        if not self.api_key:
            raise FugleError(
                "找不到 FUGLE_API_KEY。請在 .env 設定，或用 FugleClient(api_key=...) 傳入。"
            )
        self.limiter = RateLimiter()
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": self.api_key})

    def _get(self, path: str, params: dict) -> dict:
        for attempt in range(self.max_retries):
            self.limiter.acquire()
            try:
                r = self.session.get(f"{BASE_URL}{path}", params=params, timeout=20)
            except requests.RequestException as exc:
                if attempt == self.max_retries - 1:
                    raise FugleError(f"連線失敗：{exc}") from exc
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 429:            # 超過速率限制，指數退避
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 404:
                return {}                        # 該標的在該期間沒有資料
            if not r.ok:
                if attempt == self.max_retries - 1:
                    raise FugleError(f"{r.status_code} {r.text[:200]}")
                time.sleep(2 ** attempt)
                continue
            return r.json()
        raise FugleError(f"重試 {self.max_retries} 次仍失敗：{path}")

    # ------------------------------------------------------------------ 日 K

    def daily_candles(
        self,
        ticker: str,
        start: str,
        end: str,
        adjusted: bool = True,
    ) -> list[dict]:
        """單次查詢。注意單次區間可能有上限，用 backfill 分段呼叫。"""
        payload = self._get(
            f"/historical/candles/{ticker}",
            {
                "from": start,
                "to": end,
                "timeframe": "D",
                "adjusted": "true" if adjusted else "false",
                "fields": FIELDS,
                "sort": "asc",
            },
        )
        return payload.get("data", []) or []

    def stats(self, ticker: str) -> dict:
        """近 52 週統計。用來確認標的存在、拿中文名稱。"""
        return self._get(f"/historical/stats/{ticker}", {})

    def ticker_info(self, ticker: str) -> dict:
        return self._get(f"/intraday/ticker/{ticker}", {})
