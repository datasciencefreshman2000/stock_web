import { Loader2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import MobileNumericInput from './cash/MobileNumericInput'
import { ACCOUNTS } from '../constants'
import { maskAmount, usePrivacy } from '../context/PrivacyContext'
import { money } from '../utils/format'
import { useTradeTickersQuery } from '../hooks/queries'

const today = new Date().toISOString().slice(0, 10)
const EMPTY_TICKERS = []

function estimateTwFee(price, qty) {
  return Math.max(Math.trunc(Number(price || 0) * Number(qty || 0) * 0.001425 * 0.6), 1)
}

function estimateTwTax(price, qty, ticker) {
  const isEtf = ['0050', '00981A'].includes(String(ticker).toUpperCase())
  return Math.trunc(Number(price || 0) * Number(qty || 0) * (isEtf ? 0.001 : 0.003))
}

function estimateCathayUsFee(price, qty) {
  return Number(price || 0) * Number(qty || 0) * 0.001
}

function looksLikeTwTicker(ticker) {
  return /^[0-9]{4,6}[A-Z]{0,2}$/.test(ticker)
}

function looksLikeUsTicker(ticker) {
  return /^[A-Z.]{1,6}$/.test(ticker)
}

const initialForm = {
  account: ACCOUNTS[0],
  ticker: '',
  side: 'buy',
  qty: '',
  price: '',
  date: today,
  fee: '',
  note: '',
}

export default function TradeForm({ onSubmit, submitting }) {
  const { hideAmounts } = usePrivacy()
  const [form, setForm] = useState(initialForm)
  const tickersQuery = useTradeTickersQuery(form.account)
  const [tickerHint, setTickerHint] = useState('')
  const [localError, setLocalError] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [companyLoading, setCompanyLoading] = useState(false)

  // 鍵盤流程：代號 → Enter → 買賣（←→ 切換）→ Enter → 股數 → Enter → 價格 → Enter → 送出
  const tickerRef = useRef(null)
  const sideRef = useRef(null)
  const qtyRef = useRef(null)
  const priceRef = useRef(null)

  // 進頁面時把游標放到代號。只在桌機做 —— 手機上自動聚焦會直接彈出鍵盤，很煩。
  useEffect(() => {
    if (window.matchMedia('(min-width: 640px)').matches) tickerRef.current?.focus()
  }, [])

  /** Enter 預設會直接送出表單，這裡改成「跳下一格」。 */
  function enterTo(ref) {
    return (event) => {
      if (event.key !== 'Enter') return
      event.preventDefault()      // ← 沒有這行，表單會帶著空的股數/價格送出，
      ref.current?.focus()        //   後端回 422，畫面就跳出那個紅框
      ref.current?.select?.()
    }
  }

  const isTw = form.account === ACCOUNTS[0]
  const isUs = form.account === ACCOUNTS[1] || form.account === ACCOUNTS[2]
  const cathayUsFee = useMemo(() => estimateCathayUsFee(form.price, form.qty), [form.price, form.qty])
  const fee = useMemo(() => (isTw ? estimateTwFee(form.price, form.qty) : Number(form.fee || 0)), [form, isTw])
  const tax = useMemo(
    () => (isTw && form.side === 'sell' ? estimateTwTax(form.price, form.qty, form.ticker) : 0),
    [form, isTw],
  )
  const gross = Number(form.price || 0) * Number(form.qty || 0)
  const total = form.side === 'buy' ? gross + fee : gross - fee - tax
  const tickers = tickersQuery.data?.tickers || EMPTY_TICKERS
  const tickerSuggestions = useMemo(() => {
    const keyword = form.ticker.trim().toUpperCase()
    if (!keyword) return tickers.slice(0, 12)
    return tickers
      .filter((ticker) => ticker.includes(keyword) || keyword.includes(ticker))
      .sort((a, b) => {
        const aStarts = a.startsWith(keyword) ? 0 : 1
        const bStarts = b.startsWith(keyword) ? 0 : 1
        return aStarts - bStarts || a.localeCompare(b)
      })
      .slice(0, 12)
  }, [form.ticker, tickers])

  useEffect(() => {
    const ticker = form.ticker.trim().toUpperCase()
    if (!isTw || !looksLikeTwTicker(ticker)) {
      setCompanyName('')
      setCompanyLoading(false)
      return
    }

    let active = true
    const timer = setTimeout(() => {
      setCompanyLoading(true)
      api
        .getTickerInfo(form.account, ticker)
        .then((data) => {
          if (active) setCompanyName(data.company_name || '')
        })
        .catch(() => {
          if (active) setCompanyName('')
        })
        .finally(() => {
          if (active) setCompanyLoading(false)
        })
    }, 250)

    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [form.account, form.ticker, isTw])

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function updateTicker(value) {
    const ticker = value.toUpperCase().trim()
    setTickerHint('')
    setForm((current) => {
      let account = current.account
      if (account === ACCOUNTS[0] && looksLikeUsTicker(ticker)) {
        account = ACCOUNTS[1]
        setTickerHint(`看起來像美股代號，已自動切到 ${ACCOUNTS[1]}。`)
      } else if ((account === ACCOUNTS[1] || account === ACCOUNTS[2]) && looksLikeTwTicker(ticker)) {
        account = ACCOUNTS[0]
        setTickerHint(`看起來像台股代號，已自動切到 ${ACCOUNTS[0]}。`)
      }
      return { ...current, ticker, account }
    })
  }

  /**
   * 按鈕組共用的鍵盤行為：↑ ↓ 換選項。
   *
   * 用 ↑ ↓ 而不是 ← →，是因為 ← → 是全站換頁鍵（見 NavBar）。
   * 這兩組按鈕另外標了 data-page-keys="off"，
   * 所以在上面按 ← → 不會誤跳到別頁。
   */
  function arrowSelect(options, key, next) {
    return (event) => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') {
        if (next && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault()
          next.current?.focus()
          next.current?.select?.()
        }
        return
      }
      event.preventDefault()
      const size = options.length
      const step = event.key === 'ArrowDown' ? 1 : -1
      const nextIndex = (options.indexOf(form[key]) + step + size) % size
      update(key, options[nextIndex])

      // 焦點要跟著選取移動。roving tabindex 的規則是「只有選中的那顆
      // tabIndex=0」，如果焦點留在舊的那顆，它就變成一個 tabIndex=-1
      // 卻還有焦點框的按鈕 —— 看起來像壞掉。
      const group = event.currentTarget.closest('[role="radiogroup"]')
      group?.querySelectorAll('[role="radio"]')[nextIndex]?.focus()
    }
  }

  const handleSideKeyDown = arrowSelect(['buy', 'sell'], 'side', qtyRef)
  const handleAccountKeyDown = arrowSelect(ACCOUNTS, 'account', null)

  async function submit(event) {
    event.preventDefault()

    // 先在前端擋掉，不要讓後端回 422 ——
    // 那個錯誤格式是物件陣列，也是紅框顯示 [object Object] 的原因
    const qty = Number(form.qty)
    if (!form.ticker.trim()) return setLocalError('請輸入股票代號')
    if (!Number.isFinite(qty) || qty <= 0) return setLocalError('請輸入大於 0 的股數')
    if (!Number.isFinite(Number(form.price)) || Number(form.price) <= 0) {
      return setLocalError('請輸入大於 0 的價格')
    }
    setLocalError('')

    const payload = {
      account: form.account,
      ticker: form.ticker.trim().toUpperCase(),
      date: form.date,
      buy_qty: form.side === 'buy' ? qty : null,
      sell_qty: form.side === 'sell' ? qty : null,
      price: Number(form.price),
      fee: isTw ? 0 : Number(form.fee || 0),
      note: form.note,
    }
    const ok = await onSubmit(payload)
    if (ok) {
      setForm((current) => ({ ...initialForm, account: current.account, date: current.date }))
      setTickerHint('已新增，頁面保留在新增交易。')
      // 游標回到代號，可以直接打下一筆
      tickerRef.current?.focus()
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-md border border-line bg-surface p-3 sm:p-4">
      <div
        className="grid grid-cols-10 gap-2 sm:grid-cols-[2fr_2fr_1fr] sm:gap-3"
        role="radiogroup"
        aria-label="帳戶"
        data-page-keys="off"
      >
        {ACCOUNTS.map((account, index) => (
          <button
            key={account}
            type="button"
            role="radio"
            aria-checked={form.account === account}
            tabIndex={form.account === account ? 0 : -1}
            onKeyDown={handleAccountKeyDown}
            onClick={() => update('account', account)}
            className={`rounded-md border py-2 text-sm transition hover:-translate-y-0.5 hover:border-sky-400/70 hover:bg-sky-500/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.98] sm:col-span-1 sm:px-3 ${
              index === 2 ? 'col-span-2 px-1 text-xs font-medium sm:text-xs' : 'col-span-4 px-2 font-medium'
            } ${
              form.account === account ? 'border-sky-400 bg-sky-500/15 text-white shadow-sm shadow-sky-950/40' : 'border-line bg-panel text-slate-300'
            }`}
          >
            {account}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
        <label className="grid gap-2 text-sm">
          代號
          <input
            ref={tickerRef}
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2"
            value={form.ticker}
            list="ticker-suggestions"
            onChange={(event) => updateTicker(event.target.value)}
            onKeyDown={enterTo(sideRef)}
            placeholder={tickersQuery.isLoading ? '讀取曾輸入代號...' : '輸入股票代號'}
            required
          />
          <datalist id="ticker-suggestions">
            {tickerSuggestions.map((ticker) => (
              <option key={ticker} value={ticker} />
            ))}
          </datalist>
          {companyLoading || companyName ? (
            <span className="text-xs text-slate-400">
              {companyLoading ? '查詢公司名稱中...' : companyName}
            </span>
          ) : null}
          {tickerHint ? <span className="text-xs text-amber-300">{tickerHint}</span> : null}
        </label>
        <label className="grid gap-2 text-sm">
          日期
          <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" type="date" value={form.date} onChange={(event) => update('date', event.target.value)} required />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-3 sm:gap-4">
        <div className="grid gap-2 text-sm">
          <span className="flex items-center gap-2">
            買賣
            <span className="hidden text-[10px] text-slate-600 sm:inline">↑ ↓ 切換</span>
          </span>
          {/* roving tabindex：只有選中的那顆進 tab 順序，↑↓ 切換選擇 */}
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="買賣" data-page-keys="off">
            {[
              ['buy', '買入'],
              ['sell', '賣出'],
            ].map(([side, label]) => (
              <button
                key={side}
                type="button"
                role="radio"
                aria-checked={form.side === side}
                ref={form.side === side ? sideRef : null}
                tabIndex={form.side === side ? 0 : -1}
                onKeyDown={handleSideKeyDown}
                onClick={() => update('side', side)}
                className={`rounded-md border px-3 py-2 text-sm font-medium transition hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 active:scale-[0.98] ${
                  form.side === side
                    ? side === 'buy'
                      ? 'border-emerald-400/70 bg-emerald-500/15 text-emerald-100 shadow-sm shadow-emerald-950/40 focus-visible:outline-emerald-400/70'
                      : 'border-rose-400/70 bg-rose-500/15 text-rose-100 shadow-sm shadow-rose-950/40 focus-visible:outline-rose-400/70'
                    : side === 'buy'
                      ? 'border-line bg-[#0b1020] text-slate-300 hover:border-emerald-400/70 hover:bg-emerald-500/10 hover:text-emerald-100 focus-visible:outline-emerald-400/70'
                      : 'border-line bg-[#0b1020] text-slate-300 hover:border-rose-400/70 hover:bg-rose-500/10 hover:text-rose-100 focus-visible:outline-rose-400/70'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-2 text-sm">
          股數
          <MobileNumericInput
            value={form.qty}
            onChange={(value) => update('qty', value)}
            label="股數"
            currency="股"
            maxDecimals={4}
            allowZero={false}
            inputRef={qtyRef}
            onDesktopKeyDown={enterTo(priceRef)}
          />
        </div>
        <div className="grid gap-2 text-sm">
          價格
          <MobileNumericInput
            value={form.price}
            onChange={(value) => update('price', value)}
            label="價格"
            currency={isTw ? 'TWD' : 'USD'}
            maxDecimals={4}
            allowZero={false}
            masked={hideAmounts}
            inputRef={priceRef}
            // 最後一格：Enter 就送出（不 preventDefault，讓表單自己送）
          />
        </div>
      </div>

      {isUs ? (
        <div className="grid gap-2 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span>美股手續費</span>
            <button
              type="button"
              onClick={() => update('fee', cathayUsFee.toFixed(2))}
              className="rounded-md border border-sky-500 bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-100"
            >
              國泰 {hideAmounts ? maskAmount(money(cathayUsFee, 'USD')) : money(cathayUsFee, 'USD')}
            </button>
          </div>
          <MobileNumericInput
            value={form.fee}
            onChange={(value) => update('fee', value)}
            label="美股手續費"
            currency="USD"
            masked={hideAmounts}
          />
        </div>
      ) : null}

      <label className="grid gap-2 text-sm">
        備註
        <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2" value={form.note} onChange={(event) => update('note', event.target.value)} />
      </label>

      <div className="grid gap-2 rounded-md border border-line bg-panel p-3 text-xs text-slate-300 sm:grid-cols-3 sm:text-sm">
        <div>手續費：{hideAmounts ? maskAmount(money(fee)) : money(fee)}</div>
        <div>證交稅：{form.side === 'sell' ? (hideAmounts ? maskAmount(money(tax)) : money(tax)) : '--'}</div>
        <div>交易總額：{hideAmounts ? maskAmount(money(total)) : money(total)}</div>
      </div>

      {localError ? (
        <div className="rounded-md border border-rose-900 bg-rose-950/40 px-3 py-2 text-sm text-rose-100">{localError}</div>
      ) : null}

      <button
        disabled={submitting}
        className={`flex items-center justify-center gap-2 rounded-md bg-sky-500 px-4 py-3 font-medium text-white transition active:scale-[0.99] disabled:opacity-70 ${submitting ? 'submit-pulse' : 'hover:bg-sky-400'}`}
      >
        {submitting ? <Loader2 size={17} className="animate-spin" /> : null}
        {submitting ? '新增中' : '新增交易'}
      </button>
    </form>
  )
}
