import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'

import NavBar from './components/NavBar'
import { PrivacyProvider } from './context/PrivacyContext'
import AddTrade from './pages/AddTrade'
import Cash from './pages/Cash'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Holdings from './pages/Holdings'

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <div key={location.pathname} className="page-enter">
      <Routes location={location}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/holdings" element={<Holdings />} />
        <Route path="/cash" element={<Cash />} />
        <Route path="/add-trade" element={<AddTrade />} />
        <Route path="/history" element={<History />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <PrivacyProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-[#0b1020] text-slate-100">
          <main className="mx-auto w-full max-w-6xl px-3 pb-28 pt-4 sm:px-4 sm:pb-24 sm:pt-6">
            <AnimatedRoutes />
          </main>
          <NavBar />
        </div>
      </BrowserRouter>
    </PrivacyProvider>
  )
}
