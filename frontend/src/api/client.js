const BASE = import.meta.env.VITE_API_BASE || '/api'
const TOKEN_KEY = 'stock_web_token'

// --- token 保管 -----------------------------------------------------------
let token = null
try {
  token = localStorage.getItem(TOKEN_KEY)
} catch {
  token = null
}

const unauthorizedHandlers = new Set()

export const auth = {
  getToken: () => token,
  setToken(value) {
    token = value
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value)
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      // localStorage 不可用時仍能在記憶體中運作
    }
  },
  clear() {
    auth.setToken(null)
  },
  onUnauthorized(handler) {
    unauthorizedHandlers.add(handler)
    return () => unauthorizedHandlers.delete(handler)
  },
}

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    auth.clear()
    unauthorizedHandlers.forEach((handler) => handler())
    throw new ApiError('請重新登入', 401)
  }

  if (!res.ok) {
    let message = `API error: ${res.status}`
    try {
      const body = await res.json()
      message = body.detail || message
    } catch {
      // Keep default message.
    }
    throw new ApiError(message, res.status)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),

  // --- 認證 ---
  login: async (password) => {
    const result = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
    auth.setToken(result.token)
    return result
  },
  me: () => request('/auth/me'),
  logout: () => auth.clear(),

  // --- 讀取（一律只讀快取）---
  getSummary: () => request('/summary'),
  getPortfolio: (account) => request(`/portfolio/${encodeURIComponent(account)}`),
  // 每筆買單被賣掉多少、賣出均價 —— FIFO 由後端算，含分割調整
  getBuyLots: (account, ticker) =>
    request(`/portfolio/${encodeURIComponent(account)}/lots/${encodeURIComponent(ticker)}`),

  // --- 刷新（唯一會去抓最新報價的入口）---
  refreshAll: () => request('/jobs/refresh', { method: 'POST' }),
  getJobStatus: () => request('/jobs/status'),

  getTrades: (account, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value) query.set(key, value)
    })
    const suffix = query.toString() ? `?${query}` : ''
    return request(`/trades/${encodeURIComponent(account)}${suffix}`)
  },
  getTickerInfo: (account, ticker) =>
    request(`/trades/${encodeURIComponent(account)}/ticker/${encodeURIComponent(ticker)}`),
  addTrade: (data) => request('/trades', { method: 'POST', body: JSON.stringify(data) }),
  updateTrade: (id, data) =>
    request(`/trades/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteTrade: (id) => request(`/trades/${id}`, { method: 'DELETE' }),

  // --- 除權息 / 分割 ---
  getCorporateActions: (symbol) =>
    request(`/actions${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ''}`),
  addCorporateAction: (data) => request('/actions', { method: 'POST', body: JSON.stringify(data) }),
  deleteCorporateAction: (id) => request(`/actions/${id}`, { method: 'DELETE' }),
  suggestSplitWindow: (account, ticker) =>
    request(`/actions/suggest/${encodeURIComponent(account)}/${encodeURIComponent(ticker)}`),

  getManual: () => request('/manual'),
  updateManualValue: (key, value) =>
    request('/manual/value', { method: 'PATCH', body: JSON.stringify({ key, value }) }),
  updateCash: (id, amount, currency) =>
    request(`/manual/cash/${id}`, { method: 'PATCH', body: JSON.stringify({ amount, currency }) }),
  createCash: (data) => request('/manual/cash', { method: 'POST', body: JSON.stringify(data) }),
  createInvestment: (data) => request('/manual/investment', { method: 'POST', body: JSON.stringify(data) }),
  updateInvestment: (id, data) =>
    request(`/manual/investment/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteInvestment: (id) => request(`/manual/investment/${id}`, { method: 'DELETE' }),
  getCapitalMovements: () => request('/manual/capital-movements'),
  createCapitalMovement: (data) => request('/manual/capital-movements', { method: 'POST', body: JSON.stringify(data) }),
  getCapitalMovementOptions: (category = 'income_source') =>
    request(`/manual/capital-movement-options?category=${encodeURIComponent(category)}`),
  createCapitalMovementOption: (data) =>
    request('/manual/capital-movement-options', { method: 'POST', body: JSON.stringify(data) }),
  deleteCapitalMovementOption: (id) => request(`/manual/capital-movement-options/${id}`, { method: 'DELETE' }),
}

export { ApiError }
