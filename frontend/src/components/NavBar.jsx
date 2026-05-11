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
    <nav className="fixed inset-x-0 bottom-0 border-t border-line bg-[#0d1426]/95 backdrop-blur">
      <div className="mx-auto grid max-w-3xl grid-cols-5 px-2 py-2">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 rounded-md px-2 py-2 text-xs ${
                  isActive ? 'bg-panel text-white' : 'text-slate-400'
                }`
              }
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
