@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
echo ================================================
echo  SupahBetting Eredivisie Research v0.14
echo ================================================
echo [1/4] Historische 2016+ CC0 dataset lokaal controleren
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_nl_bootstrap
  echo [2/4] Getraind model snel beoordelen
  py -3 -m supahbetting.research_readiness
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Installeer Python 3.11 of hoger.
    pause
    exit /b 1
  )
  python -m supahbetting.research_nl_bootstrap
  echo [2/4] Getraind model snel beoordelen
  python -m supahbetting.research_readiness
)
echo [3/4] Monitor starten: uitslagen en echt speelschema
start "SupahBetting Research v0.14 - monitor" cmd /k ""%~dp0start_research_monitor.bat""
echo [4/4] Dashboard starten
call "%~dp0start_dashboard.bat"
