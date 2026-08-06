import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, Loader2, MessageSquareText } from 'lucide-react'

import { api } from '../../api/client'
import { useSaveQueue } from '../../hooks/useSaveQueue'
import { ACCOUNTS } from '../../constants'
import IncomeSourcePicker from './IncomeSourcePicker'
import MobileNumericInput from './MobileNumericInput'
import NumericKeypad from './NumericKeypad'
import { CREDIT_CARD_DEBT, EXPENSE_TAGS, INCOME_SOURCES, ON_HAND_CASH, OTHER_TYPES, today } from './constants'

function unique(items) {
  return [...new Set(items.filter(Boolean))]
}

export default function CapitalMovementPanel({ bankNames, positiveBankNames, onSaved,
                                               openSignal = 0, openMode = null }) {
  const [panelOpen, setPanelOpen] = useState(false)
  const [mode, setMode] = useState('income')

  // 外部（例如現金頁的「記帳」按鈕）要求展開並切到指定模式。
  // 用遞增的 openSignal 當觸發，這樣連按也有效。
  useEffect(() => {
    if (!openSignal) return
    setPanelOpen(true)
    if (openMode) setMode(openMode)
  }, [openSignal, openMode])
  const [exchange, setExchange] = useState(false)
  const [noteOpen, setNoteOpen] = useState(false)
  const [form, setForm] = useState({
    movement_date: today,
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
  })
  const [message, setMessage] = useState('')
  // 送出不擋畫面：按下去就排隊，表單立刻清空可以打下一筆。
  // 送出本身仍維持序列（餘額是讀-改-寫，並行會互相覆蓋）。
  const queue = useSaveQueue(api.createCapitalMovement, () => onSaved?.())
  const saving = queue.pending > 0

  const incomeDestinations = useMemo(() => unique([...bankNames, ON_HAND_CASH, ACCOUNTS[0]]), [bankNames])
  const transferBuckets = useMemo(() => unique([...bankNames, ON_HAND_CASH, ACCOUNTS[0], ACCOUNTS[1]]), [bankNames])
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

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

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

  function saveMovement() {
    setMessage('')
    try {
      const amount = Number(form.amount)
      if (!Number.isFinite(amount) || amount <= 0) throw new Error('請輸入大於 0 的金額')
      if (exchange && mode === 'transfer' && Number(form.to_amount) <= 0) {
        throw new Error('請輸入大於 0 的換入金額')
      }

      let payload = {
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
        payload = { ...payload, to_bucket: form.other_type, note: noteWithTag(form.other_type, form.note) }
      }

      // 排進佇列就回來，不等網路
      queue.enqueue(payload, `${payload.to_bucket} ${payload.amount}`)
      setNoteOpen(false)
      setForm((current) => ({ ...current, amount: '', to_amount: '', note: '', expense_tags: ['其他'] }))
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

  const amountLabel = mode === 'income' ? '收入金額' : mode === 'transfer' ? '調動金額' : mode === 'expense' ? '支出金額' : '其他金額'

  return (
    <section className="overflow-hidden rounded-md border border-line bg-surface">
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
        <div className="border-t border-line">
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
                <span>支出 tag</span>
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
              金額
              <MobileNumericInput
                value={form.amount}
                onChange={(value) => update('amount', normalizeAmount(value))}
                label={amountLabel}
                subtitle={mode === 'expense' ? `從 ${form.from_bucket} 支出` : undefined}
                currency={form.currency}
                onCurrencyChange={(value) => update('currency', value)}
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
              <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.currency} onChange={(event) => update('currency', event.target.value)}>
                <option value="TWD">TWD</option>
                <option value="USD">USD</option>
              </select>
            </label>

            {mode === 'transfer' ? (
              <label className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-300">
                <input className="min-h-0" type="checkbox" checked={exchange} onChange={(event) => setExchange(event.target.checked)} />
                換匯
              </label>
            ) : null}

            {mode === 'transfer' && exchange ? (
              <>
                <div className="grid gap-1 text-xs text-slate-400">
                  換入金額
                  <MobileNumericInput
                    value={form.to_amount}
                    onChange={(value) => update('to_amount', normalizeAmount(value))}
                    label="換入金額"
                    currency={form.to_currency}
                    onCurrencyChange={(value) => update('to_currency', value)}
                    allowZero={false}
                  />
                </div>
                <label className="hidden max-w-20 gap-1 text-[11px] text-slate-500 sm:grid">
                  換入幣別
                  <select className="rounded-md border border-line bg-[#0b1020] px-2 py-1.5 text-xs text-white" value={form.to_currency} onChange={(event) => update('to_currency', event.target.value)}>
                    <option value="USD">USD</option>
                    <option value="TWD">TWD</option>
                  </select>
                </label>
              </>
            ) : null}

            {mode === 'expense' ? (
              <div className="hidden sm:col-span-2 sm:block lg:col-span-6">
                <NumericKeypad
                  value={form.amount}
                  onChange={(value) => update('amount', normalizeAmount(value))}
                  currency={form.currency}
                  onCurrencyChange={(value) => update('currency', value)}
                />
              </div>
            ) : null}

            {mode !== 'expense' ? (
              <label className="grid gap-1 text-xs text-slate-400 sm:col-span-2 lg:col-span-6">
                備註
                <input className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white" value={form.note} onChange={(event) => update('note', event.target.value)} />
              </label>
            ) : null}

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
                    <span className="flex-1">未存成功：{item.label}（{item.error}）</span>
                    <button type="button" onClick={() => queue.retry(item.id)} className="rounded border border-rose-300/60 px-2 py-0.5">重試</button>
                    <button type="button" onClick={() => queue.dismiss(item.id)} className="rounded border border-rose-300/30 px-2 py-0.5 text-rose-200/70">丟棄</button>
                  </div>
                ))}
              </div>
            ) : null}

            {message ? <div className="text-xs text-rose-300 lg:col-span-6">{message}</div> : null}
          </form>
        </div>
      ) : null}
    </section>
  )
}
