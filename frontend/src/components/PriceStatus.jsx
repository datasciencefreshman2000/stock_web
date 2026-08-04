export default function PriceStatus({ status }) {
  if (!status) return null

  const providers = status.providers?.length ? status.providers.join(' / ') : null

  return (
    <div className="rounded-md border border-line bg-surface px-4 py-3 text-sm text-slate-300">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span>快取 {status.cached ?? 0} 檔</span>
        <span>新抓 {status.fetched ?? 0} 檔</span>
        {status.missing ? <span>無快取 {status.missing} 檔</span> : null}
        {status.failed ? <span className="text-amber-300">失敗 {status.failed} 檔</span> : null}
        {providers ? <span className="text-slate-500">來源 {providers}</span> : null}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-slate-500">
        {status.finished_at ? (
          <span>最後抓價：{new Date(status.finished_at).toLocaleString('zh-TW')}</span>
        ) : null}
        {status.usd_rate ? (
          <span>
            匯率 {Number(status.usd_rate).toFixed(2)}
            {status.usd_rate_fetched_at
              ? `（${new Date(status.usd_rate_fetched_at).toLocaleString('zh-TW')}）`
              : ''}
          </span>
        ) : null}
      </div>
    </div>
  )
}
