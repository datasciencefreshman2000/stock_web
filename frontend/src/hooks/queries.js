import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import { queryKeys } from '../lib/queryClient'

// --- 讀取 -----------------------------------------------------------------

export function useSummaryQuery() {
  return useQuery({ queryKey: queryKeys.summary, queryFn: api.getSummary })
}

export function usePortfolioQuery(account, enabled = true) {
  return useQuery({
    queryKey: queryKeys.portfolio(account),
    queryFn: () => api.getPortfolio(account),
    enabled,
  })
}

/** 單一標的的買入明細。FIFO 由後端計算，前端只負責顯示。 */
export function useBuyLotsQuery(account, ticker) {
  return useQuery({
    queryKey: queryKeys.buyLots(account, ticker),
    queryFn: () => api.getBuyLots(account, ticker),
    enabled: Boolean(account && ticker),
  })
}

export function useTradesQuery(account, params = {}, enabled = true) {
  return useQuery({
    queryKey: queryKeys.trades(account, params),
    queryFn: () => api.getTrades(account, params),
    enabled,
  })
}

export function useTradeTickersQuery(account) {
  return useQuery({
    queryKey: queryKeys.tradeTickers(account),
    queryFn: () => api.getTradeTickers(account),
    enabled: Boolean(account),
    staleTime: 30 * 60 * 1000,
  })
}

export function useManualQuery() {
  return useQuery({ queryKey: queryKeys.manual, queryFn: api.getManual })
}

export function useCapitalMovementsQuery(month) {
  return useQuery({
    queryKey: queryKeys.capitalMovements(month),
    queryFn: () => api.getCapitalMovements(month),
    enabled: Boolean(month),
  })
}

export function useCapitalMovementOptionsQuery(category = 'income_source') {
  return useQuery({
    queryKey: queryKeys.capitalMovementOptions(category),
    queryFn: () => api.getCapitalMovementOptions(category),
  })
}

// --- 寫入 -----------------------------------------------------------------

/**
 * 依「實際改了什麼」決定要失效哪些 query。
 *
 * 之前這裡不分青紅皂白讓四組全部失效，造成現金頁每改一個欄位
 * 就重打 summary + portfolio + trades + manual，而 summary 的快取
 * 又被後端刪掉了，於是每次都要完整重算（約 16 次 DB 往返）。
 * 改 5 個欄位就是 110 次往返、7–13 秒。
 *
 * scope 說明：
 *   'cash'    現金餘額      → 影響 summary 與 manual，不影響 trades
 *   'manual'  基金/投資項目  → 同上
 *   'trades'  交易紀錄      → 影響全部（FIFO 會變）
 *   'all'     不確定時的保險
 */
const SCOPE_KEYS = {
  cash: [
    { queryKey: queryKeys.summary, exact: true },
    { queryKey: ['portfolio'] },
    { queryKey: queryKeys.manual, exact: true },
  ],
  manual: [
    { queryKey: queryKeys.summary, exact: true },
    { queryKey: ['portfolio'] },
    { queryKey: queryKeys.manual, exact: true },
  ],
  movement: [
    { queryKey: queryKeys.summary, exact: true },
    { queryKey: ['portfolio'] },
    { queryKey: queryKeys.manual, exact: true },
    { queryKey: ['capital-movements'] },
  ],
  trades: [
    { queryKey: queryKeys.summary, exact: true },
    { queryKey: ['portfolio'] },
    { queryKey: ['trades'] },
    { queryKey: ['trade-tickers'] },
  ],
}
SCOPE_KEYS.all = Object.values(SCOPE_KEYS).flat()

export function useInvalidateMoney() {
  const client = useQueryClient()
  return useCallback(async (scope = 'all') => {
    const scopes = Array.isArray(scope) ? scope : [scope]
    const unique = new Map()
    scopes.forEach((name) => {
      const entries = SCOPE_KEYS[name] || SCOPE_KEYS.all
      entries.forEach((entry) => unique.set(`${entry.queryKey.join('|')}:${entry.exact || false}`, entry))
    })
    const entries = [...unique.values()]
    await Promise.all(entries.map((entry) => client.invalidateQueries(entry)))
    // 換頁時可能沿用 staleTime 內的舊結果，把非作用中的直接丟掉
    entries.forEach((entry) => client.removeQueries({ ...entry, type: 'inactive' }))
  }, [client])
}

/**
 * 延遲並合併失效 —— 連續輸入時不要每筆都等重算。
 *
 * 呼叫後不會立刻失效，而是排一個計時器；期間內再次呼叫會把計時器重設。
 * 所以連續記 10 筆支出只會在最後停手後觸發「一次」重算。
 *
 * 回傳：
 *   schedule(scope)  排定一次延遲失效
 *   flush()          立刻執行（例如離開頁面前）
 *   pending          是否還有排隊中的更新（可拿來顯示「同步中」）
 */
export function useDeferredInvalidate(delay = 1500) {
  const invalidate = useInvalidateMoney()
  const timerRef = useRef(null)
  const scopesRef = useRef(new Set())
  const [pending, setPending] = useState(false)

  const run = useCallback(async () => {
    timerRef.current = null
    setPending(false)
    const scopes = [...scopesRef.current]
    scopesRef.current.clear()
    await invalidate(scopes.length ? scopes : 'all')
  }, [invalidate])

  const schedule = useCallback((scope = 'all') => {
    scopesRef.current.add(scope)
    setPending(true)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(run, delay)
  }, [run, delay])

  const flush = useCallback(async () => {
    if (!timerRef.current) return
    clearTimeout(timerRef.current)
    await run()
  }, [run])

  // 離開頁面時把還沒送出的失效補做掉
  useEffect(() => () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
      const scopes = [...scopesRef.current]
      scopesRef.current.clear()
      void invalidate(scopes.length ? scopes : 'all')
    }
  }, [invalidate])

  return { schedule, flush, pending }
}

export function useTradeMutations() {
  const invalidate = useInvalidateMoney()

  const add = useMutation({ mutationFn: api.addTrade, onSuccess: () => invalidate('trades') })
  const update = useMutation({
    mutationFn: ({ id, data }) => api.updateTrade(id, data),
    onSuccess: () => invalidate('trades'),
  })
  const remove = useMutation({ mutationFn: api.deleteTrade, onSuccess: () => invalidate('trades') })

  return { add, update, remove }
}

export function useManualMutations() {
  const invalidate = useInvalidateMoney()

  return {
    updateValue: useMutation({
      mutationFn: ({ key, value }) => api.updateManualValue(key, value),
      onSuccess: () => invalidate('manual'),
    }),
    updateCash: useMutation({
      mutationFn: ({ id, amount, currency }) => api.updateCash(id, amount, currency),
      onSuccess: () => invalidate('cash'),
    }),
    createCash: useMutation({ mutationFn: api.createCash, onSuccess: () => invalidate('cash') }),
    createInvestment: useMutation({ mutationFn: api.createInvestment, onSuccess: () => invalidate('manual') }),
    updateInvestment: useMutation({
      mutationFn: ({ id, data }) => api.updateInvestment(id, data),
      onSuccess: () => invalidate('manual'),
    }),
    deleteInvestment: useMutation({ mutationFn: api.deleteInvestment, onSuccess: () => invalidate('manual') }),
    createCapitalMovement: useMutation({
      mutationFn: api.createCapitalMovement,
      onSuccess: () => invalidate('movement'),
    }),
  }
}

/** 手動刷新：等後端抓完價、重算完，再讓所有快取失效。 */
export function useRefreshAll() {
  const invalidate = useInvalidateMoney()
  const mutation = useMutation({ mutationFn: api.refreshAll, onSuccess: () => invalidate('all') })

  return {
    refreshing: mutation.isPending,
    error: mutation.error,
    refreshNow: () => mutation.mutate(),
  }
}
