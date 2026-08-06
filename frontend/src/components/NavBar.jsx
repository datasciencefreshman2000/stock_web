import { BarChart3, History, LayoutDashboard, PlusCircle, Wallet } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { preloadRoute } from '../routeLoaders'

const items = [
  { to: '/cash', label: '現金', icon: Wallet },
  { to: '/holdings', label: '持倉', icon: BarChart3 },
  { to: '/', label: '總覽', icon: LayoutDashboard, featured: true },
  { to: '/add-trade', label: '新增', icon: PlusCircle },
  { to: '/history', label: '紀錄', icon: History },
]

export default function NavBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 overflow-hidden border-t border-line bg-[#0d1426]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
      <div className="mx-auto grid w-full min-w-0 max-w-3xl grid-cols-5 items-end px-1 py-1.5 sm:px-2 sm:py-2">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onPointerEnter={() => preloadRoute(item.to)}
              onFocus={() => preloadRoute(item.to)}
              onTouchStart={() => preloadRoute(item.to)}
              className={({ isActive }) =>
                `group flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg leading-tight transition-[background-color,color,box-shadow,transform] duration-200 ease-out hover:bg-white/[0.06] hover:text-slate-100 hover:shadow-[inset_0_0_0_1px_rgba(125,211,252,0.16)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400/70 active:scale-[0.98] active:bg-white/[0.08] ${
                  item.featured ? 'px-0.5 py-2 text-xs sm:px-1.5 sm:py-2.5' : 'px-0.5 py-1.5 text-[11px] sm:px-2 sm:py-2 sm:text-xs'
                } ${isActive ? 'bg-panel text-white shadow-[inset_0_0_0_1px_rgba(148,163,184,0.12)]' : 'text-slate-400'}`
              }
            >
              <Icon className="transition duration-200 ease-out group-hover:scale-105 group-hover:text-sky-100" size={item.featured ? 22 : 18} />
              <span className={`max-w-full truncate ${item.featured ? 'font-semibold' : ''}`}>{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
