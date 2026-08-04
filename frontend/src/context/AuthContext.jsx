import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api, auth } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [status, setStatus] = useState(auth.getToken() ? 'checking' : 'signed-out')
  const queryClient = useQueryClient()

  // token 失效時（後端回 401）自動退回登入畫面，並清掉快取裡的資料
  useEffect(
    () =>
      auth.onUnauthorized(() => {
        queryClient.clear()
        setStatus('signed-out')
      }),
    [queryClient],
  )

  // 開站時驗證一次既有 token 還有沒有效
  useEffect(() => {
    if (status !== 'checking') return
    let cancelled = false
    api
      .me()
      .then(() => !cancelled && setStatus('signed-in'))
      .catch(() => !cancelled && setStatus('signed-out'))
    return () => {
      cancelled = true
    }
  }, [status])

  const login = useCallback(async (password) => {
    await api.login(password)
    setStatus('signed-in')
  }, [])

  const logout = useCallback(() => {
    api.logout()
    queryClient.clear()
    setStatus('signed-out')
  }, [queryClient])

  const value = useMemo(() => ({ status, login, logout }), [status, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
