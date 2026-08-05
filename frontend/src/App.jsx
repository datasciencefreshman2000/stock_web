import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'

import NavBar from './components/NavBar'
import PrivacyToggle from './components/PrivacyToggle'
import { AuthProvider, useAuth } from './context/AuthContext'
import { PrivacyProvider } from './context/PrivacyContext'
import AddTrade from './pages/AddTrade'
import Cash from './pages/Cash'
import CashLedger from './pages/CashLedger'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Holdings from './pages/Holdings'
import Login from './pages/Login'

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <div key={location.pathname} className="page-enter">
      <Routes location={location}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/holdings" element={<Holdings />} />
        <Route path="/cash" element={<Cash />} />
        <Route path="/cash/ledger" element={<CashLedger />} />
        <Route path="/add-trade" element={<AddTrade />} />
        <Route path="/history" element={<History />} />
      </Routes>
    </div>
  )
}

function SiteLogo() {
  const { logout } = useAuth()

  return (
    <div className="mx-auto flex w-full max-w-6xl items-center gap-2 px-3 pt-3 sm:px-4 sm:pt-4">
      <div className="grid h-8 w-8 place-items-center rounded-md border border-sky-400/40 bg-sky-500/15 text-sm font-semibold text-sky-100 shadow-sm shadow-sky-950/50">
        蔡
      </div>
      <div className="leading-tight">
        <div className="text-sm font-semibold text-white">蔡加恩的金庫</div>
        <div className="text-[11px] text-slate-500">stock vault</div>
      </div>
      <button
        type="button"
        onClick={logout}
        className="ml-auto rounded-md border border-slate-700 px-2.5 py-1 text-[11px] text-slate-400 transition hover:border-slate-500 hover:text-slate-200"
      >
        登出
      </button>
    </div>
  )
}

function AuthedApp() {
  const { status } = useAuth()

  if (status === 'checking') {
    return <div className="grid min-h-screen place-items-center bg-[#0b1020] text-slate-500">載入中…</div>
  }

  if (status !== 'signed-in') {
    return <Login />
  }

  return (
    <PrivacyProvider>
      <BrowserRouter>
        <div className="min-h-screen overflow-x-hidden bg-[#0b1020] text-slate-100">
          <SiteLogo />
          <main className="mx-auto w-full max-w-6xl px-3 pb-28 pt-4 sm:px-4 sm:pb-24 sm:pt-5">
            <AnimatedRoutes />
          </main>
          <PrivacyToggle />
          <NavBar />
        </div>
      </BrowserRouter>
    </PrivacyProvider>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AuthedApp />
    </AuthProvider>
  )
}
