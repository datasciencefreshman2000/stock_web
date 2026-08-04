import { useState } from 'react'

import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    if (!password || busy) return
    setBusy(true)
    setError('')
    try {
      await login(password)
    } catch (err) {
      setError(err.message || '登入失敗')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-[#0b1020] px-4 text-slate-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl shadow-slate-950/50"
      >
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg border border-sky-400/40 bg-sky-500/15 text-base font-semibold text-sky-100">
            蔡
          </div>
          <div className="leading-tight">
            <div className="text-base font-semibold text-white">蔡加恩的金庫</div>
            <div className="text-[11px] text-slate-500">stock vault</div>
          </div>
        </div>

        <label htmlFor="password" className="mb-2 block text-sm text-slate-400">
          密碼
        </label>
        <input
          id="password"
          type="password"
          autoFocus
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2.5 text-slate-100 outline-none transition focus:border-sky-500"
        />

        {error ? <p className="mt-3 text-sm text-rose-400">{error}</p> : null}

        <button
          type="submit"
          disabled={busy || !password}
          className="mt-5 w-full rounded-lg bg-sky-600 px-4 py-2.5 font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? '登入中…' : '登入'}
        </button>
      </form>
    </div>
  )
}
