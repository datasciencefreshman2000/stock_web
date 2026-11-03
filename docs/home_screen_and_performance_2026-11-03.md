# 主畫面設定與效能檢查

## 本次完成

- 加入 `frontend/public/manifest.webmanifest`，設定 `display: standalone`、固定啟動網址與範圍、名稱、背景色及圖示。
- HTML 補上 Apple 獨立開啟設定、主畫面名稱、180px Apple 圖示；提供 192px、512px PNG 圖示。可用 `scripts/generate_web_icons.ps1` 重新產生圖示。
- 總覽原本同時掛載手機與桌面兩套圖表，再用 CSS 隱藏其中一套。改成依 1024px 斷點只掛載需要的版本；尺寸變更的監聽會在離開時清除。
- 關閉圓餅與現金長條圖進場動畫，保留圖表、提示與點選功能。
- 前一批手機調整已移除資產金額從零開始的逐幀動畫，本次保留這項改善。
- 修正查詢快取註解與實際 1 分鐘設定不一致的問題。

## 檢查後保留的功能

- 總覽／持倉每兩分鐘重讀：仍有保持畫面資料更新的用途，沒有刪除；TanStack 預設不在背景分頁持續輪詢。返回頁面時的過期資料更新也保留。
- 財務寫入後的查詢失效：會影響現金、持倉與總覽的正確性，沒有為了減少請求而刪除。
- 頁面與圖表的動態載入、導覽時的預載：現有設計有助於減少首次下載及切頁等待，保留。
- React StrictMode：主要是開發檢查，正式環境沒有開發模式的重複檢查成本，保留。
- 沒有加入 Service Worker 或帳務離線快取；本次主畫面獨立視窗設定不需要它，也沒有引入額外套件。

## 驗證

- 正式建置成功，前端 11 項測試通過，`git diff --check` 通過。
- 合成資料本機預覽：390px 與 1280px 兩種寬度皆實際只有 3 個 Recharts 圖表實例；手機無整頁水平溢出。
- HTML 實際含 manifest 連結及 Apple standalone meta；本機 manifest HTTP 200，建置產物包含三種圖示。
- [手機總覽驗證畫面](mobile_assets_2026-11-02/dashboard-single-charts.png)。圖中資料全為合成測試資料。
- 尚未部署或於實體 iPhone 安裝驗證，沒有正式 API 或低階手機效能量測。不能將圖表實例減半解讀為整站速度加倍。

## 部署後在 iPhone 的操作

1. 等正式站部署完成。
2. 移除舊的主畫面網址圖示（只移除捷徑，不刪帳務資料）。
3. 用 Safari 開啟正式網址，分享 → 加入主畫面。
4. 若有「以網頁 App 開啟」選項，保持開啟。
5. 從新圖示啟動，確認沒有瀏覽器網址列；系統狀態列仍可能存在。獨立 App 的登入狀態可能與瀏覽器不同，必要時重新登入。

不需要更新 Supabase 或執行 SQL。本次與前一批手機修改均尚未提交或推送。

參考：[WebKit 主畫面 Web App 支援](https://webkit.org/blog/13878/)、[TanStack 輪詢機制](https://tanstack.com/query/latest/docs/framework/react/guides/polling)。
