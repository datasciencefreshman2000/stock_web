export default function PriceStatus({ status }) {
  if (!status) return null

  return (
    <div className="rounded-md border border-line bg-surface px-4 py-3 text-sm text-slate-300">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span>快取 {status.cache_size ?? 0} 檔</span>
        <span>本次快取 {status.last_cached ?? 0} 檔</span>
        <span>本次新抓 {status.last_fetched ?? 0} 檔</span>
        <span>無快取 {status.last_missing ?? 0} 檔</span>
        <span>失敗 {status.last_failed ?? 0} 檔</span>
        {status.in_progress ? <span className="text-sky-300">抓價中</span> : null}
      </div>
      {status.last_finished_at ? (
        <div className="mt-1 text-xs text-slate-500">最後刷新：{new Date(status.last_finished_at).toLocaleString()}</div>
      ) : null}
    </div>
  )
}
