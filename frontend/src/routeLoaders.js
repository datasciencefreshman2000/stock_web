export const routeLoaders = {
  '/holdings': () => import('./pages/Holdings'),
  '/cash': () => import('./pages/Cash'),
  '/cash/ledger': () => import('./pages/CashLedger'),
  '/add-trade': () => import('./pages/AddTrade'),
  '/history': () => import('./pages/History'),
}

export function preloadRoute(path) {
  // Hover/touch preloads are best-effort. A failed preload must not become
  // an unhandled rejection; normal navigation retains its error boundary.
  return routeLoaders[path]?.().catch(() => undefined)
}
