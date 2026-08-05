import { Eye, EyeOff } from 'lucide-react'

import { usePrivacy } from '../context/PrivacyContext'

export default function PrivacyToggle() {
  const { hideAmounts, toggleHideAmounts } = usePrivacy()

  return (
    <button
      type="button"
      onClick={toggleHideAmounts}
      className="fixed bottom-24 right-3 z-50 grid h-11 w-11 place-items-center rounded-full border border-line bg-surface/95 text-slate-200 shadow-lg shadow-black/30 backdrop-blur transition hover:-translate-y-0.5 hover:border-sky-400/80 hover:bg-sky-500/15 hover:text-white active:scale-95 sm:bottom-6 sm:right-6"
      title={hideAmounts ? '顯示金額' : '隱藏金額'}
      aria-label={hideAmounts ? '顯示金額' : '隱藏金額'}
    >
      {hideAmounts ? <EyeOff size={19} /> : <Eye size={19} />}
    </button>
  )
}
