@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
echo [1/3] Snelle modelcontrole (offline)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_readiness
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.11+ ontbreekt. Installeer Python.
    pause
    exit /b 1
  )
  python -m supahbetting.research_readiness
)
echo [2/3] Periodieke bron- en trainingsmonitor starten
start "SupahBetting Research v0.13 - monitor" cmd /k ""%~dp0start_research_monitor.bat""
echo [3/3] Website starten
call "%~dp0start_dashboard.bat"
