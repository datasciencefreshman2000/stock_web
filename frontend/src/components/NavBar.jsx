import { BarChart3, History, LayoutDashboard, PlusCircle, Wallet } from 'lucide-react'
import { NavLink } from 'react-router-dom'

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
      <div
        className="mx-auto grid w-screen max-w-full items-end px-1 py-1.5 sm:w-full sm:max-w-3xl sm:px-2 sm:py-2"
        style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' }}
      >
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md leading-tight transition duration-150 active:scale-95 ${
                  item.featured ? 'px-0.5 py-2 text-xs sm:px-1.5 sm:py-2.5' : 'px-0.5 py-1.5 text-[11px] sm:px-2 sm:py-2 sm:text-xs'
                } ${isActive ? 'bg-panel text-white' : 'text-slate-400'}`
              }
            >
              <Icon size={item.featured ? 22 : 18} />
              <span className={`max-w-full truncate ${item.featured ? 'font-semibold' : ''}`}>{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
