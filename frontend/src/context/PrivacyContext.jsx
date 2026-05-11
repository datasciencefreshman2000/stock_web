import { createContext, useContext, useMemo, useState } from 'react'

const PrivacyContext = createContext(null)

export function PrivacyProvider({ children }) {
  const [hideAmounts, setHideAmounts] = useState(() => localStorage.getItem('hideAmounts') === 'true')

  function toggleHideAmounts() {
    setHideAmounts((current) => {
      const next = !current
      localStorage.setItem('hideAmounts', String(next))
      return next
    })
  }

  const value = useMemo(() => ({ hideAmounts, toggleHideAmounts }), [hideAmounts])
  return <PrivacyContext.Provider value={value}>{children}</PrivacyContext.Provider>
}

export function usePrivacy() {
  const value = useContext(PrivacyContext)
  if (!value) throw new Error('usePrivacy must be used within PrivacyProvider')
  return value
}

export function maskAmount(value) {
  if (value === null || value === undefined) return value
  const text = String(value)
  const percentMatches = text.match(/-?\d+(?:\.\d+)?%/g)
  if (percentMatches?.length) return percentMatches.join(' / ')
  return '••••'
}
