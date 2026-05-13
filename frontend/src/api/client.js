const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let message = `API error: ${res.status}`
    try {
      const body = await res.json()
      message = body.detail || message
    } catch {
      // Keep default message.
    }
    throw new Error(message)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  getPriceStatus: () => request('/prices/status'),
  getSummary: (refreshPrices = false) =>
    request(`/summary${refreshPrices ? '?refresh_prices=true' : ''}`),
  getPortfolio: (account, refreshPrices = false) =>
    request(`/portfolio/${encodeURIComponent(account)}${refreshPrices ? '?refresh_prices=true' : ''}`),
  getTrades: (account, params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value) query.set(key, value)
    })
    const suffix = query.toString() ? `?${query}` : ''
    return request(`/trades/${encodeURIComponent(account)}${suffix}`)
  },
  addTrade: (data) => request('/trades', { method: 'POST', body: JSON.stringify(data) }),
  deleteTrade: (id) => request(`/trades/${id}`, { method: 'DELETE' }),
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
