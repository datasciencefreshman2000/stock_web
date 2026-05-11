import { api } from '../api/client'
import { useAsync } from './useAsync'

export function usePortfolio(account, refreshToken = 0) {
  return useAsync(() => api.getPortfolio(account, refreshToken > 0), [account, refreshToken])
}
