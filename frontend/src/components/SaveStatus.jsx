import { useAllSaves, saveQueue } from '../hooks/useSaveQueue'
import { useEffect } from 'react'
import { usePrivacy } from '../context/PrivacyContext'
export default function SaveStatus() {
  const jobs = useAllSaves()
  const { hideAmounts } = usePrivacy()
  useEffect(() => {
    if (!jobs.length) return undefined
    const guard = event => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [jobs.length])
  if (!jobs.length) return saveQueue.getLastSavedAt() ? <p role="status" className="mb-3 text-xs text-emerald-300">已儲存 · {new Date(saveQueue.getLastSavedAt()).toLocaleTimeString('zh-TW')}</p> : null
  const pending = jobs.filter(job => job.state !== 'failed')
  return <aside role="status" aria-live="polite" className="mb-4 grid gap-2 rounded-md border border-amber-500/40 bg-panel p-3 text-sm">
    {pending.length ? <p>儲存中 {pending.length} 筆，可繼續操作。關閉前請等候完成。</p> : null}
    {jobs.filter(job => job.state === 'failed').map(job => <div key={job.id} className="flex flex-wrap items-center gap-2 text-rose-200">
      <span className="flex-1">{hideAmounts ? '有一筆資料尚未儲存' : job.label || '有一筆資料尚未儲存'}：{hideAmounts ? '請重試或重新讀取資料' : job.error}</span>
      <button type="button" onClick={() => saveQueue.retry(job.id)} className="rounded border border-line px-3">重試</button>
      <button type="button" onClick={() => { if (window.confirm('確定移除這筆待確認操作？若先前已成功入帳，移除不會沖回，請至紀錄確認。')) saveQueue.dismiss(job.id) }} className="rounded border border-line px-3">移除待辦</button>
    </div>)}
  </aside>
}
