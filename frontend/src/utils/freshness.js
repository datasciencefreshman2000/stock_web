/**
 * 把時間戳換成「幾分鐘前」，並依新舊程度給顏色。
 *
 * 為什麼需要：只顯示「快取 12:00:43」看不出資料是新是舊，
 * 你得自己心算現在幾點、再回想 cron 設定。顯示「32 分鐘前」直觀得多。
 */

export function minutesSince(timestamp) {
  if (!timestamp) return null
  const then = new Date(timestamp).getTime()
  if (!Number.isFinite(then)) return null
  return Math.max(0, Math.round((Date.now() - then) / 60000))
}

export function freshnessLabel(timestamp) {
  const mins = minutesSince(timestamp)
  if (mins === null) return null
  if (mins < 1) return '剛剛'
  if (mins < 60) return `${mins} 分鐘前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小時前`
  return `${Math.floor(hours / 24)} 天前`
}

/**
 * 依「資料多舊」給顏色。門檻對應台股盤中的更新節奏：
 *   < 15 分   正常
 *   15–45 分  有點舊
 *   > 45 分   明顯過期（多半是排程空窗）
 */
export function freshnessClass(timestamp) {
  const mins = minutesSince(timestamp)
  if (mins === null) return 'text-slate-500'
  if (mins < 15) return 'text-emerald-400'
  if (mins < 45) return 'text-amber-400'
  return 'text-rose-400'
}

export function formatStamp(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-TW', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}
