export default function ValuationNotice({ data }) {
  if (data?.valuation_complete !== false) return null
  const missing = (data.missing_prices || []).map(item => typeof item === 'string' ? item : `${item.account} ${item.ticker}`)
  return <div role="alert" className="rounded-md border border-amber-500/60 bg-amber-950/30 p-3 text-sm text-amber-100">估值不完整：{missing.join('、') || '部分持倉'} 缺少報價。總資產及損益暫不顯示，避免把缺價當成虧損；可按刷新股價重試。</div>
}
