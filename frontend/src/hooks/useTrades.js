import { api } from '../api/client'
import { useAsync } from './useAsync'

export function useTrades(account, filters) {
  return useAsync(() => api.getTrades(account, filters), [
    account,
    filters.ticker,
    filters.start_date,
    filters.end_date,
  ])
}
