import { BarChart3, History, LayoutDashboard, PlusCircle, Wallet } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const items = [
  { to: '/', label: '總覽', icon: LayoutDashboard },
  { to: '/holdings', label: '持倉', icon: BarChart3 },
  { to: '/cash', label: '現金', icon: Wallet },
  { to: '/add-trade', label: '新增', icon: PlusCircle },
  { to: '/history', label: '紀錄', icon: History },
]

export default function NavBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-[#0d1426]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
      <div className="mx-auto grid max-w-3xl grid-cols-5 px-1.5 py-1.5 sm:px-2 sm:py-2">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex min-w-0 flex-col items-center gap-1 rounded-md px-1.5 py-1.5 text-[11px] leading-tight sm:px-2 sm:py-2 sm:text-xs ${
                  isActive ? 'bg-panel text-white' : 'text-slate-400'
                }`
              }
            >
              <Icon size={19} />
              <span className="max-w-full truncate">{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
