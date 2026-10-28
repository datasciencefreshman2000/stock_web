import { useEffect, useState } from 'react'
export const DRAFT_PREFIX = 'stock_web_draft:'
export function usePersistentState(key, initial) {
  const [state, setState] = useState(() => {
    try { const raw = localStorage.getItem(DRAFT_PREFIX + key); if (raw) return JSON.parse(raw) } catch { /* memory-only */ }
    return typeof initial === 'function' ? initial() : initial
  })
  useEffect(() => { try { localStorage.setItem(DRAFT_PREFIX + key, JSON.stringify(state)) } catch { /* memory-only */ } }, [key, state])
  return [state, setState]
}
