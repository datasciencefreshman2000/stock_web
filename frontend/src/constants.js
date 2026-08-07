export const ACCOUNTS = ['台股', '美股', '爸媽美股']
export const ACCOUNT_TABS = ['台股', '美股', '爸媽美股', '基金與其他投資']

// 對應後端 services/accounts.py 的 ACCOUNT_CURRENCY。
// 先前有地方寫成 `name === '美股' ? 'USD' : 'TWD'`，
// 那會讓「爸媽美股」的金額被標成台幣。
export const ACCOUNT_CURRENCY = {
  台股: 'TWD',
  美股: 'USD',
  爸媽美股: 'USD',
}

// 爸媽美股是代管的，不算進自有資產
export const EXTERNAL_ACCOUNTS = ['爸媽美股']
