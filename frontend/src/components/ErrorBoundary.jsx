import { Component } from 'react'

/**
 * 全站的最後一道防線。
 *
 * 沒有它的話，任何一個 render 期間的例外都會讓整個畫面變成全白 ——
 * 使用者只會看到空白，不知道發生什麼事、也沒有任何操作可以做。
 *
 * 另外處理一個「動態載入頁面」特有的問題：
 *
 *   頁面改成 lazy() 之後，每個頁面是獨立的 JS 檔，檔名帶內容雜湊。
 *   一旦重新部署，舊檔名就不存在了。此時如果使用者的分頁還開著、
 *   或瀏覽器手上是舊的 index.html，切頁時就會拿到
 *   「Failed to fetch dynamically imported module」，
 *   Suspense 永遠不會結束，畫面就卡住。
 *
 *   這種情況重新載入一次就好，所以自動做掉 —— 但只做一次，
 *   免得在真的壞掉時變成無限重整。
 */

const RELOAD_FLAG = 'chunk-reload-attempted'

function isChunkLoadError(error) {
  const message = String(error?.message || '')
  return /dynamically imported module|Loading chunk|Importing a module script failed/i.test(message)
}

export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error) {
    if (!isChunkLoadError(error)) return
    // 剛部署過的舊分頁：重抓一次就會拿到新的檔名
    if (sessionStorage.getItem(RELOAD_FLAG)) return
    sessionStorage.setItem(RELOAD_FLAG, '1')
    window.location.reload()
  }

  componentDidUpdate(_, prevState) {
    // 成功復原之後把旗標清掉，下次部署還能再自動重整一次
    if (prevState.error && !this.state.error) sessionStorage.removeItem(RELOAD_FLAG)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    const stale = isChunkLoadError(error)
    return (
      <div className="grid min-h-screen place-items-center bg-[#0b1020] px-4 text-slate-200">
        <div className="w-full max-w-md rounded-md border border-line bg-surface p-5">
          <h1 className="text-lg font-semibold text-white">
            {stale ? '網站剛更新過' : '這個頁面出了點問題'}
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            {stale
              ? '你手上的是舊版本，重新載入就會拿到最新的。'
              : '畫面在繪製時發生錯誤。重新載入通常就能恢復；如果一直出現，把下面的訊息給我看。'}
          </p>
          {!stale ? (
            <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded border border-line bg-[#0b1020] p-2 text-[11px] text-rose-200">
              {String(error?.message || error)}
            </pre>
          ) : null}
          <button
            type="button"
            onClick={() => {
              sessionStorage.removeItem(RELOAD_FLAG)
              window.location.reload()
            }}
            className="mt-4 w-full rounded-md bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-400"
          >
            重新載入
          </button>
        </div>
      </div>
    )
  }
}
