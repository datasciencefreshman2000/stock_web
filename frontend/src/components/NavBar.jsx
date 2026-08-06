import { BarChart3, History, LayoutDashboard, PlusCircle, Wallet } from 'lucide-react'
import { useCallback, useEffect, useRef } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { preloadRoute } from '../routeLoaders'

const items = [
  { to: '/cash', label: '現金', icon: Wallet },
  { to: '/holdings', label: '持倉', icon: BarChart3 },
  { to: '/', label: '總覽', icon: LayoutDashboard, featured: true },
  { to: '/add-trade', label: '新增', icon: PlusCircle },
  { to: '/history', label: '紀錄', icon: History },
]

function pageIndex(pathname) {
  if (pathname.startsWith('/cash')) return 0
  return items.findIndex((item) => item.to === pathname)
}

function shouldIgnorePageKey(event) {
  if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return true
  if (document.querySelector('[role="dialog"][aria-modal="true"]')) return true
  const target = event.target
  return target instanceof Element && Boolean(
    target.closest('input, textarea, select, [contenteditable="true"], [role="slider"], [data-page-keys="off"]'),
  )
}

export default function NavBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const touchRef = useRef({ startX: 0, startY: 0, handled: false })
  const ignoreClickRef = useRef(false)
  const currentIndex = pageIndex(location.pathname)

  const moveOnePage = useCallback((step, source) => {
    const index = pageIndex(location.pathname)
    if (index < 0) return
    const nextIndex = Math.max(0, Math.min(items.length - 1, index + step))
    if (nextIndex === index) return
    const target = items[nextIndex].to
    preloadRoute(target)
    navigate(target, { state: { pageDirection: step, navigationSource: source } })
  }, [location.pathname, navigate])

  useEffect(() => {
    function onKeyDown(event) {
      if (!window.matchMedia('(min-width: 768px) and (pointer: fine)').matches) return
      if (!['ArrowUp', 'ArrowDown'].includes(event.key) || shouldIgnorePageKey(event)) return
      event.preventDefault()
      moveOnePage(event.key === 'ArrowDown' ? 1 : -1, 'keyboard')
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [moveOnePage])

  function onTouchStart(event) {
    if (event.touches.length !== 1) return
    const touch = event.touches[0]
    touchRef.current = { startX: touch.clientX, startY: touch.clientY, handled: false }
  }

  function onTouchMove(event) {
    const gesture = touchRef.current
    if (gesture.handled || event.touches.length !== 1) return
    const touch = event.touches[0]
    const deltaX = touch.clientX - gesture.startX
    const deltaY = touch.clientY - gesture.startY
    if (Math.abs(deltaX) < 42 || Math.abs(deltaX) < Math.abs(deltaY) * 1.25) return

    gesture.handled = true
    ignoreClickRef.current = true
    event.preventDefault()
    moveOnePage(deltaX < 0 ? 1 : -1, 'swipe')
  }

  function onTouchEnd() {
    touchRef.current.handled = false
    window.setTimeout(() => {
      ignoreClickRef.current = false
    }, 250)
  }

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 overflow-hidden border-t border-line bg-[#0d1426]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur [touch-action:pan-y]"
      aria-label="主要頁面"
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      onTouchCancel={onTouchEnd}
      onClickCapture={(event) => {
        if (ignoreClickRef.current) event.preventDefault()
      }}
    >
      <div className="mx-auto grid w-full min-w-0 max-w-3xl grid-cols-5 items-end px-1 py-1.5 sm:px-2 sm:py-2">
        {items.map((item, index) => {
          const Icon = item.icon
          const direction = currentIndex < 0 || index === currentIndex ? 0 : index > currentIndex ? 1 : -1
          return (
            <NavLink
              key={item.to}
              to={item.to}
              state={{ pageDirection: direction, navigationSource: 'nav' }}
              onPointerEnter={() => preloadRoute(item.to)}
              onFocus={() => preloadRoute(item.to)}
              onTouchStart={() => preloadRoute(item.to)}
              className={({ isActive }) =>
                `group flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg leading-tight transition-[background-color,color,box-shadow,transform] duration-200 ease-out hover:bg-white/[0.06] hover:text-slate-100 hover:shadow-[inset_0_0_0_1px_rgba(125,211,252,0.16)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.98] active:bg-white/[0.08] ${
                  item.featured ? 'px-0.5 py-2 text-xs sm:px-1.5 sm:py-2.5' : 'px-0.5 py-1.5 text-[11px] sm:px-2 sm:py-2 sm:text-xs'
                } ${isActive ? 'bg-panel text-white shadow-[inset_0_0_0_1px_rgba(148,163,184,0.12)]' : 'text-slate-400'}`
              }
            >
              <Icon className="transition duration-200 ease-out group-hover:scale-105 group-hover:text-sky-100" size={item.featured ? 24 : 20} />
              <span className={`max-w-full truncate ${item.featured ? 'font-semibold' : ''}`}>{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
