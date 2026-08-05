import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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

export function useManualQuery() {
  return useQuery({ queryKey: queryKeys.manual, queryFn: api.getManual })
}

export function useCapitalMovementsQuery() {
  return useQuery({ queryKey: queryKeys.capitalMovements, queryFn: api.getCapitalMovements })
}

export function useCapitalMovementOptionsQuery(category = 'income_source') {
  return useQuery({
    queryKey: queryKeys.capitalMovementOptions(category),
    queryFn: () => api.getCapitalMovementOptions(category),
  })
}

// --- 寫入 -----------------------------------------------------------------

/**
 * 任何會影響金額的寫入都要讓相關快取失效。
 * 後端在交易異動時也會清掉 summary_cache 與 FIFO checkpoint，
 * 前端這邊只是讓畫面跟著重讀。
 */
export function useInvalidateMoney() {
  const client = useQueryClient()
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['summary'] }),
      client.invalidateQueries({ queryKey: ['portfolio'] }),
      client.invalidateQueries({ queryKey: ['trades'] }),
      client.invalidateQueries({ queryKey: ['manual'], exact: true }),
      client.invalidateQueries({ queryKey: ['manual', 'capital-movements'] }),
    ])

    // Route changes can otherwise reuse an inactive pre-save result during staleTime.
    const inactiveKeys = [['summary'], ['portfolio'], ['trades'], ['manual']]
    inactiveKeys.forEach((queryKey) => {
      client.removeQueries({ queryKey, type: 'inactive' })
    })
  }
}

export function useTradeMutations() {
  const invalidate = useInvalidateMoney()

  const add = useMutation({ mutationFn: api.addTrade, onSuccess: invalidate })
  const update = useMutation({
    mutationFn: ({ id, data }) => api.updateTrade(id, data),
    onSuccess: invalidate,
  })
  const remove = useMutation({ mutationFn: api.deleteTrade, onSuccess: invalidate })

  return { add, update, remove }
}

export function useManualMutations() {
  const invalidate = useInvalidateMoney()

  return {
    updateValue: useMutation({
      mutationFn: ({ key, value }) => api.updateManualValue(key, value),
      onSuccess: invalidate,
    }),
    updateCash: useMutation({
      mutationFn: ({ id, amount, currency }) => api.updateCash(id, amount, currency),
      onSuccess: invalidate,
    }),
    createCash: useMutation({ mutationFn: api.createCash, onSuccess: invalidate }),
    createInvestment: useMutation({ mutationFn: api.createInvestment, onSuccess: invalidate }),
    updateInvestment: useMutation({
      mutationFn: ({ id, data }) => api.updateInvestment(id, data),
      onSuccess: invalidate,
    }),
    deleteInvestment: useMutation({ mutationFn: api.deleteInvestment, onSuccess: invalidate }),
    createCapitalMovement: useMutation({
      mutationFn: api.createCapitalMovement,
      onSuccess: invalidate,
    }),
  }
}

/** 手動刷新：等後端抓完價、重算完，再讓所有快取失效。 */
export function useRefreshAll() {
  const invalidate = useInvalidateMoney()
  const mutation = useMutation({ mutationFn: api.refreshAll, onSuccess: invalidate })

  return {
    refreshing: mutation.isPending,
    error: mutation.error,
    refreshNow: () => mutation.mutate(),
  }
}
