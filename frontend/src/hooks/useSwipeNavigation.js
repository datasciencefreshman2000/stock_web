import { useEffect, useRef } from 'react'

/**
 * 手機左右滑動換頁。
 *
 * 為什麼要重寫（原本的版本有兩個毛病）：
 *
 * 1. **只有底部導覽列可以滑。** touch 事件掛在 <nav> 上，
 *    而那是螢幕最下面一條窄長的區域。在頁面內容上怎麼滑都沒反應，
 *    看起來就像壞掉了。
 *
 * 2. **preventDefault() 沒有作用。** React 會把 touchmove 註冊成
 *    passive listener，在裡面呼叫 preventDefault() 是無效的
 *    （console 還會噴警告）。結果瀏覽器有機會把這個水平拖曳
 *    當成自己的手勢（iOS 邊緣返回、Android overscroll），
 *    手勢被搶走，touchcancel 一發，滑動就沒了。
 *
 * 所以這裡改用原生 addEventListener 並明確指定 { passive: false }。
 *
 * 三個必要的例外（在這些地方滑動應該是捲動，不是換頁）：
 *   - 水平可捲動的容器：總覽的圖表 carousel、持倉的表格
 *   - 輸入元件與滑桿
 *   - 有 modal 打開時
 */

const THRESHOLD_PX = 60          // 位移要夠大，避免點擊時的微小抖動誤判
const HORIZONTAL_RATIO = 1.5     // 水平要明顯大於垂直，避免和上下捲動打架

function isHorizontallyScrollable(element) {
  if (!(element instanceof Element)) return false
  const { overflowX } = window.getComputedStyle(element)
  return (overflowX === 'auto' || overflowX === 'scroll')
    && element.scrollWidth > element.clientWidth + 1
}

function shouldIgnore(target) {
  if (document.querySelector('[role="dialog"][aria-modal="true"]')) return true
  if (!(target instanceof Element)) return false
  if (target.closest('input, textarea, select, [role="slider"], [data-swipe-nav="off"]')) return true

  // 往上找有沒有「還能左右捲」的祖先。持倉表格和總覽的圖表輪播都是這種。
  for (let node = target; node; node = node.parentElement) {
    if (isHorizontallyScrollable(node)) return true
  }
  return false
}

export function useSwipeNavigation(onSwipe, enabled = true) {
  const gestureRef = useRef(null)
  const onSwipeRef = useRef(onSwipe)
  onSwipeRef.current = onSwipe

  useEffect(() => {
    if (!enabled) return undefined

    function onTouchStart(event) {
      if (event.touches.length !== 1 || shouldIgnore(event.target)) {
        gestureRef.current = null
        return
      }
      const touch = event.touches[0]
      gestureRef.current = { x: touch.clientX, y: touch.clientY, done: false }
    }

    function onTouchMove(event) {
      const gesture = gestureRef.current
      // 多指 = 縮放，直接放棄這次手勢
      if (!gesture || gesture.done || event.touches.length !== 1) return

      const touch = event.touches[0]
      const dx = touch.clientX - gesture.x
      const dy = touch.clientY - gesture.y
      if (Math.abs(dx) < THRESHOLD_PX || Math.abs(dx) < Math.abs(dy) * HORIZONTAL_RATIO) return

      gesture.done = true
      // 這行只有在 passive: false 下才有效，作用是不讓瀏覽器
      // 把接下來的移動當成返回手勢／overscroll
      if (event.cancelable) event.preventDefault()
      onSwipeRef.current(dx < 0 ? 1 : -1)
    }

    function onTouchEnd() {
      gestureRef.current = null
    }

    const options = { passive: false }
    window.addEventListener('touchstart', onTouchStart, options)
    window.addEventListener('touchmove', onTouchMove, options)
    window.addEventListener('touchend', onTouchEnd)
    window.addEventListener('touchcancel', onTouchEnd)
    return () => {
      window.removeEventListener('touchstart', onTouchStart, options)
      window.removeEventListener('touchmove', onTouchMove, options)
      window.removeEventListener('touchend', onTouchEnd)
      window.removeEventListener('touchcancel', onTouchEnd)
    }
  }, [enabled])
}

export const __test__ = { shouldIgnore, isHorizontallyScrollable, THRESHOLD_PX, HORIZONTAL_RATIO }
