@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo  台股日線回補 (Yahoo Finance)
echo  8 個主題 21 檔 + 0050，約 1-2 分鐘
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 python，請確認已安裝並加入 PATH
    pause
    exit /b 1
)

echo [1/2] 安裝相依套件...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [錯誤] 套件安裝失敗，錯誤訊息在上方
    pause
    exit /b 1
)

echo [2/2] 開始抓取...
echo.
python scripts\backfill_yahoo.py > run_log.txt 2>&1
type run_log.txt

echo.
echo ============================================================
echo  完成。輸出檔案：
echo    data\price_history_yahoo.parquet   ^<- 資料
echo    run_log.txt                        ^<- 執行紀錄
echo.
echo  這兩個檔案 Claude 都讀得到，直接回去跟他說「跑完了」即可
echo ============================================================
pause
