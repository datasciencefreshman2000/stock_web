import { useCallback, useRef, useState } from 'react'

/**
 * 送出佇列 —— 讓「連續輸入」不用等上一筆存完。
 *
 * 為什麼需要：
 *   原本記帳是 `await api.createCapitalMovement()` 才解鎖按鈕，
 *   一筆網路來回大約 0.5–1.5 秒，連記 10 筆就是純粹在等。
 *
 * 為什麼仍然「一筆一筆送」而不是全部並行：
 *   資金移動會改動現金餘額，後端是「讀餘額 → 加減 → 寫回」。
 *   並行送出會互相覆蓋（lost update），餘額就錯了。
 *   所以送出保持序列，但**畫面不擋**——這兩件事是分開的。
 *
 * 失敗處理：
 *   失敗的項目留在 failed 裡，不會默默消失，可以重試或丟棄。
 *
 * 回傳：
 *   enqueue(payload, label)  排入佇列，立刻回傳
 *   pending                  還在排隊 / 傳送中的筆數
 *   failed                   [{ id, payload, label, error }]
 *   retry(id) / dismiss(id)  重試或丟棄某一筆
 */
export function useSaveQueue(sender, onDrained) {
  const queueRef = useRef([])
  const runningRef = useRef(false)
  const idRef = useRef(0)
  const [pending, setPending] = useState(0)
  const [failed, setFailed] = useState([])

  // 用 ref 拿最新的 callback，避免 drain 中途抓到舊的閉包
  const senderRef = useRef(sender)
  senderRef.current = sender
  const drainedRef = useRef(onDrained)
  drainedRef.current = onDrained

  const drain = useCallback(async () => {
    if (runningRef.current) return
    runningRef.current = true

    let sent = 0
    while (queueRef.current.length > 0) {
      const job = queueRef.current.shift()
      setPending(queueRef.current.length + 1)
      try {
        await senderRef.current(job.payload)
        sent += 1
      } catch (error) {
        setFailed((current) => [
          ...current,
          { id: job.id, payload: job.payload, label: job.label, error: error?.message || '儲存失敗' },
        ])
      }
      setPending(queueRef.current.length)
    }

    runningRef.current = false
    if (sent > 0) drainedRef.current?.()
  }, [])

  const enqueue = useCallback((payload, label = '') => {
    idRef.current += 1
    queueRef.current.push({ id: idRef.current, payload, label })
    setPending(queueRef.current.length + (runningRef.current ? 1 : 0))
    drain()
  }, [drain])

  const retry = useCallback((id) => {
    setFailed((current) => {
      const item = current.find((row) => row.id === id)
      if (item) {
        queueRef.current.push(item)
        drain()
      }
      return current.filter((row) => row.id !== id)
    })
  }, [drain])

  const dismiss = useCallback((id) => {
    setFailed((current) => current.filter((row) => row.id !== id))
  }, [])

  return { enqueue, pending, failed, retry, dismiss }
}
