// 手動投資項目的金額換算（後端已算好 *_twd，這裡只做向下相容的 fallback）
export function investmentValueTwd(row) {
  return Number(row.value_twd ?? row.value ?? 0)
}

export function investmentCashTwd(row) {
  return Number(row.cash_amount_twd ?? row.cash_amount ?? 0)
}

export function investmentCostTwd(row) {
  return Number(row.cost_twd ?? row.cost ?? 0)
}

export function investmentTotalTwd(row) {
  return Number(row.total_value_twd ?? investmentValueTwd(row) + investmentCashTwd(row))
}

export function investmentPnlTwd(row) {
  return Number(row.pnl_twd ?? investmentTotalTwd(row) - investmentCostTwd(row))
}
