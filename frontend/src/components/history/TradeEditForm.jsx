import { Save, X } from 'lucide-react'

import { ACCOUNTS } from '../../constants'
import MobileNumericInput from '../cash/MobileNumericInput'
import { isTwTradeForm } from '../../utils/trades'
import { number } from '../../utils/format'

export default function TradeEditForm({ form, onChange, onSubmit, onCancel, saving, hideAmounts }) {
  const isTw = isTwTradeForm(form)

  return (
    <form onSubmit={onSubmit} className="grid gap-3 rounded-md border border-sky-500/40 bg-panel/70 p-3">
      <div className="grid gap-2 sm:grid-cols-[0.9fr_0.9fr_1fr_0.9fr_0.8fr_0.8fr]">
        <label className="grid gap-1 text-xs text-slate-400">
          帳戶
          <select
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
            value={form.account}
            onChange={(event) => onChange('account', event.target.value)}
            disabled={saving}
          >
            {ACCOUNTS.map((account) => (
              <option key={account} value={account}>{account}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs text-slate-400">
          代號
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
            value={form.ticker}
            onChange={(event) => onChange('ticker', event.target.value.toUpperCase())}
            disabled={saving}
            required
          />
        </label>
        <label className="grid gap-1 text-xs text-slate-400">
          日期
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
            type="date"
            value={form.date}
            onChange={(event) => onChange('date', event.target.value)}
            disabled={saving}
            required
          />
        </label>
        <div className="grid gap-1 text-xs text-slate-400">
          <span>買賣</span>
          <div className="grid grid-cols-2 gap-1">
            {[
              ['buy', '買'],
              ['sell', '賣'],
            ].map(([side, label]) => (
              <button
                key={side}
                type="button"
                onClick={() => onChange('side', side)}
                disabled={saving}
                className={`rounded-md border px-2 py-2 text-sm font-medium ${
                  form.side === side
                    ? side === 'buy'
                      ? 'border-emerald-400/70 bg-emerald-500/15 text-emerald-100'
                      : 'border-rose-400/70 bg-rose-500/15 text-rose-100'
                    : 'border-line bg-[#0b1020] text-slate-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-1 text-xs text-slate-400">
          股數
          <MobileNumericInput
            value={form.qty}
            onChange={(value) => onChange('qty', value)}
            label="股數"
            currency="股"
            maxDecimals={4}
            allowZero={false}
            disabled={saving}
          />
        </div>
        <div className="grid gap-1 text-xs text-slate-400">
          價格
          <MobileNumericInput
            value={form.price}
            onChange={(value) => onChange('price', value)}
            label="價格"
            currency={isTw ? 'TWD' : 'USD'}
            maxDecimals={4}
            allowZero={false}
            masked={hideAmounts}
            disabled={saving}
          />
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-[0.8fr_minmax(0,1fr)_auto] sm:items-end">
        <div className="grid gap-1 text-xs text-slate-400">
          手續費
          <MobileNumericInput
            value={isTw ? '' : form.fee}
            onChange={(value) => onChange('fee', value)}
            label="手續費"
            currency={isTw ? 'TWD' : 'USD'}
            masked={hideAmounts}
            disabled={saving || isTw}
          />
        </div>
        <label className="grid gap-1 text-xs text-slate-400">
          備註
          <input
            className="rounded-md border border-line bg-[#0b1020] px-3 py-2 text-sm text-white"
            value={form.note}
            onChange={(event) => onChange('note', event.target.value)}
            disabled={saving}
          />
        </label>
        <div className="flex justify-end gap-2">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/70 bg-emerald-500/15 px-3 py-2 text-sm text-emerald-100 disabled:opacity-50"
          >
            <Save size={15} />
            儲存
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-2 text-sm text-slate-300 hover:border-sky-500 hover:text-white disabled:opacity-50"
          >
            <X size={15} />
            取消
          </button>
        </div>
      </div>
    </form>
  )
}
