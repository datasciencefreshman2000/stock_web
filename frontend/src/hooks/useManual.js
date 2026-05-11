import { api } from '../api/client'
import { useAsync } from './useAsync'

export function useManual() {
  return useAsync(() => api.getManual(), [])
}
