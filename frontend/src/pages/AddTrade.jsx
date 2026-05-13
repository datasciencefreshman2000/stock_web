import { useState } from 'react'

import TradeForm from '../components/TradeForm'
import { api } from '../api/client'

export default function AddTrade() {
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(payload) {
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      await api.addTrade(payload)
      setMessage('已新增交易。')
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid gap-5">
      <header>
        <h1 className="text-2xl font-semibold">新增交易</h1>
      </header>
      {error ? <div className="rounded-md border border-rose-900 bg-rose-950/40 p-4 text-rose-100">{error}</div> : null}
      {message ? <div className="rounded-md border border-emerald-900 bg-emerald-950/40 p-4 text-emerald-100">{message}</div> : null}
      <TradeForm onSubmit={submit} submitting={submitting} />
    </div>
  )
}
