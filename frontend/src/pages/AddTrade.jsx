import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import TradeForm from '../components/TradeForm'
import { api } from '../api/client'

export default function AddTrade() {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(payload) {
    setSubmitting(true)
    setError('')
    try {
      await api.addTrade(payload)
      navigate('/holdings')
    } catch (err) {
      setError(err.message)
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
      <TradeForm onSubmit={submit} submitting={submitting} />
    </div>
  )
}
