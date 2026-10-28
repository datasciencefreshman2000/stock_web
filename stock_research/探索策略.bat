@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo   策略探索器
echo ============================================================
echo.
echo   1. 看一檔股票上，所有策略的表現
echo   2. 單一策略的參數掃描
echo   3. 一個策略跨整個主題
echo   4. 一個策略跨全部 8 個主題
echo   5. 看現在的訊號狀態
echo   6. 分期表現（2010-16 / 2017-22 / 2023-26）
echo   7. 列出可用策略與標的
echo   0. 離開
echo.
set /p choice=請選擇：

if "%choice%"=="0" exit /b
if "%choice%"=="7" (
    python scripts\explore.py --list
    pause & goto menu
)

if "%choice%"=="1" (
    set /p t=股票代號（例如 2408）：
    python scripts\explore.py --ticker !t!
    pause & goto menu
)
if "%choice%"=="2" (
    set /p t=股票代號：
    set /p s=策略（ma_trend/ma_cross/momentum/breakout/rsi_reversal/short_reversal/vol_target/trend_vol）：
    python scripts\explore.py --ticker !t! --strategy !s!
    pause & goto menu
)
if "%choice%"=="3" (
    set /p s=策略：
    set /p th=主題（記憶體/ABF載板/重電/化合物半導體/PCB材料/散熱/半導體測試/晶圓代工）：
    python scripts\explore.py --strategy !s! --theme !th!
    pause & goto menu
)
if "%choice%"=="4" (
    set /p s=策略：
    python scripts\explore.py --strategy !s! --all-themes
    pause & goto menu
)
if "%choice%"=="5" (
    set /p t=股票代號：
    python scripts\explore.py --ticker !t! --now
    pause & goto menu
)
if "%choice%"=="6" (
    set /p t=股票代號：
    set /p s=策略：
    python scripts\explore.py --ticker !t! --strategy !s! --by-period
    pause & goto menu
)
goto menu
