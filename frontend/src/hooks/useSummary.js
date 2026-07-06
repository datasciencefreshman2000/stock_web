import { api } from '../api/client'
import { useAsync } from './useAsync'

export function useSummary(refreshToken = 0, refreshPrices = false) {
  return useAsync(() => api.getSummary(refreshPrices), [refreshToken, refreshPrices])
}
