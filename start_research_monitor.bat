@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
echo =================================================
echo  SupahBetting Research Monitor v0.13
echo =================================================
echo Controleert modelkwaliteit, nieuwe wedstrijden,
echo uitslagen en lokaal getrainde parameters.
echo Het eerste speelschema wordt apart gestart zodat
echo de oude 2016+ historie de kalender niet blokkeert.
echo.
echo Dit venster open laten; Ctrl+C stopt de monitor.
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
