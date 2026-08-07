"""診斷：為什麼某筆交易出現在「紀錄」，卻沒有出現在「持倉」。

用法（在 backend 資料夾下）：
    python scripts/diagnose_holdings.py
    python scripts/diagnose_holdings.py --ticker 2330
    python scripts/diagnose_holdings.py --account 台股

「紀錄」和「持倉」讀的是**不同的路徑**，所以會不一致：

    紀錄  GET /api/trades/{account}   → 直接把 trades 表撈出來顯示
    持倉  GET /api/portfolio/{account} → 跑 FIFO，只留下 current_qty > 0 的

中間有四個地方會讓一筆交易「消失」：

  1. 帳戶名稱不在 ACCOUNTS 裡
     calculate_summary 是 `if trade.get("account") in trades_by_account`，
     對不上就**靜默丟掉**。多一個空白、或是舊的 "x配置(台股)" 這種帳戶都會中。

  2. FIFO 算出來 current_qty <= 0
     全部賣光的標的本來就不該出現在持倉——這是正確行為，不是 bug。

  3. 賣出多於買入（unmatched sell）
     代表有買單沒被記錄到。FIFO 會把多出來的賣出掛在 unmatched_sell_balance，
     持倉顯示 0，但你的紀錄裡看得到那些賣單。

  4. 抓不到報價
     持倉會列出來，但沒有現價、市值算 0。

這支腳本把每一檔的判定過程印出來，直接告訴你是哪一種。
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from repositories.price_cache import list_price_cache  # noqa: E402
from repositories.trades import list_trades  # noqa: E402
from services.accounts import ACCOUNTS  # noqa: E402
from services.calculator import active_tickers, analyze_account_trades  # noqa: E402
from services.symbols import symbol_for  # noqa: E402

LINE = "=" * 78


def check_accounts(trades: list[dict]) -> list[dict]:
    """第 1 關：帳戶名稱對不上就永遠進不了持倉。"""
    counts = Counter(str(t.get("account")) for t in trades)
    unknown = {a: n for a, n in counts.items() if a not in ACCOUNTS}

    print(LINE)
    print("一、交易資料裡的帳戶")
    print(LINE)
    for account, n in counts.most_common():
        mark = "" if account in ACCOUNTS else "   ← 不在 ACCOUNTS，持倉不會算它"
        print(f"  {n:>5} 筆   {account!r}{mark}")

    if unknown:
        total = sum(unknown.values())
        print(f"\n  ⚠ 有 {total} 筆交易的帳戶不在 {ACCOUNTS}。")
        print("    這些交易在『紀錄』看得到，但『持倉』與『總覽』完全不會計算。")
        print("    常見原因：舊的帳戶名稱、或名稱前後多了空白。")
        print("    修法：把 trades.account 更新成正確的名稱，例如")
        for account in unknown:
            print(f"      update trades set account = '台股' where account = {account!r};")
    else:
        print("\n  ✓ 所有交易的帳戶都對得上。")

    return [t for t in trades if t.get("account") in ACCOUNTS]


def report_account(account: str, trades: list[dict], only_ticker: str | None) -> None:
    rows = [t for t in trades if t.get("account") == account]
    if not rows:
        return

    results = analyze_account_trades(account, rows)
    active = set(active_tickers(results))
    symbols = {t: symbol_for(account, t) for t in results}
    prices = list_price_cache(sorted(symbols.values())) if symbols else {}

    print(f"\n{LINE}")
    print(f"二、{account}｜{len(rows)} 筆交易、{len(results)} 個標的")
    print(LINE)
    print(f"  {'代號':<8}{'筆數':>5}{'買入':>11}{'賣出':>11}{'目前':>11}  判定")
    print("  " + "-" * 74)

    problems: list[str] = []
    for ticker in sorted(results):
        if only_ticker and ticker != only_ticker:
            continue
        result = results[ticker]
        mine = [t for t in rows if t["ticker"] == ticker]
        bought = sum(float(t.get("buy_qty") or 0) for t in mine)
        sold = sum(float(t.get("sell_qty") or 0) for t in mine)
        qty = result["current_qty"]
        unmatched = result.get("unmatched_sell_qty") or 0
        price = (prices.get(symbols[ticker]) or {}).get("price")

        if ticker in active and price is not None:
            verdict = "✓ 正常顯示在持倉"
        elif ticker in active:
            verdict = "⚠ 有持股但抓不到報價，市值會算 0"
            problems.append(f"{ticker}：抓不到報價（代號是否正確？是否已下市？）")
        elif unmatched > 0:
            verdict = f"⚠ 賣出比買入多 {unmatched:g} 股"
            problems.append(f"{ticker}：賣出 {sold:g} > 買入 {bought:g}，少記了買單")
        elif bought > 0 and abs(qty) < 1e-9:
            verdict = "· 已全部賣出（不該出現在持倉，正常）"
        else:
            verdict = "⚠ 有交易卻算不出持股"
            problems.append(f"{ticker}：買 {bought:g} 賣 {sold:g}，FIFO 得出 {qty:g}")

        print(f"  {ticker:<8}{len(mine):>5}{bought:>11,.0f}{sold:>11,.0f}{qty:>11,.0f}  {verdict}")

    if problems:
        print(f"\n  需要處理（{len(problems)} 項）：")
        for item in problems:
            print(f"    - {item}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", help="只看單一帳戶")
    parser.add_argument("--ticker", help="只看單一代號")
    args = parser.parse_args()

    trades = list_trades()
    print(f"\n資料庫共 {len(trades)} 筆交易")
    if len(trades) % 1000 == 0 and trades:
        print("  ⚠ 筆數剛好是 1000 的倍數。若後端還沒更新到有分頁的版本，")
        print("    這代表 PostgREST 截斷了資料（預設一次只回 1000 列，且不報錯）。")
    print()

    known = check_accounts(trades)
    ticker = args.ticker.strip().upper() if args.ticker else None
    for account in ACCOUNTS:
        if args.account and account != args.account:
            continue
        report_account(account, known, ticker)

    print(f"\n{LINE}")
    print("判讀提示")
    print(LINE)
    print("  · 已全部賣出        → 正常，持倉本來就只顯示還有股數的標的")
    print("  ⚠ 賣出比買入多      → 有買單沒記到，去『紀錄』補上那筆買進")
    print("  ⚠ 抓不到報價        → 代號打錯或已下市；持倉會列出但市值算 0")
    print("  ⚠ 帳戶不在 ACCOUNTS → 這批交易完全不會被計算，要先改帳戶名稱")


if __name__ == "__main__":
    main()
