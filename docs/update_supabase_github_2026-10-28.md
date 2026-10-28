# Supabase 與 GitHub 更新操作

適用工作目錄：`C:\Users\user\Desktop\python\stock_site`。Git 分支：`main`；遠端：`https://github.com/datasciencefreshman2000/stock_web.git`。Supabase 專案 ref：`vcjfyfrvpzxztymxrbno`。請先核對為你要更新的正式環境。

後續驗證紀錄：使用者執行 migration 後，已直接對上述 Supabase 專案執行新版只讀驗證；總結果 `PASS`、`50 checks; 0 failed`。資料庫結構與權限這一步已通過，不必因舊版驗證畫面僅顯示 id=true、revision=0 而重新執行 migration。GitHub 推送與網站部署另行確認。

## 1. 資料庫需要更新什麼

完整升級 SQL：`supabase/migrations/20261028100854_reliable_ledger.sql`。

- `cash_accounts`：補 account、category、archived_at，啟用中名稱＋幣別唯一；重複列先備份再整併及封存，保留原 DB 加總。
- `manual_investments`：補 cash_amount。
- `fifo_checkpoints`：補 calculation_version；新版計算會略過舊 checkpoint。
- `capital_movements`：補 updated_at、affects_balance。
- `manual_values`：調整限制，讓獲利提款後的投資淨入金可小於零。
- 新增 app_state、app_operations、app_login_attempts、balance_adjustments、cash_account_merge_backup 五張表。
- 一併建立帳務／快取／結算／分頁／登入限制函式、觸發器、索引及 RLS／服務端權限。

既有資料庫只執行這份新增 migration。不要重跑 schema.sql、舊 seed migrations 或新環境使用的 database_setup.sql。

## 2. 更新順序

備份資料庫 → 暫停 Cloudflare cron 並暫停使用網站 → SQL Editor 執行 migration → 執行只讀驗證 → 推送 GitHub 並完成新版部署 → 網站重新整理、刷新股價及核對餘額 → 恢復 cron。

新版程式需要新 RPC，舊版又不會排除封存現金列，兩者應在同一維護時段更新。GitHub push 只會上傳程式；Supabase 不會因此自動套 SQL。若 Vercel 已連接此 GitHub main，push 可能會觸發部署，仍需等部署成功才能恢復使用。

## 3. Supabase SQL Editor

開啟 `https://supabase.com/dashboard/project/vcjfyfrvpzxztymxrbno/sql/new`，使用 postgres 角色，在新的查詢貼上完整 migration 後 Run。不要只選取部分 SQL；檔案包含 BEGIN／COMMIT。若出錯，保留錯誤內容，先處理原因，不要跳過報錯片段。

在 VS Code PowerShell 複製完整 SQL：

```powershell
Set-Location -LiteralPath 'C:\Users\user\Desktop\python\stock_site'
Get-Content -LiteralPath '.\supabase\migrations\20261028100854_reliable_ledger.sql' -Raw -Encoding UTF8 | Set-Clipboard
```

成功後，再建立一個新的 SQL Editor 查詢，執行 `backend/sql/verify_reliable_ledger.sql`。它只讀結構及狀態，不改餘額。新版驗證檔以單一結果集顯示全部檢查，第一列 `summary / overall` 應為 `PASS`、detail 為 `50 checks; 0 failed`；後續各列 status 也都應為 PASS。`app_state` 顯示 rows=1，revision 可為 0 或之後的版本號。

舊版驗證檔有五段 SELECT，SQL Editor 可能只顯示最後一段的 id=true、revision=0；這只反映狀態表，無法單靠該畫面確認前四段。請重新複製新版單一結果集驗證檔再執行，不必因此重跑 migration。

```powershell
Get-Content -LiteralPath '.\backend\sql\verify_reliable_ledger.sql' -Raw -Encoding UTF8 | Set-Clipboard
```

重複列保存在 cash_account_merge_backup 和原表的封存列中；不會清空交易。若舊重複列本身是誤植，升級後需對照銀行真實餘額，以網站「餘額校正」調整，程式不猜測哪個數字才是真實餘額。

## 4. GitHub：先加入並檢查本次修改

以下命令由你執行；沒有 force push。遇到原生 Git 指令錯誤會停止。

```powershell
Set-Location -LiteralPath 'C:\Users\user\Desktop\python\stock_site'
if ((git branch --show-current).Trim() -ne 'main') { throw '目前不是 main，請先確認工作分支。' }
if ((git remote get-url origin).Trim() -ne 'https://github.com/datasciencefreshman2000/stock_web.git') { throw 'origin 與預期專案不符。' }

git status --short
$pathsToStage = @(
    '.gitignore', 'README.md', 'pyproject.toml', 'vercel.json',
    'backend', 'frontend', 'supabase', 'stock_research',
    'docs/cache_and_refresh.md',
    'docs/project_review_2026-10-28.md', 'docs/audit_assets_2026-10-28',
    'docs/fixes_2026-10-28.md', 'docs/fixes_assets_2026-10-28',
    'docs/update_supabase_github_2026-10-28.md'
)
git add -- $pathsToStage
if ($LASTEXITCODE -ne 0) { throw 'git add 失敗，請先處理錯誤。' }
git diff --cached --stat
git diff --cached --name-only
```

確認加入的檔案正確後，執行下一段。密鑰、原始匯出資料、研究 data／journal／results、node_modules、tmp 已由目前 ignore 規則排除；仍應檢查 staged 清單及內容。

## 5. Commit、同步遠端、推送

```powershell
git commit -m "Fix ledger reliability, FX transfers, valuation and UI flows"
if ($LASTEXITCODE -ne 0) { throw 'commit 未完成，請先查看 Git 訊息。' }

git fetch origin
if ($LASTEXITCODE -ne 0) { throw 'fetch 失敗，請確認網路或 GitHub 登入。' }

git rebase origin/main
if ($LASTEXITCODE -ne 0) { throw 'rebase 尚未完成；先解決衝突，再繼續，不要直接 push。' }

git push origin main
if ($LASTEXITCODE -ne 0) { throw 'push 失敗，請先查看 Git 訊息。' }

git status -sb
```

commit 建立本機版本；fetch 下載遠端最新紀錄；rebase 將本機這次提交接到遠端 main；push 才會把提交送到 GitHub。這裡已使用 fetch＋rebase，因此不需另外再 pull。

若 rebase 衝突，執行 git status，於 VS Code 解決衝突後，只 add 已解決檔案，再 git rebase --continue。若需要取消這次 rebase，可用 git rebase --abort；它會回到 rebase 前已建立的本機 commit，不等於清除本次修正。同步引入新程式碼或解決衝突後，重跑相關測試再 push。

若 GitHub main 有保護規則，依該 repository 規則推到 codex/ledger-uiux-fixes 並開 PR 合併；不要用 force push 繞過規則。GitHub Actions／Vercel 部署失敗與 git push 失敗是不同狀態，請另外查看部署結果。
