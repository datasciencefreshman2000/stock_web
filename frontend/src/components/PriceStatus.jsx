export default function PriceStatus({ status }) {
  if (!status) return null

  const providers = status.providers?.length ? status.providers.join(' / ') : null

  return (
    <div className="rounded-md border border-line bg-surface px-4 py-3 text-sm text-slate-300">
      <div className="mb-2 text-xs text-slate-400">報價時間：{status.oldest_quote_at ? new Date(status.oldest_quote_at).toLocaleString('zh-TW') : '尚無有效報價時間'}{status.rate_is_estimated ? <span className="ml-2 text-amber-200">匯率為備用估計值，請刷新後確認。</span> : null}</div>
      {(status.quotes || []).some(row => !row.has_price) ? <p role="alert" className="mb-2 text-amber-200">缺價標的：{status.quotes.filter(row => !row.has_price).map(row => row.symbol).join('、')}</p> : null}
      {status.failed_symbols?.length ? <p role="alert" className="mb-2 text-amber-200">本次更新失敗：{status.failed_symbols.join('、')}。已有報價的標的沿用上次價格，可稍後重試。</p> : null}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span>沿用報價 {status.cached ?? 0} 檔</span>
        <span>本次更新 {status.fetched ?? 0} 檔</span>
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
