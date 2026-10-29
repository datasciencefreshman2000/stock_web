import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRightLeft, ChevronDown, ChevronUp, Loader2, MessageSquareText } from 'lucide-react'

import { api } from '../../api/client'
import { useSaveQueue } from '../../hooks/useSaveQueue'
import { money } from '../../utils/format'
import { ACCOUNTS, ACCOUNT_CURRENCY } from '../../constants'
import { usePrivacy } from '../../context/PrivacyContext'
import { usePersistentState } from '../../hooks/usePersistentState'
import IncomeSourcePicker from './IncomeSourcePicker'
import MobileNumericInput from './MobileNumericInput'
import NumericKeypad from './NumericKeypad'
import { CREDIT_CARD_DEBT, EXPENSE_TAGS, INCOME_SOURCES, ON_HAND_CASH, OTHER_TYPES, today } from './constants'

function unique(items) {
  return [...new Set(items.filter(Boolean))]
}

export default function CapitalMovementPanel({ bankNames, positiveBankNames, onSaved,
                                               openSignal = 0, openMode = null, usdRate = 31.316 }) {
  const { hideAmounts } = usePrivacy()
  const sectionRef = useRef(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [attention, setAttention] = useState(false)
  const [mode, setMode] = usePersistentState('movement-mode', 'income')
  const previousMode = useRef(mode)

  // 外部（例如現金頁的「記帳」按鈕）要求展開並切到指定模式。
  // 用遞增的 openSignal 當觸發，這樣連按也有效。
  useEffect(() => {
    if (!openSignal) return
    setPanelOpen(true)
    if (openMode) setMode(openMode)
    setAttention(false)

    const scrollTimer = window.setTimeout(() => {
      sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setAttention(true)
    }, 80)
    const attentionTimer = window.setTimeout(() => setAttention(false), 1100)
    return () => {
      window.clearTimeout(scrollTimer)
      window.clearTimeout(attentionTimer)
    }
  }, [openSignal, openMode])
  const [exchange, setExchange] = useState(false)
  const [toAmountManual, setToAmountManual] = usePersistentState('movement-manual-destination', false)
  const [noteOpen, setNoteOpen] = useState(false)
  const [desktopKeypadOpen, setDesktopKeypadOpen] = useState(false)
  const [form, setForm] = usePersistentState('movement', () => ({
    movement_date: today(),
    income_source: INCOME_SOURCES[0],
    expense_tags: ['其他'],
    other_type: OTHER_TYPES[0],
    from_bucket: bankNames[0] || ON_HAND_CASH,
    to_bucket: bankNames[0] || ACCOUNTS[0],
    amount: '',
    currency: 'TWD',
    to_amount: '',
    to_currency: 'USD',
    note: '',
    operation_id: crypto.randomUUID(),
    affects_balance: true,
  }))
  const [message, setMessage] = useState('')
  useEffect(() => {
    if (previousMode.current === mode) return
    previousMode.current = mode
    setForm(current => ({ ...current, amount: '', to_amount: '', note: '', operation_id: crypto.randomUUID() }))
    setToAmountManual(false)
    setMessage('')
  }, [mode])
  // 送出不擋畫面：按下去就排隊，表單立刻清空可以打下一筆。
  // 全站佇列依序送出；跨裝置的並行與重試另由資料庫交易保護。
  const queue = useSaveQueue(api.createCapitalMovement, () => onSaved?.())
  const saving = queue.pending > 0

  const incomeDestinations = useMemo(() => unique([...bankNames, ON_HAND_CASH, ...ACCOUNTS]), [bankNames])
  const transferBuckets = useMemo(() => unique([...bankNames, ON_HAND_CASH, ...ACCOUNTS]), [bankNames])
  const transferDestinations = useMemo(() => unique([...transferBuckets, CREDIT_CARD_DEBT]), [transferBuckets])
  const expenseSources = useMemo(
    () => unique([ON_HAND_CASH, ...positiveBankNames, CREDIT_CARD_DEBT]),
    [positiveBankNames],
  )

  useEffect(() => {
    const fromOptions = mode === 'expense' ? expenseSources : transferBuckets
    const toOptions = mode === 'income' ? incomeDestinations : transferDestinations
    setForm((current) => {
      const next = { ...current }
      if ((mode === 'transfer' || mode === 'expense') && !fromOptions.includes(next.from_bucket)) {
        next.from_bucket = fromOptions[0] || ''
      }
      if ((mode === 'income' || mode === 'transfer') && !toOptions.includes(next.to_bucket)) {
        next.to_bucket = toOptions[0] || ''
      }
      return next.from_bucket === current.from_bucket && next.to_bucket === current.to_bucket ? current : next
    })
    if (mode !== 'transfer') setExchange(false)
    if (mode !== 'expense') setNoteOpen(false)
  }, [mode, expenseSources, incomeDestinations, transferBuckets, transferDestinations])

  // 換匯的換入金額先用目前匯率估算；使用者一旦修改，就保留實際成交金額。
  useEffect(() => {
    if (!exchange || mode !== 'transfer' || toAmountManual) return
    const amount = Number(form.amount)
    const rate = Number(usdRate)
    if (!Number.isFinite(amount) || amount <= 0 || !Number.isFinite(rate) || rate <= 0) return

    let estimated = amount
    if (form.currency === 'USD' && form.to_currency === 'TWD') estimated = amount * rate
    if (form.currency === 'TWD' && form.to_currency === 'USD') estimated = amount / rate
    const next = Number(estimated.toFixed(2)).toString()
    setForm((current) => current.to_amount === next ? current : { ...current, to_amount: next })
  }, [exchange, mode, form.amount, form.currency, form.to_currency, toAmountManual, usdRate])

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value, operation_id: crypto.randomUUID() }))
  }

  // Investment accounts have a fixed currency. Bank buckets can hold either currency.
  useEffect(() => {
    if (mode === 'income') {
      const fixed = ACCOUNT_CURRENCY[form.to_bucket]
      if (fixed && form.currency !== fixed) update('currency', fixed)
      return
    }
    if (mode !== 'transfer') return
    const currency = ACCOUNT_CURRENCY[form.from_bucket] || form.currency
    const toCurrency = ACCOUNT_CURRENCY[form.to_bucket] || (ACCOUNT_CURRENCY[form.from_bucket] === 'USD' ? 'TWD' : form.to_currency)
    if (currency === form.currency && toCurrency === form.to_currency) return
    setToAmountManual(false)
    setForm(current => ({ ...current, currency, to_currency: toCurrency, to_amount: '', operation_id: crypto.randomUUID() }))
  }, [mode, form.from_bucket, form.to_bucket])

  useEffect(() => {
    if (mode === 'transfer') setExchange(form.currency !== form.to_currency)
  }, [mode, form.currency, form.to_currency])

  function noteWithTag(tag, note) {
    return [tag, note.trim()].filter(Boolean).join(' - ')
  }

  function noteWithTags(tags, note) {
    return noteWithTag(tags.join(', '), note)
  }

  function normalizeAmount(value) {
    const cleaned = String(value).replace(/[^0-9.]/g, '')
    const [integer = '', ...decimalParts] = cleaned.split('.')
    const decimal = decimalParts.join('').slice(0, 2)
    return decimalParts.length ? `${integer || '0'}.${decimal}` : integer
  }

  function toggleExpenseTag(tag) {
    setForm((current) => {
      const selected = current.expense_tags.includes(tag)
      if (selected) {
        const remaining = current.expense_tags.filter((item) => item !== tag)
        return { ...current, expense_tags: remaining.length ? remaining : ['其他'] }
      }
      if (tag === '其他') return { ...current, expense_tags: ['其他'] }
      return {
        ...current,
        expense_tags: [...current.expense_tags.filter((item) => item !== '其他'), tag],
      }
    })
  }

  function presetTwdToUsExchange() {
    setMode('transfer'); setExchange(true); setToAmountManual(false)
    setForm(current => ({ ...current, amount: '', operation_id: crypto.randomUUID(),
      from_bucket: bankNames.includes('國泰現金') ? '國泰現金' : bankNames[0] || ON_HAND_CASH,
      to_bucket: '美股', currency: 'TWD', to_currency: 'USD', to_amount: '' }))
    setMessage('請確認換出的 TWD 與實際入帳的 USD；估算金額可以直接修改。')
  }

  function presetUsSaleExchange() {
    setMode('transfer')
    setExchange(true)
    setToAmountManual(false)
    setForm((current) => ({
      ...current,
      operation_id: crypto.randomUUID(),
      amount: '', to_amount: '',
      from_bucket: ACCOUNTS[1],
      to_bucket: bankNames.includes('國泰現金') ? '國泰現金' : bankNames[0] || '',
      currency: 'USD',
      to_currency: 'TWD',
    }))
    setMessage('請輸入美股要換出的 USD 金額，以及入帳的 TWD 金額。')
  }

  function toggleExchange(enabled) {
    setExchange(enabled)
    setToAmountManual(false)
    if (!enabled) update('to_amount', '')
  }

  function updateToCurrency(value) {
    setToAmountManual(false)
    update('to_currency', value)
  }

  function updateSourceCurrency(value) {
    setToAmountManual(false)
    update('currency', value)
  }

  function saveMovement() {
    setMessage('')
    try {
      const amount = Number(form.amount)
      if (!Number.isFinite(amount) || amount <= 0) throw new Error('請輸入大於 0 的金額')
      if (exchange && mode === 'transfer' && (!Number.isFinite(Number(form.to_amount)) || Number(form.to_amount) <= 0)) {
        throw new Error('請輸入大於 0 的換入金額')
      }

      let payload = {
        operation_id: form.operation_id,
        affects_balance: form.affects_balance !== false,
        movement_date: form.movement_date,
        from_bucket: null,
        to_bucket: form.to_bucket,
        amount,
        currency: form.currency,
        to_amount: exchange && mode === 'transfer' ? Number(form.to_amount) : null,
        to_currency: exchange && mode === 'transfer' ? form.to_currency : null,
        note: form.note.trim(),
      }

      if (mode === 'income') {
        payload = { ...payload, note: noteWithTag(form.income_source, form.note) }
      } else if (mode === 'transfer') {
        payload = { ...payload, from_bucket: form.from_bucket }
      } else if (mode === 'expense') {
        payload = {
          ...payload,
          from_bucket: form.from_bucket,
          to_bucket: '支出',
          note: noteWithTags(form.expense_tags.length ? form.expense_tags : ['其他'], form.note),
        }
      } else {
        const debt = form.other_type.includes('待還款')
        payload = { ...payload, from_bucket: debt ? form.other_type : null, to_bucket: debt ? (bankNames[0] || ON_HAND_CASH) : form.other_type, note: noteWithTag(form.other_type, form.note) }
      }

      // 排進佇列就回來，不等網路
      queue.enqueue(payload, `${payload.to_bucket} ${payload.amount}`)
      setNoteOpen(false)
      setForm((current) => ({ ...current, operation_id: crypto.randomUUID(), movement_date: today(), amount: '', to_amount: '', note: '', expense_tags: ['其他'] }))
      return true
    } catch (error) {
      setMessage(error.message || '儲存失敗，請稍後再試')
      return false
    }
  }

  function submit(event) {
    event.preventDefault()
    saveMovement()
  }

  const amountLabel = mode === 'income' ? '收入金額' : mode === 'transfer' ? '換出金額' : mode === 'expense' ? '支出金額' : '其他金額'

  return (
    <section
      ref={sectionRef}
      className={`scroll-mt-4 overflow-hidden rounded-md border bg-surface transition-[border-color,box-shadow] duration-300 sm:scroll-mt-6 ${attention ? 'ledger-focus border-sky-400/80' : 'border-line'}`}
    >
      <button
        type="button"
        onClick={() => setPanelOpen((open) => !open)}
        className="flex w-full items-center justify-between gap-3 bg-panel px-4 py-3 text-left"
        aria-expanded={panelOpen}
      >
        <span className="text-sm font-medium">資金紀錄</span>
        {panelOpen ? <ChevronUp size={17} className="text-slate-400" /> : <ChevronDown size={17} className="text-slate-400" />}
      </button>

      {panelOpen ? (
        <div className="ledger-panel-enter border-t border-line">
          <div className="grid grid-cols-4 gap-2 p-3">
            {[
              ['income', '收入'],
              ['transfer', '調動'],
              ['expense', '支出'],
              ['other', '其他'],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setMode(key)}
                aria-pressed={mode === key}
                className={`rounded-md border px-2 py-2 text-sm transition hover:-translate-y-0.5 hover:border-sky-400/70 hover:bg-sky-500/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.98] ${mode === key ? 'border-sky-400 bg-sky-500/15 text-white shadow-sm shadow-sky-950/40' : 'border-line bg-panel text-slate-300'}`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="grid gap-3 px-3 pb-3 sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
            {mode === 'transfer' ? <div className="grid gap-3 rounded-md border border-sky-500/30 bg-sky-500/[0.06] p-3 text-xs sm:col-span-2 lg:col-span-6">
              <p className="text-sky-100">選擇換匯方向，再確認兩邊實際收付金額。</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <button type="button" onClick={presetTwdToUsExchange} className="rounded border border-sky-400/50 px-3 py-2 text-sky-100">台幣帳戶 TWD → 美股 USD</button>
                <button type="button" onClick={presetUsSaleExchange} className="rounded border border-sky-400/50 px-3 py-2 text-sky-100">美股 USD → 台幣帳戶 TWD</button>
              </div>
              <p className="text-slate-400">來源與目的地可自行選擇；跨幣別會自動啟用換匯，預填的估算值可改成銀行或券商實際入帳金額。</p>
            </div> : null}

            <label className="grid gap-1 text-xs text-slate-400">
              日期
              <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" type="date" value={form.movement_date} onChange={(event) => update('movement_date', event.target.value)} />
            </label>

            {mode === 'income' ? (
              <IncomeSourcePicker value={form.income_source} onChange={(value) => update('income_source', value)} />
            ) : null}

            {mode === 'transfer' || mode === 'expense' ? (
              <label className="grid gap-1 text-xs text-slate-400">
                從哪裡
                <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.from_bucket} onChange={(event) => update('from_bucket', event.target.value)}>
                  {(mode === 'expense' ? expenseSources : transferBuckets).map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
            ) : null}

            {mode === 'income' || mode === 'transfer' ? (
              <label className="grid gap-1 text-xs text-slate-400">
                放到哪裡
                <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.to_bucket} onChange={(event) => update('to_bucket', event.target.value)}>
                  {(mode === 'income' ? incomeDestinations : transferDestinations).map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
            ) : null}

            {mode === 'other' ? (
              <label className="grid gap-1 text-xs text-slate-400">
                類型
                <select className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.other_type} onChange={(event) => update('other_type', event.target.value)}>
                  {OTHER_TYPES.map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
            ) : null}

            {mode === 'expense' ? (
              <div className="grid gap-2 text-xs text-slate-400 sm:col-span-2 lg:col-span-6">
                <span>支出分類</span>
                <div className="flex flex-wrap gap-2">
                  {EXPENSE_TAGS.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => toggleExpenseTag(tag)}
                      aria-pressed={form.expense_tags.includes(tag)}
                      className={`rounded-full border px-3 py-1 text-xs transition hover:border-sky-400/70 hover:bg-sky-500/10 hover:text-white ${
                        form.expense_tags.includes(tag) ? 'border-sky-400 bg-sky-500/15 text-sky-100' : 'border-line bg-panel text-slate-300'
                      }`}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {mode === 'expense' ? (
              <div className="grid gap-2 sm:col-span-2 lg:col-span-6">
                <button
                  type="button"
                  onClick={() => setNoteOpen((open) => !open)}
                  className="flex min-h-0 w-fit items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300"
                  aria-expanded={noteOpen}
                >
                  <MessageSquareText size={14} />
                  {form.note ? '備註（已填寫）' : '備註'}
                </button>
                {noteOpen ? (
                  <input
                    autoFocus
                    className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
                    value={form.note}
                    onChange={(event) => update('note', event.target.value)}
                    placeholder="輸入備註"
                  />
                ) : null}
              </div>
            ) : null}

            <div className="grid gap-1 text-xs text-slate-400">
              {mode === 'transfer' ? `換出金額（${form.currency}）` : `金額（${form.currency}）`}
              <MobileNumericInput
                value={form.amount}
                onChange={(value) => update('amount', normalizeAmount(value))}
                label={amountLabel}
                subtitle={mode === 'expense' ? `從 ${form.from_bucket} 支出` : undefined}
                masked={hideAmounts}
                currency={form.currency}
                onCurrencyChange={(mode === 'transfer' && ACCOUNT_CURRENCY[form.from_bucket]) || (mode === 'income' && ACCOUNT_CURRENCY[form.to_bucket]) ? undefined : updateSourceCurrency}
                onComplete={mode === 'expense' ? saveMovement : undefined}
                primaryLabel={mode === 'expense' ? '完成並儲存' : '完成'}
                secondaryLabel={mode === 'expense' ? '完成並跳出' : undefined}
                statusMessage={
                  mode === 'expense'
                    ? message || (saving ? `背景送出中${queue.pending > 1 ? ` ${queue.pending} 筆` : ''}` : '')
                    : ''
                }
                busy={saving}
                allowZero={false}
              />
            </div>

            <label className="hidden max-w-20 gap-1 text-[11px] text-slate-500 sm:grid">
              幣別
              <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.currency} disabled={(mode === 'transfer' && Boolean(ACCOUNT_CURRENCY[form.from_bucket])) || (mode === 'income' && Boolean(ACCOUNT_CURRENCY[form.to_bucket]))} onChange={(event) => updateSourceCurrency(event.target.value)}>
                <option value="TWD">TWD</option>
                <option value="USD">USD</option>
              </select>
            </label>

            {mode === 'transfer' ? (
              <label className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-300">
                <input className="min-h-0" type="checkbox" checked={exchange} readOnly disabled />
                跨幣別換匯（兩邊金額分別入帳）
              </label>
            ) : null}

            {mode === 'transfer' && exchange ? (
              <>
                <div className="grid gap-1 text-xs text-slate-400">
                  實際入帳金額（{form.to_currency}）
                  <MobileNumericInput
                    value={form.to_amount}
                    onChange={(value) => {
                      setToAmountManual(true)
                      update('to_amount', normalizeAmount(value))
                    }}
                    label="實際入帳金額"
                    masked={hideAmounts}
                    currency={form.to_currency}
                    onCurrencyChange={ACCOUNT_CURRENCY[form.to_bucket] ? undefined : updateToCurrency}
                    allowZero={false}
                  />
                  <div className="flex items-center justify-between gap-2 text-[11px] text-slate-500">
                    <span>
                      {toAmountManual ? '已改為實際成交金額' : `依 USD/TWD ${Number(usdRate).toFixed(4)} 自動估算`}
                    </span>
                    {toAmountManual ? (
                      <button
                        type="button"
                        onClick={() => setToAmountManual(false)}
                        className="text-sky-300 transition hover:text-sky-100"
                      >
                        重新估算
                      </button>
                    ) : null}
                  </div>
                </div>
                <label className="hidden max-w-20 gap-1 text-[11px] text-slate-500 sm:grid">
                  換入幣別
                  <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.to_currency} disabled={Boolean(ACCOUNT_CURRENCY[form.to_bucket])} onChange={(event) => updateToCurrency(event.target.value)}>
                    <option value="USD">USD</option>
                    <option value="TWD">TWD</option>
                  </select>
                </label>
              </>
            ) : null}

            {mode === 'expense' ? (
              <div className="hidden sm:col-span-2 sm:block lg:col-span-6">
                <button type="button" aria-expanded={desktopKeypadOpen} onClick={() => setDesktopKeypadOpen(open => !open)} className="mb-2 rounded border border-line px-3 py-2 text-xs text-slate-300">{desktopKeypadOpen ? '收合數字鍵盤' : '開啟數字鍵盤'}</button>
                {desktopKeypadOpen ? <NumericKeypad
                  value={form.amount}
                  onChange={(value) => update('amount', normalizeAmount(value))}
                  masked={hideAmounts}
                currency={form.currency}
                  onCurrencyChange={ACCOUNT_CURRENCY[form.from_bucket] && mode === 'transfer' ? undefined : updateSourceCurrency}
                /> : null}
              </div>
            ) : null}

            {mode !== 'expense' ? (
              <label className="grid gap-1 text-xs text-slate-400 sm:col-span-2 lg:col-span-6">
                備註
                <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.note} onChange={(event) => update('note', event.target.value)} />
              </label>
            ) : null}

            <label className="flex items-center gap-2 text-xs text-slate-400 sm:col-span-2 lg:col-span-6"><input type="checkbox" checked={form.affects_balance !== false} onChange={event => update('affects_balance', event.target.checked)} />同步調整目前餘額（取消勾選只補歷史紀錄）</label>
            {mode === 'transfer' && Number(form.amount) > 0 ? <div className="rounded border border-sky-500/30 bg-panel p-3 text-sm text-sky-100 sm:col-span-2 lg:col-span-6">
              扣除 {form.from_bucket} {hideAmounts ? '••••' : money(Number(form.amount), form.currency)}
              <span className="mx-2">→</span>
              入帳 {form.to_bucket} {hideAmounts ? '••••' : money(exchange ? Number(form.to_amount) : Number(form.amount), exchange ? form.to_currency : form.currency)}
            </div> : null}
            {/* 按鈕不再因為儲存中而 disabled —— 可以直接打下一筆 */}
            <button className="flex items-center justify-center gap-2 rounded-md bg-sky-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-400 active:scale-[0.99] lg:col-span-1">
              儲存紀錄
            </button>

            {saving ? (
              <div className="flex items-center gap-1.5 text-xs text-slate-400 lg:col-span-5">
                <Loader2 size={13} className="animate-spin" />
                背景送出中{queue.pending > 1 ? ` ${queue.pending} 筆` : ''}
              </div>
            ) : null}

            {queue.failed.length ? (
              <div className="grid gap-1 rounded-md border border-rose-500/50 bg-rose-500/10 p-2 text-xs text-rose-100 lg:col-span-6">
                {queue.failed.map((item) => (
                  <div key={item.id} className="flex flex-wrap items-center gap-2">
                    <span className="flex-1">未存成功：{hideAmounts ? '金額已隱藏' : item.label}（{hideAmounts ? '請重試或重新讀取' : item.error}）</span>
                    <button type="button" onClick={() => queue.retry(item.id)} className="rounded border border-rose-300/60 px-2 py-0.5">重試</button>
                    <button type="button" onClick={() => queue.dismiss(item.id)} className="rounded border border-rose-300/30 px-2 py-0.5 text-rose-200/70">丟棄</button>
                  </div>
                ))}
              </div>
            ) : null}

            {message ? <div role="status" className={`text-xs lg:col-span-6 ${/大於|失敗|不正確/.test(message) ? 'text-rose-300' : 'text-sky-200'}`}>{message}</div> : null}
          </form>
        </div>
      ) : null}
    </section>
  )
}
