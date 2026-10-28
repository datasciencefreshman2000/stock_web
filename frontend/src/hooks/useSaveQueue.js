import { useSyncExternalStore } from 'react'
import { api } from '../api/client'
import { queryClient } from '../lib/queryClient'
import { createSaveQueue } from '../lib/saveQueue'
let storage
try { storage = localStorage } catch { /* unavailable */ }
export const saveQueue = createSaveQueue({ storage,
  send(kind, payload) {
    if (kind === 'movement') return api.createCapitalMovement(payload)
    if (kind === 'cash') return api.updateCash(payload.id, payload.amount, payload.currency, payload)
    if (kind === 'cash-create') return api.createCash(payload)
    if (kind === 'value') return api.updateManualValue(payload.key, payload.value, payload)
    throw new Error('未知的儲存項目')
  },
  onSaved: () => queryClient.invalidateQueries(),
})
export function useSaveQueue(_sender, _onDrained, kind = 'movement') {
  const jobs = useSyncExternalStore(saveQueue.subscribe, saveQueue.getSnapshot)
  return { enqueue: (payload, label = '') => saveQueue.enqueue(kind, payload, label),
    pending: jobs.filter(job => job.kind === kind && job.state !== 'failed').length,
    failed: jobs.filter(job => job.kind === kind && job.state === 'failed'), retry: saveQueue.retry, dismiss: saveQueue.dismiss }
}
export function useAllSaves() { return useSyncExternalStore(saveQueue.subscribe, saveQueue.getSnapshot) }
