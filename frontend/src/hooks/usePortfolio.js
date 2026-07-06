import { api } from '../api/client'
import { useAsync } from './useAsync'

export function usePortfolio(account, refreshToken = 0, refreshPrices = false, enabled = true) {
  return useAsync(
    () => (enabled ? api.getPortfolio(account, refreshPrices) : Promise.resolve(null)),
    [account, refreshToken, refreshPrices, enabled],
  )
}
