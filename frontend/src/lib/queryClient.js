import { QueryClient } from '@tanstack/react-query'

/**
 * 後端的資料本來就是快取（由排程更新），前端沒必要一直重打。
 * staleTime 設 5 分鐘，切頁時直接用記憶體裡的資料，畫面瞬間出現。
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      // 從別的分頁 / 別的 App 切回來時重讀一次。
      // 成本是每次切回來 1 次 GET，而且後端直接命中快取（1 次 DB 往返），
      // 換到的是「回來看到的一定不是半小時前的數字」。
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => {
        // 401 是要重新登入，重試沒有意義
        if (error?.status === 401) return false
        return failureCount < 2
      },
    },
  },
})

export const queryKeys = {
  summary: ['summary'],
  portfolio: (account) => ['portfolio', account],
  buyLots: (account, ticker) => ['portfolio', account, 'lots', ticker],
  trades: (account, params) => ['trades', account, params],
  tradeTickers: (account) => ['trade-tickers', account],
  manual: ['manual', 'data'],
  capitalMovements: (month) => ['capital-movements', month],
  capitalMovementOptions: (category) => ['capital-movement-options', category],
  jobStatus: ['jobs', 'status'],
}
