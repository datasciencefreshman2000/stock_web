import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { usePersistentState } from './usePersistentState'

export function useRememberedQueryObject(key, defaults) {
  const [params, setParams] = useSearchParams()
  const [saved, setSaved] = usePersistentState(key, defaults)
  const state = useMemo(() => {
    const result = { ...defaults, ...saved }
    for (const name of Object.keys(defaults)) if (params.has(name)) result[name] = params.get(name)
    return result
  }, [params, saved])
  function setState(next) {
    const value = typeof next === 'function' ? next(state) : next
    setSaved(value)
    setParams(current => {
      const copy = new URLSearchParams(current)
      Object.keys(defaults).forEach(name => copy.set(name, String(value[name] ?? '')))
      return copy
    }, { replace: true })
  }
  return [state, setState]
}
