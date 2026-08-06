export const routeLoaders = {
  '/holdings': () => import('./pages/Holdings'),
  '/cash': () => import('./pages/Cash'),
  '/cash/ledger': () => import('./pages/CashLedger'),
  '/add-trade': () => import('./pages/AddTrade'),
  '/history': () => import('./pages/History'),
}

export function preloadRoute(path) {
  return routeLoaders[path]?.()
}
