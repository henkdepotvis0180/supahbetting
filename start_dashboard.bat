@echo off
setlocal
cd /d "%~dp0"
echo.
echo ================================================
echo  SupahBetting v0.5.1 - Lokaal onderzoeksdashboard
echo ================================================
echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m supahbetting.server
) else (
    python -m supahbetting.server
)
echo.
echo Dashboard gestopt. Controleer eventuele fouten hierboven.
pause
