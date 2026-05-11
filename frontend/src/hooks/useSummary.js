import { api } from '../api/client'
import { useAsync } from './useAsync'

export function useSummary(refreshToken = 0) {
  return useAsync(() => api.getSummary(refreshToken > 0), [refreshToken])
}
