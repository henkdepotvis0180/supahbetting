@echo off
setlocal
cd /d "%~dp0"
echo.
echo ====================================================
echo   SupahBetting - voetbal basismodel opnieuw trainen
echo ====================================================
echo.
echo Training met echte afgeronde historische wedstrijden.
echo Training: historie vanaf 2020, validatie 2024/25,
echo test 2025/26 en aanvullende beoordeling 2026/27.
echo De opgeslagen modellen worden bijgewerkt. Er worden
echo geen API-sleutels of bookmakeraccounts gebruikt.
echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m supahbetting.trained_model
) else (
    python -m supahbetting.trained_model
)
if errorlevel 1 (
    echo.
    echo Training mislukt. Controleer de meldingen hierboven.
) else (
    echo.
    echo Gereed. Start start_dashboard.bat opnieuw om het model te laden.
)
echo.
pause
