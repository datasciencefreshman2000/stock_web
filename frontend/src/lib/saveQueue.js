/** The operation ID survives failures and reloads. No React state-updater side effects. */
export function createSaveQueue({ storage, send, onSaved = () => {}, key = 'stock_web_pending_operations' }) {
  let jobs = [], running = false, generation = 0, lastSavedAt = null
  const listeners = new Set()
  try { jobs = JSON.parse(storage?.getItem(key) || '[]').map(job => ({ ...job, state: 'failed', error: '上次尚未確認儲存結果，請重試。' })) } catch { jobs = [] }
  let snapshot = jobs
  const publish = () => {
    snapshot = [...jobs]
    try { storage?.setItem(key, JSON.stringify(jobs)) } catch { /* memory-only */ }
    listeners.forEach(fn => fn())
  }
  async function drain() {
    if (running) return
    running = true
    const currentGeneration = generation
    let saved = false
    try {
      while (currentGeneration === generation) {
        const job = jobs.find(item => item.state === 'pending')
        if (!job) break
        job.state = 'sending'; publish()
        try {
          await send(job.kind, job.payload)
          if (currentGeneration !== generation) break
          jobs = jobs.filter(item => item.id !== job.id); saved = true; lastSavedAt = Date.now()
        } catch (error) {
          if (currentGeneration !== generation) break
          job.state = 'failed'; job.error = error?.message || '儲存失敗'
        }
        publish()
      }
    } finally {
      running = false
      if (saved && currentGeneration === generation) { try { await onSaved() } catch { /* committed writes remain successful; reads can retry */ } }
      if (jobs.some(job => job.state === 'pending')) void drain()
    }
  }
  return {
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn) },
    getSnapshot: () => snapshot,
    getLastSavedAt: () => lastSavedAt,
    enqueue(kind, payload, label = '') {
      const id = payload.operation_id || crypto.randomUUID()
      if (jobs.some(job => job.id === id)) return id
      jobs.push({ id, kind, payload: { ...payload, operation_id: id }, label, state: 'pending' })
      publish(); void drain(); return id
    },
    retry(id) { const job = jobs.find(item => item.id === id && item.state === 'failed'); if (!job) return; job.state = 'pending'; job.error = ''; publish(); void drain() },
    dismiss(id) { jobs = jobs.filter(item => item.id !== id || item.state !== 'failed'); publish() },
    clear() { generation += 1; jobs = []; lastSavedAt = null; publish() },
  }
}
