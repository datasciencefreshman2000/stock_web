// 持倉表格欄位定義
export const ALL_COLUMNS = [
  { key: 'ticker', label: '代號', align: 'left' },
  { key: 'qty', label: '股數' },
  { key: 'avg_price', label: '均價' },
  { key: 'current_price', label: '現價' },
  { key: 'market_value', label: '市值' },
  { key: 'pnl', label: '損益' },
  { key: 'pnl_pct', label: '損益%' },
  { key: 'weight', label: '佔比' },
]

export const MOBILE_SORT_KEYS = ['market_value', 'pnl_pct', 'ticker']
export const COMPACT_COLUMNS = ['ticker', 'market_value', 'pnl', 'pnl_pct', 'weight']
