import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'

import NavBar from './components/NavBar'
import PrivacyToggle from './components/PrivacyToggle'
import { LoadingBlock } from './components/StateBlock'
import { AuthProvider, useAuth } from './context/AuthContext'
import { PrivacyProvider } from './context/PrivacyContext'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import { routeLoaders } from './routeLoaders'

/**
 * 除了首頁以外的頁面改成動態載入。
 *
 * 為什麼：原本所有頁面打包成單一 722 kB 的 JS，進站要先下載並解析完
 * 才看得到任何東西。手機上這是實際感受得到的等待，而且你多半是先看總覽，
 * 「新增交易」那頁的程式碼在那一刻根本用不到。
 *
 * Dashboard 不做 lazy —— 它是進站第一眼會看到的，切出去反而多一次往返。
 */
const Holdings = lazy(routeLoaders['/holdings'])
const Cash = lazy(routeLoaders['/cash'])
const CashLedger = lazy(routeLoaders['/cash/ledger'])
const AddTrade = lazy(routeLoaders['/add-trade'])
const History = lazy(routeLoaders['/history'])

function AnimatedRoutes() {
  const location = useLocation()
  const direction = Number(location.state?.pageDirection || 0)
  const animationClass = direction > 0
    ? 'page-enter-forward'
    : direction < 0
      ? 'page-enter-backward'
      : 'page-enter'

  return (
    <div key={location.pathname} className={animationClass}>
      <Suspense fallback={<LoadingBlock label="正在載入頁面" />}>
        <Routes location={location}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/holdings" element={<Holdings />} />
          <Route path="/cash" element={<Cash />} />
          <Route path="/cash/ledger" element={<CashLedger />} />
          <Route path="/add-trade" element={<AddTrade />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </Suspense>
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
    return <LoadingBlock label="正在確認登入狀態" fullscreen />
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
