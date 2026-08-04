import { useState } from 'react'

import TradeForm from '../components/TradeForm'
import { useTradeMutations } from '../hooks/queries'

export default function AddTrade() {
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const { add } = useTradeMutations()
  const submitting = add.isPending

  async function submit(payload) {
    setError('')
    setMessage('')
    try {
      // 成功後 useTradeMutations 會讓總覽 / 持倉 / 紀錄的快取失效
      await add.mutateAsync(payload)
      setMessage('已新增交易。')
      return true
    } catch (err) {
      setError(err.message)
      return false
    }
  }

  return (
    <div className="grid gap-5">
      <header>
        <h1 className="text-2xl font-semibold">新增交易</h1>
      </header>
      {error ? <div className="soft-pop rounded-md border border-rose-900 bg-rose-950/40 p-4 text-rose-100">{error}</div> : null}
      {message ? <div className="soft-pop rounded-md border border-emerald-900 bg-emerald-950/40 p-4 text-emerald-100">{message}</div> : null}
      <TradeForm onSubmit={submit} submitting={submitting} />
    </div>
  )
}
