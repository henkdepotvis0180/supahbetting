@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
echo ====================================================
echo  SupahBetting Research Monitor v0.14
echo ====================================================
echo Controleert echte Eredivisie-uitslagen en agenda.
echo Met eigen football-data.org-token wordt een volledig
echo DED-seizoen bij elke cyclus veilig geverifieerd.
echo Zonder token blijven bestaande modeldata behouden.
echo Ctrl+C stopt de monitor; geen automatische inzet.
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_monitor --interval-hours 6
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Installeer Python 3.11+
    pause
    exit /b 1
  )
  python -m supahbetting.research_monitor --interval-hours 6
)
echo Monitor gestopt.
pause
